"""Unit tests for session retention / auto-purge."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from api_gateway.db import Base, SessionModel, TranscriptSegment
from api_gateway.main import _run_session_retention
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def _make_db() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


def _session(sid: str, *, days_ago: int = 0, stopped: bool = True) -> SessionModel:
    started = datetime.now(UTC) - timedelta(days=days_ago)
    return SessionModel(
        id=sid,
        label=f"Session {sid}",
        started_at=started.isoformat(),
        stopped_at=started.isoformat() if stopped else None,
    )


def _segment(session_id: str, text: str = "hello") -> TranscriptSegment:
    return TranscriptSegment(
        session_id=session_id,
        timestamp=datetime.now(UTC).isoformat(),
        text=text,
    )


@pytest.mark.asyncio
async def test_retention_by_count_purges_oldest() -> None:
    db_factory = await _make_db()

    async with db_factory() as db:
        # 5 completed sessions
        for i in range(5):
            db.add(_session(f"s{i}", days_ago=i))
            db.add(_segment(f"s{i}"))
        await db.commit()

    with (
        patch("api_gateway.main._SESSION_RETENTION_COUNT", 3),
        patch("api_gateway.main._SESSION_RETENTION_DAYS", 0),
    ):
        deleted = await _run_session_retention(db_factory)

    assert deleted == 2

    async with db_factory() as db:
        remaining = (await db.execute(select(SessionModel))).scalars().all()
        remaining_ids = {s.id for s in remaining}
        # Kept the 3 most recent (s0=today, s1=1d, s2=2d)
        assert remaining_ids == {"s0", "s1", "s2"}

        # Segments for purged sessions should be gone
        segs = (await db.execute(select(TranscriptSegment))).scalars().all()
        seg_sids = {s.session_id for s in segs}
        assert seg_sids == {"s0", "s1", "s2"}


@pytest.mark.asyncio
async def test_retention_by_days_purges_old() -> None:
    db_factory = await _make_db()

    async with db_factory() as db:
        db.add(_session("recent", days_ago=5))
        db.add(_session("old", days_ago=60))
        db.add(_segment("recent"))
        db.add(_segment("old"))
        await db.commit()

    with (
        patch("api_gateway.main._SESSION_RETENTION_COUNT", 0),
        patch("api_gateway.main._SESSION_RETENTION_DAYS", 30),
    ):
        deleted = await _run_session_retention(db_factory)

    assert deleted == 1

    async with db_factory() as db:
        remaining = (await db.execute(select(SessionModel))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].id == "recent"


@pytest.mark.asyncio
async def test_retention_skips_active_sessions() -> None:
    db_factory = await _make_db()

    async with db_factory() as db:
        # Active session (no stopped_at) should never be purged
        db.add(_session("active", days_ago=100, stopped=False))
        db.add(_session("old", days_ago=100, stopped=True))
        await db.commit()

    with (
        patch("api_gateway.main._SESSION_RETENTION_COUNT", 0),
        patch("api_gateway.main._SESSION_RETENTION_DAYS", 30),
    ):
        deleted = await _run_session_retention(db_factory)

    assert deleted == 1

    async with db_factory() as db:
        remaining = (await db.execute(select(SessionModel))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].id == "active"


@pytest.mark.asyncio
async def test_retention_noop_when_disabled() -> None:
    db_factory = await _make_db()

    async with db_factory() as db:
        db.add(_session("s1", days_ago=100))
        await db.commit()

    with (
        patch("api_gateway.main._SESSION_RETENTION_COUNT", 0),
        patch("api_gateway.main._SESSION_RETENTION_DAYS", 0),
    ):
        deleted = await _run_session_retention(db_factory)

    assert deleted == 0

    async with db_factory() as db:
        remaining = (await db.execute(select(SessionModel))).scalars().all()
        assert len(remaining) == 1


@pytest.mark.asyncio
async def test_both_policies_combine() -> None:
    """When both policies are set, the union of matches is purged."""
    db_factory = await _make_db()

    async with db_factory() as db:
        # 5 sessions: s0 (today) through s4 (40 days ago)
        for i in range(5):
            db.add(_session(f"s{i}", days_ago=i * 10))
        await db.commit()

    with (
        patch("api_gateway.main._SESSION_RETENTION_COUNT", 3),
        patch("api_gateway.main._SESSION_RETENTION_DAYS", 25),
    ):
        deleted = await _run_session_retention(db_factory)

    # Count policy: keep s0, s1, s2 → purge s3, s4
    # Days policy (>25d): purge s3 (30d), s4 (40d)
    # Union: s3, s4
    assert deleted == 2

    async with db_factory() as db:
        remaining = (await db.execute(select(SessionModel))).scalars().all()
        remaining_ids = {s.id for s in remaining}
        assert remaining_ids == {"s0", "s1", "s2"}

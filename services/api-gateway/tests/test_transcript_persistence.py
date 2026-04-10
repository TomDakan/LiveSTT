"""Unit tests for transcript persistence and session DB handling."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from api_gateway.db import Base, SessionModel, TranscriptSegment
from api_gateway.main import _handle_session_db, _persist_segment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@asynccontextmanager
async def _db_factory() -> AsyncGenerator[async_sessionmaker[Any], None]:
    """Provide an in-memory SQLite session factory with tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[Any] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_session(
    factory: async_sessionmaker[Any],
    session_id: str = "20260409-1000",
) -> None:
    """Insert a session row so FK constraints pass for segments."""
    async with factory() as db:
        db.add(
            SessionModel(
                id=session_id,
                label="Test",
                started_at="2026-04-09T10:00:00+00:00",
            )
        )
        await db.commit()


# -------------------------------------------------------------------
# _persist_segment
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_segment_writes_row() -> None:
    async with _db_factory() as factory:
        await _seed_session(factory)
        await _persist_segment(
            factory,
            "20260409-1000",
            {
                "timestamp": "2026-04-09T10:05:00Z",
                "speaker": "Alice",
                "text": "Hello world",
                "confidence": 0.95,
                "source": "live",
            },
        )

        async with factory() as db:
            rows = (
                await db.execute(select(TranscriptSegment))
            ).scalars().all()
            assert len(rows) == 1
            seg = rows[0]
            assert seg.session_id == "20260409-1000"
            assert seg.speaker == "Alice"
            assert seg.text == "Hello world"
            assert seg.confidence == pytest.approx(0.95)
            assert seg.source == "live"


@pytest.mark.asyncio
async def test_persist_segment_defaults() -> None:
    async with _db_factory() as factory:
        await _seed_session(factory)
        await _persist_segment(
            factory,
            "20260409-1000",
            {"text": "bare minimum"},
        )

        async with factory() as db:
            seg = (
                await db.execute(select(TranscriptSegment))
            ).scalar_one()
            assert seg.speaker == "Unknown"
            assert seg.confidence == pytest.approx(0.0)
            assert seg.source == "live"
            assert seg.timestamp == ""


@pytest.mark.asyncio
async def test_persist_segment_db_error_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A broken db_factory logs a warning instead of crashing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Dispose immediately so all DB ops fail.
    await engine.dispose()
    bad_factory: async_sessionmaker[Any] = async_sessionmaker(
        engine, expire_on_commit=False
    )

    with caplog.at_level(logging.WARNING):
        await _persist_segment(bad_factory, "sess-1", {"text": "hi"})

    assert any(
        "Failed to persist segment" in r.message for r in caplog.records
    )


# -------------------------------------------------------------------
# _handle_session_db
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_session_db_started() -> None:
    async with _db_factory() as factory:
        await _handle_session_db(
            factory,
            {
                "event": "started",
                "session_id": "20260409-1000",
                "label": "Morning",
                "started_at": "2026-04-09T10:00:00+00:00",
                "scheduled": False,
            },
        )

        async with factory() as db:
            row = (
                await db.execute(
                    select(SessionModel).where(
                        SessionModel.id == "20260409-1000"
                    )
                )
            ).scalar_one()
            assert row.label == "Morning"
            assert row.scheduled == 0


@pytest.mark.asyncio
async def test_handle_session_db_stopped() -> None:
    async with _db_factory() as factory:
        await _handle_session_db(
            factory,
            {
                "event": "started",
                "session_id": "20260409-1000",
                "label": "Morning",
                "started_at": "2026-04-09T10:00:00+00:00",
            },
        )
        await _handle_session_db(
            factory,
            {
                "event": "stopped",
                "session_id": "20260409-1000",
                "stopped_at": "2026-04-09T11:00:00+00:00",
            },
        )

        async with factory() as db:
            row = (
                await db.execute(
                    select(SessionModel).where(
                        SessionModel.id == "20260409-1000"
                    )
                )
            ).scalar_one()
            assert row.stopped_at == "2026-04-09T11:00:00+00:00"


@pytest.mark.asyncio
async def test_handle_session_db_idempotent_start() -> None:
    async with _db_factory() as factory:
        data = {
            "event": "started",
            "session_id": "20260409-1000",
            "label": "Morning",
            "started_at": "2026-04-09T10:00:00+00:00",
        }
        await _handle_session_db(factory, data)
        await _handle_session_db(factory, data)

        async with factory() as db:
            rows = (
                await db.execute(select(SessionModel))
            ).scalars().all()
            assert len(rows) == 1


@pytest.mark.asyncio
async def test_handle_session_db_no_session_id_noop() -> None:
    async with _db_factory() as factory:
        await _handle_session_db(factory, {"event": "started"})

        async with factory() as db:
            rows = (
                await db.execute(select(SessionModel))
            ).scalars().all()
            assert len(rows) == 0

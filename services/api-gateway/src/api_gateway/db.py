"""Database models and engine setup for LiveSTT.

Uses SQLAlchemy 2.0 async with aiosqlite. All persistent application
data (sessions, transcript segments, schedules) lives in a single
SQLite file owned by api-gateway.
"""

import os
from pathlib import Path
from typing import Any

from sqlalchemy import ForeignKey, Index
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DB_PATH = os.getenv("DB_PATH", "/data/db/livestt.db")


class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(default="")
    started_at: Mapped[str] = mapped_column()
    stopped_at: Mapped[str | None] = mapped_column(default=None)
    scheduled: Mapped[int] = mapped_column(default=0)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    timestamp: Mapped[str] = mapped_column()
    speaker: Mapped[str] = mapped_column(default="Unknown")
    text: Mapped[str] = mapped_column()
    confidence: Mapped[float] = mapped_column(default=0.0)
    source: Mapped[str] = mapped_column(default="live")

    __table_args__: Any = (Index("idx_segments_session", "session_id"),)


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(primary_key=True)
    day_of_week: Mapped[str] = mapped_column()  # JSON array
    start_time: Mapped[str] = mapped_column()  # "HH:MM"
    stop_time: Mapped[str] = mapped_column()  # "HH:MM"
    label_template: Mapped[str] = mapped_column(default="")
    stop_policy: Mapped[str] = mapped_column(default="soft")
    enabled: Mapped[int] = mapped_column(default=1)


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column()  # ISO 8601
    service: Mapped[str] = mapped_column()
    level: Mapped[str] = mapped_column()
    message: Mapped[str] = mapped_column()

    __table_args__: Any = (Index("idx_logs_timestamp", "timestamp"),)


async def create_engine_and_tables() -> tuple[
    AsyncEngine, async_sessionmaker[AsyncSession]
]:
    """Create the async engine and ensure all tables exist."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory

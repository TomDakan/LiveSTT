"""Tests for the /admin/backup and /admin/restore endpoints."""

from __future__ import annotations

import io
import tarfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from api_gateway.auth import create_token
from api_gateway.db import Base
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

JWT_SECRET = "test-secret-backup-at-least-32-bytes-long!!"


@asynccontextmanager
async def _patched_app(
    tmp_path: Path,
) -> AsyncGenerator[Any, None]:
    """Populate app.state and redirect _DB_DIR / _LANCEDB_DIR to tmp_path."""
    import api_gateway.main as main_mod
    from api_gateway.main import app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_factory: async_sessionmaker[Any] = async_sessionmaker(
        engine, expire_on_commit=False
    )

    mock_js = AsyncMock()
    kv = AsyncMock()
    kv.get.side_effect = Exception("not found")

    old_state = dict(app.state._state)
    app.state.js = mock_js
    app.state.session_kv = kv
    app.state.config_kv = kv
    app.state.jwt_secret = JWT_SECRET
    app.state.db_factory = db_factory
    app.state.nats = MagicMock()

    orig_db = main_mod._DB_DIR
    orig_lance = main_mod._LANCEDB_DIR
    main_mod._DB_DIR = tmp_path / "db"
    main_mod._LANCEDB_DIR = tmp_path / "lancedb"

    try:
        yield app
    finally:
        main_mod._DB_DIR = orig_db
        main_mod._LANCEDB_DIR = orig_lance
        app.state._state.clear()
        app.state._state.update(old_state)
        await engine.dispose()


def _auth_header() -> dict[str, str]:
    token = create_token(JWT_SECRET)
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------------
# POST /admin/backup
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_creates_valid_targz(tmp_path: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    # Seed a DB file
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    (db_dir / "livestt.db").write_bytes(b"fake-sqlite-data")

    async with (
        _patched_app(tmp_path) as app,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        resp = await client.post(
            "/admin/backup", headers=_auth_header()
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/gzip"

    # Verify it's a valid tar.gz
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        names = tar.getnames()
        assert "db/livestt.db" in names


@pytest.mark.asyncio
async def test_backup_no_data_returns_404(tmp_path: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    # Don't create the db directory
    async with (
        _patched_app(tmp_path) as app,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        resp = await client.post(
            "/admin/backup", headers=_auth_header()
        )

    assert resp.status_code == 404


# -------------------------------------------------------------------
# POST /admin/restore
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_roundtrip(tmp_path: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    original_data = b"original-sqlite-db-contents"
    (db_dir / "livestt.db").write_bytes(original_data)

    async with (
        _patched_app(tmp_path) as app,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        # Backup
        backup_resp = await client.post(
            "/admin/backup", headers=_auth_header()
        )
        assert backup_resp.status_code == 200
        archive = backup_resp.content

        # Wipe the DB
        (db_dir / "livestt.db").write_bytes(b"corrupted")

        # Restore
        restore_resp = await client.post(
            "/admin/restore",
            content=archive,
            headers={
                **_auth_header(),
                "content-type": "application/gzip",
            },
        )

    assert restore_resp.status_code == 200
    body = restore_resp.json()
    assert body["status"] == "ok"
    assert body["restored_files"]["db"] >= 1

    # Verify data restored
    assert (db_dir / "livestt.db").read_bytes() == original_data


@pytest.mark.asyncio
async def test_restore_blocks_path_traversal(tmp_path: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    # Create a malicious archive with ../etc/passwd
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"malicious content"
        info = tarfile.TarInfo(name="../etc/passwd")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)

    # Ensure db dir exists for restore
    (tmp_path / "db").mkdir()

    async with (
        _patched_app(tmp_path) as app,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        resp = await client.post(
            "/admin/restore",
            content=buf.getvalue(),
            headers={
                **_auth_header(),
                "content-type": "application/gzip",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    # The traversal entry should have been skipped
    assert body["restored_files"]["db"] == 0
    assert body["restored_files"]["lancedb"] == 0


@pytest.mark.asyncio
async def test_restore_legacy_flat_format(tmp_path: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    # Create an archive with legacy flat .db file (no db/ prefix)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"legacy-db-data"
        info = tarfile.TarInfo(name="livestt.db")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)

    db_dir = tmp_path / "db"
    db_dir.mkdir()

    async with (
        _patched_app(tmp_path) as app,
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        resp = await client.post(
            "/admin/restore",
            content=buf.getvalue(),
            headers={
                **_auth_header(),
                "content-type": "application/gzip",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["restored_files"]["db"] == 1
    assert (db_dir / "livestt.db").read_bytes() == b"legacy-db-data"

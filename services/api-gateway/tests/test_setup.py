"""Tests for the /setup/status and /setup first-run endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from api_gateway.db import AppConfig, Base
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

JWT_SECRET = "test-secret-setup-at-least-32-bytes-long!!"


@asynccontextmanager
async def _patched_app(
    *,
    admin_hash: str = "",
) -> AsyncGenerator[tuple[Any, async_sessionmaker[Any]], None]:
    """Populate app.state with an in-memory DB; no real NATS."""
    import api_gateway.auth as auth_module
    from api_gateway.main import app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_factory: async_sessionmaker[Any] = async_sessionmaker(
        engine, expire_on_commit=False
    )

    mock_js = AsyncMock()
    kv = AsyncMock()
    kv.get.side_effect = Exception("KeyNotFoundError")

    async def _empty_watch(key: str) -> AsyncGenerator[None, None]:
        return
        yield  # makes this an async generator

    kv.watch.side_effect = _empty_watch

    old_state = dict(app.state._state)
    app.state.js = mock_js
    app.state.session_kv = kv
    app.state.config_kv = kv
    app.state.jwt_secret = JWT_SECRET
    app.state.db_factory = db_factory
    app.state.nats = MagicMock()

    original_hash = auth_module.ADMIN_PASSWORD_HASH
    auth_module.ADMIN_PASSWORD_HASH = admin_hash
    try:
        yield app, db_factory
    finally:
        auth_module.ADMIN_PASSWORD_HASH = original_hash
        app.state._state.clear()
        app.state._state.update(old_state)
        await engine.dispose()


# -------------------------------------------------------------------
# GET /setup/status
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_status_needs_setup_initially() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, _),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        resp = await client.get("/setup/status")

    assert resp.status_code == 200
    assert resp.json() == {"needs_setup": True}


# -------------------------------------------------------------------
# POST /setup
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_creates_admin_and_returns_token() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, db_factory),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        resp = await client.post(
            "/setup",
            json={"password": "validpass123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "token" in body

        # Verify password hash was stored in DB
        async with db_factory() as db:
            row = (
                await db.execute(
                    select(AppConfig.value).where(
                        AppConfig.key == "admin_password_hash"
                    )
                )
            ).scalar_one()
            assert row.startswith("$2b$")


@pytest.mark.asyncio
async def test_setup_rejects_short_password() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, _),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        resp = await client.post(
            "/setup",
            json={"password": "short"},
        )

    assert resp.status_code == 422
    assert "at least" in resp.json()["error"]


@pytest.mark.asyncio
async def test_setup_twice_returns_409() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, _),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        # First setup succeeds
        resp1 = await client.post(
            "/setup", json={"password": "validpass123"}
        )
        assert resp1.status_code == 200

        # Second setup fails
        resp2 = await client.post(
            "/setup", json={"password": "anotherpass"}
        )
        assert resp2.status_code == 409
        assert resp2.json()["error"] == "setup_already_complete"


@pytest.mark.asyncio
async def test_setup_stores_deepgram_key() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, db_factory),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        await client.post(
            "/setup",
            json={
                "password": "validpass123",
                "deepgram_api_key": "sk-test-key",
            },
        )

        async with db_factory() as db:
            row = (
                await db.execute(
                    select(AppConfig.value).where(
                        AppConfig.key == "deepgram_api_key"
                    )
                )
            ).scalar_one()
            assert row == "sk-test-key"


@pytest.mark.asyncio
async def test_auth_works_after_setup() -> None:
    import api_gateway.auth as auth_module
    from httpx import ASGITransport, AsyncClient

    # Clear rate limiter state from prior tests to avoid 429
    auth_module._auth_attempts.clear()

    async with (
        _patched_app() as (app, _),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        # Setup
        await client.post(
            "/setup", json={"password": "validpass123"}
        )

        # Now authenticate with the same password
        resp = await client.post(
            "/admin/auth", json={"password": "validpass123"}
        )
        assert resp.status_code == 200
        assert "token" in resp.json()

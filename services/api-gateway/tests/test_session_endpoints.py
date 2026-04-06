"""Unit tests for the api-gateway session endpoints (Milestone 4.5)."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from api_gateway.auth import create_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_kv(
    *, active: bool = False, session_id: str = "20260101-1000"
) -> AsyncMock:
    kv = AsyncMock()
    if active:
        entry = MagicMock()
        entry.value = json.dumps(
            {
                "state": "active",
                "session_id": session_id,
                "started_at": "2026-01-01T10:00:00+00:00",
                "label": "Test",
            }
        ).encode()
        kv.get.return_value = entry
    else:
        kv.get.side_effect = Exception("KeyNotFoundError")

    async def _empty_watch(key: str) -> AsyncGenerator[None, None]:
        return
        yield  # makes this an async generator

    kv.watch.side_effect = _empty_watch
    return kv


def _make_config_kv() -> AsyncMock:
    kv = AsyncMock()
    kv.get.side_effect = Exception("not found")
    return kv


JWT_SECRET = "test-secret-for-unit-tests-at-least-32-bytes-long"


@asynccontextmanager
async def _nats_patched_app(
    session_kv: Any,
    config_kv: Any,
) -> AsyncGenerator[tuple[Any, AsyncMock], None]:
    """
    httpx 0.28 ASGITransport does not trigger the ASGI lifespan, so we skip
    the real lifespan entirely and populate app.state directly.
    """
    from api_gateway.db import Base
    from api_gateway.main import app
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_js = AsyncMock()

    # Save any existing state so tests don't bleed into each other.
    old_state = dict(app.state._state)
    app.state.js = mock_js
    app.state.session_kv = session_kv
    app.state.config_kv = config_kv
    app.state.jwt_secret = JWT_SECRET
    app.state.db_factory = db_factory

    try:
        yield app, mock_js
    finally:
        # Restore previous state (or clear it).
        app.state._state.clear()
        app.state._state.update(old_state)
        await engine.dispose()


def _auth_header() -> dict[str, str]:
    """Return an Authorization header with a valid JWT."""
    token = create_token(JWT_SECRET)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /session/start
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_start_returns_200_when_no_session() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=False)
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post("/session/start", json={"label": "Morning"})

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_session_start_publishes_start_command() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=False)
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, mock_js),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        await client.post("/session/start", json={"label": "Morning"})

    mock_js.publish.assert_called_once()
    subject, payload = mock_js.publish.call_args[0]
    assert subject == "session.control"
    data = json.loads(payload.decode())
    assert data["command"] == "start"
    assert data["label"] == "Morning"


@pytest.mark.asyncio
async def test_session_start_returns_409_when_already_active() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=True, session_id="20260101-1000")
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post("/session/start", json={})

    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "session_already_active"
    assert body["session_id"] == "20260101-1000"


@pytest.mark.asyncio
async def test_session_start_does_not_publish_when_409() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=True, session_id="20260101-1000")
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, mock_js),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        await client.post("/session/start", json={})

    mock_js.publish.assert_not_called()


# ---------------------------------------------------------------------------
# POST /session/stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_stop_returns_401_without_token() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post("/session/stop")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_session_stop_returns_401_with_invalid_token() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/session/stop",
            headers={"Authorization": "Bearer bad-token"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_session_stop_returns_200_with_valid_jwt() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, mock_js),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/session/stop",
            headers=_auth_header(),
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_js.publish.assert_called_once()
    subject, payload = mock_js.publish.call_args[0]
    assert subject == "session.control"
    data = json.loads(payload.decode())
    assert data["command"] == "stop"


# ---------------------------------------------------------------------------
# POST /admin/auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_auth_returns_token_on_valid_password() -> None:
    """Dev mode (no ADMIN_PASSWORD_HASH): any password accepted."""
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/admin/auth",
            json={"password": "anything"},
        )

    assert resp.status_code == 200
    assert "token" in resp.json()


@pytest.mark.asyncio
async def test_admin_auth_token_works_for_protected_routes() -> None:
    """JWT from /admin/auth can access protected endpoints."""
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        # Get token
        auth_resp = await client.post(
            "/admin/auth",
            json={"password": "test"},
        )
        token = auth_resp.json()["token"]

        # Use it on a protected route
        resp = await client.post(
            "/session/stop",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /session/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_status_returns_idle_when_no_session() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=False)
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/session/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "idle"
    assert "silence_timeout_s" in body


@pytest.mark.asyncio
async def test_session_status_returns_active_shape() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=True, session_id="20260101-1000")
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/session/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "active"
    assert body["session_id"] == "20260101-1000"
    assert "started_at" in body
    assert "silence_timeout_s" in body


# ---------------------------------------------------------------------------
# PATCH /admin/sessions/{session_id} (rename)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_session_updates_label() -> None:
    from api_gateway.db import SessionModel
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=False)
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        # Seed a session row
        async with app.state.db_factory() as db:
            db.add(
                SessionModel(
                    id="20260101-1000",
                    label="Old Label",
                    started_at="2026-01-01T10:00:00+00:00",
                    stopped_at="2026-01-01T11:00:00+00:00",
                )
            )
            await db.commit()

        resp = await client.patch(
            "/admin/sessions/20260101-1000",
            json={"label": "New Label"},
            headers=_auth_header(),
        )

    assert resp.status_code == 200
    assert resp.json()["label"] == "New Label"


@pytest.mark.asyncio
async def test_rename_session_returns_404_for_missing() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=False)
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.patch(
            "/admin/sessions/nonexistent",
            json={"label": "Test"},
            headers=_auth_header(),
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rename_session_requires_auth() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv(active=False)
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.patch(
            "/admin/sessions/20260101-1000",
            json={"label": "Test"},
        )

    assert resp.status_code == 401

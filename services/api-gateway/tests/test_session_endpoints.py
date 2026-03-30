"""Unit tests for the api-gateway session endpoints (Milestone 4.5)."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


@asynccontextmanager
async def _nats_patched_app(
    session_kv: Any,
    config_kv: Any,
    *,
    admin_token: str = "",
) -> AsyncGenerator[tuple[Any, AsyncMock], None]:
    """
    httpx 0.28 ASGITransport does not trigger the ASGI lifespan, so we skip
    the real lifespan entirely and populate app.state directly.
    """
    from api_gateway.main import app

    mock_js = AsyncMock()

    # Save any existing state so tests don't bleed into each other.
    old_state = dict(app.state._state)
    app.state.js = mock_js
    app.state.session_kv = session_kv
    app.state.config_kv = config_kv

    try:
        with patch.dict("os.environ", {"ADMIN_TOKEN": admin_token}):
            yield app, mock_js
    finally:
        # Restore previous state (or clear it).
        app.state._state.clear()
        app.state._state.update(old_state)


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
async def test_session_stop_returns_401_with_wrong_token() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv, admin_token="secret") as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/session/stop",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_session_stop_returns_200_with_correct_token() -> None:
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv, admin_token="secret") as (app, mock_js),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/session/stop",
            headers={"Authorization": "Bearer secret"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_js.publish.assert_called_once()
    subject, payload = mock_js.publish.call_args[0]
    assert subject == "session.control"
    data = json.loads(payload.decode())
    assert data["command"] == "stop"


@pytest.mark.asyncio
async def test_session_stop_dev_mode_accepts_any_token() -> None:
    """When ADMIN_TOKEN is empty, any token is accepted (dev mode)."""
    from httpx import ASGITransport, AsyncClient

    session_kv = _make_session_kv()
    config_kv = _make_config_kv()

    async with (
        _nats_patched_app(session_kv, config_kv, admin_token="") as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/session/stop",
            headers={"Authorization": "Bearer anything"},
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

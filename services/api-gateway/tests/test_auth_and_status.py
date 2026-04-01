"""Smoke tests for /admin/auth and /admin/status endpoints."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from api_gateway.auth import create_token

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

JWT_SECRET = "test-secret-auth-status-at-least-32-bytes-long"


@asynccontextmanager
async def _patched_app(
    session_kv: Any,
    config_kv: Any,
) -> AsyncGenerator[tuple[Any, Any], None]:
    """Populate app.state without triggering the ASGI lifespan."""
    from api_gateway.main import app

    mock_js = AsyncMock()
    old_state = dict(app.state._state)
    app.state.js = mock_js
    app.state.session_kv = session_kv
    app.state.config_kv = config_kv
    app.state.jwt_secret = JWT_SECRET

    try:
        yield app, mock_js
    finally:
        app.state._state.clear()
        app.state._state.update(old_state)


def _make_idle_kv() -> AsyncMock:
    kv = AsyncMock()
    kv.get.side_effect = Exception("KeyNotFoundError")

    async def _empty_watch(key: str) -> AsyncGenerator[None, None]:
        return
        yield  # make it an async generator

    kv.watch.side_effect = _empty_watch
    return kv


def _auth_header(secret: str = JWT_SECRET) -> dict[str, str]:
    token = create_token(secret)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /admin/auth — login success / failure / dev-mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_dev_mode_accepts_any_password() -> None:
    """When ADMIN_PASSWORD_HASH is unset, any password is accepted."""
    from httpx import ASGITransport, AsyncClient

    kv = _make_idle_kv()
    async with (
        _patched_app(kv, _make_idle_kv()) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        # Patch env so ADMIN_PASSWORD_HASH is empty (dev mode)
        with patch.dict("os.environ", {}, clear=False):
            import api_gateway.auth as auth_module

            original = auth_module.ADMIN_PASSWORD_HASH
            auth_module.ADMIN_PASSWORD_HASH = ""
            try:
                resp = await client.post(
                    "/admin/auth", json={"password": "anything-at-all"}
                )
            finally:
                auth_module.ADMIN_PASSWORD_HASH = original

    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 10


@pytest.mark.asyncio
async def test_auth_valid_bcrypt_password_returns_token() -> None:
    """When ADMIN_PASSWORD_HASH is set, correct password returns a token."""
    import bcrypt
    from httpx import ASGITransport, AsyncClient

    password = "supersecret"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    kv = _make_idle_kv()
    async with (
        _patched_app(kv, _make_idle_kv()) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        import api_gateway.auth as auth_module

        original = auth_module.ADMIN_PASSWORD_HASH
        auth_module.ADMIN_PASSWORD_HASH = hashed
        try:
            resp = await client.post("/admin/auth", json={"password": password})
        finally:
            auth_module.ADMIN_PASSWORD_HASH = original

    assert resp.status_code == 200
    assert "token" in resp.json()


@pytest.mark.asyncio
async def test_auth_wrong_password_returns_401() -> None:
    """When ADMIN_PASSWORD_HASH is set, wrong password → 401."""
    import bcrypt
    from httpx import ASGITransport, AsyncClient

    hashed = bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode()

    kv = _make_idle_kv()
    async with (
        _patched_app(kv, _make_idle_kv()) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        import api_gateway.auth as auth_module

        original = auth_module.ADMIN_PASSWORD_HASH
        auth_module.ADMIN_PASSWORD_HASH = hashed
        try:
            resp = await client.post("/admin/auth", json={"password": "wrong-password"})
        finally:
            auth_module.ADMIN_PASSWORD_HASH = original

    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_password"


@pytest.mark.asyncio
async def test_protected_route_without_token_returns_401() -> None:
    """POST /session/stop without Authorization header → 401."""
    from httpx import ASGITransport, AsyncClient

    kv = _make_idle_kv()
    async with (
        _patched_app(kv, _make_idle_kv()) as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post("/session/stop")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token_succeeds() -> None:
    """POST /session/stop with a valid JWT → 200."""
    from httpx import ASGITransport, AsyncClient

    kv = _make_idle_kv()
    async with (
        _patched_app(kv, _make_idle_kv()) as (app, mock_js),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post("/session/stop", headers=_auth_header())

    assert resp.status_code == 200
    mock_js.publish.assert_called_once()


# ---------------------------------------------------------------------------
# GET /admin/status — smoke test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_status_returns_expected_structure() -> None:
    """GET /admin/status returns dict with services, streams, disk keys."""
    from httpx import ASGITransport, AsyncClient

    kv = _make_idle_kv()

    # Mock service_health KV: one running service
    kv_entry = MagicMock()
    kv_entry.value = json.dumps(
        {"service": "audio-producer", "status": "running", "timestamp": 1234567890.0}
    ).encode()
    service_health_kv = AsyncMock()
    service_health_kv.keys.return_value = ["audio-producer"]
    service_health_kv.get.return_value = kv_entry

    # Mock JetStream: key_value returns our service_health mock
    # stream info returns a fake state
    fake_state = MagicMock()
    fake_state.messages = 42
    fake_state.bytes = 1024
    fake_state.consumer_count = 1

    fake_info = MagicMock()
    fake_info.state = fake_state

    async with _patched_app(kv, _make_idle_kv()) as (app, mock_js):
        mock_js.key_value.return_value = service_health_kv
        mock_js.find_stream_info_by_name.return_value = fake_info

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/admin/status")

    assert resp.status_code == 200
    body = resp.json()
    assert "services" in body
    assert "streams" in body
    assert "disk" in body

    # Services list has our mock entry
    assert isinstance(body["services"], list)
    assert body["services"][0]["name"] == "audio-producer"
    assert body["services"][0]["status"] == "running"

    # Streams list has at least one entry with expected shape
    assert isinstance(body["streams"], list)
    assert len(body["streams"]) > 0
    stream = body["streams"][0]
    assert "name" in stream
    assert "messages" in stream
    assert "bytes" in stream
    assert "consumers" in stream

    # Disk has expected keys
    disk = body["disk"]
    assert "total_bytes" in disk
    assert "free_bytes" in disk
    assert "used_bytes" in disk
    assert "db_size_bytes" in disk

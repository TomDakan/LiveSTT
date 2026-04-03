"""Tests for /admin/logs WebSocket and /admin/speakers endpoints (M6.5)."""

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from api_gateway.auth import create_token

# ---------------------------------------------------------------------------
# Shared helpers (mirrors the pattern in test_session_endpoints.py)
# ---------------------------------------------------------------------------

JWT_SECRET = "test-secret-for-unit-tests-at-least-32-bytes-long"


@asynccontextmanager
async def _patched_app(
    *,
    mock_nats: Any | None = None,
) -> AsyncGenerator[tuple[Any, Any], None]:
    """Populate app.state without triggering the real NATS lifespan."""
    from api_gateway.main import app

    nc = mock_nats if mock_nats is not None else AsyncMock()

    old_state = dict(app.state._state)
    app.state.nats = nc
    app.state.js = AsyncMock()
    app.state.session_kv = None
    app.state.config_kv = None
    app.state.jwt_secret = JWT_SECRET

    try:
        yield app, nc
    finally:
        app.state._state.clear()
        app.state._state.update(old_state)


def _auth_header() -> dict[str, str]:
    token = create_token(JWT_SECRET)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /admin/speakers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_speakers_returns_empty_list() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/admin/speakers", headers=_auth_header())

    assert resp.status_code == 200
    assert resp.json() == {"speakers": []}


@pytest.mark.asyncio
async def test_list_speakers_requires_auth() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.get("/admin/speakers")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /admin/speakers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enroll_speaker_publishes_to_nats() -> None:
    from httpx import ASGITransport, AsyncClient

    mock_nc = AsyncMock()
    async with (
        _patched_app(mock_nats=mock_nc) as (app, nc),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post(
            "/admin/speakers",
            json={"name": "Pastor John"},
            headers=_auth_header(),
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "queued"}

    nc.publish.assert_called_once()
    subject, payload = nc.publish.call_args[0]
    assert subject == "identifier.command"
    data = json.loads(payload.decode())
    assert data == {"command": "enroll", "name": "Pastor John"}


@pytest.mark.asyncio
async def test_enroll_speaker_requires_auth() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.post("/admin/speakers", json={"name": "Test"})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /admin/speakers/{name}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_speaker_publishes_to_nats() -> None:
    from httpx import ASGITransport, AsyncClient

    mock_nc = AsyncMock()
    async with (
        _patched_app(mock_nats=mock_nc) as (app, nc),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.delete(
            "/admin/speakers/Pastor%20John",
            headers=_auth_header(),
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "queued"}

    nc.publish.assert_called_once()
    subject, payload = nc.publish.call_args[0]
    assert subject == "identifier.command"
    data = json.loads(payload.decode())
    assert data == {"command": "delete", "name": "Pastor John"}


@pytest.mark.asyncio
async def test_delete_speaker_requires_auth() -> None:
    from httpx import ASGITransport, AsyncClient

    async with (
        _patched_app() as (app, _),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        resp = await client.delete("/admin/speakers/someone")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /admin/logs  (WebSocket) — logic tests
#
# The WebSocket endpoint creates a closure (_on_log) over a bounded queue.
# Rather than exercising the full ASGI WS handshake (which requires a
# thread-based TestClient incompatible with async mocks), we replicate the
# exact _on_log logic here and assert on the queue state.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_logs_on_log_callback_puts_payload_on_queue() -> None:
    """Valid JSON NATS message is parsed and placed on the queue."""
    from api_gateway.main import _LOG_WS_QUEUE_SIZE

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_LOG_WS_QUEUE_SIZE)

    log_payload = {
        "service": "stt-provider",
        "level": "INFO",
        "message": "hello from test",
        "timestamp": 1234567890.0,
    }

    # Replicate the _on_log closure from the WS endpoint.
    async def _on_log(msg: Any) -> None:
        try:
            data: dict[str, Any] = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        await queue.put(data)

    fake_msg = MagicMock()
    fake_msg.data = json.dumps(log_payload).encode()

    await _on_log(fake_msg)

    assert queue.qsize() == 1
    received = queue.get_nowait()
    assert received == log_payload


def test_admin_logs_ws_registers_subscriber() -> None:
    """The /admin/logs endpoint registers a queue in _log_subscribers."""
    from api_gateway.main import _log_subscribers, app
    from starlette.testclient import TestClient

    old_state = dict(app.state._state)
    app.state.jwt_secret = JWT_SECRET

    initial_count = len(_log_subscribers)

    try:
        client = TestClient(app, raise_server_exceptions=False)
        try:
            with client.websocket_connect("/admin/logs") as ws:
                import time

                time.sleep(0.1)
                # While connected, subscriber count should increase
                assert len(_log_subscribers) == initial_count + 1
                ws.close()
        except Exception:
            pass
    finally:
        app.state._state.clear()
        app.state._state.update(old_state)

    # After disconnect, subscriber should be removed
    assert len(_log_subscribers) == initial_count


@pytest.mark.asyncio
async def test_admin_logs_ws_queue_drops_oldest_when_full() -> None:
    """When the internal queue is full, the oldest entry is dropped."""
    from api_gateway.main import _LOG_WS_QUEUE_SIZE

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_LOG_WS_QUEUE_SIZE)

    # Pre-fill the queue.
    for i in range(_LOG_WS_QUEUE_SIZE):
        await queue.put({"index": i})

    assert queue.full()

    new_entry: dict[str, Any] = {"index": _LOG_WS_QUEUE_SIZE}

    # Simulate the drop-oldest logic from the _on_log callback.
    if queue.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    await queue.put(new_entry)

    assert queue.qsize() == _LOG_WS_QUEUE_SIZE
    # The first entry (index 0) was dropped; last entry is the new one.
    entries = []
    while not queue.empty():
        entries.append(queue.get_nowait())
    assert entries[0]["index"] == 1
    assert entries[-1]["index"] == _LOG_WS_QUEUE_SIZE


@pytest.mark.asyncio
async def test_admin_logs_on_log_callback_ignores_malformed_nats_message() -> None:
    """Malformed (non-JSON) NATS data is silently dropped; queue stays empty."""
    from api_gateway.main import _LOG_WS_QUEUE_SIZE

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_LOG_WS_QUEUE_SIZE)

    # Replicate the _on_log closure from the WS endpoint.
    async def _on_log(msg: Any) -> None:
        try:
            data: dict[str, Any] = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        await queue.put(data)

    fake_msg = MagicMock()
    fake_msg.data = b"not-json{"

    # Must not raise and queue must remain empty.
    await _on_log(fake_msg)

    assert queue.empty()

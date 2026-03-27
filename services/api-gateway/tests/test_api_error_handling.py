import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from api_gateway.main import _pull_loop, app, lifespan


class MockSub:
    """Mock JetStream pull subscription that returns no messages."""

    async def fetch(self, batch: int, timeout: float) -> list[Any]:
        await asyncio.sleep(timeout)
        raise TimeoutError


class MockJetStream:
    def __init__(self) -> None:
        self._sub = MockSub()

    async def pull_subscribe(self, *args: Any, **kwargs: Any) -> MockSub:
        return self._sub


class MockNatsClient:
    """Simulates NatsClient for testing."""

    def __init__(self) -> None:
        self._js = MockJetStream()

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def close(self) -> None:
        pass

    def jetstream(self) -> MockJetStream:
        return self._js


@pytest.mark.asyncio
async def test_malformed_message_logs_error() -> None:
    """Verifies that invalid JSON in a pulled NATS message is logged and ignored."""
    msg = AsyncMock()
    msg.data = b"{invalid json"

    call_count = 0

    async def fake_fetch(batch: int, timeout: float) -> list[Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [msg]
        await asyncio.sleep(0.05)
        raise TimeoutError

    mock_sub = AsyncMock()
    mock_sub.fetch.side_effect = fake_fetch

    stop_event = asyncio.Event()

    with patch("api_gateway.main.logger") as mock_logger:
        task = asyncio.create_task(_pull_loop(mock_sub, stop_event))
        await asyncio.sleep(0.15)
        stop_event.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    mock_logger.error.assert_called()
    assert "Error broadcasting NATS message" in str(mock_logger.error.call_args)


@pytest.mark.asyncio
async def test_lifespan_startup_failure() -> None:
    """Verify application handles NATS connection failure."""

    # Mock the whole NATS client object on the module
    # We must set side_effect on the mock instance's connect method
    with patch("api_gateway.main.nats_client") as mock_nats:
        mock_nats.connect.side_effect = Exception("Connection Refused")
        # Ensure close is a mock so finally block succeeds
        mock_nats.close = AsyncMock()

        cm = lifespan(app)
        with pytest.raises(Exception, match="Connection Refused"):
            async with cm:
                pass

        mock_nats.connect.assert_called()
        mock_nats.close.assert_called()


@pytest.mark.asyncio
async def test_websocket_disconnect_handling() -> None:
    """Verify clean shutdown on client disconnect."""
    from fastapi.testclient import TestClient

    mock_nats = MockNatsClient()
    app.state.nats = mock_nats

    with patch("api_gateway.main.nats_client", mock_nats):
        client = TestClient(app)
        with patch("api_gateway.main.logger") as mock_logger:
            with client.websocket_connect("/ws/transcripts") as _:
                pass  # just connect and close block to trigger disconnect

            # Logs should show disconnect
            mock_logger.info.assert_called_with("Client disconnected.")

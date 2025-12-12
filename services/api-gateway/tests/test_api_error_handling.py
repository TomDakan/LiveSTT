from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from api_gateway.main import app, lifespan
from fastapi.testclient import TestClient


class MockNatsClient:
    """Simulates NatsClient for testing."""

    def __init__(self) -> None:
        self.subscriptions: dict[str, Any] = {}

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def close(self) -> None:
        pass

    async def subscribe(self, subject: str, cb: Any) -> Any:
        self.subscriptions[subject] = cb
        return AsyncMock()

    async def trigger_message(self, subject: str, data: bytes) -> None:
        if subject in self.subscriptions:
            msg = AsyncMock()
            msg.data = data
            await self.subscriptions[subject](msg)


@pytest.mark.asyncio
async def test_malformed_message_logs_error() -> None:
    """Verifies that invalid JSON in NATS message is logged and ignored."""
    mock_nats = MockNatsClient()
    app.state.nats = mock_nats
    client = TestClient(app)

    with patch("api_gateway.main.logger") as mock_logger, client.websocket_connect(
        "/ws/transcripts"
    ) as _:
            # Send malformed JSON
            await mock_nats.trigger_message("transcript.final.>", b"{invalid json")

            # Verify error logged
            mock_logger.error.assert_called()
            # The actual error message might vary, but it should log error
            assert mock_logger.error.call_count >= 1
            call_args = str(mock_logger.error.call_args)
            assert "Error forwarding message" in call_args


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
    mock_nats = MockNatsClient()
    app.state.nats = mock_nats
    client = TestClient(app)

    with patch("api_gateway.main.logger") as mock_logger, client.websocket_connect(
        "/ws/transcripts"
    ) as _:
            pass  # just connect and close

        # Logs should show disconnect
        mock_logger.info.assert_called_with("Client disconnected.")

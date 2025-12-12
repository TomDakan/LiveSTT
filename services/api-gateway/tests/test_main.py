import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from api_gateway.main import app
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
async def test_websocket_endpoint() -> None:
    """
    Verifies that the WebSocket endpoint:
    1. Accepts connection.
    2. Subscribes to NATS topic.
    3. Forwards NATS messages to the WebSocket client.
    """
    # Setup Mock NATS
    mock_nats = MockNatsClient()
    app.state.nats = mock_nats

    # Use TestClient for WebSocket
    client = TestClient(app)

    with client.websocket_connect("/ws/transcripts") as websocket:
        # Verify subscription
        assert "transcript.final.>" in mock_nats.subscriptions

        # Simulate NATS message
        transcript_data = {"text": "Hello World", "is_final": True, "confidence": 0.99}
        await mock_nats.trigger_message(
            "transcript.final.>", json.dumps(transcript_data).encode("utf-8")
        )

        # Verify WebSocket received message
        data = websocket.receive_json()
        assert data["type"] == "transcript"
        assert data["payload"] == transcript_data

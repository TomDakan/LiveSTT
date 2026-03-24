import json
from typing import Any

import pytest
from api_gateway.main import app
from fastapi.testclient import TestClient


class MockMsg:
    def __init__(self, data: bytes) -> None:
        self.data = data


class MockNatsClient:
    def __init__(self) -> None:
        self.subscriptions: list[str] = []
        self.callbacks: dict[str, Any] = {}

    async def subscribe(self, subject: str, cb: Any) -> Any:
        self.subscriptions.append(subject)
        self.callbacks[subject] = cb
        return None

    async def trigger_message(self, subject: str, data: bytes) -> None:
        if subject in self.callbacks:
            await self.callbacks[subject](MockMsg(data))


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
        assert "text.transcript" in mock_nats.subscriptions

        # Simulate NATS message
        transcript_data = {"text": "Hello World", "is_final": True, "confidence": 0.99}
        await mock_nats.trigger_message(
            "text.transcript", json.dumps(transcript_data).encode("utf-8")
        )

        # Verify WebSocket received message
        data = websocket.receive_json()
        assert data["type"] == "transcript"
        assert data["payload"] == transcript_data

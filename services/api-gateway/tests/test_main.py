import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from messaging.nats import MockNatsClient
from api_gateway.main import app

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
        await mock_nats.trigger_message("text.transcript", json.dumps(transcript_data).encode("utf-8"))

        # Verify WebSocket received message
        data = websocket.receive_json()
        assert data["type"] == "transcript"
        assert data["payload"] == transcript_data

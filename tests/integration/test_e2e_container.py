import asyncio
import json
import os
import pytest
import websockets
from nats.aio.client import Client as NATS

# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/transcripts")

@pytest.mark.asyncio
async def test_container_e2e_flow() -> None:
    """
    End-to-End Integration Test against running containers.
    Verifies: Audio Producer (Container) -> NATS -> STT (Container) -> NATS -> Gateway (Container) -> WebSocket
    """
    print(f"Connecting to NATS at {NATS_URL}")
    print(f"Connecting to WebSocket at {WS_URL}")

    # 1. Connect to NATS to monitor traffic (optional, for debugging)
    nc = NATS()
    await nc.connect(NATS_URL)

    async def log_msg(msg):
        print(f"[NATS Monitor] Subject: {msg.subject}, Data: {len(msg.data)} bytes")

    await nc.subscribe("audio.raw", cb=log_msg)
    await nc.subscribe("text.transcript", cb=log_msg)

    # 2. Connect to WebSocket
    # The containers are already running. Audio producer should be blasting or reading file.
    # If audio producer is one-shot, it might have finished.
    # But typically in this setup, we might want to trigger it or just listen.
    # Our audio-producer Dockerfile runs main.py, which reads env vars.
    # We didn't mount a file, so it might fail if it defaults to file source and file is missing.
    # Let's check logs later. For now, let's try to connect.

    try:
        async with websockets.connect(WS_URL) as websocket:
            print("WebSocket connected. Waiting for transcripts...")

            # Wait for a transcript
            # We give it a generous timeout because startup might take a moment
            message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            data = json.loads(message)
            print(f"Received: {data}")

            assert data["type"] == "transcript"
            # We don't assert payload content strictly as it depends on audio source

    except asyncio.TimeoutError:
        pytest.fail("Timed out waiting for transcript from WebSocket")
    except Exception as e:
        pytest.fail(f"WebSocket connection failed: {e}")
    finally:
        await nc.close()

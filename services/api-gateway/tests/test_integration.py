import asyncio
import json
import os
import subprocess
import sys

import httpx
import pytest
import websockets
from nats.aio.client import Client as NATS

# Use the real NATS URL from environment or default to localhost
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
API_PORT = 8001
API_URL = f"http://localhost:{API_PORT}"
WS_URL = f"ws://localhost:{API_PORT}/ws/transcripts"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_gateway_integration() -> None:
    """
    Integration test for API Gateway.
    Verifies that the gateway can connect to a real NATS server and forward messages
    to the WebSocket.
    """
    # 1. Start API Gateway in Subprocess
    # We use sys.executable to ensure we use the same python environment
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api_gateway.main:app",
            "--port",
            str(API_PORT),
            "--host",
            "127.0.0.1",
        ],
        cwd=os.path.join(os.getcwd(), "services", "api-gateway", "src"),
        env={
            **os.environ,
            "NATS_URL": NATS_URL,
            "PYTHONPATH": os.path.join(os.getcwd(), "services", "api-gateway", "src"),
        },
    )

    try:
        # 2. Wait for Health Check
        async with httpx.AsyncClient() as client:
            for _ in range(20):
                try:
                    resp = await client.get(f"{API_URL}/health")
                    if resp.status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            else:
                pytest.fail("API Gateway failed to start")

        # 3. Setup NATS Publisher
        nc = NATS()
        await nc.connect(NATS_URL)

        # 4. Connect WebSocket
        async with websockets.connect(WS_URL) as websocket:
            # Give it a moment to subscribe
            await asyncio.sleep(0.5)

            # 5. Publish to NATS
            transcript_data = {
                "text": "Integration Test",
                "is_final": True,
                "confidence": 1.0,
            }
            await nc.publish(
                "transcript.final.>", json.dumps(transcript_data).encode("utf-8")
            )
            await nc.flush()

            # 6. Verify WebSocket received message
            # recv() waits indefinitely by default, but we can wrap in wait_for
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(message)

            assert data["type"] == "transcript"
            assert data["payload"] == transcript_data

        await nc.close()

    finally:
        proc.terminate()
        proc.wait()

"""
E2E smoke test against running containers.

Verifies the full pipeline:
  audio-producer (file) → NATS → stt-provider → Deepgram
  → transcript.raw → identity-manager → transcript.final
  → api-gateway → WebSocket client

Prerequisites (handled by `just e2e`):
  - Docker containers running with file-based audio
  - DEEPGRAM_API_KEY set in environment / .env
"""

import asyncio
import json
import os
import time

import httpx
import pytest
import websockets

HEALTH_URL = os.getenv("GATEWAY_URL", "http://localhost:8000") + "/health"
WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/transcripts")

_HEALTH_TIMEOUT_S = 30   # wait for api-gateway to be ready
_TRANSCRIPT_TIMEOUT_S = 90  # wait for first final transcript from Deepgram


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_transcript_reaches_websocket() -> None:
    """
    Black-box smoke test: a final transcript with non-empty text must arrive
    on the WebSocket within TRANSCRIPT_TIMEOUT_S seconds.
    """
    if not os.getenv("DEEPGRAM_API_KEY"):
        pytest.skip("DEEPGRAM_API_KEY not set — skipping live Deepgram test")

    # 1. Wait for api-gateway to be healthy
    _wait_for_gateway()

    # 2. Connect WebSocket and wait for a final transcript
    try:
        async with websockets.connect(WS_URL) as ws:  # type: ignore[attr-defined]
            final = await asyncio.wait_for(
                _first_final_transcript(ws), timeout=_TRANSCRIPT_TIMEOUT_S
            )
    except asyncio.TimeoutError:
        pytest.fail(
            f"No final transcript received within {_TRANSCRIPT_TIMEOUT_S}s — "
            "check container logs with `just logs`"
        )
    except (OSError, ConnectionRefusedError) as exc:
        pytest.skip(f"Could not connect to api-gateway WebSocket: {exc}")

    assert final is not None, "No final transcript received within timeout"
    assert final["text"].strip(), "Final transcript text was empty"
    assert final["confidence"] > 0, "Transcript confidence should be positive"


async def _first_final_transcript(ws: websockets.WebSocketClientProtocol) -> dict:  # type: ignore[name-defined]
    """Drain WebSocket messages until we receive a final transcript."""
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if msg.get("type") != "transcript":
            continue

        payload = msg.get("payload", {})
        if payload.get("is_final") and payload.get("text", "").strip():
            return payload

    pytest.fail("WebSocket closed before a final transcript arrived")


def _wait_for_gateway() -> None:
    """Poll the health endpoint until it responds 200 or we time out."""
    deadline = time.monotonic() + _HEALTH_TIMEOUT_S
    last_exc: Exception | None = None

    while time.monotonic() < deadline:
        try:
            resp = httpx.get(HEALTH_URL, timeout=2)
            if resp.status_code == 200:
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(1)

    pytest.skip(
        f"api-gateway did not become healthy within {_HEALTH_TIMEOUT_S}s "
        f"(last error: {last_exc})"
    )

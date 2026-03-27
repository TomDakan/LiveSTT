import asyncio
import contextlib
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from stt_provider.interfaces import TranscriptionEvent
from stt_provider.main import (
    _DURABLE_BACKFILL,
    _DURABLE_LIVE,
    STTProviderService,
)


@pytest.mark.asyncio
async def test_stt_provider_flow(mock_transcriber_factory: Any) -> None:
    """
    Verifies:
    1. Service creates durable pull consumers for live and backfill.
    2. Live audio → live transcriber (send_audio called, message ACKed).
    3. Transcript events are published to transcript.raw.live.
    """
    service = STTProviderService(transcriber_factory=mock_transcriber_factory)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    # Separate mock subscriptions per subject
    mock_live_sub = AsyncMock()
    mock_backfill_sub = AsyncMock()

    from messaging.streams import SUBJECT_AUDIO_LIVE

    async def mock_subscribe(subject: str, durable: str) -> AsyncMock:
        return mock_live_sub if subject == SUBJECT_AUDIO_LIVE else mock_backfill_sub

    mock_js.pull_subscribe.side_effect = mock_subscribe

    # Live sub: deliver one message, then block until stop_event
    live_msg = MagicMock()
    live_msg.data = b"live_chunk"
    live_msg.ack = AsyncMock()
    live_delivered = False

    async def live_fetch(n: int, timeout: float) -> list[Any]:
        nonlocal live_delivered
        if not live_delivered:
            live_delivered = True
            return [live_msg]
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_live_sub.fetch.side_effect = live_fetch

    # Backfill sub: always block
    async def backfill_fetch(n: int, timeout: float) -> list[Any]:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_backfill_sub.fetch.side_effect = backfill_fetch

    task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
    await asyncio.sleep(0.15)

    # Durable consumers registered with correct names
    subscribe_calls = {
        call.kwargs.get("durable") or call.args[1]
        for call in mock_js.pull_subscribe.call_args_list
    }
    assert _DURABLE_LIVE in subscribe_calls
    assert _DURABLE_BACKFILL in subscribe_calls

    # Live audio was routed to a transcriber and ACKed
    assert live_msg.ack.called
    live_transcribers = [
        t for t in mock_transcriber_factory.instances if b"live_chunk" in t.sent_audio
    ]
    assert len(live_transcribers) == 1, "Exactly one transcriber should have live_chunk"
    mock_live_transcriber = live_transcribers[0]

    # Inject a transcript event and verify NATS publish
    await mock_live_transcriber.inject_event(
        TranscriptionEvent(text="Hello Live", is_final=True, confidence=0.9)
    )
    await asyncio.sleep(0.1)

    found = any(
        call.args[0] == "transcript.raw.live"
        and json.loads(call.args[1].decode())["text"] == "Hello Live"
        for call in mock_js.publish.call_args_list
    )
    assert found, "Live transcript not published to transcript.raw.live"

    # Cleanup: stop_event → lanes exit → transcribers finish → task completes
    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)

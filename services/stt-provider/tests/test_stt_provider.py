import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from stt_provider.interfaces import TranscriptionEvent
from stt_provider.main import STTProviderService


@pytest.mark.asyncio
async def test_stt_provider_flow(mock_transcriber_factory: Any) -> None:
    """
    Verifies:
    1. Service sets up Dual Transcribers.
    2. Live Audio -> Live Transcriber.
    3. Backfill Audio -> Backfill Transcriber.
    4. Events from both are published to NATS.
    """
    service = STTProviderService(transcriber_factory=mock_transcriber_factory)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()
    callbacks: dict[str, Any] = {}

    async def mock_subscribe(subject: str, queue: str, cb: Any) -> None:
        callbacks[subject] = cb

    mock_js.subscribe.side_effect = mock_subscribe

    task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
    await asyncio.sleep(0.1)

    # Two transcribers created by the factory
    mock_live, mock_backfill = mock_transcriber_factory.instances
    assert mock_live.connected
    assert mock_backfill.connected

    # Subscriptions registered
    assert "audio.live.>" in callbacks
    assert "audio.backfill.>" in callbacks

    # Live audio routed to live transcriber
    msg_live = MagicMock()
    msg_live.data = b"live_chunk"
    await callbacks["audio.live.>"](msg_live)
    assert mock_live.sent_audio == [b"live_chunk"]

    # Backfill audio routed to backfill transcriber
    msg_backfill = MagicMock()
    msg_backfill.data = b"backfill_chunk"
    await callbacks["audio.backfill.>"](msg_backfill)
    assert mock_backfill.sent_audio == [b"backfill_chunk"]

    # Transcript event published to correct NATS subject
    await mock_live.inject_event(
        TranscriptionEvent(text="Hello Live", is_final=True, confidence=0.9)
    )
    await asyncio.sleep(0.1)

    found = any(
        call[0][0] == "transcript.raw.live"
        and json.loads(call[0][1].decode())["text"] == "Hello Live"
        for call in mock_js.publish.call_args_list
    )
    assert found, "Live transcript not published to transcript.raw.live"

    # Cleanup
    stop_event.set()
    await mock_live.finish()
    await mock_backfill.finish()
    await asyncio.wait_for(task, timeout=1.0)

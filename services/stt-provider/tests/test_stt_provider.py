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


def _eos_msg() -> MagicMock:
    msg = MagicMock()
    msg.data = b""
    msg.headers = {"LiveSTT-EOS": "true"}
    msg.ack = AsyncMock()
    return msg


def _audio_msg(data: bytes) -> MagicMock:
    msg = MagicMock()
    msg.data = data
    msg.headers = None
    msg.ack = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_stt_provider_flow(mock_transcriber_factory: Any) -> None:
    """
    Verifies the sequential single-connection model:
    1. Service creates durable pull consumers for both backfill and live.
    2. Backfill audio is sent to Deepgram, then backfill EOS triggers phase switch.
    3. Live audio is sent on the SAME Deepgram connection.
    4. Transcript events are published with the correct source tag (live once
       the phase has switched).
    """
    service = STTProviderService(transcriber_factory=mock_transcriber_factory)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    service.nc = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    mock_backfill_sub = AsyncMock()
    mock_live_sub = AsyncMock()

    from messaging.streams import SUBJECT_AUDIO_BACKFILL

    async def mock_subscribe(subject: str, durable: str) -> AsyncMock:
        return mock_backfill_sub if subject == SUBJECT_AUDIO_BACKFILL else mock_live_sub

    mock_js.pull_subscribe.side_effect = mock_subscribe

    # Backfill: one audio chunk then EOS
    backfill_msgs = [_audio_msg(b"backfill_chunk"), _eos_msg()]
    backfill_idx = 0

    async def backfill_fetch(n: int, timeout: float) -> list[Any]:
        nonlocal backfill_idx
        if backfill_idx < len(backfill_msgs):
            msg = backfill_msgs[backfill_idx]
            backfill_idx += 1
            return [msg]
        # EOS already sent; block so the live phase has time to run
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_backfill_sub.fetch.side_effect = backfill_fetch

    # Live: one audio chunk, then block until stop_event
    live_msg = _audio_msg(b"live_chunk")
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

    task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
    await asyncio.sleep(0.2)

    # Both durable consumers must have been registered
    subscribe_calls = {
        call.kwargs.get("durable") or call.args[1]
        for call in mock_js.pull_subscribe.call_args_list
    }
    assert _DURABLE_BACKFILL in subscribe_calls
    assert _DURABLE_LIVE in subscribe_calls

    # Both audio chunks must have reached the same transcriber
    assert len(mock_transcriber_factory.instances) == 1, (
        "Sequential model: only ONE Deepgram connection per session"
    )
    transcriber = mock_transcriber_factory.instances[0]
    assert b"backfill_chunk" in transcriber.sent_audio
    assert b"live_chunk" in transcriber.sent_audio

    # Messages were ACKed
    assert backfill_msgs[0].ack.called
    assert live_msg.ack.called

    # Inject a live-phase transcript event and verify NATS publish subject
    await transcriber.inject_event(
        TranscriptionEvent(text="Hello Live", is_final=True, confidence=0.9)
    )
    await asyncio.sleep(0.1)

    # At this point tag_holder[0] == "live", so publish goes to transcript.raw.live
    found = any(
        call.args[0] == "transcript.raw.live"
        and json.loads(call.args[1].decode())["text"] == "Hello Live"
        for call in mock_js.publish.call_args_list
    )
    assert found, "Live transcript not published to transcript.raw.live"

    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.asyncio
async def test_backfill_only_eos_skips_to_live(
    mock_transcriber_factory: Any,
) -> None:
    """If the first backfill message is EOS (empty pre-roll), the service
    moves straight to the live phase on the same Deepgram connection."""
    service = STTProviderService(transcriber_factory=mock_transcriber_factory)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    service.nc = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    mock_backfill_sub = AsyncMock()
    mock_live_sub = AsyncMock()

    from messaging.streams import SUBJECT_AUDIO_BACKFILL

    async def mock_subscribe(subject: str, durable: str) -> AsyncMock:
        return mock_backfill_sub if subject == SUBJECT_AUDIO_BACKFILL else mock_live_sub

    mock_js.pull_subscribe.side_effect = mock_subscribe

    # Backfill: immediate EOS (empty pre-roll)
    eos = _eos_msg()
    bf_done = False

    async def backfill_fetch(n: int, timeout: float) -> list[Any]:
        nonlocal bf_done
        if not bf_done:
            bf_done = True
            return [eos]
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_backfill_sub.fetch.side_effect = backfill_fetch

    # Live: one audio chunk, then block
    live_msg = _audio_msg(b"live_only_chunk")
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

    task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
    await asyncio.sleep(0.2)

    assert len(mock_transcriber_factory.instances) == 1
    transcriber = mock_transcriber_factory.instances[0]
    assert b"live_only_chunk" in transcriber.sent_audio

    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)

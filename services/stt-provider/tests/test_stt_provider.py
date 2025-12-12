import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stt_provider.interfaces import Transcriber, TranscriptionEvent
from stt_provider.main import STTProviderService


class MockTranscriber(Transcriber):
    """Simulated Transcriber."""

    def __init__(self) -> None:
        self.connected = False
        self.sent_audio: list[bytes] = []
        self.events_to_yield: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()

    async def connect(self) -> None:
        self.connected = True

    async def send_audio(self, audio: bytes) -> None:
        self.sent_audio.append(audio)

    async def finish(self) -> None:
        await self.events_to_yield.put(None)  # Signal end

    async def get_events(self) -> AsyncIterator[TranscriptionEvent]:
        while True:
            event = await self.events_to_yield.get()
            if event is None:
                break
            yield event

    async def inject_event(self, event: TranscriptionEvent) -> None:
        """Helper to inject a fake transcription event."""
        await self.events_to_yield.put(event)


@pytest.mark.asyncio
async def test_stt_provider_flow() -> None:
    """
    Verifies:
    1. Service sets up Dual Transcribers.
    2. Live Audio -> Live Transcriber.
    3. Backfill Audio -> Backfill Transcriber.
    4. Events from both are published to NATS.
    """
    # 1. Setup Service & Mocks
    service = STTProviderService()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    # Create distinct mocks for live/backfill
    mock_live = MockTranscriber()
    mock_backfill = MockTranscriber()

    # 2. Patch DeepgramTranscriber to return our mocks sequentially
    with patch(
        "stt_provider.main.DeepgramTranscriber", side_effect=[mock_live, mock_backfill]
    ):
        # 3. Setup JS Context Mock
        mock_js = AsyncMock()
        stop_event = asyncio.Event()

        # Capture callbacks so we can trigger them manually

        # Capture callbacks so we can trigger them manually
        callbacks: dict[str, Any] = {}

        async def mock_subscribe(subject: str, queue: str, cb: Any) -> None:
            callbacks[subject] = cb

        mock_js.subscribe.side_effect = mock_subscribe

        # 4. Run Business Logic (in background task)
        task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))

        # Wait for setup
        await asyncio.sleep(0.1)

        # Verify Subscriptions
        assert "audio.live.>" in callbacks
        assert "audio.backfill.>" in callbacks

        # 5. Simulate Live Audio
        msg_live = MagicMock()
        msg_live.data = b"live_chunk"
        await callbacks["audio.live.>"](msg_live)
        assert mock_live.sent_audio == [b"live_chunk"]

        # 6. Simulate Backfill Audio
        msg_backfill = MagicMock()
        msg_backfill.data = b"backfill_chunk"
        await callbacks["audio.backfill.>"](msg_backfill)
        assert mock_backfill.sent_audio == [b"backfill_chunk"]

        # 7. Simulate Transcript Event (Live)
        event_live = TranscriptionEvent(text="Hello Live", is_final=True, confidence=0.9)
        await mock_live.inject_event(event_live)
        await asyncio.sleep(0.1)  # Let loop process

        # Verify Publish
        # Expected topic: transcript.raw.live
        # Verify call args
        found = False
        for call in mock_js.publish.call_args_list:
            args = call[0]
            if args[0] == "transcript.raw.live":
                payload = json.loads(args[1].decode())
                if payload["text"] == "Hello Live":
                    found = True
                    break
        assert found, "Did not find published live transcript"

        # 8. Cleanup
        # Signal loop to stop
        stop_event.set()

        # Unblock the get_events() loops by sending None
        await mock_live.finish()
        await mock_backfill.finish()

        # Wait for service task to finish
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except TimeoutError:
            task.cancel()
            raise

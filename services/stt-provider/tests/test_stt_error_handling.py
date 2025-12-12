import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stt_provider.interfaces import Transcriber, TranscriptionEvent
from stt_provider.main import STTProviderService


@pytest.mark.asyncio
async def test_stream_verification_failure() -> None:
    """Verify service exits gracefully if stream creation fails."""
    service = STTProviderService()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock(side_effect=Exception("NATS Down"))

    stop_event = asyncio.Event()
    mock_js = AsyncMock()

    # Capture logs
    with patch.object(service.logger, "critical") as mock_log:
        await service.run_business_logic(mock_js, stop_event)
        mock_log.assert_called_with("Stream verification failed: NATS Down")


@pytest.mark.asyncio
async def test_transcriber_connection_failure() -> None:
    """Verify service exits gracefully if Deepgram connection fails."""
    service = STTProviderService()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    # Mock Transcriber to fail connect
    mock_transcriber = AsyncMock(spec=Transcriber)
    mock_transcriber.connect.side_effect = Exception("Deepgram Auth Error")

    with patch("stt_provider.main.DeepgramTranscriber", return_value=mock_transcriber):
        stop_event = asyncio.Event()
        mock_js = AsyncMock()

        with patch.object(service.logger, "critical") as mock_log:
            await service.run_business_logic(mock_js, stop_event)
            mock_log.assert_called_with("Deepgram connection failed: Deepgram Auth Error")


@pytest.mark.asyncio
async def test_publish_failure() -> None:
    """Verify service logs error if NATS publish fails but continues processing."""
    service = STTProviderService()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    # Mock Transcriber to yield one event then finish
    mock_transcriber = AsyncMock(spec=Transcriber)

    # Event Queue for mocking get_events generator
    queue: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()

    event = TranscriptionEvent(text="test", is_final=True, confidence=1.0)
    await queue.put(event)
    # Put enough Nones for both consumers (Live and Backfill) to exit
    await queue.put(None)
    await queue.put(None)

    async def mock_get_events() -> AsyncIterator[TranscriptionEvent]:
        while True:
            evt = await queue.get()
            if evt is None:
                break
            yield evt

    mock_transcriber.get_events = mock_get_events
    mock_transcriber.connect = AsyncMock()
    mock_transcriber.finish = AsyncMock()

    with patch("stt_provider.main.DeepgramTranscriber", return_value=mock_transcriber):
        stop_event = asyncio.Event()
        mock_js = AsyncMock()
        mock_js.subscribe = AsyncMock()
        # Mock publish to fail
        mock_js.publish.side_effect = Exception("Publish Failed")

        with patch.object(service.logger, "error") as mock_log:
            # Run logic
            task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))

            # Wait for task to finish (it should finish when queue is empty)
            await asyncio.wait_for(task, timeout=1.0)

            # Verify error logged
            mock_log.assert_called()
            # Check if any call contains our expected error
            found = False
            for call in mock_log.call_args_list:
                if "Failed to publish" in str(call) and "Publish Failed" in str(call):
                    found = True
                    break
            assert found, "Did not find expected error log"

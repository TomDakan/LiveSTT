import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mock_transcriber import MockTranscriber
from stt_provider.interfaces import TranscriptionEvent
from stt_provider.main import STTProviderService


@pytest.mark.asyncio
async def test_stream_verification_failure() -> None:
    """Service exits gracefully if stream creation fails."""
    service = STTProviderService()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock(side_effect=Exception("NATS Down"))

    with patch.object(service.logger, "critical") as mock_log:
        await service.run_business_logic(AsyncMock(), asyncio.Event())
        mock_log.assert_called_with("Stream verification failed: NATS Down")


@pytest.mark.asyncio
async def test_transcriber_connection_failure_retries() -> None:
    """Service retries Deepgram connection; exits cleanly once stop_event fires."""
    attempt_count = 0

    class AlwaysFailingTranscriber(MockTranscriber):
        async def connect(self, **kwargs: Any) -> None:
            nonlocal attempt_count
            attempt_count += 1
            raise Exception("Auth Error")

    service = STTProviderService(transcriber_factory=AlwaysFailingTranscriber)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    with patch("stt_provider.main._RECONNECT_INITIAL_DELAY_S", 0.01):
        task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
        await asyncio.sleep(0.15)
        assert attempt_count >= 2, "Expected at least 2 connection attempts"
        stop_event.set()
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_transcriber_connection_succeeds_after_failure(
    mock_transcriber_factory: Any,
) -> None:
    """Service connects successfully after an initial failure."""
    attempts = 0

    class FailFirstTranscriber(MockTranscriber):
        async def connect(self, **kwargs: Any) -> None:
            nonlocal attempts
            attempts += 1
            if attempts <= 1:  # first attempt fails
                raise Exception("Temporary Error")
            await super().connect(**kwargs)

    service = STTProviderService(transcriber_factory=FailFirstTranscriber)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    service.nc = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()
    mock_sub = AsyncMock()
    mock_js.pull_subscribe.return_value = mock_sub

    # Return one audio message first (to trigger Deepgram connect),
    # then timeout for all subsequent fetches.
    audio_msg = MagicMock()
    audio_msg.data = b"\x00" * 160
    audio_msg.headers = None
    audio_msg.ack = AsyncMock()
    first_call = True

    async def fetch(n: int, timeout: float) -> list[Any]:
        nonlocal first_call
        if first_call:
            first_call = False
            return [audio_msg]
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_sub.fetch.side_effect = fetch

    with patch("stt_provider.main._RECONNECT_INITIAL_DELAY_S", 0.01):
        task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
        await asyncio.sleep(0.2)

    stop_event.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert attempts > 1, "Expected retries and eventual success"


@pytest.mark.asyncio
async def test_publish_failure(mock_transcriber_factory: Any) -> None:
    """Service logs error if NATS publish fails but continues processing."""
    service = STTProviderService(transcriber_factory=mock_transcriber_factory)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    service.nc = AsyncMock()

    mock_js = AsyncMock()
    mock_js.publish.side_effect = Exception("Publish Failed")
    stop_event = asyncio.Event()
    mock_sub = AsyncMock()
    mock_js.pull_subscribe.return_value = mock_sub

    # Return one audio message first (to trigger Deepgram connect),
    # then timeout for all subsequent fetches.
    audio_msg = MagicMock()
    audio_msg.data = b"\x00" * 160
    audio_msg.headers = None
    audio_msg.ack = AsyncMock()
    first_call = [True]  # single sub now (sequential model)

    async def fetch(n: int, timeout: float) -> list[Any]:
        if first_call and first_call.pop():
            return [audio_msg]
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_sub.fetch.side_effect = fetch

    with patch.object(service.logger, "error") as mock_log:
        task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
        await asyncio.sleep(0.05)

        # Inject event into the single transcriber instance
        first_transcriber = mock_transcriber_factory.instances[0]
        await first_transcriber.inject_event(
            TranscriptionEvent(text="test", is_final=True, confidence=1.0)
        )
        await asyncio.sleep(0.05)

        stop_event.set()
        await asyncio.wait_for(task, timeout=2.0)

    found = any(
        "Failed to publish" in str(call) and "Publish Failed" in str(call)
        for call in mock_log.call_args_list
    )
    assert found, "Did not find expected publish error log"


@pytest.mark.asyncio
async def test_buffer_then_catchup_flow() -> None:
    """After 3 connection failures, the transcriber succeeds and all
    buffered audio is eventually delivered.
    """
    connect_attempts = 0
    sent_chunks: list[bytes] = []

    class FailThreeTimesTranscriber(MockTranscriber):
        async def connect(self, **kwargs: Any) -> None:
            nonlocal connect_attempts
            connect_attempts += 1
            if connect_attempts <= 3:
                raise ConnectionError(f"attempt {connect_attempts}")
            await super().connect(**kwargs)

        async def send_audio(self, audio: bytes) -> None:
            sent_chunks.append(audio)
            await super().send_audio(audio)

    service = STTProviderService(transcriber_factory=FailThreeTimesTranscriber)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    service.nc = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()
    mock_sub = AsyncMock()
    mock_js.pull_subscribe.return_value = mock_sub

    # Pre-buffer 5 audio messages, then an EOS
    buffered_msgs: list[Any] = []
    for i in range(5):
        m = MagicMock()
        m.data = f"chunk-{i}".encode()
        m.headers = None
        m.subject = "audio.backfill.test-session"
        m.ack = AsyncMock()
        buffered_msgs.append(m)

    eos_msg = MagicMock()
    eos_msg.data = b""
    eos_msg.headers = {"LiveSTT-EOS": "true"}
    eos_msg.subject = "audio.backfill.test-session"
    eos_msg.ack = AsyncMock()
    buffered_msgs.append(eos_msg)

    call_idx = 0

    async def fetch(n: int, timeout: float) -> list[Any]:
        nonlocal call_idx
        if call_idx < len(buffered_msgs):
            msg = buffered_msgs[call_idx]
            call_idx += 1
            return [msg]
        # After all messages delivered, wait for stop
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_sub.fetch.side_effect = fetch

    with patch("stt_provider.main._RECONNECT_INITIAL_DELAY_S", 0.01):
        task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
        await asyncio.sleep(1.0)

    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)

    assert connect_attempts == 4, (
        f"Expected 3 failures + 1 success, got {connect_attempts}"
    )
    assert len(sent_chunks) == 5, (
        f"All 5 buffered chunks should be delivered, got {len(sent_chunks)}"
    )


@pytest.mark.asyncio
async def test_finish_exception_does_not_hang_run_lane() -> None:
    """_run_session_loop must complete even if finish() raises and drain_task stalls."""

    class FinishRaisingTranscriber(MockTranscriber):
        async def finish(self) -> None:
            # Raise without putting None into the queue — _on_close never fires.
            raise RuntimeError("finish boom")

    service = STTProviderService(transcriber_factory=FinishRaisingTranscriber)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    service.nc = AsyncMock()

    mock_js = AsyncMock()
    stop_event = asyncio.Event()
    mock_sub = AsyncMock()
    mock_js.pull_subscribe.return_value = mock_sub

    # Return one audio message first (to trigger Deepgram connect),
    # then timeout for all subsequent fetches.
    audio_msg = MagicMock()
    audio_msg.data = b"\x00" * 160
    audio_msg.headers = None
    audio_msg.ack = AsyncMock()
    first_call = [True]  # single sub now (sequential model)

    async def fetch(n: int, timeout: float) -> list[Any]:
        if first_call and first_call.pop():
            return [audio_msg]
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        raise TimeoutError

    mock_sub.fetch.side_effect = fetch

    # Use a very short drain timeout so the test does not take 5 seconds.
    with patch("stt_provider.main._DRAIN_TIMEOUT_S", 0.1):
        task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
        await asyncio.sleep(0.05)
        stop_event.set()
        # Must complete well within the patched drain timeout + margin.
        await asyncio.wait_for(task, timeout=1.0)

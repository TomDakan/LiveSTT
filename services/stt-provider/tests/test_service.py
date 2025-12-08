import asyncio
import json

import pytest
from messaging.nats import MockNatsClient
from stt_provider.interfaces import TranscriptionEvent
from stt_provider.service import STTService

from .mocks import MockTranscriber


@pytest.mark.asyncio
async def test_stt_service_flow() -> None:
    """
    Verifies the full flow:
    1. Audio message received via NATS.
    2. Sent to Transcriber.
    3. Transcriber yields event.
    4. Service publishes event to NATS.
    """
    # TODO: 1. Setup Mocks and Service
    # Hint: Instantiate MockNatsClient, MockTranscriber, and STTService
    nats = MockNatsClient()
    transcriber = MockTranscriber()
    service = STTService(nats, transcriber)

    # TODO: 2. Start Service (in background)
    # Hint: Use asyncio.create_task(service.start())
    service_task = asyncio.create_task(service.start())  # noqa: RUF006, F841  # pyright: ignore[reportUnusedVariable]
    # Hint: Wait a bit for it to be "connected" (mock property)
    await asyncio.sleep(0.1)

    # TODO: 3. Simulate Audio Input
    # Hint: Use nats.trigger_message("audio.raw", b"...")
    await nats.trigger_message("audio.raw", b"...")
    # TODO: 4. Verify sent to transcriber
    # Hint: Check transcriber.sent_audio list
    assert len(transcriber.sent_audio) == 1

    # TODO: 5. Simulate Transcript Event
    # Hint: Create a TranscriptionEvent and use transcriber.inject_event()
    event = TranscriptionEvent(
        text="test",
        is_final=True,
        confidence=1.0,
    )
    await transcriber.inject_event(event)
    await asyncio.sleep(0.1)

    # TODO: 6. Verify output published to NATS
    # Hint: Check nats.published_messages list
    # Hint: Verify subject is "text.transcript" and payload is valid JSON
    assert len(nats.published_messages) == 1
    assert nats.published_messages[0]["subject"] == "text.transcript"
    assert nats.published_messages[0]["data"] == json.dumps(
        {
            "text": "test",
            "is_final": True,
            "confidence": 1.0,
        }
    ).encode("utf-8")

    # TODO: 7. Cleanup
    # Hint: await service.stop()
    await service.stop()

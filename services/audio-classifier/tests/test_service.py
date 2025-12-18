import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from audio_classifier.main import AudioClassifierService
from messaging.streams import SUBJECT_AUDIO_LIVE, CLASSIFICATION_STREAM_CONFIG

@pytest.fixture
def service():
    svc = AudioClassifierService()
    svc.nats_manager = MagicMock()
    svc.nats_manager.connect = AsyncMock(return_value=(MagicMock(), MagicMock()))
    svc.nats_manager.ensure_stream = AsyncMock()
    svc.js = AsyncMock()
    return svc

def test_run_business_logic(service):
    asyncio.run(_async_test_run_business_logic(service))

async def _async_test_run_business_logic(service):
    stop_event = asyncio.Event()
    js_mock = AsyncMock()

    # Task to stop event after short delay
    async def stop_later():
        await asyncio.sleep(0.1)
        stop_event.set()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(stop_later())
        tg.create_task(service.run_business_logic(js_mock, stop_event))

    # Verify stream ensured
    service.nats_manager.ensure_stream.assert_called_once()

    # Verify subscription
    js_mock.subscribe.assert_called_once_with(
        subject=SUBJECT_AUDIO_LIVE,
        queue="audio-classifier-group",
        cb=service._handle_audio
    )

from audio_classifier.interfaces import ClassificationResult

def test_handle_audio(service):
    asyncio.run(_async_test_handle_audio(service))

async def _async_test_handle_audio(service):
    msg = MagicMock()
    msg.data = b"fake_audio_data"

    # Mock classifier to avoid OpenVINO/Stub behavior affecting this test
    service.classifier = MagicMock()
    service.classifier.classify.return_value = ClassificationResult(
        label="test_label",
        confidence=0.5,
        timestamp=12345.0
    )

    await service._handle_audio(msg)

    # Verify processing
    service.classifier.classify.assert_called_once_with(b"fake_audio_data")

    # Verify publish
    service.js.publish.assert_called_once()
    call_args = service.js.publish.call_args
    assert call_args[0][0] == "classification.live"
    assert b"test_label" in call_args[0][1]

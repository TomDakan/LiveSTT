import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from audio_producer.audiosource import FileSource
from audio_producer.main import AudioProducerService

from tests.mocks import MockAudioSource


@pytest.mark.asyncio
async def test_get_audio_source_file_override(monkeypatch):
    """Verify FileSource is selected when AUDIO_FILE is set."""
    monkeypatch.setenv("AUDIO_FILE", "test.wav")
    service = AudioProducerService()
    # Mock nats_manager so ensure_stream doesn't fail
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    source = service._get_audio_source()
    assert isinstance(source, FileSource)
    assert source.file_path == "test.wav"


@pytest.mark.asyncio
async def test_run_business_logic_preroll():
    """Verify audio chunks are published to preroll.audio by default."""
    # Setup
    service = AudioProducerService()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    # Mock the internal _get_audio_source to return our controlled MockSource
    mock_source = MockAudioSource(limit=3, chunk_size=10)
    service._get_audio_source = MagicMock(return_value=mock_source)  # type: ignore

    # Mock JS context
    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    # Run
    await service.run_business_logic(mock_js, stop_event)

    # Verify
    # Should have called publish 3 times to "preroll.audio"
    assert mock_js.publish.call_count == 3

    # Check arguments of first call
    args, _ = mock_js.publish.call_args_list[0]
    assert args[0] == "preroll.audio"
    assert args[1] == b"\x00" * 10


@pytest.mark.asyncio
async def test_run_business_logic_live():
    """Verify audio chunks are published to audio.live.{session_id} when active."""
    # Setup
    service = AudioProducerService()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    service.is_active = True
    service.session_id = "test-session-123"

    mock_source = MockAudioSource(limit=1)
    service._get_audio_source = MagicMock(return_value=mock_source)  # type: ignore

    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    # Run
    await service.run_business_logic(mock_js, stop_event)

    # Verify
    mock_js.publish.assert_called_with("audio.live.test-session-123", b"\x00" * 1600)

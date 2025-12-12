import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deepgram.core.events import EventType
from stt_provider.deepgram_adapter import DeepgramTranscriber


@pytest.mark.asyncio
async def test_deepgram_adapter_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test connection establishment."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test_key")

    mock_client_cls = MagicMock()
    mock_client_instance = MagicMock()
    mock_listen_v1 = MagicMock()
    mock_connect_cm = AsyncMock()
    mock_connection = AsyncMock()

    # Mock chain: Client -> listen.v1 -> connect() -> AsyncContextManager -> Connection
    mock_client_cls.return_value = mock_client_instance
    mock_client_instance.listen.v1 = mock_listen_v1
    mock_listen_v1.connect.return_value = mock_connect_cm
    mock_connect_cm.__aenter__.return_value = mock_connection
    # .on is synchronous in the SDK (registering callbacks)
    mock_connection.on = MagicMock()

    with patch("stt_provider.deepgram_adapter.AsyncDeepgramClient", mock_client_cls):
        adapter = DeepgramTranscriber()
        await adapter.connect()

        # Verify connect called with correct options
        mock_listen_v1.connect.assert_called()
        call_kwargs = mock_listen_v1.connect.call_args.kwargs
        assert call_kwargs["model"] == "nova-3"
        assert call_kwargs["encoding"] == "linear16"

        # Verify event handlers registered
        assert mock_connection.on.call_count >= 4
        # Check specific events
        events_registered = [args[0] for args, _ in mock_connection.on.call_args_list]
        assert EventType.OPEN in events_registered
        assert EventType.MESSAGE in events_registered
        assert EventType.CLOSE in events_registered
        assert EventType.ERROR in events_registered


@pytest.mark.asyncio
async def test_deepgram_adapter_send_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test_key")

    with patch("stt_provider.deepgram_adapter.AsyncDeepgramClient"):
        adapter = DeepgramTranscriber()
        adapter.connection = AsyncMock()

        await adapter.send_audio(b"fake_audio")

        adapter.connection.send_media.assert_called()
        # deepgram-sdk types are hard to mock exactly without importing them,
        # but we check the method was called.


@pytest.mark.asyncio
async def test_deepgram_adapter_receive_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test_key")

    with patch("stt_provider.deepgram_adapter.AsyncDeepgramClient"):
        adapter = DeepgramTranscriber()
        # Initialize queue
        adapter._event_queue = asyncio.Queue()

        # Simulate Message
        mock_result = MagicMock()
        mock_result.channel.alternatives = [
            MagicMock(transcript="Hello", confidence=0.99)
        ]
        mock_result.is_final = True

        await adapter._on_message(mock_result)

        event = await adapter._event_queue.get()
        assert event is not None
        assert event.text == "Hello"
        assert event.is_final is True
        assert event.confidence == 0.99

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stt_provider.interfaces import Transcriber, TranscriptionEvent
from stt_provider.main import STTProviderService

from .mock_transcriber import MockTranscriber


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
async def test_transcriber_connection_failure() -> None:
    """Service exits gracefully if transcriber connection fails."""

    class FailingTranscriber(MockTranscriber):
        async def connect(self, **kwargs: Any) -> None:
            raise Exception("Auth Error")

    service = STTProviderService(transcriber_factory=FailingTranscriber)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    with patch.object(service.logger, "critical") as mock_log:
        await service.run_business_logic(AsyncMock(), asyncio.Event())
        mock_log.assert_called_with("Deepgram connection failed: Auth Error")


@pytest.mark.asyncio
async def test_publish_failure(mock_transcriber_factory: Any) -> None:
    """Service logs error if NATS publish fails but continues processing."""
    service = STTProviderService(transcriber_factory=mock_transcriber_factory)
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()

    mock_js = AsyncMock()
    mock_js.subscribe = AsyncMock()
    mock_js.publish.side_effect = Exception("Publish Failed")

    with patch.object(service.logger, "error") as mock_log:
        task = asyncio.create_task(
            service.run_business_logic(mock_js, asyncio.Event())
        )
        await asyncio.sleep(0.1)

        mock_live, mock_backfill = mock_transcriber_factory.instances
        await mock_live.inject_event(
            TranscriptionEvent(text="test", is_final=True, confidence=1.0)
        )
        await asyncio.sleep(0.1)
        await mock_live.finish()
        await mock_backfill.finish()
        await asyncio.wait_for(task, timeout=1.0)

    found = any(
        "Failed to publish" in str(call) and "Publish Failed" in str(call)
        for call in mock_log.call_args_list
    )
    assert found, "Did not find expected publish error log"

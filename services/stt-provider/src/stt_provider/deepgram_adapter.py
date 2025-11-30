import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from deepgram import AsyncDeepgramClient, DeepgramClientOptions
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import ListenV2ControlMessage, ListenV2MediaMessage

from .interfaces import Transcriber, TranscriptionEvent

logger = logging.getLogger(__name__)

class DeepgramTranscriber(Transcriber):
    """
    Implementation of Transcriber using Deepgram SDK v5 Async Client (WebSocket) Listen V2.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY is required")

        config = DeepgramClientOptions(verbose=logging.WARNING)
        self.client = AsyncDeepgramClient(self.api_key, config)
        self.connection: Any = None
        self._event_queue: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()

    async def connect(self) -> None:
        """Establishes WebSocket connection to Deepgram."""

        self.connection = self.client.listen.v2.connect(
            model="nova-3",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            sample_rate=16000,
            interim_results=True,
        )
        await self.connection.__aenter__()

        self.connection.on(EventType.OPEN, self._on_open)
        self.connection.on(EventType.MESSAGE, self._on_message)
        self.connection.on(EventType.CLOSE, self._on_close)
        self.connection.on(EventType.ERROR, self._on_error)

    async def _on_open(self, *args: Any, **kwargs: Any) -> None:
        logger.info("Deepgram Connection Opened")

    async def _on_message(self, result: Any, **kwargs: Any) -> None:
        if not hasattr(result, "channel"):
            return

        alternatives = result.channel.alternatives
        if not alternatives:
            return

        transcript = alternatives[0].transcript
        if not transcript and not result.is_final:
            return

        event = TranscriptionEvent(
            text=transcript,
            is_final=result.is_final,
            confidence=alternatives[0].confidence,
        )
        await self._event_queue.put(event)

    async def _on_close(self, *args: Any, **kwargs: Any) -> None:
        logger.info("Deepgram Connection Closed")
        await self._event_queue.put(None) # Signal end of stream

    async def _on_error(self, error: Any, **kwargs: Any) -> None:
        logger.error(f"Deepgram Error: {error}")

    async def send_audio(self, audio: bytes) -> None:
        if self.connection:
            await self.connection.send_media(ListenV2MediaMessage())

    async def finish(self) -> None:
        if self.connection:
            await self.connection.send_control(ListenV2ControlMessage(type="CloseStream"))
            await self.connection.__aexit__(None, None, None)
            self.connection = None

    async def get_events(self) -> AsyncIterator[TranscriptionEvent]:
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
            yield event

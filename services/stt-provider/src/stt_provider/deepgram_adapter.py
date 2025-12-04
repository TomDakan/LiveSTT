import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import ListenV1ControlMessage, ListenV1MediaMessage

from .interfaces import Transcriber, TranscriptionEvent

logger = logging.getLogger(__name__)


class DeepgramTranscriber(Transcriber):
    """
    Implementation of Transcriber using Deepgram SDK
    v3 Async Client (WebSocket) Listen V1.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY is required")

        self.client = AsyncDeepgramClient(api_key=self.api_key)
        self.connection: Any = None
        self._connection_cm: Any = None
        self._listening_task: asyncio.Task[Any] | None = None
        self._event_queue: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()

    async def connect(self) -> None:
        """Establishes WebSocket connection to Deepgram."""
        # Using listen.v1 for standard transcription with Nova-3
        options = {
            "model": "nova-3",
            "language": "en-US",
            "smart_format": True,
            "encoding": "linear16",
            "sample_rate": 16000,
            "interim_results": True,
        }

        self._connection_cm = self.client.listen.v1.connect(**options)
        self.connection = await self._connection_cm.__aenter__()

        self.connection.on(EventType.OPEN, self._on_open)
        self.connection.on(EventType.MESSAGE, self._on_message)
        self.connection.on(EventType.CLOSE, self._on_close)
        self.connection.on(EventType.ERROR, self._on_error)

        # Start listening loop
        if hasattr(self.connection, "start_listening"):
            self._listening_task = asyncio.create_task(self.connection.start_listening())
        elif hasattr(self.connection, "start"):
            self._listening_task = asyncio.create_task(self.connection.start())

    async def _on_open(self, *args: Any, **kwargs: Any) -> None:
        logger.info("Deepgram Connection Opened")

    async def _on_message(self, result: Any, **kwargs: Any) -> None:
        # v1 message structure
        if not hasattr(result, "channel"):
            return

        alternatives = result.channel.alternatives
        if not alternatives:
            return

        transcript = alternatives[0].transcript
        if not transcript and not getattr(result, "is_final", False):
            return

        event = TranscriptionEvent(
            text=transcript,
            is_final=getattr(result, "is_final", False),
            confidence=alternatives[0].confidence,
        )
        await self._event_queue.put(event)

    async def _on_close(self, *args: Any, **kwargs: Any) -> None:
        logger.info("Deepgram Connection Closed")
        await self._event_queue.put(None)

    async def _on_error(self, error: Any, **kwargs: Any) -> None:
        logger.error(f"Deepgram Error: {error}")

    async def send_audio(self, audio: bytes) -> None:
        if self.connection:
            await self.connection.send_media(ListenV1MediaMessage(audio))

    async def finish(self) -> None:
        if self.connection:
            await self.connection.send_control(ListenV1ControlMessage(type="Finalize"))
            await self._connection_cm.__aexit__(None, None, None)
            self.connection = None

    async def get_events(self) -> AsyncIterator[TranscriptionEvent]:
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
            yield event

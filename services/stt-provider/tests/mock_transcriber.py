import asyncio
from collections.abc import AsyncIterator
from typing import Any

from stt_provider.interfaces import Transcriber, TranscriptionEvent


class MockTranscriber(Transcriber):
    """In-process mock transcriber for integration tests.

    Implements the Transcriber protocol without hitting Deepgram.
    Use inject_event() to push canned TranscriptionEvents, or enable
    auto_respond to get a single interim + final event per audio chunk.
    """

    def __init__(self, auto_respond: bool = False) -> None:
        self.connected = False
        self.finalized = False
        self.finished = False
        self.sent_audio: list[bytes] = []
        self._queue: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()
        self._auto_respond = auto_respond
        self._chunk_count = 0

    async def connect(self, **kwargs: Any) -> None:
        self.connected = True

    async def send_audio(self, audio: bytes) -> None:
        self.sent_audio.append(audio)
        if self._auto_respond:
            self._chunk_count += 1
            # Emit an interim then a final event every 5 chunks
            await self._queue.put(
                TranscriptionEvent(
                    text=f"chunk {self._chunk_count}",
                    is_final=False,
                    confidence=0.8,
                )
            )
            if self._chunk_count % 5 == 0:
                await self._queue.put(
                    TranscriptionEvent(
                        text=f"sentence {self._chunk_count // 5}",
                        is_final=True,
                        confidence=0.95,
                    )
                )

    async def finalize(self) -> None:
        self.finalized = True
        # Emit a final event to signal the flush, like Deepgram would
        await self._queue.put(
            TranscriptionEvent(
                text="",
                is_final=True,
                confidence=0.0,
            )
        )

    async def finish(self) -> None:
        self.finished = True
        await self._queue.put(None)

    async def get_events(self) -> AsyncIterator[TranscriptionEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    async def inject_event(self, event: TranscriptionEvent) -> None:
        """Push a specific event into the stream."""
        await self._queue.put(event)

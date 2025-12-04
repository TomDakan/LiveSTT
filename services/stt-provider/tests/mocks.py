import asyncio
from collections.abc import AsyncIterator

from stt_provider.interfaces import Transcriber, TranscriptionEvent


class MockTranscriber(Transcriber):
    """Simulated Transcriber."""

    def __init__(self) -> None:
        self.connected = False
        self.sent_audio: list[bytes] = []
        self.events_to_yield: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()

    async def connect(self) -> None:
        self.connected = True

    async def send_audio(self, audio: bytes) -> None:
        self.sent_audio.append(audio)

    async def finish(self) -> None:
        await self.events_to_yield.put(None)  # Signal end

    async def get_events(self) -> AsyncIterator[TranscriptionEvent]:
        while True:
            event = await self.events_to_yield.get()
            if event is None:
                break
            yield event

    async def inject_event(self, event: TranscriptionEvent) -> None:
        """Helper to inject a fake transcription event."""
        await self.events_to_yield.put(event)

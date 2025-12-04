from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class TranscriptionEvent:
    """Represents a single transcription result."""

    text: str
    is_final: bool
    confidence: float


@runtime_checkable
class Transcriber(Protocol):
    """Interface for a Speech-to-Text engine."""

    async def connect(self) -> None:
        """Establishes connection to the STT provider."""
        ...

    async def send_audio(self, audio: bytes) -> None:
        """Sends a chunk of audio for transcription."""
        ...

    async def finish(self) -> None:
        """Signals end of stream."""
        ...

    def get_events(self) -> AsyncIterator[TranscriptionEvent]:
        """Yields transcription events as they arrive."""
        ...

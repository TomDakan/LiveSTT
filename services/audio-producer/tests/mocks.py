import asyncio
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

from audio_producer.interfaces import AudioSource


class MockAudioSource(
    AudioSource,
):
    """Simulates an audio source for testing."""

    def __init__(
        self, sample_rate: int = 16000, chunk_size: int = 1600, limit: int | None = None
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.limit = limit

    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes."""
        count = 0
        while self.limit is None or count < self.limit:
            delay = self.chunk_size / self.sample_rate
            yield b"\x00" * self.chunk_size
            await asyncio.sleep(delay)
            count += 1

    async def __aenter__(self) -> Self:
        """Enter the runtime context related to this object."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the runtime context related to this object."""
        pass

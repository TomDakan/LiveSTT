import asyncio
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

from interfaces import AudioSource


class WindowsSource(AudioSource):
    """Audio source for Windows."""

    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1600) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes."""
        delay = self.chunk_size / self.sample_rate
        while True:
            yield b"\x00" * self.chunk_size
            await asyncio.sleep(delay)

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


class LinuxSource(AudioSource):
    """Audio source for Linux."""

    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1600) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes."""
        delay = self.chunk_size / self.sample_rate
        while True:
            yield b"\x00" * self.chunk_size
            await asyncio.sleep(delay)

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

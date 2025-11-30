import asyncio
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

try:
    import alsaaudio
except ImportError:
    alsaaudio = None

try:
    import pyaudio
except ImportError:
    pyaudio = None
from .interfaces import AudioSource


class WindowsSource(AudioSource):
    """Audio source for Windows."""

    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1600) -> None:
        self.pyaudio = pyaudio.PyAudio()
        self.stream_obj = self.pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size,
        )
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate

    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes."""
        while True:
            data = await asyncio.to_thread(
                self.stream_obj.read, self.chunk_size, exception_on_overflow=False
            )
            yield data

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

    def __init__(self, sample_rate: int, chunk_size: int) -> None:
        self.inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL)
        self.inp.setchannels(1)
        self.inp.setrate(sample_rate)
        self.inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        self.inp.setperiodsize(chunk_size)
        self.chunk_size = chunk_size

    async def stream(self) -> AsyncIterator[bytes]:
        while True:
            length, data = await asyncio.to_thread(self.inp.read)
            if length > 0:
                yield data

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

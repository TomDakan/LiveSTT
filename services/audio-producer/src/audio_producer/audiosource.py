import asyncio
from collections.abc import AsyncIterator
from types import TracebackType
from typing import TYPE_CHECKING, Self, override

if TYPE_CHECKING:
    import alsaaudio as _alsaaudio  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    import pyaudio as _pyaudio  # type: ignore[import-untyped]  # pyright: ignore[reportMissingImports]
else:
    # Platform specific imports
    try:
        import alsaaudio as _alsaaudio
    except ImportError:
        _alsaaudio = None

    try:
        import pyaudio as _pyaudio
    except ImportError:
        _pyaudio = None
import wave

from .interfaces import AudioSource


class FileSource(AudioSource):
    """Audio source that reads from a WAV file."""

    file_path: str
    chunk_size: int
    loop: bool
    wf: wave.Wave_read

    def __init__(
        self, file_path: str, chunk_size: int = 1600, loop: bool = False
    ) -> None:
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.loop = loop

    @override
    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes from the file."""
        while True:
            data = self.wf.readframes(self.chunk_size)
            if not data:
                if self.loop:
                    self.wf.rewind()
                    continue
                break
            yield data
            # Simulate real-time streaming
            await asyncio.sleep(self.chunk_size / 16000)

    @override
    async def __aenter__(self) -> Self:
        self.wf = wave.open(self.file_path, "rb")  # noqa: SIM115
        if self.wf.getnchannels() != 1:
            raise ValueError("Audio file must be mono")
        if self.wf.getsampwidth() != 2:
            raise ValueError("Audio file must be 16-bit PCM")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.wf.close()


if _pyaudio:

    class WindowsSource(AudioSource):
        """Audio source for Windows."""

        pyaudio_instance: _pyaudio.PyAudio
        stream_obj: _pyaudio.Stream
        chunk_size: int
        sample_rate: int

        def __init__(self, sample_rate: int = 16000, chunk_size: int = 1600) -> None:
            self.pyaudio_instance = _pyaudio.PyAudio()
            self.stream_obj = self.pyaudio_instance.open(
                format=_pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size,
            )
            self.chunk_size = chunk_size
            self.sample_rate = sample_rate

        @override
        async def stream(self) -> AsyncIterator[bytes]:
            """Yields chunks of raw PCM audio bytes."""
            while True:
                data = await asyncio.to_thread(
                    self.stream_obj.read, self.chunk_size, exception_on_overflow=False
                )
                yield data

        @override
        async def __aenter__(self) -> Self:
            """Enter the runtime context related to this object."""
            return self

        @override
        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> None:
            """Exit the runtime context related to this object."""
            pass


if _alsaaudio:

    class LinuxSource(AudioSource):
        """Audio source for Linux."""

        def __init__(self, sample_rate: int, chunk_size: int) -> None:
            self.inp = _alsaaudio.PCM(_alsaaudio.PCM_CAPTURE, _alsaaudio.PCM_NORMAL)
            self.inp.setchannels(1)
            self.inp.setrate(sample_rate)
            self.inp.setformat(_alsaaudio.PCM_FORMAT_S16_LE)
            self.inp.setperiodsize(chunk_size)
            self.chunk_size = chunk_size

        @override
        async def stream(self) -> AsyncIterator[bytes]:
            while True:
                length, data = await asyncio.to_thread(self.inp.read)
                if length > 0:
                    yield data

        @override
        async def __aenter__(self) -> Self:
            """Enter the runtime context related to this object."""
            return self

        @override
        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> None:
            """Exit the runtime context related to this object."""
            pass

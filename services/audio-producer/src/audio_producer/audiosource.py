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
import logging
import wave

from .interfaces import AudioSource

_logger = logging.getLogger(__name__)


class FileSource(AudioSource):
    """Audio source that reads from a WAV file."""

    file_path: str
    chunk_size: int
    loop: bool
    wf: wave.Wave_read

    def __init__(
        self, file_path: str, chunk_size: int = 1536, loop: bool = False
    ) -> None:
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.loop = loop
        self.running = True

    @override
    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes from the file."""
        while self.running:
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
        self.running = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.running = False
        self.wf.close()


if _pyaudio:

    class WindowsSource(AudioSource):
        """Audio source for Windows."""

        pyaudio_instance: _pyaudio.PyAudio
        stream_obj: _pyaudio.Stream
        chunk_size: int
        sample_rate: int

        def __init__(self, sample_rate: int = 16000, chunk_size: int = 1536) -> None:
            self.chunk_size = chunk_size
            self.sample_rate = sample_rate
            self.running = True

        @override
        async def stream(self) -> AsyncIterator[bytes]:
            """Yields chunks of raw PCM audio bytes."""
            while self.running:
                try:
                    data = await asyncio.to_thread(
                        self.stream_obj.read,
                        self.chunk_size,
                        exception_on_overflow=False,
                    )
                    yield data
                except OSError as e:
                    _logger.error("Error reading from audio device: %s", e)
                    break

        @override
        async def __aenter__(self) -> Self:
            """Enter the runtime context related to this object."""
            self.pyaudio_instance = _pyaudio.PyAudio()
            self.stream_obj = self.pyaudio_instance.open(
                format=_pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
            )
            self.running = True
            return self

        @override
        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> None:
            """Exit the runtime context related to this object."""
            self.running = False
            self.stream_obj.stop_stream()
            self.stream_obj.close()
            self.pyaudio_instance.terminate()


if _alsaaudio:

    class LinuxSource(AudioSource):
        """Audio source for Linux."""

        def __init__(self, sample_rate: int, chunk_size: int) -> None:
            self.sample_rate = sample_rate
            self.chunk_size = chunk_size
            self.running = True

        @override
        async def stream(self) -> AsyncIterator[bytes]:
            while self.running:
                try:
                    length, data = await asyncio.to_thread(self.inp.read)
                    if length > 0:
                        yield data
                    elif length < 0:
                        _logger.error("ALSA Error: %s", length)
                        break
                except OSError as e:
                    _logger.error("Error reading from ALSA device: %s", e)
                    break

        @override
        async def __aenter__(self) -> Self:
            """Enter the runtime context related to this object."""
            self.inp = _alsaaudio.PCM(_alsaaudio.PCM_CAPTURE, _alsaaudio.PCM_NORMAL)
            self.inp.setchannels(1)
            self.inp.setrate(self.sample_rate)
            self.inp.setformat(_alsaaudio.PCM_FORMAT_S16_LE)
            self.inp.setperiodsize(self.chunk_size)
            self.running = True
            return self

        @override
        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> None:
            """Exit the runtime context related to this object."""
            self.running = False
            if hasattr(self.inp, "close"):
                self.inp.close()
            elif hasattr(self.inp, "stop"):
                self.inp.stop()
            else:
                # Fallback if no explicit close method is exposed.
                # Explicit deletion can trigger C-extension cleanup if implemented.
                pass

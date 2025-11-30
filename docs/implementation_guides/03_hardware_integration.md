# Implementation Guide: Hardware Integration

## Objective
Implement the concrete `AudioSource` classes for Windows and Linux to capture real microphone audio.

## 1. Dependencies
We need platform-specific libraries to access the audio hardware.

*   **Windows**: `pyaudio` (PortAudio wrapper).
*   **Linux**: `pyalsaaudio` (ALSA wrapper, works with PipeWire via ALSA plugin).

### `pyproject.toml` Updates
```toml
dependencies = [
    "nats-py>=2.6.0",
    "pyalsaaudio>=0.10.0; sys_platform == 'linux'",
    "pyaudio>=0.2.14; sys_platform == 'win32'",
    "numpy>=1.26.0",
]
```

## 2. `WindowsSource` (PyAudio)
Uses `pyaudio` to open a blocking stream and read chunks.

### Implementation Details
*   **Init**: Initialize `PyAudio`, open stream (Format=Int16, Channels=1, Rate=16000).
*   **Stream**: Loop `stream.read(chunk_size)`.
*   **Cleanup**: Close stream, terminate PyAudio.
*   **Blocking I/O**: `pyaudio` is blocking. We should run the read in a separate thread or use `asyncio.to_thread` to avoid blocking the asyncio event loop.

```python
import pyaudio
import asyncio

class WindowsSource(AudioSource):
    def __init__(self, sample_rate: int, chunk_size: int):
        self.pa = pyaudio.PyAudio()
        self.stream_obj = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size
        )
        self.chunk_size = chunk_size

    async def stream(self) -> AsyncIterator[bytes]:
        while True:
            # Run blocking read in thread
            data = await asyncio.to_thread(
                self.stream_obj.read, self.chunk_size, exception_on_overflow=False
            )
            yield data
```

## 3. `LinuxSource` (PyAlsaAudio)
Uses `alsaaudio` to read from the default capture device (which PipeWire emulates).

### Implementation Details
*   **Init**: `alsaaudio.PCM(type=alsaaudio.PCM_CAPTURE, mode=alsaaudio.PCM_NORMAL)`.
*   **Config**: Set channels, rate, format, period size.
*   **Stream**: `l, data = inp.read()`.
*   **Blocking I/O**: Similar to PyAudio, use `asyncio.to_thread`.

```python
import alsaaudio
import asyncio

class LinuxSource(AudioSource):
    def __init__(self, sample_rate: int, chunk_size: int):
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
```

## 4. Testing
Since we cannot easily mock hardware in unit tests, we will rely on:
1.  **Manual Verification**: Running the service on the actual OS.
2.  **Mock Tests**: We already have `MockAudioSource` for logic testing.

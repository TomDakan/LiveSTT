import asyncio
import contextlib
import os
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from audiosource import AudioSource, LinuxSource, WindowsSource
from interfaces import NatsClient
from nats.aio.client import Client as NATS


@runtime_checkable
class AudioPublisher(Protocol):
    """Interface for an audio source."""

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


@dataclass
class NatsAudioPublisher(AudioPublisher):
    """Orchestrates audio streaming from source to NATS."""

    source: AudioSource
    nats: NatsClient
    subject: str = "audio.raw"

    async def start(self) -> None:
        """Consumes audio from source and publishes to NATS."""
        async with self.source as stream_source:
            async for chunk in stream_source.stream():
                await self.nats.publish(self.subject, chunk)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the runtime context related to this object."""
        await self.nats.close()


async def main() -> None:
    """Application entrypoint."""
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    sample_rate = int(os.getenv("SAMPLE_RATE", 16000))
    chunk_size = int(os.getenv("CHUNK_SIZE", 1600))

    nats = NATS()
    await nats.connect(nats_url)

    source: AudioSource
    match os.getenv("OS"):
        case "Windows":
            source = WindowsSource(sample_rate, chunk_size)
        case "Linux":
            source = LinuxSource(sample_rate, chunk_size)
        case _:
            raise ValueError("Unsupported OS")

    publisher = NatsAudioPublisher(source=source, nats=nats)
    await publisher.start()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())

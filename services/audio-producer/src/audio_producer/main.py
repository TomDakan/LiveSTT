import asyncio
import contextlib
import os
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from messaging.nats import NatsClient
from nats.aio.client import Client as NATS

from .interfaces import AudioSource


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

    chunk_size = int(os.getenv("CHUNK_SIZE", 1600))

    nats = NATS()
    await nats.connect(nats_url)

    audio_file = os.getenv("AUDIO_FILE")

    source: AudioSource
    if audio_file:
        print(f"Using FileSource: {audio_file}")
        from .audiosource import FileSource

        source = FileSource(audio_file, chunk_size, loop=True)
    else:
        raise ValueError("AUDIO_FILE environment variable is required")

    publisher = NatsAudioPublisher(source=source, nats=nats)
    await publisher.start()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())

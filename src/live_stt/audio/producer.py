from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioSource(Protocol):
    """Interface for an audio source."""

    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes."""
        ...


class MockAudioSource:
    """Simulates an audio source for testing."""

    # TODO: Implement this class
    pass

from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any, Protocol, Self, runtime_checkable


@runtime_checkable
class NatsClient(Protocol):
    async def publish(self, subject: str, payload: bytes) -> None: ...
    async def connect(self, servers: list[str] | str, **kwargs: Any) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class AudioSource(Protocol):
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

    def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes."""
        ...

import asyncio
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class NatsClient(Protocol):
    """Interface for NATS interaction."""

    async def publish(self, subject: str, payload: bytes) -> None:
        """Publishes a message to a subject."""
        ...

    async def subscribe(self, subject: str, queue: str = "", cb: Any = None) -> Any:
        """Subscribes to a subject with a callback."""
        ...

    async def close(self) -> None:
        """Closes the connection."""
        ...

    async def connect(self, servers: list[str] | str) -> None:
        """Connects to NATS server(s)."""
        ...


class MockNatsClient:
    """Simulated NATS client for testing."""

    def __init__(self) -> None:
        self.published_messages: list[dict[str, Any]] = []
        self.subscriptions: dict[str, Any] = {}
        self.is_closed = False
        self.is_connected = False

    async def connect(self, servers: list[str] | str, **kwargs: Any) -> None:
        self.is_connected = True

    async def close(self) -> None:
        self.is_closed = True

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published_messages.append({"subject": subject, "data": payload})

    async def subscribe(self, subject: str, queue: str = "", cb: Any = None, **kwargs: Any) -> Any:
        self.subscriptions[subject] = cb
        return object() # Return a dummy subscription object

    async def trigger_message(self, subject: str, data: bytes) -> None:
        """Helper to simulate an incoming message."""
        if subject in self.subscriptions:
            # Create a dummy msg object with .data attribute
            class Msg:
                def __init__(self, d: bytes): self.data = d

            cb = self.subscriptions[subject]
            if asyncio.iscoroutinefunction(cb):
                await cb(Msg(data))
            else:
                cb(Msg(data))

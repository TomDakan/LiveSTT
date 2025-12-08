import asyncio
from typing import Any, Protocol, runtime_checkable

from nats.aio.client import Client as NATS
from nats.js.api import RetentionPolicy, StorageType, StreamConfig


@runtime_checkable
class NatsClient(Protocol):
    """Interface for NATS interaction."""

    async def publish(self, subject: str, payload: bytes) -> None:
        """Publishes a message to a subject."""
        ...

    async def subscribe(
        self, subject: str, queue: str = "", cb: Any = None, **kwargs: Any
    ) -> Any:
        """Subscribes to a subject with a callback."""
        ...

    async def close(self) -> None:
        """Closes the connection."""
        ...

    async def connect(self, servers: list[str] | str) -> None:
        """Connects to NATS server(s)."""
        ...


class JetStreamClient:
    """NATS client with JetStream support."""

    def __init__(self) -> None:
        self.nc = NATS()
        self.js: Any = None

    async def connect(self, servers: list[str] | str) -> None:
        await self.nc.connect(servers)
        self.js = self.nc.jetstream()

    async def close(self) -> None:
        await self.nc.close()

    async def ensure_stream(self, name: str, subjects: list[str], max_age: float) -> None:
        """
        Ensures a stream exists with the given configuration.
        Storage is always FILE.
        """
        if not self.js:
            raise RuntimeError("Not connected")

        config = StreamConfig(
            name=name,
            subjects=subjects,
            max_age=max_age,  # nats-py converts this to nanoseconds
            storage=StorageType.FILE,
            retention=RetentionPolicy.LIMITS,
        )
        try:
            await self.js.add_stream(config)
        except Exception as e:
            # If stream exists with different config, it might fail.
            # For now we log/ignore, or try update.
            # But add_stream usually handles updates or idempotency.
            print(f"Warning: Failed to add stream {name}: {e}")
            try:
                await self.js.update_stream(config)
            except Exception as e2:
                print(f"Error: Failed to update stream {name}: {e2}")
                raise

    async def publish(self, subject: str, payload: bytes) -> None:
        if not self.js:
            raise RuntimeError("Not connected")
        await self.js.publish(subject, payload)

    async def subscribe(
        self,
        subject: str,
        queue: str = "",
        cb: Any = None,
        durable: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if not self.js:
            raise RuntimeError("Not connected")

        # If durable is set, we must use manual ack or explicit ack usually.
        # But for simplicity we don't force it here, relying on defaults or kwargs
        # if needed. However, for queue groups + durables, we need options.
        # nats-py subscribe configures consumer.
        return await self.js.subscribe(
            subject, queue=queue, cb=cb, durable=durable, **kwargs
        )


class MockNatsClient:
    """Simulated NATS client for testing."""

    def __init__(self) -> None:
        self.published_messages: list[dict[str, Any]] = []
        self.subscriptions: dict[str, Any] = {}
        self.is_closed = False
        self.is_connected = False
        self.streams: dict[str, Any] = {}

    async def connect(self, servers: list[str] | str, **kwargs: Any) -> None:
        self.is_connected = True

    async def close(self) -> None:
        self.is_closed = True

    async def ensure_stream(self, name: str, subjects: list[str], max_age: float) -> None:
        self.streams[name] = {"subjects": subjects, "max_age": max_age}

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published_messages.append({"subject": subject, "data": payload})

    async def subscribe(
        self, subject: str, queue: str = "", cb: Any = None, **kwargs: Any
    ) -> Any:
        self.subscriptions[subject] = cb
        return object()  # Return a dummy subscription object

    async def trigger_message(self, subject: str, data: bytes) -> None:
        """Helper to simulate an incoming message."""
        if subject in self.subscriptions:
            # Create a dummy msg object with .data attribute
            class Msg:
                def __init__(self, d: bytes):
                    self.data = d

                async def ack(self):
                    pass

            cb = self.subscriptions[subject]
            if asyncio.iscoroutinefunction(cb):
                await cb(Msg(data))
            else:
                cb(Msg(data))

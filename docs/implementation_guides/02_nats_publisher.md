# Implementation Guide: NATS Publisher (Audio Producer)

## Objective
Implement the `main.py` entrypoint and the `NatsAudioPublisher` class. This component bridges the `AudioSource` (data) and NATS (transport).

## 1. The `NatsAudioPublisher` Class
This class orchestrates the streaming process.

### Responsibilities
1.  **Dependency Injection**: Accepts an `AudioSource` and a NATS `Client` in `__init__`.
2.  **Publishing**: Iterates over `source.stream()` and publishes data to the `audio.raw` subject.
3.  **Graceful Shutdown**: Stops streaming when a stop signal is received.

### Reference Implementation (Scaffold)
```python
from dataclasses import dataclass
from nats.aio.client import Client as NATS
from audiosource import AudioSource

@dataclass
class NatsAudioPublisher:
    source: AudioSource
    nats: NATS
    subject: str = "audio.raw"

    async def start(self) -> None:
        """Consumes audio from source and publishes to NATS."""
        async with self.source as stream_source:
            async for chunk in stream_source.stream():
                await self.nats.publish(self.subject, chunk)
```

## 2. The `main()` Entrypoint
This is the application bootstrapper.

### Responsibilities
1.  **Configuration**: Read env vars (e.g., `NATS_URL`, `SAMPLE_RATE`).
2.  **Setup**:
    *   Connect to NATS.
    *   Initialize `MockAudioSource` (or `PyAudioSource` later).
    *   Initialize `NatsAudioPublisher`.
3.  **Execution**: Run the publisher.
4.  **Cleanup**: Close NATS connection on exit.

### NATS Connection Pattern
```python
nc = NATS()
await nc.connect("nats://localhost:4222")
# ... use nc ...
await nc.close()
```

## 3. Testing Strategy
Since this involves network I/O (NATS), we have two options:
1.  **Mock NATS**: Pass a `MockNatsClient` to `NatsAudioPublisher` and verify `publish` was called.
2.  **Integration Test**: Run a real NATS server (via `just up`) and verify messages appear.

For this phase, let's focus on **Unit Testing** with a Mock NATS client.

### Test Case: Publish Logic
-   Setup: `MockAudioSource` (yields 3 chunks), `MockNatsClient`.
-   Action: `await publisher.start()`
-   Assert: `MockNatsClient.publish` called 3 times with correct subject and data.

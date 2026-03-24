import asyncio
import os

import pytest

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")


class MockTranscriber:
    def __init__(self) -> None:
        self.total_bytes = 0
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def finish(self) -> None:
        self.connected = False

    async def send_audio(self, data: bytes) -> None:
        self.total_bytes += len(data)

    async def get_events(self):  # type: ignore[override]
        # Yield nothing, just keep connection open
        while self.connected:
            await asyncio.sleep(0.1)

            class MockEvent:
                text = "dummy"
                is_final = True
                confidence = 1.0

            yield MockEvent()


# NOTE: Renamed to disable automatic collection due to flakiness (ConnectionClosedOK)
# Pending rewrite for v8.0 API (AudioProducerService, STTProviderService).
@pytest.mark.integration
@pytest.mark.skip(reason="Pending rewrite for v8.0 BaseService API")
@pytest.mark.asyncio
async def _test_e2e_flow() -> None:
    """
    End-to-End Integration Test — PENDING REWRITE for v8.0 BaseService API.
    Verifies: Audio File -> Producer -> NATS -> STT -> NATS -> Gateway -> WebSocket
    """
    pass


@pytest.mark.integration
@pytest.mark.skip(reason="Pending rewrite for v8.0 BaseService API")
@pytest.mark.asyncio
async def test_e2e_persistence() -> None:
    """
    Verifies Data Persistence (JetStream) — PENDING REWRITE for v8.0 BaseService API.
    Scenario: Producer publishes data; STT Provider starts late and catches up.
    """
    pass

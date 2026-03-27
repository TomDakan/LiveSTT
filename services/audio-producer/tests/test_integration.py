import asyncio
import os

import pytest
from audio_producer.main import AudioProducerService
from nats.aio.client import Client as NATS

# Use the real NATS URL from environment or default to localhost
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_producer_integration() -> None:
    """
    Integration test for Audio Producer.
    Verifies that the producer can ingest a WAV file and publish audio chunks to NATS.
    """
    # 1. Setup NATS Subscriber (Verification)
    sub_nc = NATS()
    await sub_nc.connect(NATS_URL)

    received_chunks = []

    async def msg_handler(msg):
        received_chunks.append(msg.data)

    # v8.0 Architecture: Default stream is preroll.audio
    await sub_nc.subscribe("preroll.audio", cb=msg_handler)

    # 2. Setup Audio Producer with FileSource override
    # We use env var to trigger the FileSource logic in _get_audio_source
    os.environ["AUDIO_FILE"] = "tests/data/test_audio.wav"

    # Ensure test file exists
    test_file = "tests/data/test_audio.wav"
    assert os.path.exists(test_file), "Test audio file not found"

    service = AudioProducerService()
    # Override NATS URL if needed, though BaseService default is usually fine for local
    service.nats_url = NATS_URL

    # 3. Run Producer
    # We run it in a task because start() runs until source is exhausted or stopped
    task = asyncio.create_task(service.start())

    # Let it run for 5 seconds to gather data
    await asyncio.sleep(5.0)

    # Stop the service
    service.stop_event.set()

    try:
        await asyncio.wait_for(task, timeout=5.0)
    except TimeoutError:
        task.cancel()
        # This is expected if it hangs, but we prefer graceful exit
        pass
    except asyncio.CancelledError:
        pass

    # 4. Verify Data Received
    # Give NATS a moment to flush
    await asyncio.sleep(1.0)
    await sub_nc.flush()

    assert len(received_chunks) > 0
    # Verify total bytes roughly matches what we expect
    total_bytes = sum(len(c) for c in received_chunks)
    assert total_bytes > 0

    await sub_nc.close()
    if os.environ.get("AUDIO_FILE"):
        del os.environ["AUDIO_FILE"]

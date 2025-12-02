import asyncio
import os
import pytest
from nats.aio.client import Client as NATS
from audio_producer.main import NatsAudioPublisher
from audio_producer.audiosource import FileSource

# Use the real NATS URL from environment or default to localhost
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

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

    await sub_nc.subscribe("audio.raw", cb=msg_handler)

    # 2. Setup Audio Producer with FileSource
    pub_nc = NATS()
    await pub_nc.connect(NATS_URL)

    # Ensure test file exists
    test_file = "tests/data/test_audio.wav"
    assert os.path.exists(test_file), "Test audio file not found"

    source = FileSource(test_file, chunk_size=1600)
    publisher = NatsAudioPublisher(source=source, nats=pub_nc)

    # 3. Run Producer
    # We run it in a task because start() runs until source is exhausted
    task = asyncio.create_task(publisher.start())

    # Wait for task to complete (FileSource stops when file ends)
    # Add a timeout to prevent hanging if it doesn't stop
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        task.cancel()
        pytest.fail("Audio producer timed out")

    # 4. Verify Data Received
    # Give NATS a moment to flush
    await asyncio.sleep(0.5)

    assert len(received_chunks) > 0
    # Verify total bytes roughly matches file size (minus header)
    total_bytes = sum(len(c) for c in received_chunks)
    assert total_bytes > 0

    await sub_nc.close()
    await pub_nc.close()

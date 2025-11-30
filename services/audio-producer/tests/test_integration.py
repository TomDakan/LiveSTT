import asyncio
import os
import pytest
from nats.aio.client import Client as NATS
from audio_producer.main import NatsAudioPublisher
from tests.mocks import MockAudioSource

@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_producer_publishes_to_nats():
    """
    Integration test:
    1. Connects to real NATS (using os.getenv("NATS_URL")).
    2. Subscribes to 'audio.raw'.
    3. Uses MockAudioSource to generate 5 chunks of audio.
    4. Runs NatsAudioPublisher with the real NATS client.
    5. Asserts that 5 messages are received on the topic.
    """
    # TODO: 1. Setup NATS Client for verification (Subscriber)
    # Hint: Use NATS() and connect to os.getenv("NATS_URL", "nats://localhost:4222")
    # Hint: Subscribe to "audio.raw" and append msg.data to a list
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nats = NATS()
    await nats.connect(nats_url)
    received_messages = []

    async def message_handler(msg):
        received_messages.append(msg.data)

    await nats.subscribe("audio.raw", cb=message_handler)
    # TODO: 2. Setup NATS Client for Publisher (Producer)
    nc_pub = NATS()
    await nc_pub.connect(nats_url)
    # TODO: 3. Setup Publisher with Mock Source
    # Hint: mock_source = MockAudioSource(limit=5)
    mock_source = MockAudioSource(limit=5)
    publisher = NatsAudioPublisher(source=mock_source, nats=nc_pub)
    # TODO: 4. Run Publisher
    # Hint: await publisher.start()
    await publisher.start()
    # TODO: 5. Assertions
    # Hint: assert len(received_messages) == 5
    assert len(received_messages) == 5

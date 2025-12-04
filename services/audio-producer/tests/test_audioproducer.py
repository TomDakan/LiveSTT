import pytest
from audio_producer.main import NatsAudioPublisher
from messaging.nats import MockNatsClient

from tests.mocks import MockAudioSource


@pytest.mark.asyncio
async def test_mock_nats_publisher() -> None:
    source = MockAudioSource(sample_rate=16000, chunk_size=1600, limit=3)
    nats = MockNatsClient()
    producer = NatsAudioPublisher(source=source, nats=nats)
    await producer.start()
    assert len(nats.published_messages) == 3

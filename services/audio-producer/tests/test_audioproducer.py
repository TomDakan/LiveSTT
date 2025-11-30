import pytest
from main import NatsAudioPublisher
from mocks import MockAudioSource, MockNatsClient


@pytest.mark.asyncio
async def test_mock_nats_publisher() -> None:
    source = MockAudioSource(sample_rate=16000, chunk_size=1600, limit=3)
    nats = MockNatsClient()
    producer = NatsAudioPublisher(source=source, nats=nats)
    await producer.start()
    assert nats.publish_calls == 3

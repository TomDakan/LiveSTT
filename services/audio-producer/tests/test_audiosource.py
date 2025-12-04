import time

import pytest

from audio_producer.interfaces import AudioSource

from tests.mocks import MockAudioSource


@pytest.mark.asyncio
async def test_mock_timing() -> None:
    EPSILON = 0.1
    TARGET_SECONDS = 1.0

    start_time = time.perf_counter()
    source = MockAudioSource(sample_rate=16000, chunk_size=1600)
    stream = source.stream()
    for i in range(1, 11):
        _chunk = await anext(stream)
        i += 1
    end_time = time.perf_counter()

    elapsed_time = end_time - start_time
    assert abs(elapsed_time - TARGET_SECONDS) <= EPSILON


@pytest.mark.asyncio
async def test_mock_data_format() -> None:
    source = MockAudioSource(sample_rate=16000, chunk_size=1600)
    stream = source.stream()
    chunk = await anext(stream)
    assert isinstance(chunk, bytes)
    assert len(chunk) == 1600


def test_mock_producer_interface_compliance() -> None:
    source = MockAudioSource()
    assert isinstance(source, AudioSource)

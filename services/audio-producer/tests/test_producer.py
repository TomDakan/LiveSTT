import time

import pytest
from producer import MockAudioSource


@pytest.mark.asyncio
async def test_mock_timing() -> None:
    EPSILON = 0.05
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

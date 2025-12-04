# Implementation Guide: Audio Producer

## Objective
Implement the `AudioSource` abstraction and a `MockAudioSource` for testing. This is the foundation of the `audio-producer` service.

## 1. The Interface (`AudioSource`)
We need a protocol that defines how we get audio. It should be agnostic to the source (Microphone vs. File vs. Mock).

### Requirements
-   **Protocol Name**: `AudioSource`
-   **Method**: `stream()`
    -   **Returns**: An `AsyncIterator[bytes]` (chunks of raw PCM audio).
    -   **Context Manager**: It should likely be an async context manager (`__aenter__`/`__aexit__`) to handle resource cleanup (opening/closing streams).

### Reference Implementation (Scaffold)
```python
from typing import Protocol, AsyncIterator, runtime_checkable

@runtime_checkable
class AudioSource(Protocol):
    """Interface for an audio source."""

    async def stream(self) -> AsyncIterator[bytes]:
        """Yields chunks of raw PCM audio bytes."""
        ...
```

## 2. The Implementation (`MockAudioSource`)
Since we are on dev machines without specific hardware, we need a Mock that simulates a microphone.

### Requirements
-   **Class Name**: `MockAudioSource`
-   **Config**: Should accept `sample_rate` (default 16000) and `chunk_size` (default 1024 or 4096).
-   **Behavior**:
    -   In `stream()`, it should `yield` bytes.
    -   **Content**: Silence (`b'\x00' * size`) or Random Noise (using `os.urandom` or `numpy`).
    -   **Timing**: It MUST simulate real-time. If `chunk_size` represents 100ms of audio, it should `await asyncio.sleep(0.1)` between yields.

## 3. Testing Strategy
We need to verify that our `MockAudioSource` behaves like a real stream.

### Test Case 1: Interface Compliance
-   Verify `MockAudioSource` implements `AudioSource` (using `isinstance` if `@runtime_checkable` is used, or just duck typing).

### Test Case 2: Timing Accuracy
-   **Goal**: Ensure it doesn't dump all data instantly.
-   **Logic**:
    1.  Initialize `MockAudioSource(rate=16000, chunk_size=1600)`. (1600 samples @ 16kHz = 0.1 seconds).
    2.  Consume 10 chunks.
    3.  Measure elapsed time.
    4.  Assert elapsed time is roughly 1.0 second (allow some jitter, e.g., 0.9s to 1.1s).

### Test Case 3: Data Format
-   Assert yielded chunks are `bytes`.
-   Assert `len(chunk)` equals the configured byte size (Note: 16-bit audio = 2 bytes per sample. So `chunk_size=1600` samples = 3200 bytes).

## 4. Helpful Snippets

### Async Test Structure
```python
import pytest
import asyncio
from producer import MockAudioSource  # Import from local src

@pytest.mark.asyncio
async def test_mock_timing():
    source = MockAudioSource(rate=16000, chunk_size=1600)
    # ... implementation ...
```

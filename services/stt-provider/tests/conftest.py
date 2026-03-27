import pytest

from .mock_transcriber import MockTranscriber


@pytest.fixture
def mock_transcriber_factory():
    """Returns a factory that always produces fresh MockTranscribers.

    Pass this to STTProviderService(transcriber_factory=...) to avoid
    hitting Deepgram in tests.
    """
    instances: list[MockTranscriber] = []

    def factory() -> MockTranscriber:
        t = MockTranscriber()
        instances.append(t)
        return t

    factory.instances = instances  # type: ignore[attr-defined]
    return factory


@pytest.fixture
def auto_mock_transcriber_factory():
    """Like mock_transcriber_factory but each instance auto-responds to audio."""
    instances: list[MockTranscriber] = []

    def factory() -> MockTranscriber:
        t = MockTranscriber(auto_respond=True)
        instances.append(t)
        return t

    factory.instances = instances  # type: ignore[attr-defined]
    return factory

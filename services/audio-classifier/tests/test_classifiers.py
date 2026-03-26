import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from audio_classifier.classifiers import (
    SileroVADClassifier,
    StubClassifier,
)
from audio_classifier.interfaces import ClassificationResult


def _pcm_bytes(num_samples: int = 1536) -> bytes:
    """Return silent int16 PCM bytes."""
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


def test_stub_classifier() -> None:
    classifier = StubClassifier()
    result = classifier.classify(b"some_bytes")
    assert isinstance(result, ClassificationResult)
    assert result.label == "speech"
    assert result.confidence > 0.9


@patch("audio_classifier.classifiers.ONNXRUNTIME_AVAILABLE", False)
def test_silero_vad_fallback_missing_lib() -> None:
    with patch("audio_classifier.classifiers.logger") as mock_logger:
        classifier = SileroVADClassifier()
        mock_logger.warning.assert_called_with(
            "onnxruntime not installed. Falling back to StubClassifier."
        )
        assert isinstance(classifier._delegate, StubClassifier)
        result = classifier.classify(_pcm_bytes())
        assert result.label == "speech"


@patch("audio_classifier.classifiers.ONNXRUNTIME_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=False)
def test_silero_vad_fallback_missing_model(mock_exists: MagicMock) -> None:
    with patch("audio_classifier.classifiers.logger") as mock_logger:
        classifier = SileroVADClassifier(model_path="missing/model.onnx")
        assert mock_logger.warning.called
        assert "Silero VAD model not found" in mock_logger.warning.call_args[0][0]
        assert isinstance(classifier._delegate, StubClassifier)


@patch("audio_classifier.classifiers.ONNXRUNTIME_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("audio_classifier.classifiers.ort")
def test_silero_vad_loads(mock_ort: MagicMock, mock_exists: MagicMock) -> None:
    mock_ort.InferenceSession.return_value = MagicMock()
    classifier = SileroVADClassifier(model_path="valid/model.onnx")
    from pathlib import Path

    mock_ort.InferenceSession.assert_called_once_with(str(Path("valid/model.onnx")))
    assert classifier._delegate is classifier


@patch("audio_classifier.classifiers.ONNXRUNTIME_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("audio_classifier.classifiers.ort")
def test_silero_vad_classify_speech(mock_ort: MagicMock, mock_exists: MagicMock) -> None:
    """High speech probability → label='speech'."""
    mock_session = MagicMock()
    mock_session.run.return_value = (
        np.array([[0.9]], dtype=np.float32),
        np.zeros((2, 1, 64), dtype=np.float32),
        np.zeros((2, 1, 64), dtype=np.float32),
    )
    mock_ort.InferenceSession.return_value = mock_session

    classifier = SileroVADClassifier(model_path="valid/model.onnx")
    result = classifier.classify(_pcm_bytes())

    assert result.label == "speech"
    assert result.confidence == pytest.approx(0.9, abs=1e-5)
    mock_session.run.assert_called_once()


@patch("audio_classifier.classifiers.ONNXRUNTIME_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("audio_classifier.classifiers.ort")
def test_silero_vad_classify_non_speech(
    mock_ort: MagicMock, mock_exists: MagicMock
) -> None:
    """Low speech probability → label='non-speech'."""
    mock_session = MagicMock()
    mock_session.run.return_value = (
        np.array([[0.1]], dtype=np.float32),
        np.zeros((2, 1, 64), dtype=np.float32),
        np.zeros((2, 1, 64), dtype=np.float32),
    )
    mock_ort.InferenceSession.return_value = mock_session

    classifier = SileroVADClassifier(model_path="valid/model.onnx")
    result = classifier.classify(_pcm_bytes())

    assert result.label == "non-speech"
    assert result.confidence == pytest.approx(0.1, abs=1e-5)


@patch("audio_classifier.classifiers.ONNXRUNTIME_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("audio_classifier.classifiers.ort")
def test_silero_vad_state_carried_across_calls(
    mock_ort: MagicMock, mock_exists: MagicMock
) -> None:
    """Hidden state returned by the model is fed back on the next call."""
    h_after = np.ones((2, 1, 64), dtype=np.float32) * 0.5
    c_after = np.ones((2, 1, 64), dtype=np.float32) * 0.3

    mock_session = MagicMock()
    mock_session.run.return_value = (
        np.array([[0.8]], dtype=np.float32),
        h_after,
        c_after,
    )
    mock_ort.InferenceSession.return_value = mock_session

    classifier = SileroVADClassifier(model_path="valid/model.onnx")
    classifier.classify(_pcm_bytes())
    classifier.classify(_pcm_bytes())

    assert mock_session.run.call_count == 2
    # run(None, ort_inputs) — ort_inputs is the second positional arg
    second_inputs = mock_session.run.call_args_list[1][0][1]
    np.testing.assert_array_equal(second_inputs["h0"], h_after)
    np.testing.assert_array_equal(second_inputs["c0"], c_after)

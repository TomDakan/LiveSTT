from unittest.mock import MagicMock, patch

from audio_classifier.classifiers import (
    OpenVinoClassifier,
    StubClassifier,
)
from audio_classifier.interfaces import ClassificationResult


def test_stub_classifier() -> None:
    classifier = StubClassifier()
    result = classifier.classify(b"some_bytes")
    assert isinstance(result, ClassificationResult)
    assert result.label == "speech"
    assert result.confidence > 0.9


@patch("audio_classifier.classifiers.OPENVINO_AVAILABLE", False)
def test_openvino_classifier_fallback_missing_lib() -> None:
    # Should log warning and use Stub
    with patch("audio_classifier.classifiers.logger") as mock_logger:
        classifier = OpenVinoClassifier()
        mock_logger.warning.assert_called_with(
            "OpenVINO not installed. Falling back to StubClassifier."
        )
        assert isinstance(classifier.classifier, StubClassifier)
        result = classifier.classify(b"chunk")
        assert result.label == "speech"


@patch("audio_classifier.classifiers.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=False)
def test_openvino_classifier_fallback_missing_model(mock_exists: MagicMock) -> None:
    # Should log warning and use Stub
    with patch("audio_classifier.classifiers.logger") as mock_logger:
        classifier = OpenVinoClassifier(model_path="missing/model.xml")
        mock_logger.warning.assert_called()
        assert "Model file not found" in mock_logger.warning.call_args[0][0]
        assert isinstance(classifier.classifier, StubClassifier)


@patch("audio_classifier.classifiers.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("audio_classifier.classifiers.Core")
def test_openvino_classifier_loads(mock_core: MagicMock, mock_exists: MagicMock) -> None:
    # Mock Core behavior
    mock_runtime = MagicMock()
    mock_core.return_value = mock_runtime

    classifier = OpenVinoClassifier(model_path="valid/model.xml")

    # Verify it attempted to load
    mock_runtime.read_model.assert_called_once()
    mock_runtime.compile_model.assert_called_once()

    # Should identify as itself (OpenVinoClassifier) not Stub
    assert classifier.classifier is classifier

    # Test valid classify path (passed through mock logic)
    result = classifier.classify(b"chunk")
    assert result.label == "uncertain"

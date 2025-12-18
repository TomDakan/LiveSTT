import pytest
from unittest.mock import MagicMock, patch
from audio_classifier.classifiers import StubClassifier, OpenVinoClassifier, ClassificationResult

def test_stub_classifier():
    classifier = StubClassifier()
    result = classifier.classify(b"chunk")
    assert isinstance(result, ClassificationResult)
    assert result.label == "speech"
    assert result.confidence > 0.9

@patch("audio_classifier.classifiers.OPENVINO_AVAILABLE", False)
def test_openvino_classifier_fallback_missing_lib():
    # Should fallback to Stub if lib missing
    classifier = OpenVinoClassifier()
    assert isinstance(classifier.classifier, StubClassifier)
    result = classifier.classify(b"chunk")
    assert result.label == "speech"

@patch("audio_classifier.classifiers.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=False)
def test_openvino_classifier_fallback_missing_model(mock_exists):
    # Should fallback to Stub if model missing
    classifier = OpenVinoClassifier(model_path="missing/model.xml")
    assert isinstance(classifier.classifier, StubClassifier)

@patch("audio_classifier.classifiers.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("audio_classifier.classifiers.Core")
def test_openvino_classifier_loads(mock_core, mock_exists):
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

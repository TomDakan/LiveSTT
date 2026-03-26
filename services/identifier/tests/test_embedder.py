import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from identifier.embedder import OpenVinoEmbedder, StubEmbedder, _log_mel_features


def _pcm(seconds: float = 1.5, sr: int = 16000) -> bytes:
    """Return silent int16 PCM for the given duration."""
    n = int(seconds * sr)
    return struct.pack(f"<{n}h", *([0] * n))


def _noise_pcm(seconds: float = 1.5, sr: int = 16000) -> bytes:
    rng = np.random.default_rng(42)
    samples = (rng.standard_normal(int(seconds * sr)) * 16000).astype(np.int16)
    return samples.tobytes()


# --- StubEmbedder ---


def test_stub_always_returns_none() -> None:
    assert StubEmbedder().embed(_pcm()) is None


# --- OpenVinoEmbedder fallbacks ---


@patch("identifier.embedder.OPENVINO_AVAILABLE", False)
def test_openvino_fallback_no_lib() -> None:
    with patch("identifier.embedder.logger") as mock_log:
        e = OpenVinoEmbedder()
        mock_log.warning.assert_called()
        assert isinstance(e._delegate, StubEmbedder)
        assert e.embed(_pcm()) is None


@patch("identifier.embedder.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=False)
def test_openvino_fallback_missing_model(mock_exists: MagicMock) -> None:
    with patch("identifier.embedder.logger") as mock_log:
        e = OpenVinoEmbedder(model_path="missing/model.xml")
        mock_log.warning.assert_called()
        assert isinstance(e._delegate, StubEmbedder)


@patch("identifier.embedder.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("identifier.embedder.Core")
def test_openvino_loads_model(mock_core: MagicMock, mock_exists: MagicMock) -> None:
    mock_runtime = MagicMock()
    mock_core.return_value = mock_runtime

    e = OpenVinoEmbedder(model_path="valid/model.xml")

    mock_runtime.read_model.assert_called_once()
    mock_runtime.compile_model.assert_called_once()
    assert e._delegate is e


@patch("identifier.embedder.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("identifier.embedder.Core")
def test_openvino_embed_returns_normalised_vector(
    mock_core: MagicMock, mock_exists: MagicMock
) -> None:
    raw_embedding = np.random.default_rng(0).standard_normal(256).astype(np.float32)
    mock_compiled = MagicMock()
    mock_compiled.return_value = {"output": raw_embedding[np.newaxis]}
    mock_core.return_value.compile_model.return_value = mock_compiled

    e = OpenVinoEmbedder(model_path="valid/model.xml")
    result = e.embed(_noise_pcm())

    assert result is not None
    assert result.shape == (256,)
    assert pytest.approx(np.linalg.norm(result), abs=1e-5) == 1.0


@patch("identifier.embedder.OPENVINO_AVAILABLE", True)
@patch("pathlib.Path.exists", return_value=True)
@patch("identifier.embedder.Core")
def test_openvino_returns_none_for_short_audio(
    mock_core: MagicMock, mock_exists: MagicMock
) -> None:
    mock_core.return_value.compile_model.return_value = MagicMock()
    e = OpenVinoEmbedder()
    # < 250 ms
    assert e.embed(_pcm(seconds=0.1)) is None


# --- Mel feature extraction ---


def test_log_mel_features_shape() -> None:
    audio = np.zeros(24000, dtype=np.float32)
    features = _log_mel_features(audio)
    assert features.ndim == 3
    assert features.shape[0] == 1  # batch
    assert features.shape[2] == 80  # mel bins


def test_log_mel_features_normalised() -> None:
    rng = np.random.default_rng(1)
    audio = rng.standard_normal(24000).astype(np.float32)
    features = _log_mel_features(audio)
    # CMVN should produce approx zero mean / unit variance per bin
    mean = features[0].mean(axis=0)
    assert np.abs(mean).max() < 0.1

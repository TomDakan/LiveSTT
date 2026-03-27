import logging
from pathlib import Path

import numpy as np

try:
    from openvino import Core  # type: ignore[import-untyped]

    OPENVINO_AVAILABLE = True
except ImportError:
    Core = None
    OPENVINO_AVAILABLE = False

from .interfaces import Embedder

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_N_MELS = 80
_WIN_LENGTH = 400  # 25 ms at 16 kHz
_HOP_LENGTH = 160  # 10 ms at 16 kHz
_N_FFT = 512
_MIN_SAMPLES = _SAMPLE_RATE // 4  # 250 ms minimum


class StubEmbedder(Embedder):
    """No-op embedder — returns None so all speakers appear as Unknown."""

    def embed(self, audio_pcm: bytes) -> None:
        return None


class OpenVinoEmbedder(Embedder):
    """
    WeSpeaker ResNet34 speaker embedder via OpenVINO.

    Input: raw int16 PCM at 16 kHz mono.
    Processing: pre-emphasis → 80-dim log mel-filterbank (25 ms / 10 ms) →
                CMVN → OpenVINO inference → L2-normalised 256-dim embedding.

    Falls back to StubEmbedder when OpenVINO is not installed or the model
    file is missing — the rest of the pipeline continues with Unknown speakers.
    """

    def __init__(self, model_path: str = "models/wespeaker.xml") -> None:
        self._delegate: Embedder

        if not OPENVINO_AVAILABLE:
            logger.warning("OpenVINO not installed. Falling back to StubEmbedder.")
            self._delegate = StubEmbedder()
            return

        path = Path(model_path)
        if not path.exists():
            logger.warning(
                f"WeSpeaker model not found at {model_path}. "
                "Falling back to StubEmbedder."
            )
            self._delegate = StubEmbedder()
            return

        try:
            assert Core is not None
            core = Core()
            model = core.read_model(model=path)
            self._compiled = core.compile_model(model=model, device_name="AUTO")
            self._delegate = self
            logger.info(f"WeSpeaker model loaded: {model_path}")
        except Exception as e:
            logger.error(
                f"Failed to load WeSpeaker model: {e}. Falling back to StubEmbedder."
            )
            self._delegate = StubEmbedder()

    def embed(self, audio_pcm: bytes) -> np.ndarray | None:
        if self._delegate is not self:
            return self._delegate.embed(audio_pcm)

        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio) < _MIN_SAMPLES:
            return None

        features = _log_mel_features(audio)  # [1, T, 80]

        try:
            result = self._compiled({"feats": features})
            embedding = next(iter(result.values())).flatten()
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return None

        norm = np.linalg.norm(embedding)
        if norm < 1e-10:
            return None
        return (embedding / norm).astype(np.float32)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Numpy-only log mel-filterbank (no librosa / scipy required)
# ---------------------------------------------------------------------------


def _log_mel_features(audio: np.ndarray) -> np.ndarray:
    """Return log mel-filterbank features with CMVN, shape [1, T, 80]."""
    # Pre-emphasis
    audio = np.concatenate(([audio[0]], audio[1:] - 0.97 * audio[:-1]))

    # Frame the signal
    n_frames = max(1, 1 + (len(audio) - _WIN_LENGTH) // _HOP_LENGTH)
    idx = np.arange(_WIN_LENGTH)[None, :] + _HOP_LENGTH * np.arange(n_frames)[:, None]
    # Clamp indices to avoid out-of-bounds on the last frame
    idx = np.clip(idx, 0, len(audio) - 1)
    frames = audio[idx] * np.hamming(_WIN_LENGTH)  # [T, win_length]

    # Power spectrum via FFT
    if _WIN_LENGTH < _N_FFT:
        frames = np.pad(frames, ((0, 0), (0, _N_FFT - _WIN_LENGTH)))
    power = np.abs(np.fft.rfft(frames, n=_N_FFT)) ** 2  # [T, n_fft//2+1]

    # Log mel-filterbank
    mel_spec = power @ _mel_filterbank()  # [T, n_mels]
    log_mel = np.log(mel_spec + 1e-10)

    # CMVN
    mean = log_mel.mean(axis=0, keepdims=True)
    std = log_mel.std(axis=0, keepdims=True) + 1e-8
    return ((log_mel - mean) / std)[np.newaxis].astype(np.float32)  # type: ignore[no-any-return]  # [1, T, 80]


def _mel_filterbank() -> np.ndarray:
    """Build an [n_fft//2+1, n_mels] mel filterbank matrix (cached implicitly)."""
    n_freqs = _N_FFT // 2 + 1
    low_mel = 2595.0 * np.log10(1.0 + 0.0 / 700.0)
    high_mel = 2595.0 * np.log10(1.0 + (_SAMPLE_RATE / 2) / 700.0)
    mel_pts = np.linspace(low_mel, high_mel, _N_MELS + 2)
    hz_pts = 700.0 * (10.0 ** (mel_pts / 2595.0) - 1.0)
    bins = np.floor((_N_FFT + 1) * hz_pts / _SAMPLE_RATE).astype(int)

    fb = np.zeros((n_freqs, _N_MELS), dtype=np.float32)
    for m in range(1, _N_MELS + 1):
        left, center, right = bins[m - 1], bins[m], bins[m + 1]
        for k in range(left, center):
            fb[k, m - 1] = (k - left) / max(center - left, 1)
        for k in range(center, right):
            fb[k, m - 1] = (right - k) / max(right - center, 1)
    return fb

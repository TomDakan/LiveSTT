import logging
import time
from pathlib import Path

try:
    import numpy as np
    import onnxruntime as ort

    ONNXRUNTIME_AVAILABLE = True
except ImportError:
    ONNXRUNTIME_AVAILABLE = False

from .interfaces import AudioClassifier, ClassificationResult

logger = logging.getLogger(__name__)

# Must match the chunk size published by audio-producer (ADR-0012)
_CHUNK_SAMPLES = 1536


class StubClassifier(AudioClassifier):
    """Fallback classifier when runtime or model is unavailable."""

    def classify(self, audio_data: bytes) -> ClassificationResult:
        return ClassificationResult(
            label="speech", confidence=0.99, timestamp=time.time()
        )


class SileroVADClassifier(AudioClassifier):
    """
    Voice Activity Detection using Silero VAD (ONNX Runtime).

    Maintains LSTM hidden state across calls for accurate streaming VAD.
    Falls back to StubClassifier if onnxruntime is unavailable or the model
    file is missing — the rest of the pipeline continues unaffected.
    """

    def __init__(
        self,
        model_path: str = "models/silero_vad.onnx",
        threshold: float = 0.5,
    ) -> None:
        self._threshold = threshold
        self._delegate: AudioClassifier

        if not ONNXRUNTIME_AVAILABLE:
            logger.warning("onnxruntime not installed. Falling back to StubClassifier.")
            self._delegate = StubClassifier()
            return

        path = Path(model_path)
        if not path.exists():
            logger.warning(
                f"Silero VAD model not found at {model_path}. "
                "Falling back to StubClassifier."
            )
            self._delegate = StubClassifier()
            return

        try:
            self._session = ort.InferenceSession(str(path))
            self._reset_state()
            self._delegate = self
            logger.info(f"Silero VAD model loaded: {model_path}")
        except Exception as e:
            logger.error(
                f"Failed to load Silero VAD model: {e}. Falling back to StubClassifier."
            )
            self._delegate = StubClassifier()

    def _reset_state(self) -> None:
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def classify(self, audio_data: bytes) -> ClassificationResult:
        if self._delegate is not self:
            return self._delegate.classify(audio_data)

        # Convert int16 PCM bytes to float32 in [-1, 1]
        audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        audio = audio[:_CHUNK_SAMPLES]

        if len(audio) < 512:
            return ClassificationResult(
                label="non-speech", confidence=0.0, timestamp=time.time()
            )

        ort_inputs = {
            "input": audio[np.newaxis, :],
            "h0": self._h,
            "c0": self._c,
        }
        output, self._h, self._c = self._session.run(None, ort_inputs)
        speech_prob = float(output[0][0])

        label = "speech" if speech_prob >= self._threshold else "non-speech"
        return ClassificationResult(
            label=label, confidence=speech_prob, timestamp=time.time()
        )

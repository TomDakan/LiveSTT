from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    timestamp: float


class AudioClassifier(ABC):
    @abstractmethod
    def classify(self, audio_data: bytes) -> ClassificationResult:
        """
        Classify a chunk of audio data.

        Args:
            audio_data: Raw audio bytes (PCM)

        Returns:
            ClassificationResult containing label and confidence
        """
        pass

from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    @abstractmethod
    def embed(self, audio_pcm: bytes) -> np.ndarray | None:
        """Extract a speaker embedding from raw int16 PCM audio.

        Returns a normalised 256-dim float32 vector, or None if the audio
        is unsuitable (too short, silent, model unavailable).
        """
        pass


class VoiceprintStore(ABC):
    @abstractmethod
    def enroll(self, name: str, embedding: np.ndarray) -> None:
        """Store or overwrite the voiceprint for a named speaker."""
        pass

    @abstractmethod
    def identify(
        self, embedding: np.ndarray, threshold: float = 0.25
    ) -> tuple[str, float] | None:
        """Return (speaker_name, confidence) if cosine distance <= threshold, else None.

        confidence = 1.0 - cosine_distance  (higher is more certain).
        """
        pass

    @abstractmethod
    def delete(self, name: str) -> None:
        """Remove a speaker's voiceprint (right-to-erasure / crypto-shred support)."""
        pass

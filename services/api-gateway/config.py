# services/api-gateway/app/config.py
import os

from typed_settings import loader, settings


@settings
class AppConfig:
    # Load from Docker Secret if available, else fallback (safe for dev)
    deepgram_key_file: str = "/run/secrets/deepgram_key"

    @property
    def deepgram_key(self) -> str:
        if os.path.exists(self.deepgram_key_file):
            return open(self.deepgram_key_file).read().strip()
        return os.getenv("DEEPGRAM_API_KEY", "")


# Load settings
conf = loader.load_settings(AppConfig, loaders=[])

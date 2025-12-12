import asyncio
import os

from messaging.service import BaseService
from messaging.streams import (
    AUDIO_STREAM_CONFIG,
    PREROLL_STREAM_CONFIG,
)

# Import the module itself so we can safely check for platform-specific classes
from . import audiosource


class AudioProducerService(BaseService):
    def __init__(self):
        super().__init__("audio-producer")
        self.session_id: str | None = None
        self.is_active = False

    def _get_audio_source(self):
        """
        Factory method to select the correct Audio Source based on
        Env Vars and Platform availability.
        """
        # 1. High Priority: File Override (for Testing/Simulation)
        audio_file = os.getenv("AUDIO_FILE")
        if audio_file:
            self.logger.info(f"Source: File ({audio_file})")
            return audiosource.FileSource(audio_file, chunk_size=1600, loop=True)

        # 2. Windows Microphone
        if hasattr(audiosource, "WindowsSource"):
            self.logger.info("Source: Windows Microphone (PyAudio)")
            return audiosource.WindowsSource()

        # 3. Linux Microphone
        if hasattr(audiosource, "LinuxSource"):
            self.logger.info("Source: Linux Microphone (ALSA)")
            # You might want to make sample/chunk configurable via env vars
            return audiosource.LinuxSource(sample_rate=16000, chunk_size=1600)

        # 4. Fallback / Error
        raise RuntimeError(
            "No valid Audio Source found! "
            "Set AUDIO_FILE env var or ensure PyAudio/ALSA is installed."
        )

    async def run_business_logic(self, js, stop_event):
        # 1. Ensure Streams Exist
        try:
            await self.nats_manager.ensure_stream(**PREROLL_STREAM_CONFIG)
            await self.nats_manager.ensure_stream(**AUDIO_STREAM_CONFIG)
            self.logger.info("Audio Streams Verified")
        except Exception as e:
            self.logger.critical(f"Failed to verify streams: {e}")
            return

        # 2. Initialize the appropriate source
        try:
            source = self._get_audio_source()
        except Exception as e:
            self.logger.critical(f"Failed to initialize audio source: {e}")
            return

        # 3. Start Streaming
        self.logger.info("Audio Stream Started")

        async with source as stream:
            async for chunk in stream.stream():
                if stop_event.is_set():
                    break

                # Logic: Atomic Routing (Live vs Preroll)
                if self.is_active and self.session_id:
                    await js.publish(f"audio.live.{self.session_id}", chunk)
                else:
                    await js.publish("preroll.audio", chunk)


if __name__ == "__main__":
    service = AudioProducerService()
    asyncio.run(service.start())

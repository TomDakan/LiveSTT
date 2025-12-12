from typing import Any

from nats.js.api import RetentionPolicy, StorageType

# Configuration for the Pre-Roll Buffer (Memory Ring Buffer)
PREROLL_STREAM_CONFIG: dict[str, Any] = {
    "name": "PRE_BUFFER",
    "subjects": ["preroll.audio"],
    "storage": StorageType.MEMORY,
    "retention": RetentionPolicy.LIMITS,
    "max_msg_size": 8192,  # 8KB - Safely holds 1600 bytes + headers
    "max_bytes": 64 * 1024 * 1024,  # 64MB Buffer (~10 mins 16kHz)
}

# Configuration for the Persistent Audio Stream (File WorkQueue)
AUDIO_STREAM_CONFIG: dict[str, Any] = {
    "name": "AUDIO_STREAM",
    "subjects": ["audio.live.>", "audio.backfill.>"],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.WORK_QUEUE,
    "max_age": 60 * 60,  # 1 Hour Safety Net
}

# Configuration for the Transcription Results (File Limits)
TRANSCRIPTION_STREAM_CONFIG: dict[str, Any] = {
    "name": "TRANSCRIPTION_STREAM",
    "subjects": ["transcript.raw.>", "transcript.identity.>", "transcript.final.>"],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.LIMITS,
    "max_age": 7 * 24 * 60 * 60,  # 7 Days
}

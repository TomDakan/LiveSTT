from typing import Any

from nats.js.api import RetentionPolicy, StorageType

# --- Subject Constants ---
SUBJECT_PREFIX_PREROLL = "preroll.audio"
SUBJECT_PREFIX_AUDIO_LIVE = "audio.live"
SUBJECT_PREFIX_AUDIO_BACKFILL = "audio.backfill"

SUBJECT_PREFIX_AUDIO_BACKFILL = "audio.backfill"

SUBJECT_PREFIX_TRANSCRIPT_RAW = "transcript.raw"
SUBJECT_TRANSCRIPT_RAW = f"{SUBJECT_PREFIX_TRANSCRIPT_RAW}.>"
SUBJECT_TRANSCRIPT_FINAL = "transcript.final.>"

# Concrete Subjects (for publishing/subscribing)
SUBJECT_AUDIO_LIVE = f"{SUBJECT_PREFIX_AUDIO_LIVE}.>"
SUBJECT_AUDIO_BACKFILL = f"{SUBJECT_PREFIX_AUDIO_BACKFILL}.>"

# Configuration for the Pre-Roll Buffer (Memory Ring Buffer)
PREROLL_STREAM_CONFIG: dict[str, Any] = {
    "name": "PRE_BUFFER",
    "subjects": [SUBJECT_PREFIX_PREROLL],
    "storage": StorageType.MEMORY,
    "retention": RetentionPolicy.LIMITS,
    "max_msg_size": 8192,  # 8KB - Safely holds 1600 bytes + headers
    "max_bytes": 64 * 1024 * 1024,  # 64MB Buffer (~10 mins 16kHz)
}

# Configuration for the Persistent Audio Stream (File WorkQueue)
AUDIO_STREAM_CONFIG: dict[str, Any] = {
    "name": "AUDIO_STREAM",
    "subjects": [SUBJECT_AUDIO_LIVE, SUBJECT_AUDIO_BACKFILL],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.WORK_QUEUE,
    "max_age": 60 * 60,  # 1 Hour Safety Net
}

# Configuration for the Transcription Results (File Limits)
TRANSCRIPTION_STREAM_CONFIG: dict[str, Any] = {
    "name": "TRANSCRIPTION_STREAM",
    "subjects": [
        SUBJECT_TRANSCRIPT_RAW,
        "transcript.identity.>",
        SUBJECT_TRANSCRIPT_FINAL,
    ],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.LIMITS,
    "max_age": 7 * 24 * 60 * 60,  # 7 Days
}

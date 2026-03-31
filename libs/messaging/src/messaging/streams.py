from typing import Any

from nats.js.api import RetentionPolicy, StorageType

# --- Subject Constants ---
SUBJECT_PREFIX_PREROLL = "preroll.audio"
SUBJECT_PREFIX_AUDIO_LIVE = "audio.live"
SUBJECT_PREFIX_AUDIO_BACKFILL = "audio.backfill"

SUBJECT_PREFIX_TRANSCRIPT_RAW = "transcript.raw"
SUBJECT_TRANSCRIPT_RAW = f"{SUBJECT_PREFIX_TRANSCRIPT_RAW}.>"
SUBJECT_PREFIX_TRANSCRIPT_INTERIM = "transcript.interim"
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

# Configuration for the Persistent Audio Stream (File Limits)
# LIMITS (not WORK_QUEUE) allows multiple independent durable consumers
# (stt-provider and identifier) to each track their own read position.
AUDIO_STREAM_CONFIG: dict[str, Any] = {
    "name": "AUDIO_STREAM",
    "subjects": [SUBJECT_AUDIO_LIVE, SUBJECT_AUDIO_BACKFILL],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.LIMITS,
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

# Configuration for the Session Control Stream
SESSION_STREAM_CONFIG: dict[str, Any] = {
    "name": "SESSION_STREAM",
    "subjects": ["session.control"],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.LIMITS,
    "max_msgs_per_subject": 1,  # only the latest command matters
    "max_age": 60,  # stale commands (>60s old) are discarded on restart
}

# KV bucket name for session state — created by audio-producer, read by others
SESSION_KV_BUCKET = "session_state"

# Configuration for the Classification Results (Memory/Volatile)
SUBJECT_PREFIX_CLASSIFICATION = "classification"
SUBJECT_CLASSIFICATION_LIVE = f"{SUBJECT_PREFIX_CLASSIFICATION}.live.>"

CLASSIFICATION_STREAM_CONFIG: dict[str, Any] = {
    "name": "CLASSIFICATION_STREAM",
    "subjects": [SUBJECT_CLASSIFICATION_LIVE],
    "storage": StorageType.MEMORY,
    "retention": RetentionPolicy.LIMITS,
    "max_msgs": 1000,  # Keep last 1000 classifications
}

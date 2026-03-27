# ADR-0011: NATS JetStream Retention Policy

**Date**: 2025-12-06
**Status**: ACCEPTED

**Context**:
We are migrating to NATS JetStream for data persistence ("Black Box"). We need to define how long data is kept to balance disk usage on the NUC (256GB NVMe) against recovery capabilities.

**Decision**:
Set the following retention policies (MaxAge) for JetStream streams:

1.  **Audio Stream (`audio.raw`)**: **60 minutes**
    -   *Rationale*: Raw audio (16kHz PCM) consumes ~115MB/hour. Keeping 24 hours would consume ~2.7GB. While the disk can handle this, the primary use case for "catch up" is short-term internet outages (minutes to hours). 60 minutes is sufficient for almost all outage scenarios.
    -   *Configuration*: `NATS_AUDIO_RETENTION` env var (Default: `3600s`).

2.  **Transcript/Event Stream (`text.transcript`, `identity.event`)**: **7 days**
    -   *Rationale*: JSON data is text-based and highly compressible. 7 days allows for weekly debugging and review of past events.
    -   *Configuration*: `NATS_TEXT_RETENTION` env var (Default: `604800s`).

**Consequences**:
-   **Positive**: Efficient disk usage. Sufficient buffer for "Split-Brain" recovery (Cloud STT catching up).
-   **Negative**: If an outage lasts longer than 1 hour, raw audio will be lost.
-   **Mitigation**: The system is designed for real-time usage. Prolonged outages should trigger other alerts.

---

## Amendment (ADR-0013 / ADR-0014, 2026-03)

**Subject names, stream names, and retention semantics have changed since this ADR was written.**

| Original (this ADR) | Current |
|---------------------|---------|
| `audio.raw` | `AUDIO_STREAM`: subjects `audio.live.>`, `audio.backfill.>` |
| `text.transcript` | `TRANSCRIPTION_STREAM`: subjects `transcript.raw.>`, `transcript.identity.>`, `transcript.final.>` |
| `identity.event` | merged into `TRANSCRIPTION_STREAM` above |

**Consumer semantics (WORK_QUEUE → LIMITS)**: The `AUDIO_STREAM` originally used
`RetentionPolicy.WORK_QUEUE` (messages deleted after the single consumer acknowledged them).
This was changed to `RetentionPolicy.LIMITS` so that `stt-provider` and `identifier` can
independently consume audio via separate durable pull consumers, each tracking their own
position. Messages are now retained for the full `max_age` window (1 hour) regardless of
consumer acknowledgement state.

The 1-hour and 7-day retention windows remain unchanged and are still correct.

See [ADR-0013](0013-stt-provider-pull-consumers-and-deepgram-reconnection.md) for pull
consumer rationale and [ADR-0014](0014-audio-stream-limits-retention.md) for the
WORK_QUEUE → LIMITS decision.

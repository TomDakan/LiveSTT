# ADR-0014: AUDIO_STREAM Retention Policy — WORK_QUEUE → LIMITS

**Date**: 2026-03-27
**Status**: ACCEPTED
**Amends**: ADR-0011

---

## Context

`AUDIO_STREAM` was originally configured with `RetentionPolicy.WORK_QUEUE`. This policy
deletes messages as soon as any consumer acknowledges them and enforces a single active
consumer per stream.

Two services need independent access to every audio chunk:

- **`stt-provider`**: streams audio to Deepgram for transcription (durable consumer `stt_live` / `stt_backfill`)
- **`identifier`**: buffers audio windows for speaker embedding (durable consumer `identifier_live` / `identifier_backfill`)

Under `WORK_QUEUE`, only one of these consumers can be active. Whichever registers first
gets all messages; the other starves. This was discovered during e2e testing when both
services subscribed using pull consumers (ADR-0013).

## Decision

Change `AUDIO_STREAM` retention from `RetentionPolicy.WORK_QUEUE` to `RetentionPolicy.LIMITS`.

```python
# libs/messaging/src/messaging/streams.py
AUDIO_STREAM_CONFIG: dict[str, Any] = {
    "name": "AUDIO_STREAM",
    "subjects": [SUBJECT_AUDIO_LIVE, SUBJECT_AUDIO_BACKFILL],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.LIMITS,  # was: WORK_QUEUE
    "max_age": 60 * 60,  # 1 Hour Safety Net (unchanged)
}
```

Under `LIMITS`, NATS retains messages until `max_age` expires, regardless of consumer
state. Each durable pull consumer independently tracks its own sequence position and
receives every message. Acknowledgement advances that consumer's position only; it does
not delete the message.

**Important**: changing retention on an existing stream requires deleting and recreating
the stream (NATS rejects in-place retention policy changes). The `just nuke` recipe handles
this by wiping the NATS bind-mount / named volume before restarting.

## Consequences

### Positive
- Both `stt-provider` and `identifier` independently consume all audio without competing
- Durable consumer positions survive service restarts (resume from last ACK — ADR-0013)
- Offline buffering behaviour is preserved: audio accumulates while Deepgram is unreachable

### Negative
- Storage footprint increases: messages are now retained for the full `max_age` window
  (~112MB/hour at 16kHz/16-bit/1536-sample chunks) rather than being deleted on ack
- This is intentional — the 1-hour buffer is the designed recovery window (ADR-0011)

### Risks and Mitigations
- **Risk**: A permanently-offline durable consumer holds a reference, preventing cleanup
  - **Mitigation**: `LIMITS` ages messages out after `max_age` regardless of consumer state;
    unlike `INTEREST`, there is no unbounded growth risk
- **Risk**: Stream config change breaks existing deployments
  - **Mitigation**: `just nuke` wipes `/data/nats` and recreates all streams cleanly;
    documented in runbooks

## References

- [ADR-0011](0011-retention-policy.md) - Original retention policy (WORK_QUEUE, now amended)
- [ADR-0013](0013-stt-provider-pull-consumers-and-deepgram-reconnection.md) - Pull consumer pattern
- `libs/messaging/src/messaging/streams.py` - Stream configuration

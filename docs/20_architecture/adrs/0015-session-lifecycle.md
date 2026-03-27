# ADR-0015: Session Lifecycle Management

**Date**: 2026-03-26
**Status**: ACCEPTED

---

## Context

Milestone 4.5 plans a `session.control` subject to replace the `AUTO_SESSION` env-var hack. Before implementing that milestone, the session lifecycle design must be fully specified. Several questions were left open in the roadmap:

1. How are session IDs generated? (The codebase currently uses a random 8-char UUID hex.)
2. How does a session end? (No stop mechanism was designed.)
3. Where is session state stored so that service restarts do not corrupt it?
4. Who is authorised to start vs. stop a session?

Additional context from the operating environment:
- Multiple events (church services, Bible studies, etc.) happen on the same day.
- Any attendee should be able to start transcription; no one person "owns" a session.
- Stopping transcription prematurely affects all attendees currently reading the live feed.

---

## Decision

### 1. Session ID Format

Session IDs use the format `YYYYMMDD-HHMM` derived from the **session start time** (the moment the first `start` command is received), e.g. `20260326-1030`.

**Rationale:**
- Human-readable in NATS subject names (`audio.live.20260326-1030`).
- Naturally unique per event (assumes no two events start within the same minute).
- Deterministic across audio-producer restarts: the session ID is recovered from NATS KV (see §3), not regenerated.
- Sortable and meaningful for debugging and archiving.

The `SESSION_ID` env-var override is retained for CI/testing use only.

### 2. Session Authorization — Asymmetric Start/Stop

| Action | Authorization |
|--------|---------------|
| `POST /session/start` | Unauthenticated — any user |
| `POST /session/stop` | Admin JWT required |
| Auto-stop (silence) | Internal — no user action |

**Rationale:** Any audience member should be able to start transcription on demand (Deepgram is only billed while a session is active). However, a manual stop takes the transcript away from all connected clients, so it is restricted to admins. Auto-stop is the primary termination mechanism for the normal case.

### 3. Session State in NATS KV

Session state is authoritative in NATS JetStream KV, bucket **`session_state`**.

| Key | Value (JSON) | Description |
|-----|--------------|-------------|
| `current` | `{"session_id": "...", "started_at": "<ISO8601>", "state": "active\|idle"}` | Active session; absent or `"idle"` when no session is running |
| `config` | `{"silence_timeout_s": 300}` | Operator-configurable session parameters |

On audio-producer startup, it reads `current` from KV:
- If `state == "active"` → resume the existing session (same session ID, same NATS subjects). Transition directly to `ACTIVE` without a new flush.
- If absent or `state == "idle"` → remain `IDLE`, publish to `preroll.audio`.

This makes audio-producer restarts transparent: the session ID and timing are recovered, not regenerated.

### 4. Session Start Flow

1. Client `POST /session/start` → api-gateway publishes `{"command": "start"}` to `SESSION_STREAM` (`session.control` subject).
2. audio-producer receives command, derives `session_id = strftime("%Y%m%d-%H%M")` from current UTC time, writes `current` KV entry with `state = "active"`.
3. audio-producer transitions `IDLE → ACTIVE`: switches mic publish from `preroll.audio` → `audio.live.<session_id>`, spawns background flush of `PRE_BUFFER` → `audio.backfill.<session_id>`.
4. api-gateway returns `{"session_id": "<id>", "started_at": "<ISO8601>"}` to the client.

If a session is already active when `start` is received, audio-producer logs a warning and ignores the command (idempotent).

### 5. Session End — Auto-Stop (Primary)

audio-producer tracks a **silence counter**: if every audio chunk published to `audio.live.<session_id>` for the last `silence_timeout_s` seconds has an RMS below `SILENCE_THRESHOLD_DBFS` (default: −50 dBFS), audio-producer triggers an automatic stop.

`silence_timeout_s` is read from the `config` KV key at session start and re-read whenever a `vocab.updated`-style reload event is published. Default: **300 seconds (5 minutes)**.

### 6. Session End — Manual Stop (Admin Only)

`POST /session/stop` requires a valid admin JWT. api-gateway publishes `{"command": "stop"}` to `SESSION_STREAM`. audio-producer receives it and proceeds identically to auto-stop.

### 7. Session Stop Flow (Both Paths)

1. audio-producer publishes an **EOS marker** to `audio.live.<session_id>`: a normal-sized zero-byte (or silence) PCM message with NATS message header `LiveSTT-EOS: true`.
2. audio-producer transitions `ACTIVE → IDLE`: switches back to `preroll.audio`, clears `current` KV entry (sets `state = "idle"`).
3. stt-provider live lane: on receiving the EOS header, sends "Finalize" to Deepgram and closes the WebSocket cleanly. Returns to waiting for the next session's audio.
4. identifier live lane: on receiving the EOS header, flushes any partial audio buffer (discards it), returns to waiting.

**No new session is started automatically.** The system returns to `IDLE` state until the next `start` command.

### 8. `SESSION_STREAM` JetStream Configuration

```python
SESSION_STREAM_CONFIG = {
    "name": "SESSION_STREAM",
    "subjects": ["session.control"],
    "storage": StorageType.FILE,
    "retention": RetentionPolicy.LIMITS,
    "max_msgs_per_subject": 1,   # keep only the latest command
    "max_age": 60,               # 60-second TTL — stale commands are discarded
}
```

Using `max_msgs_per_subject: 1` ensures audio-producer never processes a backlog of stale start/stop commands on restart.

---

## Consequences

### Positive
- Session IDs are human-readable and stable across restarts.
- Auto-stop prevents runaway Deepgram billing after a service ends.
- Any attendee can start transcription; only admins can manually stop it.
- NATS KV provides a single authoritative source of session state for all services (api-gateway status page, health dashboard, future mobile clients).

### Negative
- Two events starting within the same minute on the same day will collide on session ID. Mitigation: the UI should display a warning and prompt for a manual suffix if `current` KV already has an `active` session when a start command is received.
- Silence-based auto-stop requires RMS computation in audio-producer, which is not yet implemented. A stub that auto-stops after a fixed wall-clock timeout (e.g., 4 hours) is acceptable as a first implementation.
- The EOS header mechanism requires stt-provider and identifier to inspect NATS message headers, which they do not currently do.

### Future Work
- Integrate Silero VAD (audio-classifier) as a smarter silence detector to replace RMS threshold.
- Add a `session.events` subject where audio-producer publishes lifecycle events (`started`, `stopped`, `silence_warning`) for the admin UI to display.

---

## References

- [ROADMAP.md — Milestone 4.5](../../ROADMAP.md)
- [ADR-0009 — NATS Migration](0009-nats-migration.md)
- [ADR-0013 — Pull Consumers and Deepgram Reconnection](0013-stt-provider-pull-consumers-and-deepgram-reconnection.md)
- [Design Review 2026-03](../design_review_2026_03.md)

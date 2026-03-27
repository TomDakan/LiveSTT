# Implementation Prompt: Pre-4.5 Hardening

This prompt is for planning and implementing the next batch of work on LiveSTT.
Paste it into a fresh conversation.

---

## Your Role

You are implementing a focused set of bug fixes and hardening changes on the LiveSTT
project. These are pre-requisites that must land before Milestone 4.5 (session control)
is built. Do not implement Milestone 4.5 features — that comes next.

## Read First (mandatory — do not skip any)

Read these files in full before writing a single line of code:

1. `CLAUDE.md` — project overview, architecture, commands, conventions
2. `docs/20_architecture/design_review_2026_03.md` — the full review findings; this is
   your work order. Pay attention to the status symbols.
3. `docs/20_architecture/adrs/0015-session-lifecycle.md` — decided session design
   (context for #5 below, do NOT implement it yet)
4. `libs/messaging/src/messaging/service.py` — BaseService
5. `libs/messaging/src/messaging/nats.py` — NatsJSManager
6. `services/identity-manager/src/identity_manager/main.py` — the fusion engine
7. `services/stt-provider/src/stt_provider/main.py` — dual-lane transcription
8. `services/api-gateway/src/api_gateway/main.py` — gateway + WebSocket
9. `services/api-gateway/src/api_gateway/static/index.html` — the UI
10. `docker-compose.yml`

## Scope of This Work

Implement exactly the items listed below, in order. Stop after item 5. Do not
add features, refactor code outside the changed area, or fix issues not on this list.

### 1. `restart: unless-stopped` on all services (CRITICAL-4)

Add `restart: unless-stopped` to `nats`, `api-gateway`, and `audio-producer` in
`docker-compose.yml`. (`stt-provider` and `identity-manager` already have it.)

### 2. Fix identity-manager: race condition + ack ordering (CRITICAL-1 + CRITICAL-2)

Two bugs in `services/identity-manager/src/identity_manager/main.py`, fix together:

**Race condition** (`_fusion_loop`): The loop currently does `self._pending = still_pending`
after iterating and awaiting publishes. Any item appended to `self._pending` during an
await is silently lost. Fix: snapshot at the top of each cycle —
`batch = self._pending; self._pending = []` — then process `batch`.

**Ack-before-processing** (`_transcript_subscriber`): Final transcripts are acked
immediately after being appended to `_pending`. If the service crashes after the ack but
before the fusion loop publishes to `transcript.final.*`, the transcript is permanently
lost. Fix: for final transcripts, ack only after `_publish()` succeeds. Use `await msg.nak()`
(or simply do not ack, letting the message redeliver) if `_publish` fails. For interim
transcripts (which call `_publish` directly before acking), ack after the publish call.

Ensure the existing tests in `services/identity-manager/tests/test_identity_manager.py`
still pass after your changes, and add tests covering:
- A final transcript appended to `_pending` during a simulated publish await is NOT lost
- A publish failure on a final transcript causes the message to be nacked (not lost)

### 3. Remove NATS port bindings (HIGH-4)

In `docker-compose.yml`, remove the `ports` block from the `nats` service entirely.
NATS ports 4222 and 8222 must not be accessible from the host or LAN. All inter-service
communication uses the `internal_overlay` Docker network.

Verify that `just nats-spy`, `just nats-tail`, and `just nats-health` still work after
this change (they use `--network=host` on a nats-box container, which accesses the host
network — these will need to be updated to use `--network livesst_internal_overlay`
or the compose network name). Update the justfile recipes accordingly.

### 4. Convert api-gateway to a JetStream durable pull consumer (CRITICAL-3)

In `services/api-gateway/src/api_gateway/main.py`, replace the core NATS subscription:

```python
await nats_client.subscribe(TRANSCRIPT_TOPIC, cb=nats_callback)
```

with a JetStream durable pull consumer on `transcript.final.>` using durable name
`api_gateway`. Use `deliver_new` as the deliver policy (the UI only needs transcripts
from when the current client connected, not historical replay — reconnect resilience
within a session is the goal, not full history). Pull in a background asyncio task
using a loop similar to the pattern in `stt-provider/_run_lane`. Broadcast received
messages to WebSocket clients exactly as the current callback does.

The gateway must still shut down cleanly via the FastAPI lifespan context manager.
The existing tests in `services/api-gateway/tests/` must continue to pass.

### 5. Show backfill transcripts in the UI (HIGH-7)

The UI in `services/api-gateway/src/api_gateway/static/index.html` currently filters
out any message where `source !== 'live'`. Remove this filter.

Instead, distinguish backfill visually:
- Backfill segments (`source === 'backfill'`) are rendered with dimmed text
  (`text-white/40` instead of `text-white/85`) and a `[PRE-ROLL]` prefix in the
  timestamp column.
- A thin horizontal separator line is inserted between the last backfill segment and
  the first live segment.
- The separator should be inserted dynamically: once the first `source === 'live'`
  `is_final` message arrives after one or more backfill messages have been rendered,
  insert the separator above it (not before — insert it once, idempotently).

No changes to the backend are needed for this item.

## Constraints

- Run `just qa` before considering any item done. All checks must pass.
- The e2e test (`just e2e`) must continue to pass end-to-end.
- Do not change any stream configurations, retention policies, or NATS subject names.
- Do not implement Milestone 4.5 (session control, `POST /session/start`, etc.).
- Do not add new dependencies unless absolutely necessary.
- Conventional commit messages: `fix:` for bug fixes, `refactor:` only if explicitly
  asked. One commit per numbered item above is a reasonable granularity.
- Never include `Co-Authored-By` trailers in commits.

## Definition of Done

All five items are implemented, `just qa` passes, `just e2e` passes, and each change
has a passing test (new or existing) that would have caught the bug it fixes.

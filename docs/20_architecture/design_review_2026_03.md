# Design Review: v8.0 Buffered Brain (March 2026)

**Reviewer**: Architecture review (Claude Code)
**Date**: 2026-03-26
**Scope**: Full codebase review covering data integrity, fault tolerance, security,
Time Zipper correctness, operational readiness, architecture gaps, testing, and code quality.

## Status Key

| Symbol | Meaning |
|--------|---------|
| 🔴 | Open — not yet addressed |
| 🟡 | Decision made — awaiting implementation |
| 🟢 | Resolved / accepted as-is with rationale |

---

## Architectural Decisions Resolved

These were open design questions raised during the review. All are now decided.

| # | Question | Decision | Reference |
|---|----------|----------|-----------|
| 1 | Should backfill (pre-roll) transcripts appear in the UI? | **Yes**, with visual distinction from live segments (e.g. dimmed, `[PRE-ROLL]` label, or separator). Late arrivals can skim context. | — |
| 2 | How should Time Zipper timestamps work? | Wall-clock matching is acknowledged as broken for backfill. **Next step**: audit Deepgram word-level `start`/`end` timestamps as audio-relative anchors; design sequence-number-based matching in a future ADR before the full identity pipeline is built. | — |
| 3 | Should session IDs be deterministic? | **Yes**. Format `YYYYMMDD-HHMM` from session start time, stored in NATS KV `session_state`. Multiple events per day are expected; no date-only scheme. | [ADR-0015](adrs/0015-session-lifecycle.md) |
| 4 | Is PRE_BUFFER loss on NATS restart acceptable? | **Yes for v8.0**. OTA updates should be scheduled off-hours. A `TODO` comment is sufficient for now; future improvement could snapshot pre-roll periodically. | — |
| 5 | Should session start/stop be authenticated? | **Asymmetric**: start is unauthenticated (any attendee can start); manual stop requires admin JWT (prevents one user silencing the feed for everyone). Auto-stop on 5-minute silence is the default. | [ADR-0015](adrs/0015-session-lifecycle.md) |

---

## Findings

### 🟢 Critical — Resolved

---

**[CRITICAL-1] identity-manager acks messages before they are fused and published**
Files: [identity-manager/main.py](../../../services/identity-manager/src/identity_manager/main.py) lines 84–96

`_transcript_subscriber` appends a final transcript to the in-memory `_pending` list and
immediately calls `await msg.ack()`. The fusion loop processes `_pending` asynchronously.
If identity-manager crashes after the ack but before `_fusion_loop` calls `_publish()`,
the transcript is permanently lost — NATS considers it consumed.

*Impact*: Silent transcript loss on any identity-manager crash.

*Recommendation*: Ack final transcripts only after `transcript.final.*` is successfully
published. Use NATS `nak()` to requeue on failure, or implement a write-ahead approach
(publish first, ack second).

🟢 **Resolved**: Final transcripts are now acked only after `_publish()` succeeds; failures call `msg.nak()`.

---

**[CRITICAL-2] Race condition in fusion loop silently drops transcripts**
Files: [identity-manager/main.py](../../../services/identity-manager/src/identity_manager/main.py) lines 148–165

`_fusion_loop` iterates over `self._pending` and calls `await self._publish(...)` inside
the loop. That `await` yields control, allowing `_transcript_subscriber` to append to the
same list. When the loop finishes and executes `self._pending = still_pending`, the
newly appended items — which were added to the old list object — are silently discarded.

*Impact*: Any final transcript arriving during a publish is permanently dropped. Under
normal speech load this is reliably reproducible.

*Recommendation*: Snapshot at the top of each cycle: `batch = self._pending;
self._pending = []`. Process `batch`; new arrivals go into the fresh `self._pending`
and are picked up next iteration.

🟢 **Resolved**: `_fusion_loop` now snapshots with `batch = self._pending; self._pending = []` at the top of each cycle.

---

**[CRITICAL-3] api-gateway uses a core NATS subscription, not a JetStream durable consumer**
Files: [api-gateway/main.py](../../../services/api-gateway/src/api_gateway/main.py) line 70

`nats_client.subscribe(TRANSCRIPT_TOPIC, cb=nats_callback)` is a core NATS subscription.
It only receives messages published *after* the subscription is established. Any transcript
published while api-gateway is restarting is never delivered — no replay, no catch-up.

*Impact*: Every api-gateway restart creates a permanent gap in the WebSocket feed. No
transcript history is recoverable.

*Recommendation*: Replace with a JetStream durable pull consumer on `transcript.final.>`
(`deliver_new` or `deliver_last_per_subject` as appropriate). This is consistent with
how stt-provider and identity-manager consume their subjects.

🟢 **Resolved**: api-gateway now uses a JetStream durable pull consumer (`deliver_new`, durable name `api_gateway`).

---

**[CRITICAL-4] audio-producer, api-gateway, and nats have no `restart: unless-stopped`**
Files: [docker-compose.yml](../../../docker-compose.yml) lines 14–49

Only `stt-provider` and `identity-manager` have a restart policy. If audio-producer
crashes during a live service, all audio capture stops silently with no alert and no
self-healing. NATS has no restart policy — a NATS crash takes down the entire pipeline.

*Impact*: A single crash of the most hardware-dependent service (audio-producer) permanently
silences transcription for the rest of the service.

*Recommendation*: Add `restart: unless-stopped` to all services. This is already noted in
Milestone 7.5 of the roadmap; it should be treated as a hotfix, not a milestone item.

🟢 **Resolved**: All services now have `restart: unless-stopped` in `docker-compose.yml`.

---

### 🔴 High — Will fail under foreseeable conditions

---

**[HIGH-1] NATS consumer position silently advances past aged-out messages (>1 hour outage)**
Files: [streams.py](../../../libs/messaging/src/messaging/streams.py) line 38,
[ADR-0011](adrs/0011-retention-policy.md)

When a Deepgram outage exceeds 1 hour, audio messages age out of `AUDIO_STREAM`
(`max_age = 3600s`). NATS silently advances the durable consumer to the oldest surviving
message. No error is logged by stt-provider. Audio from the beginning of the outage is
permanently lost with no operator indication.

*Impact*: A 90-minute outage silently loses 30 minutes of audio with no log entry or alert.

*Recommendation*: On Deepgram reconnect, compare the consumer's pending sequence against
the stream's first available sequence (available via JetStream consumer info API). If the
consumer has fallen behind the stream head, log a structured WARNING with the estimated
lost duration.

🟢 **Resolved**: After each `_connect_with_retry`, `stt-provider` queries `consumer_info()` and `stream_info("AUDIO_STREAM")` and logs a structured WARNING with estimated lost seconds when the consumer sequence lags the stream head.

---

**[HIGH-2] Transcript timestamps are publish-time, not audio-capture-time**
Files: [stt-provider/main.py](../../../services/stt-provider/src/stt_provider/main.py) line 176,
[identifier/main.py](../../../services/identifier/src/identifier/main.py) line 129

Both `TranscriptPayload.timestamp` and the identifier's identity event timestamp are set
to `datetime.now(UTC)` at publish time. During backfill (5 minutes of pre-roll arriving
in a burst), hundreds of events are published within seconds with nearly identical
timestamps. The Time Zipper's `_find_identity` becomes non-deterministic over this dense set.

*Impact*: The "time travel" backfill feature produces incorrect or random speaker attribution
for all pre-roll audio. Catch-up transcripts also display with wrong timestamps in the UI
(all show the reconnection moment, not when speech occurred).

*Recommendation* (deferred pending Deepgram API audit): Deepgram returns word-level
`start`/`end` timestamps relative to the audio stream. Propagate those, alongside the NATS
message sequence number of the first audio chunk in the transcript, through to the
identity-manager. Match on sequence overlap rather than wall-clock proximity. Capture
this as a separate ADR before the full identity pipeline is built.

---

**[HIGH-3] stt-provider shutdown hangs when `transcriber.finish()` is suppressed**
Files: [stt-provider/main.py](../../../services/stt-provider/src/stt_provider/main.py) lines 153–156

The `finally` block suppresses all exceptions from `transcriber.finish()`. If `finish()`
raises, `_on_close` never fires, no `None` sentinel enters `_event_queue`, and
`await drain_task` blocks indefinitely. The service hangs until Docker's SIGKILL timeout.

*Impact*: On any abnormal Deepgram disconnection the service stalls for ~10 seconds,
during which no audio is consumed.

*Recommendation*: Replace `contextlib.suppress(Exception)` with explicit exception logging.
Add `await asyncio.wait_for(drain_task, timeout=5.0)` with a fallback cancel.

🟢 **Resolved**: `finish()` now logs a WARNING on exception instead of suppressing; `drain_task` is wrapped in `asyncio.wait_for(..., timeout=_DRAIN_TIMEOUT_S)` with cancel-on-timeout fallback.

---

**[HIGH-4] NATS ports 4222 and 8222 exposed on all interfaces — no authentication**
Files: [docker-compose.yml](../../../docker-compose.yml) lines 7–8

Ports 4222 (client) and 8222 (HTTP management) are bound to `0.0.0.0`, making them
reachable from the church LAN. Any LAN device can subscribe to raw audio PCM, publish
fake transcripts, or inspect stream configuration via the management API. NATS has no
authentication configured.

*Impact*: Privacy (raw speech accessible on LAN), integrity (fake transcripts injectable),
and information leakage (internal architecture visible).

*Recommendation*: Remove the `ports` block for NATS entirely. No service outside the
Docker bridge network needs direct NATS access. Debug via `docker exec` or Balena SSH.

🟢 **Resolved**: `ports` block removed from the `nats` service in `docker-compose.yml`. `just nats-spy/nats-tail/nats-health` updated to use `--network container:nats`.

---

**[HIGH-5] identity-manager matched identity events are never removed from the pool**
Files: [identity-manager/main.py](../../../services/identity-manager/src/identity_manager/main.py) lines 128–146

After `_find_identity` matches an identity event to a transcript, the event remains in
`_identities`. It can match subsequent transcripts indefinitely until evicted by the
500-item cap. Backfill and live identity events share the same unsegregated list.

*Impact*: A backfill identity event (e.g., "Pastor Mike" from pre-roll) contaminates live
transcript attribution for all transcripts within 2.0 seconds of its timestamp.

*Recommendation*: Segregate `_identities` by `source` (live vs. backfill). Mark matched
events as consumed to prevent re-use. Use `collections.deque` with `maxlen` per source.

🟢 **Resolved**: `_identities` replaced with `_live_identities` and `_backfill_identities` deques (maxlen=MAX_BUFFER each); `_identity_subscriber` routes by `source`; `_find_identity` searches only the matching pool.

---

**[HIGH-6] Heartbeat loop exits on first exception and never restarts**
Files: [service.py](../../../libs/messaging/src/messaging/service.py) lines 64–77

The `except Exception` block in `_heartbeat_task` is at the function's outer scope,
outside the while loop. Any escaped exception causes the coroutine to return permanently.
The KV entry expires after 5s TTL; the service appears dead to health monitoring even
if its business logic is running correctly.

*Impact*: Health dashboard becomes unreliable, operators learn to ignore it.

*Recommendation*: Move try/except inside the while loop so individual failures are retried
on the next 2-second tick.

🟢 **Resolved**: `try/except` moved inside the `while` loop in `_heartbeat_task`; transient put failures are logged and retried on the next 2-second tick.

---

**[HIGH-7] Backfill transcripts silently filtered from UI — no operator visibility on failure**
Files: [index.html](../../../services/api-gateway/src/api_gateway/static/index.html) line 218

The UI filters `source !== 'live'`. Per the resolved design decision (§1 above), backfill
*should* be shown. Additionally, if backfill transcription fails silently, operators have
no indication.

*Impact*: 5 minutes of pre-roll audio may be transcribed incorrectly or not at all with
no operator-visible indication. Late arrivals lose the promised context.

*Recommendation*: Remove the source filter. Render backfill segments with a distinct
visual style (dimmed, `[PRE-ROLL]` timestamp prefix, or a separator line). Publish a
`session.events` NATS message when the backfill consumer is exhausted so the UI can show
"Pre-roll complete ✓" or "Pre-roll failed ⚠".

🟢 **Resolved**: UI now renders backfill with dimmed text, `[PRE-ROLL]` timestamp prefix, and a separator line before the first live segment.

---

### 🔴 Medium — Degraded behaviour or operational difficulty

---

**[MEDIUM-1] `ensure_stream` silently continues on double failure — stream may not exist**
Files: [nats.py](../../../libs/messaging/src/messaging/nats.py) lines 54–63

If both `add_stream` and `update_stream` fail, `ensure_stream` logs a warning and returns
normally. Calling services continue to publish to a stream that may not exist.

*Recommendation*: Raise an exception on double failure so calling services halt cleanly
rather than publishing into a void.

🟢 **Resolved**: `ensure_stream` now raises `RuntimeError` on double failure instead of logging a warning.

---

**[MEDIUM-2] `ConnectionManager.broadcast()` never disconnects stuck WebSocket clients**
Files: [api-gateway/main.py](../../../services/api-gateway/src/api_gateway/main.py) lines 39–44

`contextlib.suppress(Exception)` silently ignores all send errors. Clients that drop
without a clean close frame accumulate in `active_connections` indefinitely, generating
a suppressed error on every broadcast.

*Recommendation*: Track per-connection failure counts; disconnect after a threshold.
Add WebSocket ping/pong to detect dead connections proactively.

🟢 **Resolved**: `broadcast()` now collects failed connections in a `dead` list and calls `disconnect()` on each after iterating.

---

**[MEDIUM-3] Audio-producer `js.publish()` has no error handling**
Files: [audio-producer/main.py](../../../services/audio-producer/src/audio_producer/main.py) lines 91–95

A NATS publish failure raises an unhandled exception that terminates `run_business_logic`.
Without `restart: unless-stopped` (see CRITICAL-4), this permanently stops audio capture.

*Recommendation*: Wrap publishes in try/except, log errors, and continue the loop.

🟢 **Resolved**: Both `js.publish()` calls in `audio-producer` are wrapped in try/except; errors are logged and the loop continues.

---

**[MEDIUM-4] Catch-up transcripts display with wrong timestamps in the UI**
Files: [stt-provider/main.py](../../../services/stt-provider/src/stt_provider/main.py) line 176

After a Deepgram outage, catch-up transcripts are published with `datetime.now(UTC)` —
the reconnection moment. All 5 minutes of catch-up appear with the same timestamp,
making the transcript record useless as an accessibility or archiving artefact.

*Recommendation*: Embed audio capture timestamps in NATS message headers (see HIGH-2).
Short-term: use Deepgram's word-level `start` offset plus the connection's start wall time
to reconstruct an approximate capture timestamp.

---

**[MEDIUM-5] Deployment checklist missing critical production-readiness checks**
Files: [deployment_checklist.md](../../60_ops/deployment_checklist.md)

Missing steps: verify `restart: unless-stopped` on all services; verify NATS ports are
NOT accessible from a LAN device; test audio-producer crash-and-restart mid-session;
test api-gateway restart with active WebSocket clients; confirm BalenaOS persistent
volume is mounted (not just writable).

*Recommendation*: Add the missing steps. The WER score line should note that Milestone 0.5
(gold-standard data) is a prerequisite and link to it.

---

**[MEDIUM-6] Interim transcripts stored in `TRANSCRIPTION_STREAM` for 7 days**
Files: [streams.py](../../../libs/messaging/src/messaging/streams.py) lines 41–52

Deepgram emits interim results at ~100–200ms intervals. Over a 2-hour service this
generates ~36,000–72,000 interim messages. Stored for 7 days across 52 services/year
this approaches 1GB/year in data with zero long-term value.

*Recommendation*: Either publish only `is_final: true` transcripts to the persistent stream,
or use a separate short-lived stream (1-hour retention) for interim results.

---

**[MEDIUM-7] `ALLOWED_ORIGINS` defaults to `http://localhost:3000` — wrong for production**
Files: [api-gateway/main.py](../../../services/api-gateway/src/api_gateway/main.py) line 87

The default CORS origin is a React dev server. Production access from the church LAN
(e.g. `http://192.168.1.100:8000`) is not covered. docker-compose does not set this.

*Recommendation*: Default to `*` for this LAN appliance (all access is local) or
document the correct value; set it explicitly in docker-compose.

🟢 **Resolved**: `ALLOWED_ORIGINS` default changed to `"*"`.

---

**[MEDIUM-8] Tailwind CSS loaded from external CDN — no SRI hash**
Files: [index.html](../../../services/api-gateway/src/api_gateway/static/index.html) line 7

The UI fails to render (unstyled) during internet outages. No Subresource Integrity hash
means a CDN compromise could inject arbitrary JavaScript.

*Recommendation*: Bundle the Tailwind output as a static asset during the Docker build.

🟢 **Resolved**: api-gateway Dockerfile adds a `tailwind-builder` stage that downloads the Tailwind standalone CLI and generates `tailwind.css`; `index.html` loads it via `<link>` instead of the CDN script tag.

---

**[MEDIUM-9] Deepgram `keywords` parameter is deprecated in Nova-3**
Files: [ROADMAP.md](../../../ROADMAP.md) lines 104–115

Milestone 7 plans `keywords` for vocabulary boosting. Nova-3 uses `keyterm`. Additionally,
`find_and_replace` post-processing is more reliable than probability boosting for proper
nouns (speaker names, sermon titles).

*Recommendation*: Verify current Nova-3 API docs before implementing Milestone 7.
Implement `find_and_replace` as the primary correction path; use `keyterm` as supplementary.

---

**[MEDIUM-10] Session control command is ephemeral — start command lost on audio-producer restart**

Now resolved by ADR-0015, which specifies `SESSION_STREAM` with `max_msgs_per_subject: 1`
and a 60-second TTL, plus NATS KV for persistent session state. 🟡 Awaiting implementation.

---

### 🔴 Low — Improvement opportunity or minor inconsistency

---

**[LOW-1] `SUBJECT_PREFIX_AUDIO_BACKFILL` defined twice in streams.py**
Files: [streams.py](../../../libs/messaging/src/messaging/streams.py) lines 8 and 10

Duplicate constant definition (same value). Harmless but confusing.

*Recommendation*: Remove the duplicate on line 10.

🟢 **Resolved**: Duplicate `SUBJECT_PREFIX_AUDIO_BACKFILL` definition removed.

---

**[LOW-2] `_on_error` in Deepgram adapter does not signal the fetch loop**
Files: [deepgram_adapter.py](../../../services/stt-provider/src/stt_provider/deepgram_adapter.py) line 87–88

Deepgram error events are logged but do not trigger reconnection. A degraded connection
that sends errors without closing continues to receive audio silently dropped by Deepgram.

*Recommendation*: In `_on_error`, put `None` into `_event_queue` to trigger the same
shutdown-and-reconnect path as `_on_close`.

🟢 **Resolved**: `_on_error` now puts `None` into `_event_queue`, triggering the same reconnect path as `_on_close`.

---

**[LOW-3] WebSocket endpoint has no connection limit**
Files: [api-gateway/main.py](../../../services/api-gateway/src/api_gateway/main.py) lines 107–126

No cap on concurrent connections. Low risk on a church LAN but `active_connections` can
accumulate stuck clients indefinitely (see MEDIUM-2).

*Recommendation*: Add a `MAX_WS_CONNECTIONS` limit (e.g. 50). Reject new connections
above the limit with HTTP 503.

---

**[LOW-4] `DEEPGRAM_API_KEY` visible via `docker inspect`**
Files: [docker-compose.yml](../../../docker-compose.yml) line 59

Env vars are readable by anyone with Docker CLI access on the device. Acceptable given
BalenaOS SSH access controls, but worth noting.

*Recommendation*: Acceptable for v8.0. Long-term, consider Docker secrets or Balena's
secrets API.

---

**[LOW-5] health-watchdog is a stub — no action on missed heartbeats**

The heartbeat mechanism (KV put every 2s, 5s TTL) is implemented in BaseService.
The health-watchdog service that reads it is a stub that takes no action. The health
dashboard planned in Milestone 6.5 will consume this data.

*Recommendation*: No immediate action required; ensure health-watchdog is not listed as
a production dependency before it is implemented.

---

**[LOW-6] data-sweeper adds no enforcement — NATS `max_age` handles retention**

NATS JetStream enforces retention automatically. The data-sweeper as described in the
roadmap is purely observational reporting that duplicates what `nats server report streams`
already provides.

*Recommendation*: Either give data-sweeper a meaningful purpose (e.g. emit disk-usage
metrics to NATS KV for the admin dashboard) or remove it from the architecture.

---

## Top 5 Production-Blocking Items (Ordered)

All resolved as of 2026-03-27.

1. 🟢 **CRITICAL-4** — `restart: unless-stopped` added to all services.
2. 🟢 **CRITICAL-1 + CRITICAL-2** — Identity-manager ack ordering and fusion loop race condition fixed.
3. 🟢 **HIGH-4** — NATS port bindings removed from docker-compose.
4. 🟢 **CRITICAL-3** — api-gateway converted to JetStream durable pull consumer.
5. 🟢 **HIGH-7** — Backfill transcripts shown in UI with visual distinction.

---

## Open ADR Work

| Topic | Status | Reference |
|-------|--------|-----------|
| Session lifecycle (ID format, start/stop auth, auto-stop, EOS, KV state) | 🟡 Decided, awaiting implementation | [ADR-0015](adrs/0015-session-lifecycle.md) |
| Time Zipper timestamp matching (audio-relative via Deepgram word offsets) | 🔴 Needs Deepgram API audit + new ADR | — |
| Custom vocabulary — `keyterm` vs `find_and_replace` for Nova-3 | 🔴 Needs investigation before Milestone 7 | — |

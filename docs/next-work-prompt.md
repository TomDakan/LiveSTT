# Implementation Prompt: Resilience Hardening (Batch 2)

This prompt is for the next batch of work on LiveSTT. Paste it into a fresh conversation.

---

## Your Role

You are implementing the remaining open findings from the March 2026 design review.
After this batch, the review will be clear and the codebase will be ready for
Milestone 4.5 (Session Control). Do not implement any Milestone 4.5 features.

## Read First (mandatory — do not skip any)

1. `CLAUDE.md` — project conventions, commands, architecture summary
2. `docs/20_architecture/design_review_2026_03.md` — your work order; focus on items
   still marked 🔴
3. `services/stt-provider/src/stt_provider/main.py`
4. `services/stt-provider/src/stt_provider/deepgram_adapter.py`
5. `services/identity-manager/src/identity_manager/main.py`
6. `libs/messaging/src/messaging/service.py`
7. `libs/messaging/src/messaging/nats.py`
8. `libs/messaging/src/messaging/streams.py`
9. `services/api-gateway/src/api_gateway/main.py`
10. `services/audio-producer/src/audio_producer/main.py`
11. `services/api-gateway/src/api_gateway/static/index.html`

**HIGH-2 is explicitly deferred** — timestamp semantics require a Deepgram API audit
and a new ADR before implementation. Do not attempt it here.

## Scope of This Work

Implement the items below in order. Mark each as 🟢 in `design_review_2026_03.md`
when done. Stop after item 6.

---

### 1. Fix stt-provider shutdown hang (HIGH-3)

File: `services/stt-provider/src/stt_provider/main.py`

The `finally` block in `_run_lane` suppresses all exceptions from
`transcriber.finish()`. If `finish()` raises, `_on_close` never fires, no `None`
enters `_event_queue`, and `await drain_task` blocks forever.

Two fixes:

**a)** Replace `contextlib.suppress(Exception)` on `finish()` with explicit logging:
```python
try:
    await transcriber.finish()
except Exception as e:
    self.logger.warning(f"[{source_tag}] finish() failed: {e}")
```

**b)** Add a timeout to `await drain_task` so a stuck drain never hangs shutdown:
```python
try:
    await asyncio.wait_for(drain_task, timeout=5.0)
except TimeoutError:
    self.logger.warning(f"[{source_tag}] drain_task timed out; cancelling")
    drain_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await drain_task
```

Add or update tests in `services/stt-provider/tests/` to verify that a `finish()`
exception does not cause `_run_lane` to hang.

---

### 2. Fix Deepgram error events don't trigger reconnect (LOW-2)

File: `services/stt-provider/src/stt_provider/deepgram_adapter.py`

`_on_error` logs the error but does not signal the fetch loop. A degraded Deepgram
connection that sends error events without closing continues to receive audio that
Deepgram silently drops.

Put `None` into `_event_queue` in `_on_error` so it triggers the same
shutdown-and-reconnect path as `_on_close`:

```python
async def _on_error(self, error: Any, **kwargs: Any) -> None:
    logger.error(f"Deepgram Error: {error}")
    await self._event_queue.put(None)
```

---

### 3. Fix identity-manager: source segregation for identity events (HIGH-5)

File: `services/identity-manager/src/identity_manager/main.py`

All identity events (live and backfill) are stored in a single `_identities` list.
A backfill identity event can match a live transcript and vice versa, producing wrong
speaker attribution at session start (the highest-traffic moment).

Changes:

**a)** Replace `self._identities: list[dict[str, Any]]` with two source-specific
deques:
```python
from collections import deque
self._live_identities: deque[dict[str, Any]] = deque(maxlen=MAX_BUFFER)
self._backfill_identities: deque[dict[str, Any]] = deque(maxlen=MAX_BUFFER)
```

**b)** In `_identity_subscriber`, route incoming events by source:
```python
source = data.get("source", "live")
if source == "backfill":
    self._backfill_identities.append(data)
else:
    self._live_identities.append(data)
```
Remove the old `MAX_BUFFER` cap check (deque `maxlen` handles it).

**c)** Update `_find_identity` to accept a `source` parameter and search only the
matching deque:
```python
def _find_identity(
    self, transcript_ts: str | None, source: str = "live"
) -> dict[str, Any] | None:
    pool = (
        self._backfill_identities
        if source == "backfill"
        else self._live_identities
    )
    ...
```

**d)** In `_fusion_loop`, pass the transcript's source when calling `_find_identity`:
```python
source = pending.data.get("source", "live")
identity = self._find_identity(pending.data.get("timestamp"), source=source)
```

Update the existing tests and add a test verifying that a backfill identity event
does not match a live transcript.

---

### 4. Detect and log audio gap after >1 hour Deepgram outage (HIGH-1)

File: `services/stt-provider/src/stt_provider/main.py`

When a durable consumer reconnects after messages have aged out of `AUDIO_STREAM`,
NATS silently advances the consumer's position. There is no existing code to detect
or log this.

After each successful `_connect_with_retry`, query the JetStream consumer info to
compare the consumer's pending deliver sequence against the stream's first available
sequence. If the consumer is behind the stream head, log a structured WARNING:

```python
# After transcriber = await self._connect_with_retry(...)
try:
    info = await sub.consumer_info()
    stream_info = await js.stream_info("AUDIO_STREAM")
    first_seq = stream_info.state.first_seq
    consumer_seq = info.delivered.stream_seq
    if consumer_seq < first_seq:
        gap_msgs = first_seq - consumer_seq
        # At 96ms/chunk, estimate lost duration
        lost_s = gap_msgs * 0.096
        self.logger.warning(
            f"[{source_tag}] Audio gap detected: ~{lost_s:.0f}s of audio "
            f"aged out during outage (consumer was at seq {consumer_seq}, "
            f"stream now starts at {first_seq})"
        )
except Exception as e:
    self.logger.debug(f"[{source_tag}] Could not check consumer lag: {e}")
```

This is a detection-and-log change only — no data recovery is attempted (the gap is
irrecoverable by design per ADR-0011). The `except` block is intentionally broad and
non-fatal: consumer info is advisory.

---

### 5. Quick fixes (commit as one or individually — all small)

These are all one-to-five line changes. Address them together:

**a) Heartbeat loop retry (HIGH-6)**
File: `libs/messaging/src/messaging/service.py`

The `except Exception` in `_heartbeat_task` is outside the while loop — any exception
permanently stops the heartbeat. Move it inside so transient errors are retried:

```python
while not self.stop_event.is_set():
    try:
        payload = ...
        await self.kv.put(self.service_name, payload)
        await asyncio.sleep(2)
    except Exception as e:
        self.logger.warning(f"Heartbeat tick failed (will retry): {e}")
        await asyncio.sleep(2)
```

Keep the outer `create_key_value` call outside the loop (run once at startup); only
the put/sleep cycle moves inside.

**b) `ensure_stream` raises on double failure (MEDIUM-1)**
File: `libs/messaging/src/messaging/nats.py`

Change the final `logger.warning` to `raise RuntimeError(...)` so calling services
fail fast rather than publishing to a non-existent stream.

**c) audio-producer publish error handling (MEDIUM-3)**
File: `services/audio-producer/src/audio_producer/main.py`

Wrap both `js.publish()` calls in the audio loop with try/except. Log the error and
`continue` — losing a single chunk is better than crashing the loop:

```python
try:
    await js.publish(subject, chunk)
except Exception as e:
    self.logger.error(f"Publish failed (chunk dropped): {e}")
```

**d) CORS default (MEDIUM-7)**
File: `services/api-gateway/src/api_gateway/main.py`

Change the default `ALLOWED_ORIGINS` from `"http://localhost:3000"` to `"*"`.
This is a LAN appliance; all HTTP access is local:
```python
ALLOW_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
```

**e) Remove duplicate constant (LOW-1)**
File: `libs/messaging/src/messaging/streams.py`

`SUBJECT_PREFIX_AUDIO_BACKFILL` is defined on two consecutive lines. Remove the
duplicate (line 10).

**f) Disconnect stuck WebSocket clients (MEDIUM-2)**
File: `services/api-gateway/src/api_gateway/main.py`

`broadcast()` silently suppresses all send errors; failed clients accumulate
indefinitely. Track failures and disconnect after a threshold:

```python
async def broadcast(self, message: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for connection in list(self.active_connections):
        try:
            await connection.send_json({"type": "transcript", "payload": message})
        except Exception:
            dead.append(connection)
    for connection in dead:
        self.disconnect(connection)
```

---

### 6. Bundle Tailwind CSS as a static asset (MEDIUM-8)

File: `services/api-gateway/src/api_gateway/static/index.html` and
`services/api-gateway/Dockerfile`

The UI currently loads Tailwind from `https://cdn.tailwindcss.com`. On a church
appliance, the UI must work even when the internet is down (Deepgram outage mode).
A CDN fetch failure leaves the UI unstyled.

**a)** In the api-gateway Dockerfile, add a build step that downloads the Tailwind
standalone CLI and generates `static/tailwind.css` from the classes used in
`index.html`:

```dockerfile
# Download Tailwind standalone CLI and generate CSS
RUN curl -sLo /tmp/tailwindcss \
      https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x /tmp/tailwindcss \
    && /tmp/tailwindcss \
         --input /dev/null \
         --content /app/services/api-gateway/src/api_gateway/static/index.html \
         --output /app/services/api-gateway/src/api_gateway/static/tailwind.css \
         --minify
```

**b)** In `index.html`, replace:
```html
<script src="https://cdn.tailwindcss.com"></script>
```
with:
```html
<link rel="stylesheet" href="/static/tailwind.css">
```

Verify the UI renders correctly after `just up-build`.

---

## After All Items Are Done

1. Update `docs/20_architecture/design_review_2026_03.md`: mark each completed item
   🟢 with a one-line resolution note.
2. Run `just qa` — all checks must pass.
3. Run `just e2e` — must pass end-to-end.
4. One commit per numbered item is appropriate. Never include `Co-Authored-By` trailers.

## What Comes Next (do NOT implement now)

After this batch the next work is **Milestone 4.5: Session Control**. See
`docs/20_architecture/adrs/0015-session-lifecycle.md` for the full design and
`ROADMAP.md` for the feature checklist. A new implementation prompt will be written
before that work begins.

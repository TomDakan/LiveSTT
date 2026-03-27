# STT Provider Pull Consumers and Deepgram Reconnection

**Date**: 2026-03-26
**Status**: ACCEPTED

**Context**:
The original `stt-provider` used ephemeral JetStream push subscriptions (queue group, no durable name). This created two problems:

1. **No position tracking**: Without a durable consumer, NATS does not persist the consumer's read position. If the service restarts, it begins consuming from the current head of the stream — audio buffered during the downtime is silently skipped.

2. **No Deepgram resilience**: Audio arrived via push callbacks regardless of whether Deepgram was reachable. If `connect()` failed at startup, the service exited. If Deepgram dropped mid-session, `send_audio()` failed silently while the push subscription continued delivering chunks that were never transcribed.

This defeated the offline buffering rationale in ADR-0009, which states JetStream persistence allows services to "catch up after restart or network outage."

**Decision**:
Switch `stt-provider` to JetStream durable pull consumers (`durable="stt_live"` / `durable="stt_backfill"`). Audio chunks are only fetched from NATS (`sub.fetch()`) when a live Deepgram WebSocket connection exists. Deepgram connections use exponential backoff retry (initial 2s, max 60s, doubling each attempt). The service never exits on Deepgram failure — it retries until either connectivity is restored or a shutdown signal arrives.

The lane structure is:
1. Subscribe once with a durable name (position persists across restarts)
2. Outer reconnect loop: call `_connect_with_retry` → get a live Deepgram connection
3. Inner fetch loop: pull audio from NATS, send to Deepgram, ACK only after successful send
4. On Deepgram disconnect (send failure or clean close): exit inner loop, call `finish()`, reconnect

**Consequences**:
- **Positive**: Audio is never lost during Deepgram outages up to the AUDIO_STREAM 1-hour retention window (ADR-0011). Service restarts resume from the last ACKed message position.
- **Positive**: No application-level audio buffering needed — JetStream handles it transparently.
- **Positive**: Deepgram reconnect is automatic and self-healing; operators only need to ensure DEEPGRAM_API_KEY is valid.
- **Negative**: Transcription output is delayed (not dropped) during outages. Live display will show a gap, then catch up in near-real-time once Deepgram reconnects.
- **Negative**: Pull consumers introduce slightly higher latency than push (one `fetch` round-trip per chunk), negligible at 96ms chunk intervals (ADR-0012).

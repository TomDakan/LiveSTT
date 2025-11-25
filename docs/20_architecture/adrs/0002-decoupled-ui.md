# Split stt-provider from api-gateway (Decoupled UI)

* **Status:** Accepted
* **Date:** 2025-11-19
* **Supersedes:** Version 5.x architecture (monolithic "Brain" service)

---

## Context

In system design Version 5.x, the `api-gateway` service handled both:
1. **UI/Orchestration**: Serving the web interface, managing WebSocket connections, storing config in SQLite
2. **Transcription**: Managing the Deepgram WebSocket  connection, handling reconnection logic, buffering audio

This created a **failure domain coupling**: if the Deepgram client crashed (e.g., due to a network error or API bug), the entire UI would become unresponsive, preventing admins from diagnosing the issue or manually recovering the system.

**Problem Statement**: The kiosk UI must remain live and manageable even if the transcription engine encounters a fatal error or network outage.

---

## Decision

We will **split transcription logic into a separate `stt-provider` service** (Version 6.0).

### New Architecture
```
audio-producer → audio-broker → stt-provider (Deepgram client)
                                    ↓ (publishes text.transcript)
                              audio-broker → api-gateway (UI)
```

### Responsibilities
| Service | Role | Cannot Touch |
|---------|------|--------------|
| **stt-provider** | Cloud integration, resilience, QA | Web UI, config DB |
| **api-gateway** | Web UI, config, correlation | Raw audio, Deepgram API |

### Communication
- `stt-provider` subscribes to `audio.raw` from broker
- `stt-provider` publishes `text.transcript` and `system.alert` to broker
- `api-gateway` subscribes to `text.transcript` and `system.alert`

---

## Consequences

### Positive
- **Fault isolation**: Deepgram SDK crash does not affect UI responsiveness
- **Independent scaling**: `stt-provider` can be restarted without dropping WebSocket connections to clients
- **Clear separation of concerns**: `api-gateway` has no audio processing code
- **Improved testability**: Can mock `text.transcript` events to test UI without Deepgram API

### Negative
- **Additional container**: One more service to monitor (mitigated by `health-watchdog`)
- **Increased complexity**: Correlation logic must be added to `api-gateway` (maps Speaker 0 → Tom via identity events)

### Risks and Mitigations
- **Risk**: Broker becomes bottleneck
  - **Mitigation**: ZMQ is designed for high-throughput IPC, benchmarked at \>1M msg/s
- **Risk**: Message ordering issues (transcript arrives before identity event)
  - **Mitigation**: Timestamps in payloads, `api-gateway` maintains correlation buffer

### Impact on Security
- **Benefit**: `api-gateway` cannot be compromised via audio buffer overflow attacks (no raw audio access)
- **Trade-off**: More attack surface (two services vs. one), mitigated by container isolation

---

## Alternatives Considered

### Alternative 1: Keep Monolithic Brain
**Why rejected**:
- Single point of failure violates high-availability requirement
- Difficult to debug transcription issues when UI is frozen

### Alternative 2: Run stt-provider in Separate Thread (Not Container)
**Why rejected**:
- Python threading does not provide crash isolation (one uncaught exception crashes process)
- Cannot independently restart transcription logic without restarting UI

### Alternative 3: Use Supervisor (systemd-style Process Manager)
**Why rejected**:
- Adds complexity vs. Docker's built-in `restart: always`
- Does not provide network-level isolation

---

## References

- [System Design V6.0](../../system_design.md) - Section 3 (Component Design)
- [Architecture Definition](../architecture_definition.md) - Component interaction diagram
- [Roadmap](../../roadmap_draft.md) - Phase 2 (M3: stt-provider implementation)

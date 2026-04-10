# Test Documentation vs. Implementation Audit

**Date:** 2026-04-09
**Branch:** feat/ops/quick-wins
**Reviewer:** Code-reviewer agent

---

## 1. Test Case Traceability Table

| Source | Test Description | Status | Test File | Priority |
|--------|-----------------|--------|-----------|----------|
| Traceability (FR-003) | Capture audio from USB (16kHz PCM) | Partial | `test_audioproducer.py`, `test_audiosource.py` (mocked) | Medium |
| Traceability (FR-004) | Stream audio to Deepgram via WebSocket | Implemented | `test_deepgram_adapter.py`, `test_stt_provider.py` | -- |
| Traceability (FR-005) | Display transcripts <500ms latency | Missing | N/A | Medium |
| Traceability (FR-007) | Buffer audio during internet outages | Partial | `test_stt_error_handling.py` (retry only, no catchup) | **High** |
| Traceability (FR-008) | Catch up on buffered audio | Partial | `test_stt_provider.py` (backfill model tested) | -- |
| Traceability (FR-012) | Speaker ID via voiceprint | Partial | `test_pipeline.py`, `test_embedder.py` (unit mocks only) | Medium |
| Traceability (FR-013) | Label transcripts with speaker names | Implemented | `test_identity_manager.py` | -- |
| Traceability (NFR-003) | 99.9% uptime via restart/decoupling | Partial | `test_health_watchdog.py` (detection only) | -- |
| Traceability (NFR-004) | UI responsive during stt-provider crash | Missing | N/A | Medium |
| Traceability (NFR-008) | No plaintext API keys in logs | Missing | N/A | **High** |
| Traceability (NFR-013) | 30 concurrent WebSocket clients | Missing | N/A | Low |
| Master Plan 3.1 | Unit tests 80% coverage | Partial | Threshold is 75% (lowered in `abf79e0`) | Medium |
| Master Plan 3.2 | Audio->Broker->STT->Gateway integration | **Stale** | `test_e2e.py` -- both tests `@skip` | **High** |
| Master Plan 3.2 | DB persistence of transcripts | Missing | N/A | **High** |
| Master Plan 3.2 | Error handling (Deepgram timeout) | Implemented | `test_stt_error_handling.py` | -- |
| CI/CD 5.2 | Integration tests via docker-compose.test.yml | Missing | File doesn't exist | **High** |
| ADR-0015 | Session lifecycle state machine | Implemented | `test_session_state_machine.py` (28 tests) | -- |
| ADR-0015 | KV recovery on restart | Implemented | `test_session_state_machine.py` (4 tests) | -- |
| ADR-0016 | Admin auth (bcrypt, JWT, dev-mode) | Implemented | `test_auth_and_status.py` | -- |
| ADR-0016 | Expired JWT rejection | Missing | N/A | Medium |
| ADR-0013 | Durable consumer position persistence | Partial | Durable names verified, no restart-resume test | Medium |
| Roadmap M4.5 | Session retention auto-purge | Implemented | `test_session_retention.py` | -- |
| Roadmap M7.5 | system-manager containers.py | Missing | Zero coverage for Docker mgmt | **High** |
| Roadmap | Backup/restore endpoints | Missing | N/A | Medium |
| Roadmap | Setup wizard / first-run | Missing | N/A | Medium |

## 2. ADR Testability Notes

| ADR | Requirement | State |
|-----|-------------|-------|
| ADR-0009 (NATS migration) | Services catch up after restart via JetStream | No restart-resume integration test |
| ADR-0012 (Chunk size) | All sources must produce 1536-sample chunks | No assertion on constant |
| ADR-0013 (Pull consumers) | Durable position persistence, exponential backoff | Backoff tested; persistence not |
| ADR-0014 (LIMITS retention) | Multiple consumers on same stream | Not tested |
| ADR-0015 (Session lifecycle) | Full state machine | Well tested |
| ADR-0016 (Admin auth) | bcrypt, JWT, dev-mode, expired token | Expired JWT not tested |

## 3. Top 8 Missing Tests (Prioritized)

### High Priority

1. **system-manager `containers.py` unit tests** -- Docker socket access with zero coverage. Mock Docker client, pure Python. Highest-risk untested code.

2. **Rewrite `test_e2e.py` integration test** -- Both tests skipped since v8.0. Needs: Audio->NATS->stt-provider(mock)->identity-manager->api-gateway->WS. Infra: NATS container, no Deepgram key.

3. **Transcript persistence to SQLite** -- No test that `api-gateway` persists `TranscriptSegment` rows during active sessions. Infra: in-memory SQLite, mock NATS.

4. **API key leak prevention (NFR-008)** -- No check that `DEEPGRAM_API_KEY` never appears in logs. Infra: pure Python, `caplog` fixture.

### Medium Priority

5. **Expired JWT rejection** -- ADR-0016 specifies short-lived JWTs but no test for expiry. Create token with TTL=0, assert 401. Pure Python.

6. **Backup/restore endpoint tests** -- Data loss risk if archive format changes. Verify round-trip backup->restore. Infra: `tmp_path` SQLite.

7. **Setup wizard endpoints** -- `/setup/status` and `/setup` have no coverage. Infra: in-memory SQLite, ASGI test client.

8. **Deepgram offline buffering (FR-007/008)** -- Verify buffer-then-catchup flow with mock transcriber that fails N times then succeeds.

## 4. Stale/Broken Tests

| File | Issue | Action |
|------|-------|--------|
| `tests/integration/test_e2e.py` | Both tests `@skip("Pending rewrite for v8.0")`. References old ZMQ-era API. | Rewrite or remove |
| `api-gateway/tests/test_main.py::test_connection_manager_broadcast` | `@skip("TestClient threadloop incompatibility")` since written | Rewrite using `_nats_patched_app` pattern (low priority) |

## 5. Stale Documentation

- **Traceability matrix** -- References ZMQ, `broker` service, SpeechBrain, Jetson Orin Nano. Needs full rewrite for v8.0.
- **Master test plan** -- References ZMQ, `broker`, wrong test paths (`tests/unit/`), 80% coverage (actual: 75%), `just test-integration` (doesn't exist yet).
- **CI/CD doc** -- References `.github/workflows/test.yml` and `security.yml` that don't exist. Actual workflow is `main.yaml`. `docker-compose.test.yml` documented but doesn't exist.

## 6. Strengths

- Session state machine testing is excellent (28 tests, full lifecycle)
- Identity-manager fusion logic well-tested (cross-source isolation, timeouts, concurrent safety)
- STT error handling solid (retry, publish failure, sequential model)
- Auth covers important paths
- `_patched_app` test helper pattern is clean and reusable
- Pre-commit hooks (ruff, mypy strict, bandit, detect-secrets) provide strong quality gate

# Requirements Traceability Matrix

## Overview
This document maps functional/non-functional requirements to design decisions and implementation milestones, ensuring complete coverage.

---

## Functional Requirements Traceability

| Req ID | Requirement | Design Component | Milestone | Test Plan |
|--------|-------------|------------------|-----------|-----------|
| **FR-001** | Generate initial phrases from YouTube captions | `scripts/mine_phrases.py` | M0.5 | Manual execution: Output `initial_phrases.json` |
| **FR-002** | Maintain Gold Standard test corpus (WER < 5%) | Manual transcription | M0.5 | CI: Run clips through stt-provider, measure WER |
| **FR-003** | Capture audio from USB audio interface (16kHz PCM) | audio-producer service | M2 | Integration test: Mock audio → broker |
| **FR-004** | Stream audio to Deepgram via WebSocket | stt-provider service | M3 | Integration test: Live Deepgram connection |
| **FR-005** | Display transcripts with <500ms latency | api-gateway WebSocket broadcast | M3 | Performance test: Measure end-to-end latency |
| **FR-006** | Detect audio clipping and alert | audio-producer RMS monitoring | M1 | Unit test: Inject clipped audio, verify alert |
| **FR-007** | Buffer audio during internet outages | stt-provider on-disk buffer | M5 | Resilience test: Disconnect network, verify buffer |
| **FR-008** | Catch up on buffered audio | stt-provider catch-up logic | M5 | Resilience test: Reconnect, verify no data loss |
| **FR-009** | Save low-confidence snippets (<0.85) | stt-provider QA loop | M9 | Unit test: Mock low confidence, verify save |
| **FR-010** | Encrypt saved audio snippets (AES-256) | stt-provider per-file encryption | M7 | Security test: Attempt decrypt without key |
| **FR-011** | Profanity filtering (blocklist/allowlist) | stt-provider sanitizer | M4 | Unit test: Inject profanity, verify filtered |
| **FR-012** | Identify enrolled speakers via voiceprint | identifier service (SpeechBrain) | M12 | Integration test: Enroll voiceprint, verify match |
| **FR-013** | Label transcripts with speaker names | api-gateway correlation engine | M13 | Integration test: Map Speaker 0 → Tom |
| **FR-014** | Crypto-shredding of voiceprints | api-gateway crypto-shred API | M10 | Security test: Delete key, verify unrecoverable |
| **FR-015** | Run on Jetson Orin Nano (Tier 1) | Multi-arch Docker builds | M0 | Deployment test: Flash BalenaOS, deploy |
| **FR-016** | Run on desktop GPU (Tier 2) and CPU (Tier 3) | Docker ARG BASE_IMAGE strategy | M0 | CI test: Build on multiple platforms |
| **FR-017** | Deploy via BalenaOS with zero-config | Balena Public URL, Supervisor | M2 | Deployment test: `balena push` from CLI |

---

## Non-Functional Requirements Traceability

| Req ID | Requirement | Design Decision | Verification | ADR |
|--------|-------------|-----------------|--------------|-----|
| **NFR-001** | Transcript latency \<500ms | ZMQ direct routing, local broker | Performance benchmark | [ADR-0001](../20_architecture/adrs/0001-zmq-broker.md) |
| **NFR-002** | Handle 2-hour sessions without restart | Stateless services, memory limits | Load test: 2-hour continuous stream | - |
| **NFR-003** | 99.9% uptime | `restart: always`, decoupled services | Health-watchdog monitoring | [ADR-0002](../20_architecture/adrs/0002-decoupled-ui.md) |
| **NFR-004** | UI responsive during transcription crash | Separate stt-provider service | Fault injection: Kill stt-provider | [ADR-0002](../20_architecture/adrs/0002-decoupled-ui.md) |
| **NFR-005** | Auto-restart crashed containers \<10s | Docker restart policy | Integration test: Kill container, measure recovery | - |
| **NFR-006** | Encrypt PII at rest (AES-256) | Per-file encryption + TPM sealing | Security audit: Verify encryption | [Threat Model](../20_architecture/threat_model.md) |
| **NFR-007** | TPM key sealing (Tier 1) | Balena TPM integration | Security test: Boot compromise detection | [Threat Model](../20_architecture/threat_model.md) |
| **NFR-008** | No plaintext API keys in logs | Environment vars, log sanitization | Code review: Grep for API key logging | - |
| **NFR-009** | Deployment \<30 min (non-technical) | Balena one-command deploy | User testing: Church volunteer deploy | [ADR-0005](../20_architecture/adrs/0005-balenaos-deployment.md) |
| **NFR-010** | Responsive UI (mobile) | FastAPI + responsive HTML/CSS | Browser test: iOS/Android viewport | - |
| **NFR-011** | Actionable error messages | Custom exception handlers in api-gateway | Manual test: Trigger errors, verify messages | - |
| **NFR-012** | Single-device optimization | No distributed coordination | Architecture review | - |
| **NFR-013** | Support 30 concurrent WebSocket clients | FastAPI async WebSocket handling | Load test: 30 concurrent connections | - |

---

## Milestone → Requirement Coverage

| Milestone | Requirements Addressed | Deliverable |
|-----------|------------------------|-------------|
| **M0** | FR-015, FR-016 | Docker builds, multi-arch support |
| **M0.5** | FR-001, FR-002 | Data Harvest: Silver (phrase mining), Gold (regression corpus) |
| **M1** | FR-003, FR-006 | audio-producer, broker, api-gateway skeleton |
| **M2** | FR-017, NFR-009 | Balena deployment, public URL |
| **M3** | FR-002, FR-003, FR-008, NFR-001 | stt-provider, end-to-end transcription |
| **M4** | FR-011 | Profanity filtering (sanitizer) |
| **M5** | FR-005, FR-006 | On-disk buffering, resilience |
| **M6** | NFR-003, NFR-004 | health-watchdog, status monitoring |
| **M7** | FR-010, NFR-006, NFR-007 | Encryption, TPM sealing, WebSocket auth |
| **M8** | FR-007 | sqladmin dashboard |
| **M9** | FR-009 | QA loop, low-confidence snippets |
| **M10** | FR-014 | Voiceprint enrollment, crypto-shredding |
| **M12** | FR-012 | identifier service (SpeechBrain) |
| **M13** | FR-013, NFR-013 | Correlation engine, speaker labels |

---

## User Story → Requirement → Milestone Map

| User Story | Requirements | Milestone |
|------------|--------------|-----------|
| **US-001** (View live transcripts) | FR-003, NFR-001 | M3 |
| **US-002** (Connection status) | NFR-003, NFR-004 | M6 |
| **US-003** (Custom vocabulary) | FR-008 | M3 |
| **US-004** (Review low-confidence snippets) | FR-009 | M9 |
| **US-005** (Enroll voiceprints) | FR-012, FR-014 | M10, M12 |
| **US-006** (Profanity filtering) | FR-011 | M4 |
| **US-007** (Easy deployment) | FR-017, NFR-009 | M2 |
| **US-008** (Test without GPU) | FR-016 | M0 |

---

## Orphaned Requirements Check
✅ All requirements traced to design components and milestones.

---

**See Also:**
- [PRD](prd.md) - Full requirements specification
- [Roadmap](../roadmap_draft.md) - Milestone definitions
- [Master Test Plan](../50_qa/master_test_plan.md) - Test coverage

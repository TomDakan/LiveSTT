# Roadmap (v8.0 Buffered Brain)

## Overview
This document outlines the development roadmap for Live STT (v8.0 Buffered Brain), organized by phases and milestones.

---

## Phase 1: The "Ironclad" Foundation (Week 1)
**Goal**: Crash-proof Hardware Setup & Basic Audio

### Milestone 0.5: The Data Harvest (Data Strategy)
- **Silver Mining**: Download 20h YouTube auto-captions, extract phrases using `mine_phrases.py`
- **Gold Creation**:
  - Download 3 service recordings
  - Extract 15 × 3-minute clips (ffmpeg)
  - Manually correct transcripts (Human-in-the-Loop)
  - Commit to `tests/data/gold_standard/`

### Milestone 1: Hardware & OS
- [ ] Provision ASRock NUC N97 with BalenaOS
- [ ] Configure BIOS (Power On After Fail, Watchdog)
- [ ] Implement "Black Box" Loopback Filesystem (`entrypoint.sh`)

### Milestone 2: Audio Pipeline
- [x] `audio-producer` service (ALSA/PyAudio/File -> NATS via `BaseService`)
- [ ] Verify Focusrite Solo input (16kHz, Linear16)
- [x] NATS JetStream configuration (`PRE_BUFFER`, `AUDIO_STREAM`, `TRANSCRIPTION_STREAM` defined in `libs/messaging/streams.py`)
- [x] Implement "Pre-Roll" publishing logic (`preroll.audio` when IDLE, `audio.live.<session_id>` when ACTIVE)

---

## Phase 2: The "Cloud Ear" (Week 2)
**Goal**: End-to-End Transcription (Mic -> UI)

### Milestone 3: Cloud Transcription
- [x] Update `stt-provider` to consume NATS (`audio.live` & `audio.backfill`)
- [x] Implement Deepgram Nova-3 streaming
- [x] Implement Backfill Worker (Throttled Background Upload)
- [ ] "Black Box" offline buffering logic

### Milestone 4: Full System Integration (Text Only)
- [x] Update `api-gateway` to consume `transcript.raw.*` (temporary; will switch to `transcript.final` once `identity-manager` is built)
- [ ] End-to-end testing (Mic -> NATS -> Deepgram -> UI)
- [ ] Web UI updates (WebSocket consumer)

---

## Phase 3: The "Edge Eye" (Week 3)
**Goal**: Biometric Identification & Hybrid Tagging

### Milestone 5: OpenVINO Optimization
- [ ] Export Silero VAD to ONNX
- [ ] Export WeSpeaker ResNet34 to ONNX (INT8 Quantization)
- [ ] Create `identifier` service skeleton

### Milestone 6: Identity Manager
- [ ] Implement `identifier` service (VAD + Vector Extraction)
- [ ] Implement `identity-manager` service (Session Map + Fusion)
- [ ] Merge `transcript.raw` and `transcript.identity` into `transcript.final`

---

## Phase 4: Integration & Burn-In (Week 4)
**Goal**: Deployment Ready

### Milestone 7: Full System Integration
- [ ] End-to-end testing (Mic -> UI)
- [ ] Web UI updates (WebSocket consumer)
- [ ] 7-Day Burn-in Test

---

## Future Roadmap (Post-v7.3)

### Q1 2026: Enterprise Features
- [ ] LDAP/SSO Integration
- [ ] Cloud Archiving
- [ ] Mobile App

---

**See Also:**
- [Architecture Definition](docs/20_architecture/architecture_definition.md)
- [System Design v8.0](docs/20_architecture/system_design_v8.0.md)

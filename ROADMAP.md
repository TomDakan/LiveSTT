# Roadmap (v7.3)

## Overview
This document outlines the development roadmap for Live STT (v7.3 Industrial Split-Brain), organized by phases and milestones.

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
- [ ] `audio-producer` service (ALSA -> NATS)
- [ ] Verify Focusrite Solo input (16kHz, Linear16)
- [ ] NATS JetStream configuration (`audio.raw` persistence)

---

## Phase 2: The "Cloud Ear" (Week 2)
**Goal**: End-to-End Transcription (Mic -> UI)

### Milestone 3: Cloud Transcription
- [ ] Update `stt-provider` to consume NATS
- [ ] Implement Deepgram Nova-3 streaming
- [ ] "Black Box" offline buffering logic

### Milestone 4: Full System Integration (Text Only)
- [ ] Update `api-gateway` to consume `text.transcript`
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
- [ ] Implement `identity-manager` service (Session Map)
- [ ] Merge `text.transcript` and `identity.event`

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
- [System Design v7.3](docs/temp_design_update.md)

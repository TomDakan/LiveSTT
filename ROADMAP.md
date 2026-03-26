# Roadmap (v8.0 Buffered Brain)

## Overview
This document outlines the development roadmap for Live STT (v8.0 Buffered Brain), organized by phases and milestones.

---

## Phase 1: The "Ironclad" Foundation (Week 1)
**Goal**: Crash-proof Hardware Setup & Basic Audio

### Milestone 0.5: The Data Harvest (Data Strategy)
- [ ] **Silver Mining**: Download 20h YouTube auto-captions, extract phrases using `mine_phrases.py`
- [ ] **Gold Creation**:
  - Download 3 service recordings
  - Extract 15 × 3-minute clips (ffmpeg)
  - Manually correct transcripts (Human-in-the-Loop)
  - Commit to `tests/data/gold_standard/`

### Milestone 1: Hardware & OS
- [ ] Provision ASRock NUC N97 with BalenaOS
- [ ] Configure BIOS (Power On After Fail, Watchdog)
- [ ] Implement "Black Box" Loopback Filesystem (`entrypoint.sh`)

### Milestone 2: Audio Pipeline
- [x] `audio-producer` service (ALSA/PyAudio/File → NATS via `BaseService`)
- [ ] Verify RME Babyface Pro input on target hardware (16kHz, Linear16)
  - Note: WSL2 kernel lacks `snd-usb-audio`; file-based testing used for dev/CI
- [x] NATS JetStream stream definitions (`PRE_BUFFER`, `AUDIO_STREAM`, `TRANSCRIPTION_STREAM` in `libs/messaging/streams.py`)
- [x] Pre-Roll / Live routing logic (`preroll.audio` when IDLE, `audio.live.<session_id>` when ACTIVE)
- [x] Standardised audio chunk size: 1536 samples / 96ms (ADR-0012)

---

## Phase 2: The "Cloud Ear" (Week 2)
**Goal**: End-to-End Transcription (Mic → UI)

### Milestone 3: Cloud Transcription
- [x] `stt-provider` consumes `audio.live` & `audio.backfill` from NATS
- [x] Deepgram Nova-3 streaming via injected `Transcriber` interface (supports mock for testing)
- [x] Backfill worker (throttled background upload)
- [ ] "Black Box" offline buffering: detect Deepgram disconnection and resume from buffered NATS position on reconnect

### Milestone 4: Full System Integration (Text Only)
- [x] `api-gateway` consumes `transcript.raw.*` (temporary; switches to `transcript.final.*` once identity pipeline is active)
- [ ] End-to-end test: Mic → NATS → Deepgram → UI (`just e2e` recipe)
- [ ] Web UI updates (WebSocket consumer)

---

## Phase 3: The "Edge Eye" (Week 3)
**Goal**: Biometric Identification & Hybrid Tagging

### Milestone 5: Audio Classification & Model Preparation
- [x] `audio-classifier` service with Silero VAD (ONNX Runtime, pre-trained model bundled in Docker image)
- [ ] Obtain and convert WeSpeaker ResNet34 to OpenVINO IR format (`models/wespeaker.xml`)
- [x] `identifier` service skeleton + full pipeline (audio buffering, embedding, cosine similarity, LanceDB)

### Milestone 6: Identity Pipeline
- [x] `identifier` service: dual-lane pipeline, `OpenVinoEmbedder` (fallback to stub), `LanceDBVoiceprintStore`
- [x] `identity-manager` "Time Zipper": fuses `transcript.raw.*` + `transcript.identity.*` → `transcript.final.*`
- [x] `identity-manager` Dockerfile
- [ ] Wire speaker enrollment: `POST /v1/admin/enrollment` (api-gateway) → `identifier` NATS command channel
- [ ] End-to-end biometric test: enroll voiceprint → verify speaker label appears in `transcript.final.*`

### Milestone 6.5: Supporting Services
- [x] `health-watchdog`: reads NATS KV `service_health` bucket, alerts on missing heartbeats
- [x] `data-sweeper`: periodic JetStream stream stats reporting (retention handled by JetStream limits)
- [x] Dockerfiles for all 8 services

---

## Phase 4: Integration & Burn-In (Week 4)
**Goal**: Deployment Ready

### Milestone 7: Full System Integration
- [ ] End-to-end test: Mic → NATS → Deepgram + Identifier → UI with speaker labels
- [ ] Web UI updates (WebSocket consumer, speaker name display)
- [ ] 7-Day Burn-in Test on ASRock NUC N97

---

## Future Roadmap (Post-v8.0)

### Q2 2026: Enterprise Features
- [ ] LDAP/SSO Integration
- [ ] Cloud Archiving
- [ ] Mobile App
- [ ] Fully offline STT via local model (Whisper or similar) for hardware with sufficient CPU/GPU

---

**See Also:**
- [Architecture Definition](docs/20_architecture/architecture_definition.md)
- [System Design v8.0](docs/20_architecture/system_design_v8.0.md)

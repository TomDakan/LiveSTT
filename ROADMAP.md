# Roadmap

## Overview
This document outlines the development roadmap for Live STT, organized by quarterly releases and detailed milestones.

---

## Version 6.2 Development (Current)

Development is organized into 4 phases with 13 milestones:

### Phase 0: Foundation & Data Strategy (M0-M0.5)
**Goal**: Establish the build pipeline and test datasets

#### Milestone 0: Scaffolding & Config
- Repo initialization & Docker strategy
- `just` setup automation (Secrets/Data directories)

#### Milestone 0.5: The Data Harvest ⭐
- **Silver Mining**: Download 20h YouTube auto-captions, extract phrases using `mine_phrases.py`
- **Gold Creation**: 
  - Download 3 service recordings
  - Extract 15 × 3-minute clips (ffmpeg)
  - Manually correct transcripts (Human-in-the-Loop)
  - Commit to `tests/data/gold_standard/`

---

### Phase 1: Infrastructure & Messaging (M1-M2)
**Goal**: Establish the "Nervous System" (ZMQ broker)

#### Milestone 1: The Core Stack
- `broker` service (Two-Port: 5555/5556)
- `mock-audio-producer` (ZMQ HWM testing)
- `api-gateway` (UI Skeleton)

#### Milestone 2: Hardware Validation
- Deploy to NUC/Jetson
- Thermal burn-in testing (`stress-ng`)

---

### Phase 2: Core STT & Resilience (M3-M6)
**Goal**: Implement decoupled transcription

#### Milestone 3: The stt-provider
- Deepgram SDK integration
- **Regression Test**: Run Gold Standard clips, calculate WER

#### Milestone 4: Context & Quality
- Music Detection (`audio-classifier`)
- PhraseSet injection (using M0.5 data)

#### Milestone 5: Zero Data Loss
- NVMe buffering ("Catch Up" logic)
- Frontend timestamp sorting

#### Milestone 6: Observability
- `health-watchdog` service
- Status monitoring

---

### Phase 3: Security & Compliance (M7-M11)
**Goal**: Secure PII and build admin interfaces

#### Milestone 7: data-sweeper & Encryption
- Automated data retention (configurable via env var)
- AES-256 per-file encryption

#### Milestone 8: Admin Dashboard
- SQLAdmin integration
- PhraseSet management UI

#### Milestone 9: The Review Queue
- Low-confidence snippet capture
- Admin playback interface

#### Milestone 10: Speaker Enrollment
- Voiceprint upload functionality
- Encrypted storage

#### Milestone 11: GPU Infrastructure Upgrade
- Migrate to Tier 1 (Jetson) or Tier 2 (Desktop GPU)

---

### Phase 4: Local AI (M12-M13)
**Goal**: Enable biometric speaker identification

#### Milestone 12: identifier Service
- SpeechBrain ECAPA-TDNN integration
- GPU-accelerated inference

#### Milestone 13: Correlation Engine
- Map Deepgram "Speaker 0" to enrolled names
- UI display with speaker labels

---

## Quarterly Release Plan

### Q1 2026: Foundation (v0.5)
**Status**: In Progress

- [x] Core Architecture Definition
- [x] Basic Transcription (Deepgram)
- [x] Documentation structure (Docs-as-Code)
- [ ] Web UI Implementation (M1)
- [ ] Docker Compose Dev Environment (M0-M1)

**Corresponds to**: Phases 0-1 (M0-M2)

---

### Q2 2026: Production Ready (v1.0)
**Target Features**:

- [ ] Jetson Orin Nano Support (Tier 1)
- [ ] Speaker Identification (SpeechBrain)
- [ ] BalenaCloud Deployment
- [ ] Offline Buffering & Recovery

**Corresponds to**: Phases 2-3 (M3-M11)

**Release Criteria**:
- Gold Standard regression test: WER < 5%
- 60-minute thermal stability test passes
- Data retention compliance verified

---

### Q3 2026: Enhanced Features (v1.5)
**Target Features**:

- [ ] Open Captioning (HDMI Output)
- [ ] Translation Support (Deepgram Translate)
- [ ] Custom Vocabulary Editor UI


**Status**: Planning phase

---

### Q4 2026: Enterprise (v2.0)
**Target Features**:

- [ ] LDAP/SSO Integration
- [ ] Cloud Archiving (S3)
- [ ] Mobile App (iOS/Android)
- [ ] Analytics Dashboard

**Status**: Future consideration

---

## Key Milestones Summary

| Milestone | Phase | Description | Status |
|-----------|-------|-------------|--------|
| **M0** | Foundation | Scaffolding & Docker | ✅ Complete |
| **M0.5** | Foundation | Data Harvest (Silver/Gold) | 🔄 In Progress |
| **M1** | Infrastructure | Core Stack (broker, gateway) | 📋 Planned |
| **M2** | Infrastructure | Hardware Validation | 📋 Planned |
| **M3** | STT | stt-provider + WER Testing | 📋 Planned |
| **M7** | Security | data-sweeper & Encryption | 📋 Planned |
| **M8** | Security | Admin Dashboard | 📋 Planned |
| **M12** | AI | Speaker Identification | 📋 Planned |

For detailed technical specifications, see:
- [Architecture Definition](docs/20_architecture/architecture_definition.md)
- [Master Test Plan](docs/50_qa/master_test_plan.md)
- [Traceability Matrix](docs/10_requirements/traceability_matrix.md)

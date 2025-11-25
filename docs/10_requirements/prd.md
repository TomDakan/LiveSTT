# Product Requirements Document (PRD)

## 1. Problem Statement
Churches need live transcription of sermons and liturgy for:
- **Accessibility**: Deaf/hard-of-hearing congregants
- **Multilingual support**: Non-native speakers following along
- **Archival**: Automated transcript logging for later reference

Existing solutions (cloud transcription services) require:
- High Per-minute costs (\$0.006+/min → \$360+/month for 1000 min/month)
- Complex integration (no turnkey appliance)
- Expensive hardware

**Goal**: Provide a self-hosted, cost-effective transcription appliance for use with personal devices to display the transcriptions.

---

## 2. User Stories

| ID | As a... | I want to... | So that... | Priority |
|----|---------|--------------|------------|----------|
| **US-001** | User | View live transcripts on my personal device | I can follow along during the service | P0 |
| **US-002** | Kiosk Operator | See connection status (live/reconnecting) | I know if the system is working | P0 |
| **US-003** | Admin | Upload custom vocabulary (staff names, biblical terms) | Transcripts have correct spellings | P1 |
| **US-004** | Admin | Review low-confidence transcript snippets | I can correct errors and improve the model | P1 |
| **US-005** | Admin | Enroll speaker voiceprints | The system labels speakers by name (not Speaker 0) | P2 |
| **US-006** | Admin | Configure profanity filtering | Inappropriate words never appear on screen | P1 |
| **US-007** | Operator | Deploy to hardware without technical expertise | I don't need to hire a consultant | P0 |
| **US-008** | Developer | Test the system without GPU hardware | I can contribute on my laptop | P1 |

---

## 3. Functional Requirements

### Core Transcription (M0-M6)
- **FR-001**: The system SHALL capture audio from a USB audio interface at 16kHz, 16-bit PCM
- **FR-002**: The system SHALL stream audio to Deepgram API via WebSocket
- **FR-003**: The system SHALL display transcripts on a web UI with \<500ms latency
- **FR-004**: The system SHALL detect audio clipping and alert the operator
- **FR-005**: The system SHALL buffer audio to disk during internet outages
- **FR-006**: The system SHALL catch up on buffered audio upon reconnection

### Administration (M7-M11)
- **FR-007**: The system SHALL provide an admin dashboard for configuration
- **FR-008**: The system SHALL support custom vocabulary (PhraseSet JSON upload)
- **FR-009**: The system SHALL save low-confidence snippets (\<0.85) for review
- **FR-010**: The system SHALL encrypt all saved audio snippets with AES-256
- **FR-011**: The system SHALL support profanity filtering (hard blocklist + soft allowlist)

### Speaker Identification (M12-M13)
- **FR-012**: The system SHALL identify enrolled speakers via voiceprint matching
- **FR-013**: The system SHALL label transcripts with speaker names (overriding Deepgram's Speaker 0/1)
- **FR-014**: The system SHALL support crypto-shredding of voiceprints (delete key → file unrecoverable)

### Deployment (M0-M2)
- **FR-015**: The system SHALL run on Jetson Orin Nano (Tier 1)
- **FR-016**: The system SHALL run on desktop GPU (Tier 2) and CPU-only (Tier 3) for development
- **FR-017**: The system SHALL deploy via BalenaOS with zero-config networking

---

## 4. Non-Functional Requirements

### Performance
- **NFR-001**: Transcript latency SHALL be \<500ms (microphone → UI display)
- **NFR-002**: The system SHALL handle continuous 2-hour sessions without restart

### Reliability
- **NFR-003**: The system SHALL achieve 99.9% uptime (excluding scheduled maintenance)
- **NFR-004**: The UI SHALL remain responsive even if transcription service crashes
- **NFR-005**: The system SHALL auto-restart crashed containers within 10 seconds

### Security
- **NFR-006**: All PII (voiceprints, audio snippets) SHALL be encrypted at rest (AES-256)
- **NFR-007**: Encryption keys SHALL be sealed to TPM on Tier 1 hardware
- **NFR-008**: The system SHALL NOT log API keys in plaintext

### Usability
- **NFR-009**: Operators with no technical background SHALL complete deployment in \<30 minutes
- **NFR-010**: The Web UI SHALL be accessible from mobile devices (responsive design)
- **NFR-011**: Error messages SHALL be actionable (not stack traces)

### Scalability
- **NFR-012**: The system is optimized for single-device deployment (not fleet-wide load balancing)
- **NFR-013**: The system SHALL support up to 30 concurrent WebSocket clients

---

## 5. Out of Scope (V1.0)
- Multi-language support (English-only)
- On-device STT (cloud-only for V1)
- Multi-site transcription (1 device per church)
- Real-time translation (transcript → Spanish, etc.)
- Video captioning (audio-only for V1)
- Projector display mode (V1 targets personal devices only)

---

## 6. Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| **Word Error Rate (WER)** | \<10% on liturgical content | Manual review of 1000-word samples |
| **Deployment Time** | \<30 min (non-technical user) | User testing with church volunteers |
| **Cost Savings** | \>80% vs. cloud STT (\$360/mo → \$68/mo) | Deepgram API usage + hardware amortization |
| **Uptime** | \>99% over 30-day period | Health-watchdog logs |

---

## 7. Acceptance Criteria
- [ ] Live transcripts display on web UI during 2-hour church service
- [ ] System recovers automatically from 10-minute internet outage (zero data loss)
- [ ] Admin can upload custom vocabulary and see improved accuracy
- [ ] Low-confidence snippets (\<0.85) saved to `/data/review/` (encrypted)

---

**See Also**:
- [System Design](../system_design.md) - Technical architecture
- [Roadmap](../roadmap_draft.md) - Development milestones
- [Traceability Matrix](traceability_matrix.md) - Requirements → Design → Milestones mapping

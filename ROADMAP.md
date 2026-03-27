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
- [x] "Black Box" offline buffering: detect Deepgram disconnection and resume from buffered NATS position on reconnect

### Milestone 4: Full System Integration (Text Only)
- [x] `api-gateway` consumes `transcript.final.*` via identity-manager
- [x] End-to-end test: File audio → NATS → Deepgram → identity-manager → WebSocket UI (`just e2e`)
- [x] Web UI: live transcript display with speaker badges, interim results, auto-scroll

### Milestone 4.5: Session Control
**Goal**: Replace the `AUTO_SESSION` env-var hack with real session lifecycle management.

- [ ] Add `session.control` NATS subject + `SESSION_STREAM` JetStream config
- [ ] `audio-producer`: subscribe to `session.control`; on `start` command, generate session ID,
  flush pre-roll buffer to `audio.backfill.<session_id>`, begin publishing to `audio.live.<session_id>`;
  on `stop`, return to IDLE
- [ ] `api-gateway`: `POST /session/start` and `POST /session/stop` endpoints that publish to
  `session.control` (no auth required — any audience member can start transcription)
- [ ] UI: prominent "Start / Stop Recording" button visible on the main transcript page;
  show session status (idle / recording / elapsed time)
- [ ] Unit tests for session state machine in audio-producer

---

## Phase 3: The "Edge Eye" (Week 3)
**Goal**: Biometric Identification, Admin Interface & Vocabulary Tuning

### Milestone 5: Audio Classification & Model Preparation
- [x] `audio-classifier` service with Silero VAD (ONNX Runtime, pre-trained model bundled in Docker image)
- [ ] Obtain and convert WeSpeaker ResNet34 to OpenVINO IR format (`models/wespeaker.xml`)
- [x] `identifier` service skeleton + full pipeline (audio buffering, embedding, cosine similarity, LanceDB)

### Milestone 6: Identity Pipeline
- [x] `identifier` service: dual-lane pipeline, `OpenVinoEmbedder` (fallback to stub), `LanceDBVoiceprintStore`
- [x] `identity-manager` "Time Zipper": fuses `transcript.raw.*` + `transcript.identity.*` → `transcript.final.*`
- [x] `identity-manager` Dockerfile
- [ ] Wire speaker enrollment: `POST /v1/admin/speakers` (api-gateway) → `identifier` NATS command channel
- [ ] End-to-end biometric test: enroll voiceprint → verify speaker label appears in `transcript.final.*`

### Milestone 6.5: Admin Interface & Authentication
**Goal**: Secure admin panel for managing enrollment, vocabulary, and system state.

**Authentication**
- [ ] Single admin token (bcrypt-hashed env var `ADMIN_PASSWORD_HASH`) + JWT issuance
- [ ] `POST /admin/auth` → returns short-lived JWT; all `/admin/*` routes require Bearer token
- [ ] JWT middleware in api-gateway; token expiry configurable via `ADMIN_TOKEN_TTL_S`

**Admin UI** (separate route `/admin`, same server)
- [ ] Admin login page (simple token form, no username)
- [ ] Speaker enrollment panel: list enrolled speakers, upload audio sample to enroll,
  delete voiceprint
- [ ] System status panel: service heartbeat table (from NATS KV `service_health`),
  NATS stream stats (message counts, bytes, consumer lag), disk usage

**Log Viewer**
- [ ] `GET /admin/logs` WebSocket: stream structured log lines from all services in real time
  (api-gateway subscribes to a `logs.>` NATS subject; each service publishes structured log
  records there in addition to stdout)
- [ ] Filter by service name and log level in the UI

### Milestone 7: Vocabulary Intelligence
**Goal**: Close the feedback loop between transcription errors and Deepgram custom vocabulary.

- [ ] **Pre-seeded domain vocabulary**: admin can import known domain-specific word lists
  (e.g. books of the Bible, speaker names, local place names) before a single service runs;
  stored in `custom_vocab` table and immediately active for Deepgram `keywords`
- [ ] **Low-confidence word tracking**: `stt-provider` records words/phrases where
  `confidence < LOW_CONF_THRESHOLD` (default 0.75) to a SQLite table in `api-gateway`'s
  data volume (`/data/db/vocab.db`)
- [ ] **Admin review UI**: table of candidate words sorted by frequency; admin can
  approve (add to custom vocab) or dismiss; approved words merge with pre-seeded list
- [ ] **Deepgram keyword injection**: words in `custom_vocab` are passed as `keywords` in
  Deepgram connection options; `stt-provider` reloads the list on `vocab.updated` NATS event
  without restarting
- [ ] **Export/import**: `GET /admin/vocab/export` (CSV) and `POST /admin/vocab/import`
  for migrating vocabulary lists between deployments; ship a starter `church_vocab.csv`
  (books of the Bible + common liturgical terms) in `data/vocab/`

### Milestone 7.5: Ops & Hardware Tooling
**Goal**: Make deploying and debugging on the NUC N97 fast and low-friction.

**BalenaOS deployment preparation**
- [ ] Add `balena.yml` to repo root (`defaultDeviceType: intel-nuc`, fleet name, `version: "2.1"`)
- [ ] Audit `docker-compose.yml` for Balena compatibility: replace all bind mounts with
  named volumes under `/data/` (BalenaOS persistent NVMe partition that survives OTA
  updates): `nats_data:/data/nats`, `db_data:/data/db`, `lancedb_data:/data/lancedb`;
  ensure audio device passthrough (`/dev/snd`) and `group_add: audio` work under supervisor
- [ ] Set `DEEPGRAM_API_KEY` and other runtime secrets via Balena Cloud fleet environment
  variables (injected at runtime — no `.env` file on device, secrets never in image/git);
  support per-device API key overrides for sites with separate Deepgram accounts
- [ ] Add `restart: unless-stopped` to all services (currently missing on api-gateway,
  audio-producer, identity-manager, nats)
- [ ] `just deploy` — `balena push <fleet>` wrapper
- [ ] `just deploy-check` — smoke-test a device by UUID (`curl /health`, NATS ping via
  Balena public URL)
- [ ] Document Balena SSH workflow for live debugging in `docs/60_ops/runbooks.md`

**Docker / Compose**
- [ ] Add `healthcheck:` directives to all services in `docker-compose.yml` so
  `restart: unless-stopped` only kicks in after a true health failure (not a cold-start race)
- [ ] `docker-compose.override.yml` for local dev (relaxed health timeouts, mounted source dirs)

**`justfile` recipes**
- [ ] `just status` — one-shot summary: container health, NATS stream stats
  (message counts, consumer lag per service), disk usage at `/data`
- [ ] `just nats-streams` — pretty-print all stream configs and current state

**Backup & restore**
- [ ] `POST /admin/backup` → streams a tar archive of `/data/db` (vocab, transcripts) and
  `/data/lancedb` (voiceprints); downloadable via admin UI or `just backup-device <uuid>`
- [ ] `POST /admin/restore` → accepts tar archive, restores vocab and voiceprints
- [ ] Reserve `BACKUP_DESTINATION` env var for future cloud backup (S3/GCS); not
  implemented in v8.0 but architecture accommodates it
- [ ] Audio NATS data (`/data/nats`) explicitly excluded from backup — transient by design

**Web-accessible status page**
- [ ] `GET /admin/status` — read-only JSON view of service health and stream stats
  (no auth required; safe to expose on local network)

---

## Phase 4: Integration & Burn-In (Week 4)
**Goal**: Deployment Ready

### Milestone 8: Full System Integration
- [ ] End-to-end test: Mic → NATS → Deepgram + Identifier → UI with speaker labels
- [ ] 7-Day Burn-in Test on ASRock NUC N97
- [ ] Word Error Rate (WER) benchmark against gold-standard recordings from Milestone 0.5

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

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

- [x] Add `session.control` NATS subject + `SESSION_STREAM` JetStream config
- [x] `audio-producer`: subscribe to `session.control`; on `start` command, generate session ID,
  flush pre-roll buffer to `audio.backfill.<session_id>`, begin publishing to `audio.live.<session_id>`;
  on `stop`, return to IDLE
- [x] `api-gateway`: `POST /session/start` and `POST /session/stop` endpoints that publish to
  `session.control` (no auth required — any audience member can start transcription)
- [x] UI: prominent "Start / Stop Recording" button visible on the main transcript page;
  show session status (idle / recording / elapsed time)
- [x] Unit tests for session state machine in audio-producer
- [x] Session naming: operator can supply a human-readable label ("Sunday Morning — March 30")
  at session start or stop; stored alongside the session ID for archive and retrieval
- [x] Connection status indicator in the viewer UI: clearly distinguish live/active,
  degraded (Deepgram reconnecting), and idle/paused states — audience should never be
  left wondering if the system is working

**Viewer UX**
- [x] Font size controls (A- / A+) on the transcript page — church audiences skew older;
  persist the preference in localStorage
- [x] QR code displayed on the main page / `/display` route so audience members can load
  the transcript on their phones without typing a URL; the device must know its own
  externally-reachable URL to generate the code — this differs by deployment type:
  Balena public device URL (managed fleet, already stable HTTPS) vs. local IP or mDNS
  hostname (self-hosted); the first-run onboarding wizard is the natural place to capture
  a configurable `SITE_URL` that the QR code renders from
- [x] Kiosk / presentation mode (`/display` route): full-screen, large text, high contrast,
  no admin chrome — suitable for a dedicated screen at the front of the venue;
  auto-scrolls and shows connection status but has no interactive controls

**Scheduled sessions**
- [x] Rename `data-sweeper` → `system-manager`; expand its mandate to own all background
  operational concerns: NATS stream stats (current), transcript retention/purge, and
  session scheduling — keeping these out of api-gateway which should stay UI/HTTP-focused
- [x] Admin UI and API (`POST /admin/schedules`) to define recurring session schedules:
  day-of-week + start time + stop time + optional label template
  (e.g. "Sunday Morning — {date}"); stored in `livestt.db`; requires `SITE_TIMEZONE`
  to be set (captured in first-run onboarding)
- [x] `system-manager` reads schedule config and fires `session.control` start/stop
  commands via NATS at the configured times — no operator action required
- [x] Admin UI: schedule list with enable/disable toggle and next-run preview
- [x] **Design decision (resolved)**: schedule end-time precedence — per-schedule
  `stop_policy` field: *soft* (default, rely on silence timeout), *hard* (exact time),
  or *grace_N* (delay N minutes then hard stop)

### Milestone 4.75: Transcript Persistence & Archive
**Goal**: Persist completed session transcripts so operators can retrieve, export, and correct them after the fact.

**Storage** (design decision): all persistent data (sessions, transcripts, schedules) is
stored in a single SQLite file at `/data/db/livestt.db`, owned by api-gateway. Schema:
`sessions`, `transcript_segments`, and `schedules` tables. system-manager reads schedules
via api-gateway's HTTP API. One persistence backend, one backup path, one volume.

- [x] `api-gateway` persists transcript segments to `livestt.db` during active sessions
- [x] `GET /admin/sessions` — list past sessions with name, date, duration
- [x] `GET /admin/sessions/<id>/export` — download transcript as plain text or PDF;
  available in the admin UI as a "Download transcript" button
- [ ] Transcript correction UI: post-session view where the operator can edit segment text
  before exporting (STT errors on proper nouns — names, scripture references — are common);
  low priority, deferred to future milestone
- [x] `livestt.db` included in the `POST /admin/backup` archive

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

**Authentication** *(ADR-0016)*
- [x] Single admin password (bcrypt-hashed env var `ADMIN_PASSWORD_HASH`) + ephemeral JWT issuance
- [x] `POST /admin/auth` → returns short-lived JWT; all mutating `/admin/*` routes require Bearer token
- [x] `require_admin` FastAPI dependency; token expiry configurable via `ADMIN_TOKEN_TTL_S`

**Admin UI** (separate route `/admin`, same server)
- [x] Admin login page (password form, JWT stored in localStorage)
- [x] Speaker enrollment panel: enroll by name, delete via NATS command to `identifier.command`
  (stub — identifier does not yet consume these commands)
- [x] System status panel: service heartbeat table (from NATS KV `service_health` with
  30s staleness TTL), NATS stream stats, disk usage
- [x] Current session card with live status + admin stop button (`POST /session/stop`)

**Log Viewer**
- [x] `GET /admin/logs` WebSocket: stream structured log lines from all services in real time
  (api-gateway subscribes to `logs.>` NATS subject; each service publishes via
  `NatsLogHandler` when `NATS_LOG_FORWARDING=true`)
- [x] Filter by service name and log level in the UI

**Future UI items**
- [ ] Session rename/relabel (edit label of active or past session)
- [ ] Session start feedback: show a "Processing pre-roll…" indicator while
  backfill is draining to Deepgram (~2s delay) — the greyed-out Start button
  makes it look frozen with no visual feedback

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

**`data-sweeper` → `system-manager` rename** *(completed in M4.5)*
- [x] Rename service directory, Python package, Docker image tag, and compose service name
- [ ] Update `MONITORED_SERVICES` list in `health-watchdog` to reference `system-manager`
- [ ] Update `docs/` and `CLAUDE.md` references

**BalenaOS deployment preparation**
- [ ] Add `balena.yml` to repo root (`defaultDeviceType: intel-nuc`, fleet name, `version: "2.1"`)
- [ ] Audit `docker-compose.yml` for Balena compatibility: replace all bind mounts with
  named volumes under `/data/` (BalenaOS persistent NVMe partition that survives OTA
  updates): `nats_data:/data/nats`, `db_data:/data/db`, `lancedb_data:/data/lancedb`;
  ensure audio device passthrough (`/dev/snd`) and `group_add: audio` work under supervisor
- [ ] Set `DEEPGRAM_API_KEY` and other runtime secrets via Balena Cloud fleet environment
  variables (injected at runtime — no `.env` file on device, secrets never in image/git);
  support per-device API key overrides for sites with separate Deepgram accounts
- [x] Add `restart: always` to all services (ADR-0017)
- [ ] `just deploy` — `balena push <fleet>` wrapper
- [ ] `just deploy-check` — smoke-test a device by UUID (`curl /health`, NATS ping via
  Balena public URL)
- [ ] Document Balena SSH workflow for live debugging in `docs/60_ops/runbooks.md`

**Service management via admin UI**
- [ ] system-manager service orchestration: enable/disable individual services from the
  admin UI (e.g., disable `identifier` + `audio-classifier` at venues without speaker ID)
- [ ] Docker socket backend: system-manager calls Docker Engine API to start/stop containers;
  optional Balena Supervisor API backend when running on BalenaOS
- [x] Restart policy review: `restart: always` selected (ADR-0017); service disable will
  use `docker update --restart=no` or Balena Supervisor API
- [ ] Web-based onboarding flow: first-run setup wizard (admin password, Deepgram API key,
  timezone, optional service toggles) — the appliance should be fully configurable without
  CLI access

**Docker / Compose**
- [x] Add `healthcheck:` directives to all services in `docker-compose.yml`;
  non-HTTP services use `/tmp/healthy` marker file touched by BaseService heartbeat
- [x] Migrate bind mounts to named volumes (`nats_data`, `db_data`) for Balena compatibility
- [x] `depends_on` with `condition: service_healthy` for startup ordering
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
- [x] `GET /admin/status` — read-only JSON view of service health and stream stats
  (no auth required; safe to expose on local network)

**Network discovery**
- [ ] mDNS / Zeroconf: advertise the device as `livestt.local` (or configurable hostname)
  so operators and audience members can reach it without knowing the IP address;
  implement via the `avahi-daemon` sidecar or equivalent in the Docker Compose stack;
  document in the runbook and first-run onboarding wizard;
  **Note**: managed BalenaOS fleet devices already get a stable public HTTPS URL from
  Balena Cloud, so mDNS is primarily a self-hosted quality-of-life improvement

**Transcript retention**
- [ ] Configurable auto-purge policy: keep the last N sessions or purge segments older
  than X days (default: keep last 30 sessions); enforced by a scheduled cleanup task in
  api-gateway; prevents unbounded disk growth on long-running devices

**Log persistence & admin viewer**
- [ ] Server-side ring buffer: subscribe to `logs.>` once at api-gateway startup and keep
  the last N messages (e.g., 500) in memory; replay on WebSocket connect so the admin
  log viewer shows recent history instead of starting empty
- [ ] Persistent log storage: store ERROR and CRITICAL logs to SQLite (or a dedicated
  `logs` table) with 30-day default retention; configurable retention per level via
  admin UI or env var (e.g., `LOG_RETENTION_DAYS_ERROR=30`, `LOG_RETENTION_INFO=7`)
- [ ] Admin log viewer: backfill from persistent storage on page load; live-stream via
  existing WebSocket for new entries

**Log export for bug reporting**
- [ ] `GET /admin/logs/export` — download a tar archive of recent structured log output
  from all services (bounded by time range or line count); surfaced in the admin UI as
  a "Download logs" button for self-hosted deployments
- [ ] For managed BalenaOS fleet devices: logs are already streamed to Balena Cloud and
  accessible via `balena logs <uuid>` or the dashboard — document this in the runbook
  so fleet operators know where to look without needing the export endpoint
- [ ] "How to report a bug" doc (GitHub wiki or `docs/`) covering both paths: Balena
  dashboard for managed devices, log export for self-hosted; include guidance on
  redacting sensitive content (transcripts) before sharing

---

## Phase 4: Integration & Burn-In (Week 4)
**Goal**: Deployment Ready

### Milestone 8: Full System Integration
- [ ] End-to-end test: Mic → NATS → Deepgram + Identifier → UI with speaker labels
- [ ] 7-Day Burn-in Test on ASRock NUC N97
- [ ] Word Error Rate (WER) benchmark against gold-standard recordings from Milestone 0.5

---

## Future Roadmap (Post-v8.0)

### First-Run Onboarding
**Goal**: Replace the env-var approach to admin credentials with a guided setup wizard shown on first load, so a non-technical operator can configure the device out of the box without editing config files.

Design and implementation deferred until LiveSTT is feature-complete. Considerations:

- Detect "first run" state (e.g. no `ADMIN_PASSWORD_HASH` set, or a `first_run` flag in the DB/KV store)
- Redirect all HTTP traffic to an onboarding wizard until setup is complete
- Wizard steps: set admin password (written as bcrypt hash to persistent storage), optionally configure site name / timezone / Deepgram API key override
- After completion, mark setup done and redirect to the normal UI
- Must be secure against an attacker on the local network racing to complete setup before the operator (consider a device-local secret or PIN printed on the hardware label)

### Viewer Password (v2.0)
Current assumption: network-level access control is sufficient — organizations that want
to restrict who can view the live transcript should run LiveSTT on a private/restricted
network rather than open public Wi-Fi. A viewer password feature (separate from admin
auth) can be added in v2.0 if demand warrants it.

### Branding / White-Label (v2.0, low priority)
Configurable site title and logo so self-hosted deployments aren't all labelled "LiveSTT".
Likely a small set of env vars (`SITE_NAME`, `LOGO_URL`) rendered into the UI at build
or serve time. Low effort when the time comes, but not worth designing around now.

### Q2 2026: Enterprise Features
- [ ] LDAP/SSO Integration
- [ ] Cloud Archiving
- [ ] Mobile App
- [ ] Fully offline STT via local model (Whisper or similar) for hardware with sufficient CPU/GPU

---

**See Also:**
- [Architecture Definition](docs/20_architecture/architecture_definition.md)
- [System Design v8.0](docs/20_architecture/system_design_v8.0.md)

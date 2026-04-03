# Deployment Pre-Flight Checklist (v8.0)

## Overview
Complete this checklist before deploying Live STT (v8.0 Buffered Brain) to production.

---

## 1. Hardware Validation (ASRock NUC N97)

### 1.1 BIOS Settings
- [ ] **Restore AC Power Loss**: Power On
- [ ] **Watchdog Timer**: Enabled
- [ ] **Virtualization**: VT-d Enabled (for Docker)

### 1.2 Audio Interface (Focusrite Solo)
- [ ] **Sample Rate**: 48kHz (System default) -> 16kHz (Resampled by PipeWire)
- [ ] **Gain Knob**: Set to ~50% (Green halo on speech)
- [ ] **Phantom Power (48V)**: OFF (unless using condenser mic)

### 1.3 Thermal Stress
- [ ] **Burn-in**: Run `stress-ng` for 30 mins.
- [ ] **Check**: Case should be warm but touchable. No throttling.

---

## 2. Software Validation

### 2.1 NATS Messaging
- [ ] **Health Check**: `just nats-health` returns OK.
- [ ] **Persistence**: "Black Box" mount (`/data/nats`) is writable.
- [ ] **Spy Test**: `just nats-spy` shows `audio.live` traffic when speaking.

### 2.2 Admin Authentication
- [ ] **ADMIN_PASSWORD_HASH**: Set in environment / `.env` file (generate with
      `python -c "import bcrypt; print(bcrypt.hashpw(b'<password>', bcrypt.gensalt()).decode())"`).
      If unset, the admin UI accepts any password — **must not be left unset in production**.
- [ ] **Verify login**: Open `/admin`, enter the configured password, confirm the session
      management panel loads without a 401 error.

### 2.3 Deepgram Connectivity
- [ ] **API Key**: Valid (Check `stt-provider` logs).
- [ ] **Latency**: Transcript appears < 1s after speech.

### 2.4 Biometrics
- [ ] **Enrollment**: Successfully enroll a test user.
- [ ] **Identification**: Speak as test user -> Transcript shows correct name.

### 2.5 Service Resilience
- [ ] **Restart policy**: All services in `docker-compose.yml` have `restart: always` (ADR-0017)
- [ ] **NATS isolation**: `docker-compose.yml` does NOT expose NATS ports to the host
      (verify no `ports:` block on the `nats` service)
- [ ] **Audio-producer crash recovery**: Kill the `audio-producer` container mid-session
      (`docker kill audio-producer`); verify it restarts and resumes the active session
      from NATS KV within 30 seconds
- [ ] **API-gateway restart**: Kill `api-gateway` while WebSocket clients are connected;
      verify clients reconnect and resume receiving transcripts
- [ ] **Docker healthchecks**: `docker compose ps` shows all services as `healthy`
- [ ] **BalenaOS volume**: Verify named volumes (`nats_data`, `db_data`) are on the
      persistent partition (not a tmpfs or overlay-only mount)

### 2.6 Persistent Data
- [ ] **Data volume**: `/data/db/` contains `livestt.db` (sessions, transcripts, schedules).
      This volume MUST NOT be wiped during updates — it holds all persistent application data.
      Verify the Docker volume is named (not anonymous) and is not re-created on `docker-compose up`.
- [ ] **Backup**: `POST /admin/backup` returns a tar.gz containing `livestt.db`.
      Verify the archive can be extracted and the database is readable.

---

## 3. Failure Recovery

- [ ] **Unplug Internet**: System buffers audio.
- [ ] **Reconnect Internet**: Transcripts "catch up" rapidly.
- [ ] **Power Pull**: System reboots automatically and resumes.

---

## Sign-Off

**Deployed By**: _______________
**Date**: _______________
**Device UUID**: _______________
**WER Score**: ______% *(Requires Milestone 0.5 gold-standard dataset — skip if not yet available)*

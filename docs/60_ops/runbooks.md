# Operational Runbooks

## Overview
This document provides step-by-step procedures for common operational tasks across all deployment tiers.

---

## Runbook Index
1. [Data Harvest (M0.5)](#1-data-harvest-m05)
2. [Initial Deployment (Tier 1 - Balena)](#2-initial-deployment-tier-1---balena)
3. [Initial Deployment (Tier 2/3 - Docker Compose)](#3-initial-deployment-tier-23---docker-compose)
4. [Adding Custom Vocabulary](#4-adding-custom-vocabulary)
5. [Enrolling a Speaker Voiceprint](#5-enrolling-a-speaker-voiceprint)
6. [Recovering from Internet Outage](#6-recovering-from-internet-outage)
7. [Debugging Audio Issues](#7-debugging-audio-issues)
8. [Rotating Deepgram API Key](#8-rotating-deepgram-api-key)
9. [Backup & Restore](#9-backup--restore)
10. [Emergency Shutdown](#10-emergency-shutdown)
11. [Troubleshooting Service Crashes](#11-troubleshooting-service-crashes)

---

## 1. Data Harvest (M0.5)

**Purpose**: Create test datasets for phrase mining (Silver) and regression testing (Gold)

### Silver Standard (Phrase Mining)
**Goal**: Extract high-frequency proper nouns for `initial_phrases.json`

**Steps**:
1. Download YouTube auto-captions (~20 hours)
   ```bash
   # Using yt-dlp
   yt-dlp --write-auto-sub --skip-download --sub-lang en \
          --output "data/silver/%(title)s.%(ext)s" \
          <channel-url>
   ```

2. Extract phrases using mining script
   ```bash
   python scripts/mine_phrases.py data/silver/ \
          --output=config/initial_phrases.json \
          --min-frequency=3
   ```

3. Review and commit
   ```bash
   git add config/initial_phrases.json
   git commit -m "feat(data): update phrase mining results"
   ```

### Gold Standard (Manual Correction)
**Goal**: Create human-verified test corpus for WER regression testing

**Steps**:
1. Download 3 representative service recordings

2. Extract 15 × 3-minute clips (stratified sampling)
   ```bash
   # 30% Sermon (clips 1-5)
   ffmpeg -i service1.mp4 -ss 00:15:00 -t 00:03:00 -vn -ar 16000 tests/data/gold_standard/sermon_01.wav
  
   # 30% Liturgy (clips 6-10)
   ffmpeg -i service2.mp4 -ss 00:05:00 -t 00:03:00 -vn -ar 16000 tests/data/gold_standard/liturgy_01.wav
   
   # 20% Announcements (clips 11-13)
   ffmpeg -i service3.mp4 -ss 00:45:00 -t 00:03:00 -vn -ar 16000 tests/data/gold_standard/announce_01.wav
   
   # 20% Transitions (clips 14-15)
   ffmpeg -i service1.mp4 -ss 00:30:00 -t 00:03:00 -vn -ar 16000 tests/data/gold_standard/transition_01.wav
   ```

3. Manual correction using Subtitle Edit
   - Open `.wav` file
   - Auto-generate transcript (temp)
   - Manually correct all errors
   - Export as plain text (`.txt`)

4. Commit paired files
   ```bash
   git add tests/data/gold_standard/*.wav tests/data/gold_standard/*.txt
   git commit -m "test(gold): add regression test clips"
   ```

**Pass Criteria**: CI regression test must achieve WER < 5%

---

## 2. Initial Deployment (Tier 1 - Balena)

**Prerequisites**:
- Jetson Orin Nano with BalenaOS flashed
- Balena account with fleet created
- Deepgram API key

**Steps**:
```bash
# 1. Install Balena CLI
npm install -g balena-cli

# 2. Login to Balena
balena login

# 3. Add device to fleet
balena device add <FLEET_NAME>
# Follow prompts to provision device

# 4. Set environment variables (in Balena dashboard)
DEEPGRAM_API_KEY=<your_key>
LOG_LEVEL=INFO

# 5. Deploy application
cd /path/to/live-stt
balena push <FLEET_NAME>

# 6. Wait for build (~10 minutes)
# Monitor: https://dashboard.balena-cloud.com

# 7. Verify deployment
balena ssh <DEVICE_UUID>
docker ps  # Should show all services running
```

**Verification**:
- Navigate to public device URL: `https://<device-uuid>.balena-devices.com:8000`
- Should see "Live STT" web UI with "Reconnecting..." status (no audio yet)

---

## 2. Initial Deployment (Tier 2/3 - Docker Compose)

**Prerequisites**:
- Docker & Docker Compose installed
- Deepgram API key

**Steps**:
```bash
# 1. Clone repository
git clone https://github.com/yourusername/live-stt.git
cd live-stt

# 2. Create .env file
cp .env.example .env
nano .env  # Set DEEPGRAM_API_KEY

# 3. (Optional) Set up mock audio for testing
export MOCK_FILE=/path/to/sermon_sample.wav

# 4. Start services
just up  # Or: docker compose up -d

# 5. Check logs
just logs  # Or: docker compose logs -f

# 6. Verify all services running
docker compose ps
```

**Verification**:
- Navigate to `http://localhost:8000`
- Should see web UI with live status

---

## 3. Adding Custom Vocabulary

**Purpose**: Improve transcription accuracy for names, liturgical terms

**Steps**:
```bash
# Option A: Via Admin UI (when available in M8)
# 1. Navigate to http://<device-url>:8000/admin
# 2. Click "PhraseSet" table
# 3. Click "Add Entry"
# 4. Fill:
#    - phrase: "Pastor Mike"
#    - boost: 8
# 5. Click "Save"

# Option B: Direct Database Edit (before M8)
balena ssh <DEVICE_UUID>
sqlite3 /data/config.db
INSERT INTO phrase_set (phrase, boost) VALUES ('Pastor Mike', 8);
.quit

# 3. Restart stt-provider to reload phrases
docker compose restart stt-provider  # Or: balena restart <service-id>
```

**Verification**:
- Speak test phrase during live session
- Check transcript for correct capitalization

---

## 4. Enrolling a Speaker Voiceprint

**Prerequisites**: Milestone 10+ (voiceprint support implemented)

**Steps**:
```bash
# 1. Navigate to enrollment UI
https://<device-url>:8000/admin/enrollment

# 2. Enter speaker name
# 3. Click "Start Recording"
# 4. Read consent script aloud (~15 seconds)
# 5. Click "Submit Enrollment"

# 6. Verify enrollment
balena ssh <DEVICE_UUID>
ls /data/enrollment/  # Should see <speaker-name>.wav.enc
```

**Verification**:
- During next live session, transcripts should show speaker name instead of "Speaker 0"

---

## 5. Recovering from Internet Outage

**Scenario**: Internet drops for 30 minutes during service

**Automatic Recovery**:
1. `stt-provider` detects Deepgram WebSocket disconnect
2. Audio buffered to `/data/buffer/buffer.wav`
3. When internet returns, `stt-provider` reconnects
4. Buffered audio streamed to Deepgram (catch-up mode)
5. Transcripts appear with historical timestamps

**Manual Verification**:
```bash
# Check buffer file size (should grow during outage)
balena ssh <DEVICE_UUID>
ls -lh /data/buffer/
# If buffer.wav exists and is >1MB, buffering is active

# Check stt-provider logs
docker compose logs stt-provider | grep "buffering"
```

**Post-Recovery**:
- No action required (automatic)
- `/data/buffer/buffer.wav` deleted after successful upload

---

## 6. Debugging Audio Issues

### Issue: No Audio Detected
```bash
# 1. Check audio device
balena ssh <DEVICE_UUID>
arecord -l  # List capture devices
# Should show USB audio interface

# 2. Test capture manually
arecord -D hw:1,0 -f S16_LE -r 16000 -c 1 -d 5 test.wav
aplay test.wav  # Should hear 5-second recording

# 3. Check audio-producer logs
docker compose logs audio-producer | grep "RMS"
# Should show RMS values (0 = silence, >1000 = audio detected)
```

### Issue: Clipping Alerts
```bash
# Symptoms: "Audio clipping detected" alerts in UI

# 1. Reduce PA system output level (gain knob on mixer)
# 2. Check audio-producer logs for RMS peaks
docker compose logs audio-producer | grep "clipping"

# Target: RMS < 20000 (70% of max 32767)
```

---

## 7. Rotating Deepgram API Key

**Trigger**: Key compromised, or routine 90-day rotation

**Steps**:
```bash
# 1. Generate new key in Deepgram console
# https://console.deepgram.com/project/<project-id>/keys

# 2. Update environment variable
# Balena:
balena env set DEEPGRAM_API_KEY <new_key> --device <DEVICE_UUID>

# Docker Compose:
nano .env  # Update DEEPGRAM_API_KEY
just up-build  # Restart services

# 3. Verify new key works
docker compose logs stt-provider | grep "Connected to Deepgram"

# 4. Revoke old key in Deepgram console
```

**Downtime**: ~30 seconds (during service restart)

---

## 8. Backup & Restore

### Backup
```bash
# 1. Backup configuration database
balena ssh <DEVICE_UUID>
cp /data/config.db /tmp/config_backup_$(date +%Y%m%d).db
exit

# 2. Download backup
balena ssh <DEVICE_UUID> cat /tmp/config_backup_*.db > config_backup.db

# 3. Backup encryption keys (Tier 2/3 only)
scp user@device:/config/master.key master.key.backup

# 4. Backup voiceprints (optional, if migrating device)
balena ssh <DEVICE_UUID> tar -czf /tmp/enrollment_backup.tar.gz /data/enrollment/
balena ssh <DEVICE_UUID> cat /tmp/enrollment_backup.tar.gz > enrollment_backup.tar.gz
```

### Restore
```bash
# 1. Upload config database
balena ssh <DEVICE_UUID> "cat > /data/config.db" < config_backup.db

# 2. Restore voiceprints
balena ssh <DEVICE_UUID> "cat > /tmp/enrollment.tar.gz" < enrollment_backup.tar.gz
balena ssh <DEVICE_UUID>
tar -xzf /tmp/enrollment.tar.gz -C /data/

# 3. Restart services
docker compose up -d --force-recreate
```

---

## 9. Emergency Shutdown

**Scenarios**: Fire alarm, power maintenance, immediate evacuation

**Steps**:
```bash
# Graceful shutdown (30 seconds)
balena ssh <DEVICE_UUID>
docker compose down
sudo poweroff

# Forced shutdown (if system unresponsive)
# Hold power button for 10 seconds
```

**Data Safety**: All data written to NVMe with `fsync()` calls, no data loss on graceful shutdown

---

## 10. Troubleshooting Service Crashes

### stt-provider Crash Loop
```bash
# Symptoms: Transcripts stop appearing, logs show repeated restarts

# 1. Check last 50 log lines
docker compose logs --tail=50 stt-provider

# Common causes:
# - Invalid Deepgram API key → Update env var
# - Network unreachable → Check firewall (port 443 outbound)
# - Out of disk space → Clean /data/buffer/

# 2. Check disk space
df -h /data

# 3. Manually restart service
docker compose restart stt-provider
```

### api-gateway Not Responding
```bash
# Symptoms: Cannot access web UI

# 1. Check if container is running
docker compose ps | grep api-gateway

# 2. Check logs for errors
docker compose logs api-gateway | grep ERROR

# 3. Restart service
docker compose restart api-gateway

# 4. If still failing, rebuild
just rebuild-hard api-gateway
```

---

**See Also:**
- [HSI](../20_architecture/hsi.md) - Service topology
- [Secrets Manifest](secrets_manifest.md) - Credential management
- [CI/CD](cicd.md) - Automated deployment

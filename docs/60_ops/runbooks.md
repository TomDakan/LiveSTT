# Operational Runbooks (v8.0)

## Overview
This document provides step-by-step procedures for common operational tasks for the Live STT system (v8.0 Buffered Brain).

---

## Runbook Index
1. [NATS Debugging](#1-nats-debugging)
2. [Initial Deployment (Industrial NUC)](#2-initial-deployment-industrial-nuc)
3. [Recovering from Internet Outage](#3-recovering-from-internet-outage)
4. [Debugging Audio Issues](#4-debugging-audio-issues)
5. [Rotating Deepgram API Key](#5-rotating-deepgram-api-key)
6. [Emergency Shutdown](#6-emergency-shutdown)
7. [Troubleshooting Service Crashes](#7-troubleshooting-service-crashes)

---

## 1. NATS Debugging

**Purpose**: Inspect message flow and troubleshoot communication issues.

### 1.1 Spy on All Messages
Watch live traffic on the bus:
```bash
just nats-spy
# Output:
# [#1] Received on "audio.live"
# [#2] Received on "transcript.raw": {"text": "Hello world", ...}
```

### 1.2 Check Server Health
Verify NATS JetStream status:
```bash
just nats-health
# Output: OK
```

### 1.3 Inspect Specific Topic
Debug audio flow specifically:
```bash
just nats-tail subject="audio.live"
```

---

## 2. Initial Deployment (Industrial NUC)

**Prerequisites**:
- ASRock NUC N97 with BalenaOS flashed
- Deepgram API key

**Steps**:
1.  **Provision Device**: Follow [Assembly Guide](../40_hardware/assembly_guide.md).
2.  **Set Variables** (Balena Dashboard):
    - `DEEPGRAM_API_KEY`: `<your_key>`
    - `LOG_LEVEL`: `INFO`
3.  **Deploy**:
    ```bash
    balena push live-stt-production
    ```
4.  **Verify**:
    - Check "Black Box" mount: `balena ssh <uuid> mount | grep nats`
    - Check NATS health: `docker logs nats`

---

## 3. Recovering from Internet Outage

**Scenario**: Internet drops for 30 minutes during service.

**Automatic Recovery**:
1.  `stt-provider` detects disconnect.
2.  Audio is buffered to NATS JetStream (persisted to `/data/nats` "Black Box").
3.  When internet returns, `stt-provider` replays missed messages.
4.  Transcripts appear with historical timestamps.

**Manual Verification**:
```bash
# Check NATS JetStream storage usage
balena ssh <uuid>
du -sh /data/nats
```

---

## 4. Debugging Audio Issues

### Issue: No Audio Detected
```bash
# 1. Spy on audio.raw subject
just nats-tail subject="audio.live"
# If no messages appear, audio-producer is failing to capture.

# 2. Check audio-producer logs
docker compose logs audio-producer
# Look for "Input overflow" or "Device not found"
```

### Issue: Clipping Alerts
```bash
# 1. Check system.alert subject
just nats-tail subject="system.alert"
# Look for {"type": "clipping", "severity": "warn"}

# 2. Adjust Focusrite Gain Knob (aim for green halo, not red)
```

---

## 5. Rotating Deepgram API Key

**Trigger**: Key compromised or expired.

**Steps**:
1.  Generate new key in Deepgram Console.
2.  Update Balena Variable: `DEEPGRAM_API_KEY`.
3.  Services will auto-restart.
4.  Verify:
    ```bash
    docker logs stt-provider | grep "Connected to Deepgram"
    ```

---

## 6. Emergency Shutdown

**Scenarios**: Fire alarm, power maintenance.

**Steps**:
1.  **Graceful**: `balena ssh <uuid> poweroff`
2.  **Forced**: Hold power button 10s.
    - *Note*: "Black Box" journaling prevents corruption even on forced shutdown.

---

## 7. Troubleshooting Service Crashes

### stt-provider Crash Loop
```bash
# 1. Check logs
docker logs stt-provider --tail 50

# Common causes:
# - Invalid API Key (401 Unauthorized)
# - NATS unreachable (Check nats container)
```

### NATS Server Failing
```bash
# 1. Check disk space (Black Box full?)
df -h /data

# 2. Check permissions
ls -l /data/nats
# Should be owned by nats:nats (1000:1000)
```

---

**See Also:**
- [NATS Tooling](nats_tooling.md) - Advanced debugging
- [HSI](../20_architecture/hsi.md) - Service topology

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

### 2.2 Deepgram Connectivity
- [ ] **API Key**: Valid (Check `stt-provider` logs).
- [ ] **Latency**: Transcript appears < 1s after speech.

### 2.3 Biometrics
- [ ] **Enrollment**: Successfully enroll a test user.
- [ ] **Identification**: Speak as test user -> Transcript shows correct name.

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
**WER Score**: ______%

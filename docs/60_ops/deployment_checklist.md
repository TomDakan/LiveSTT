# Deployment Pre-Flight Checklist

## Overview
Complete this checklist before deploying Live STT to production hardware.

---

## Pre-Deployment Validation

### Hardware Stability
- [ ] **Thermal Burn-in**: 60-minute stress test passes
  ```bash
  stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 1G --timeout 3600s
  ```
  - **Pass Criteria**: No thermal throttling, temperatures remain within spec
  - **Document**: Record peak temperatures in deployment notes

### Network Resilience
- [ ] **Network Disconnect Test**: 10-minute offline test
  - Disconnect internet/WAN
  - Continue audio input for 10 minutes
  - Reconnect network
  - **Pass Criteria**: All buffered audio transcribed correctly, timestamps ordered

### Data Compliance
- [ ] **Data Retention Verified**: `data-sweeper` service functional
  - Create test files in `/data/review/`
  - Wait for `RETENTION_HOURS` + 1 hour
  - **Pass Criteria**: Files automatically deleted

### Accuracy
- [ ] **Gold Standard Regression Test**: WER < 5%
  ```bash
  just test-gold-corpus
  ```
  - **Pass Criteria**: Word Error Rate < 5% against `tests/data/gold_standard/`
  - **Document**: Record exact WER percentage

### Security (Tier-Specific)

#### Tier 1 (Jetson)
- [ ] TPM key sealing verified
- [ ] Secure Boot enabled
- [ ] Full-disk encryption (LUKS) configured

#### Tier 2/3 (Desktop/CI)
- [ ] Encryption keys secured (not in Git)
- [ ] `.env` file properly gitignored
- [ ] Master encryption key permissions: `chmod 600`

### Service Health
- [ ] All core services start successfully
  - `broker`
  - `audio-producer`
  - `stt-provider`
  - `api-gateway`
- [ ] Optional services configured per tier
  - `audio-classifier` (if music detection enabled)
  - `identifier` (Tier 1/2 only, if GPU available)
  - `health-watchdog` (recommended)
  - `data-sweeper` (recommended for compliance)

### Integration Tests
- [ ] WebSocket connection established from client
- [ ] Transcripts appear in UI within 500ms
- [ ] Admin dashboard accessible (local network only)
- [ ] PhraseSet modifications reflected in transcripts

---

## Post-Deployment

### First 24 Hours
- [ ] Monitor logs for errors
  ```bash
  docker compose logs -f --tail=100
  ```
- [ ] Verify disk space usage trends
- [ ] Test user-facing WebSocket connections
- [ ] Confirm data retention automation working

### First Week
- [ ] Review Gold Standard WER in production environment
- [ ] Validate buffering behavior during network fluctuations
- [ ] Confirm no thermal issues during extended use
- [ ] Gather user feedback on transcript accuracy

---

## Rollback Plan

If critical issues are discovered:

1. **Stop services**: `docker compose down`
2. **Restore previous version**: `git checkout <previous-tag>`
3. **Redeploy**: `docker compose up -d`
4. **Verify**: Run smoke tests
5. **Document**: Record issue in GitHub Issues

---

## Sign-Off

**Deployed By**: _______________  
**Date**: _______________  
**Hardware Tier**: Tier 1 / Tier 2 / Tier 3 _(circle one)_  
**Git Commit**: _______________  
**WER Result**: _______________%  

**Notes**:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

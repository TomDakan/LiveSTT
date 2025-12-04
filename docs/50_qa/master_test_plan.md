# Master Test Plan

## 1. Introduction
This document outlines the testing strategy for the Live STT system, covering unit, integration, and end-to-end testing across all hardware tiers.

---

## 2. Test Scope

### In Scope
- **Core Services**: audio-producer, broker, stt-provider, api-gateway
- **ML Services**: audio-classifier, identifier (Tier 1/2 only)
- **Hardware Tiers**: Jetson Orin Nano (Tier 1), Desktop (Tier 2), CI (Tier 3)
- **Resilience**: Network outages, power loss, service crashes

### Out of Scope
- **Deepgram API Internal Accuracy**: We assume Deepgram works as advertised
- **BalenaOS Internals**: We assume the OS is stable
- **Hardware Durability**: Physical drop testing, water resistance

---

## 3. Data Strategy (v6.2)

### 3.1 Silver Standard (Phrase Mining)
- **Source**: YouTube Auto-Captions (~20 hours of church services)
- **Purpose**: Extract high-frequency proper nouns for `initial_phrases.json`
- **Tool**: `scripts/mine_phrases.py`
- **Output**: PhraseSet seed file (staff names, liturgical terms, locations)
- **Constraint**: Never used for WER calculation (AI-generated, contains inherent errors)

### 3.2 Gold Standard (Regression Testing)
- **Source**: Manually corrected transcripts (Human-in-the-Loop)
- **Volume**: ~1 hour (20 × 3-minute clips)
- **Composition**: Stratified sampling
  - 30% Sermon (main teaching content)
  - 30% Liturgy (responsive readings, prayers)
  - 20% Announcements (community updates)
  - 20% Transitions (worship team, scene changes)
- **Purpose**: CI regression testing
- **Pass Criteria**: Word Error Rate (WER) < 5%
- **Location**: `tests/data/gold_standard/`

**Workflow**:
1. Download service recordings
2. Extract representative clips using ffmpeg
3. Use Subtitle Edit for manual transcript correction
4. Commit `.wav` + `.txt` pairs to Git
5. CI pipeline runs Gold clips through `stt-provider` and calculates WER

---

## 4. Testing Levels

### 3.1 Unit Testing (Tier 3)
- **Focus**: Individual functions and classes
- **Tools**: `pytest`, `pytest-mock`
- **Coverage Target**: 80% line coverage
- **Execution**: CI pipeline (every commit)

**Key Areas**:
- Audio chunking logic
- ZMQ message serialization
- Database CRUD operations
- Configuration parsing

### 3.2 Integration Testing (Tier 3)
- **Focus**: Service-to-service communication
- **Tools**: `docker compose`, `pytest` integration suite
- **Execution**: CI pipeline (every PR)

**Key Scenarios**:
- Audio producer → Broker → STT Provider flow
- WebSocket client connection & subscription
- Database persistence of transcripts
- Error handling (e.g., Deepgram API timeout)

### 3.3 End-to-End (E2E) Testing (Tier 1/2)
- **Focus**: Full system validation with real hardware
- **Tools**: Manual verification, automated load scripts
- **Execution**: Before release

**Key Scenarios**:
- **Full Session**: 60-minute continuous transcription
- **Outage Recovery**: Disconnect internet for 5 mins, verify catch-up
- **Voiceprint**: Enroll speaker, verify identification in live stream
- **Performance**: Verify <500ms latency under load

---

## 4. Test Environment

| Environment | Hardware | Purpose | Data |
|-------------|----------|---------|------|
| **Local Dev** | Tier 2/3 | Unit/Integration tests | Mock audio files |
| **CI Runner** | Tier 3 | Automated regression | Synthetic data |
| **Staging** | Tier 1 | E2E / Acceptance testing | Real microphone input |
| **Production** | Tier 1 | Live monitoring | Real service audio |

---

## 5. Test Data Strategy

### Mock Audio
- **Source**: `test_fixtures/audio/sermon_sample.wav` (16kHz mono)
- **Usage**: Injected by `audio-producer` when `MOCK_FILE` env var is set
- **Content**: 5 minutes of clear speech with known transcript

### Voiceprints
- **Test Set**: 5 distinct speakers (male/female, various accents)
- **Enrollment**: Scripted consent reading (15s)
- **Validation**: Cross-validation matrix (verify no false positives)

---

## 6. Automated Test Suite

### Structure
```
tests/
├── unit/
│   ├── test_audio_producer.py
│   ├── test_stt_provider.py
│   └── ...
├── integration/
│   ├── test_zmq_flow.py
│   ├── test_database.py
│   └── ...
├── e2e/
│   ├── test_latency.py
│   └── ...
└── fixtures/
    └── sermon_sample.wav
```

### Running Tests
```bash
# Run all unit tests
just test

# Run integration tests (requires Docker)
just test-integration

# Run specific test
pytest tests/unit/test_audio_producer.py
```

---

## 7. Manual Test Cases

### TC-001: Cold Boot to Live
1. Power on device
2. Wait 60 seconds
3. Speak into microphone
4. **Expected**: Transcript appears on Web UI within 2 seconds

### TC-002: Internet Recovery
1. Start transcription
2. Unplug Ethernet/WAN
3. Continue speaking for 2 minutes
4. Reconnect Ethernet
5. **Expected**: Buffered transcripts appear within 30 seconds, ordered correctly

### TC-003: Speaker Identification
1. Enroll "Pastor Mike"
2. Have "Pastor Mike" speak
3. **Expected**: Transcript labeled "Pastor Mike"
4. Have unknown person speak
5. **Expected**: Transcript labeled "Speaker 0"

---

## 8. Defect Management

### Severity Levels
- **Critical**: System crash, data loss, no transcription
- **High**: High latency (>2s), speaker ID failure, API key leak
- **Medium**: UI glitch, minor transcript formatting issue
- **Low**: Typo in logs, documentation error

### Reporting
- **Tool**: GitHub Issues
- **Required Info**: Logs, steps to reproduce, hardware tier

---

## 9. Release Criteria

- [ ] All unit tests pass (100%)
- [ ] Integration tests pass (100%)
- [ ] Code coverage > 80%
- [ ] **Gold Standard regression test: WER < 5%**
- [ ] No critical/high open defects
- [ ] Successful 1-hour stability run on Tier 1 hardware
- [ ] Security scan (Bandit/Safety) clean

---

**See Also:**
- [Performance Benchmarks](performance_benchmarks.md) - Latency/throughput targets
- [CI/CD](../60_ops/cicd.md) - Automation pipeline

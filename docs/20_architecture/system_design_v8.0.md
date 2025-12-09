# System Design Document: v8.0 ("Buffered Brain")

**Status**: ACTIVE
**Target Platform**: Industrial x86 (Intel N97)
**Pattern**: Buffered Split-Brain (Store-and-Forward + Parallel Processing)
**Date**: December 2025

---

## 1. Executive Summary

The v8.0 architecture combines the "Split-Brain" reliability of v7.3 with a robust "Store-and-Forward" data strategy. It introduces a pre-roll buffer to catch audio *before* a session starts and ensures that both Transcription (Deegram) and Identification (OpenVINO) are applied to every second of audio, whether Live or Backfilled.

**Key Changes from v7.3:**
1.  **Pre-Roll Buffering**: Always-on recording into a memory ring buffer ensures no words are lost during "Wake Up".
2.  **Dual-Lane Processing**: Both `stt-provider` and `identifier` act as dual-consumers, processing high-priority "Live" data and background "Backfill" data simultaneously.
3.  **Server-Side Fusion**: The `identity-manager` provides a strict "Zipper" layer, ensuring that the Web UI receives fully attributed text rather than raw streams.

---

## 2. System Architecture

### 2.1 Hardware Topology
*Remains unchanged from v7.3.*
- **Compute**: ASRock Industrial NUC BOX-N97.
- **Storage**: Transcend 256GB NVMe (Power Loss Protected) + Loopback Journaling.
- **Audio**: Focusrite Scarlett Solo (-127dB EIN).

### 2.2 NATS Stream Topology (The Backbone)

We utilize 3 distinct persistence layers to manage data lifecycle and separation of concerns.

#### A. `PRE_BUFFER` (The Rolling Cache)
Captures "Idle" audio.
- **Subjects**: `preroll.audio`
- **Storage**: **Memory** (Ring Buffer)
- **Retention**: Limits (Max Age: 6 Minutes)
- **Role**: Allows the user to "Go Back in Time" 5 minutes when hitting Record.

#### B. `AUDIO_STREAM` (The Source of Truth)
Stores the permanent session audio.
- **Subjects**: `audio.live.>`, `audio.backfill.>`
- **Storage**: **File** (NVMe)
- **Retention**: WorkQueue (Messages persist until Ack'd by processors)
- **Max Age**: 60 Minutes (Safety Net)

#### C. `TRANSCRIPTION_STREAM` (The Result)
Stores all generated text, identity events, and fused results.
- **Subjects**:
    - `transcript.raw.>` (Deepgram Output)
    - `transcript.identity.>` (OpenVINO Output)
    - `transcript.final.>` (Fused "Zipped" Output)
- **Storage**: **File** (NVMe)
- **Retention**: Limits (Max Age: 7 Days)
- **Role**: Serves as the database for the Web UI.

---

## 3. Component Design

### 3.1 Service: `audio-producer` (The Ingress)
- **State**: `IDLE` vs `ACTIVE`.
- **Logic**:
    - **Atomic Switch**: Routes microphone data to `preroll.audio` (IDLE) or `audio.live` (ACTIVE).
    - **Flash Flush**: On "Start Session", triggers a background task to move `PRE_BUFFER` data to `audio.backfill`.
    - **EOS**: Appends End-of-Stream headers to the backfill stream.

### 3.2 Service: `stt-provider` (The Ear)
- **Role**: Deepgram Transcription.
- **Dual Pipeline**:
    1.  **Live Worker**: Priority `High`. Subscribes to `audio.live`. Minimal Latency.
    2.  **Backfill Worker**: Priority `Background`. Subscribes to `audio.backfill`. Throttled upload to Deepgram.
- **Output**: Publishes to `transcript.raw.{session_id}`.

### 3.3 Service: `identifier` (The Biometric Brain)
- **Role**: OpenVINO Speaker Identification.
- **Dual Pipeline**:
    1.  **Live Worker**: Priority `High`. Fast-path vector lookup.
    2.  **Backfill Worker**: Priority `Background`. Processes backfill audio chunks to identify "Who spoke 3 minutes ago".
- **Output**: Publishes to `transcript.identity.{session_id}`.

### 3.4 Service: `identity-manager` (The Zipper)
- **Role**: Server-Side Data Fusion.
- **Logic**:
    - Subscribes to `transcript.raw` (Text) AND `transcript.identity` (Who).
    - **Buffering**: Maintains a sliding window of recent text segments.
    - **Matching**: Applies "Identity Tags" to Text Segments based on overlapping Timestamps.
    - **Resolution**: Handles out-of-order arrival (e.g., Backfill identity arrives after Live text).
- **Output**: Publishes `transcript.final.{session_id}` containing fully attributed JSON objects (Text + Speaker Name).

### 3.5 Service: `api-gateway` (The View)
- **Role**: Simple Relay.
- **Logic**:
    - Replays `transcript.final.{session_id}` to connected WebSockets.
    - Does **NOT** perform business logic or merging.

---

## 4. Workflows

### 4.1 "The Time Travel Start"
1.  System is IDLE. `audio-producer` loops audio into `PRE_BUFFER`.
2.  User clicks "Start Session".
3.  `audio-producer`:
    - Switches Live Microphone -> `audio.live`.
    - Spawns Task: Drain `PRE_BUFFER` -> `audio.backfill`.
4.  `stt-provider` & `identifier`:
    - Spin up **Live Workers** immediately (Latency < 500ms).
    - Spin up **Backfill Workers** to process the past 5 mins.
5.  `identity-manager`:
    - Receives Live events (Real-time).
    - Receives Backfill events (Burst).
    - Merges and emits `transcript.final`.
6.  Web UI:
    - Receives a flood of "Past" messages (Backfill) followed by smooth "Live" messages.

# System Design Document: v7.3 (Industrial Split-Brain)

**Status**: ARCHITECTURE LOCKED
**Target Platform**: Industrial x86 (Intel N97)
**Pattern**: Parallel Processing Streams (Cloud Text + Edge Identity)
**Date**: November 26, 2025

---

## 1. Executive Summary

The v7.3 architecture solves the "Resource Contention" and "Reliability" risks of the previous v6.x Jetson design by pivoting to a robust industrial x86 platform.

- **The Shift**: Abandon NVIDIA Jetson for a Fanless ASRock Industrial NUC (N97).
- **The Strategy**: Decouple Transcription (Cloud) from Identification (Edge). This allows us to use massive cloud models for high-accuracy text (**Deepgram Nova-3**) while running zero-latency biometric security locally on the Intel iGPU (**OpenVINO**).
- **The Result**: A headless, 365-day "Set and Forget" appliance that eliminates OOM (Out of Memory) kills and filesystem corruption.

---

## 2. System Architecture

### 2.1 Hardware Topology

The system is contained within a single physical enclosure (The "Brain").

- **Compute**: ASRock Industrial NUC BOX-N97 (Fanless)
  - *Role*: Runs all logic, databases, and Docker containers.
- **Memory**: 16GB DDR4-3200 (Single SODIMM)
  - *Benefit*: Eliminates swap-thrashing; fits entire OS + Databases in RAM.
- **Storage**: Transcend MTE712A 256GB NVMe (Industrial Grade)
  - *Feature*: **Power Loss Protection (PLP)** capacitors prevent file corruption during hard power cuts.
- **Audio Input**: Focusrite Scarlett Solo 4th Gen
  - *Benefit*: -127dB EIN noise floor provides "Clean Lab" quality audio for Biometric Vectorization.
- **Watchdog**: Hardware WDT (ITE IT8xxx Chipset)
  - *Role*: Hard-resets the CPU if the OS kernel hangs for >60 seconds.

### 2.2 Data Path (The "Split-Brain")

The audio signal splits immediately upon capture into two parallel processing streams:

1.  **Stream A (Cloud "Ear")**:
    - `Audio` → `Deepgram API` → `Text/Diarization` (Latency: ~500ms)
    - *Role*: High-accuracy transcription and speaker segmentation (Speaker A vs Speaker B).

2.  **Stream B (Edge "Eye")**:
    - `Audio` → `Silero VAD` → `WeSpeaker (OpenVINO)` → `Vector ID` (Latency: ~100ms)
    - *Role*: Biometric identification (Speaker A = "Alice").

3.  **The Merge (Hybrid Tagging)**:
    - The **Identity Manager** applies the biometric labels to the Deepgram speaker segments.
    - *Strategy*: "Hybrid Tagging" - Use Deepgram for *when* someone spoke, use Local Biometrics only to *tag* who it was. This avoids timestamp drift issues.

---

## 3. Component Design (Microservices)

### 3.1 Service: `audio-producer` (Hardware Abstraction)
- **Role**: The single source of truth for audio data.
- **Input**: PipeWire Source (Focusrite Scarlett Solo).
- **Configuration**: 16kHz, Mono, S16LE.
- **Logic**:
  - Direct Hardware Access (via PipeWire) to prevent drift.
  - Publishes raw PCM chunks to internal NATS subject `audio.raw`.
- **Safety**: Uses a Ring Buffer to prevent blocking if consumers lag.

### 3.2 Service: `stt-provider` (The Ear)
- **Role**: Transcription & Rough Diarization.
- **Logic**:
  - Subscribes to `audio.raw`.
  - Streams via WebSocket to **Deepgram Nova-3**.
  - Config: `smart_format=true`, `diarize=true`, `interim_results=true`.
- **Resilience**:
  - **Offline Mode**: If internet is lost, diverts audio to the "Black Box" Loopback Filesystem to catch up later.
- **Output**: Publishes ephemeral text events to `text.transcript`.

### 3.3 Service: `identifier` (The Biometric Brain)
- **Role**: Speaker Identification (Who is speaking?).
- **Engine**: OpenVINO Runtime (Targeting N97 iGPU).
- **Pipeline**:
  1.  **Trigger**: Silero VAD v5 (ONNX) detects voice activity.
  2.  **Capture**: Accumulates 1.5s of audio.
  3.  **Inference**: WeSpeaker ResNet34 (INT8 Quantized) extracts a 256-dimension vector.
  4.  **Lookup**: Queries local **LanceDB** vector store.
  5.  **Threshold**: Matches if Cosine Similarity > 0.85.
- **Output**: Publishes `identity.event` (e.g., `User: Alice, Conf: 0.92`) to NATS.

### 3.4 Service: `identity-manager` (The Time Zipper)
- **Role**: Sensor Fusion / Hybrid Tagging.
- **Problem**: Deepgram knows *what* was said (but uses generic "Speaker 0"). The Identifier knows *who* spoke (but has no text).
- **Logic (Hybrid Tagging)**:
  - Listens to both `text.transcript` and `identity.event`.
  - Maintains a "Session Map" of `Deepgram Speaker ID` → `Biometric User ID`.
  - **Rule**: If "Speaker 0" is active, and Biometrics identifies "Alice" with high confidence, map `Speaker 0 = Alice` for the session.
  - **Lazy Re-identification**: Only re-scan speaker if confidence drops or silence > 30s.
- **Output**: Broadcasts the merged event to the API Gateway.

### 3.5 Service: `api-gateway` (The Facade)
- **Role**: Secure Public Interface.
- **Protocol**: WebSocket (`ws://0.0.0.0:8000/events`).
- **Logic**:
  - Subscribes to internal NATS topics.
  - Sanitizes JSON (removes internal debug flags).
  - Broadcasts to any connected LAN clients (BYOD / Dashboards).
- **Security**: Enforces "Read-Only" (External clients cannot publish to NATS).

---

## 4. Data Strategy

### 4.1 "Black Box" Persistence
To prevent filesystem corruption on the NUC, we do not write NATS data directly to the OS partition.

- **Mechanism**: A pre-allocated 4GB Loopback File (`/data/nats.img`).
- **Format**: `ext4` with `data=journal` (Full Data Journaling).
- **Mount**: Mounted at `/var/lib/nats` inside the container.
- **Guarantee**: Atomic writes. If power is cut, the journal replays on boot, ensuring zero corruption.

### 4.2 Biometric Enrollment
- **Storage**: **LanceDB** (Embedded Vector DB).
- **Backup**: Since Vector IDs are critical, the LanceDB folder is rsync'd to the "Black Box" partition hourly.

---

## 5. Master Roadmap (v7.3 Build)

### Phase 1: The "Ironclad" Foundation
- **Goal**: Crash-proof Hardware Setup.
- **Tasks**:
  - Provision ASRock N97 with BalenaOS.
  - Configure BIOS: "Power On After Fail", "Watchdog Enabled".
  - Implement `entrypoint.sh` for `data=journal` loopback mount.
  - **Validation**: 50x Hard Power Pull Test.

### Phase 2: The Model Conversion
- **Goal**: Fit AI into the N97.
- **Tasks**:
  - Export Silero VAD and WeSpeaker to ONNX.
  - Run ONNX Quantization (Float32 → INT8).
  - Write OpenVINO Python shim for iGPU offload.
  - **Validation**: Inference speed < 50ms per chunk.

### Phase 3: The "Zipper" Logic
- **Goal**: Accurate Speaker Attribution.
- **Tasks**:
  - Implement `identity-manager` service.
  - Build "Session Map" class.
  - Implement "Hybrid Tagging" logic.
  - **Validation**: Conversation Test (Two speakers swapping turns).

### Phase 4: Integration & Burn-In
- **Goal**: Deployment Ready.
- **Tasks**:
  - Integrate Focusrite Audio Source (PipeWire).
  - Full System Burn-in (7 Days).
  - **Validation**: No memory leaks, no zombie processes.

---

## 6. Bill of Materials (BOM)

| Component | Model | Specification | Est. Price |
|-----------|-------|---------------|------------|
| **Compute** | ASRock Ind. NUC BOX-N97 | Intel N97, Fanless Chassis | $240 |
| **Memory** | Crucial 16GB SODIMM | DDR4-3200 | $35 |
| **Storage** | Transcend MTE712A | 256GB NVMe w/ PLP | $65 |
| **Audio** | Focusrite Scarlett Solo 4th Gen | Low-Noise Preamp (-127dB EIN) | $140 |
| **Cabling** | USB-C to USB-C | High-quality Shielded | $15 |
| **Total** | | | **~$495** |

# Hardware/Software Interface (HSI) Document

## 1. Overview
This document defines the hardware/software interface for the Live STT system, including Docker service configurations, ZMQ topology, volume mounts, and hardware dependencies.

## 2. Docker Service Topology

### 2.1 Service Mesh
```yaml
services:
  broker:             # Central message bus handling both audio and transcripts
  audio-producer:     # Microphone capture
  api-gateway:        # Web UI & config
  stt-provider:       # Deepgram client
  audio-classifier:   # Optional: Music detection
  identifier:         # Optional: Speaker ID (GPU required)
  health-watchdog:    # Optional: Service monitoring
  data-sweeper:       # Optional: Automated data retention compliance
```

### 2.2 Network Configuration
```yaml
networks:
  internal_overlay:
    driver: bridge
    internal: false  # Allows stt-provider to reach Deepgram API
```

**All services** communicate via ZMQ through the internal network. Only `api-gateway` exposes ports to the host.

## 3. ZMQ Broker Topology

### 3.1 Broker Configuration
```cpp
// broker (C++ zmq_proxy)
zmq::socket_t frontend(context, ZMQ_XSUB);  // Receive from publishers
zmq::socket_t backend(context, ZMQ_XPUB);   // Send to subscribers

frontend.bind("tcp://*:5555");  // Publishers connect here
backend.bind("tcp://*:5556");   // Subscribers connect here
zmq::proxy(frontend, backend);  // Bidirectional relay
```

### 3.2 Topic Hierarchy
| Topic | Publisher | Subscriber(s) | Payload Format |
|-------|-----------|---------------|----------------|
| `audio.raw` | audio-producer | stt-provider, audio-classifier, identifier | Binary PCM (16-bit, 16kHz, mono) |
| `text.transcript` | stt-provider | api-gateway | JSON: `{"text": "...", "confidence": 0.95, "speaker": 0}` |
| `system.alert` | audio-producer, stt-provider, audio-classifier | api-gateway | JSON: `{"type": "clipping"|"reconnecting"|"music", "severity": "warn"}` |
| `identity.event` | identifier | api-gateway | JSON: `{"speaker_id": "Tom", "confidence": 0.89, "timestamp_ms": 12345}` |

### 3.3 Connection Strings
```python
# Publishers
socket = context.socket(zmq.PUB)
socket.connect("tcp://broker:5555")

# Subscribers
socket = context.socket(zmq.SUB)
socket.connect("tcp://broker:5556")
socket.setsockopt_string(zmq.SUBSCRIBE, "audio.raw")
```

## 4. Volume Mounts

### 4.1 Persistent Data (`/data`)
```yaml
volumes:
  - ./data:/data

/data/
  ├── config.db         # SQLite (api-gateway)
  ├── buffer/           # Audio buffer during outages (stt-provider)
  ├── review/           # Low-confidence snippets (stt-provider)
  │   └── {uuid}.enc    # AES-256 encrypted .wav
  └── enrollment/       # Voiceprint audio (identifier)
      └── Tom.wav.enc
```

**Permissions**: `stt-provider` (write), `api-gateway` (read/write), `identifier` (read)

### 4.2 Configuration (`/config`)
```yaml
volumes:
  - ./config:/config:ro

/config/
  ├── initial_phrases.json   # Deepgram PhraseSet seed
  └── master.key             # Encryption key (Tier 2/3) or TPM ref (Tier 1)
```

### 4.3 Secrets
```bash
# Injected via environment (Docker Compose) or Balena Supervisor
DEEPGRAM_API_KEY=<redacted>
ENCRYPTION_KEY_PATH=/config/master.key  # Or tpm://slot/1 (Tier 1)
```

## 5. Hardware Dependencies

### 5.1 Audio Input
- **Interface**: ALSA (Linux)
- **Device**: `/dev/snd/` (auto-selected by PortAudio/sounddevice)
- **Format**: 16-bit PCM, 16kHz, mono (output to ZMQ)
- **Buffer**: 100ms chunks (1600 samples)

**Input Channel Handling**:
- **Mono microphone**: Direct capture, no processing
- **Stereo PA feed**: Auto-detected, downmixed to mono via channel averaging
  ```python
  # audio-producer automatic downmix
  if input_channels == 2:
      stereo_array = np.frombuffer(chunk, dtype=np.int16).reshape(-1, 2)
      mono_array = stereo_array.mean(axis=1).astype(np.int16)  # L+R / 2
      chunk = mono_array.tobytes()
  ```
- **Performance Impact**: \<1ms latency, negligible CPU usage

```python
# audio-producer configuration
import sounddevice as sd

def callback(indata, frames, time, status):
    if status:
        print(status)
    # indata is numpy array (frames, channels)
    zmq_socket.send(indata.tobytes())

with sd.InputStream(channels=1, samplerate=16000, dtype='int16', callback=callback):
    sd.sleep(1000000)
```

### 5.2 GPU (Optional - Tier 1/2)
| Service | Model | VRAM Required | Runtime |
|---------|-------|---------------|---------|
| **identifier** | SpeechBrain ECAPA-TDNN | ~500MB | PyTorch (CUDA 12 / l4t) |
| **audio-classifier** | YAMNet (TFLite) | ~10MB | TensorFlow Lite (CPU) |

**Dockerfile Strategy**:
```dockerfile
ARG BASE_IMAGE=python:3.13-slim  # Tier 3 (CPU)
# Override: --build-arg BASE_IMAGE=nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3  # Tier 1
FROM ${BASE_IMAGE}
```

### 5.3 Storage
- **Minimum**: 16GB (OS + Docker images)
- **Recommended**: 64GB NVMe (for audio buffering during extended outages)
- **Encryption**: LUKS (full disk) + AES-256 (per-file for PII)

## 6. Port Mappings

| Service | Internal Port | External Port | Protocol | Purpose |
|---------|---------------|---------------|----------|---------|
| api-gateway | 8000 | 8000 | HTTP/WSS | Web UI, WebSocket |
| api-gateway | 8001 | - | HTTP | Admin dashboard (internal only) |
| broker | 5555 | - | TCP (ZMQ) | Publisher ingress |
| broker | 5556 | - | TCP (ZMQ) | Subscriber egress |

**Public Access**: Via Balena Public URL (HTTPS) or travel router (local network)

## 7. Restart Policies
```yaml
restart: always  # broker, api-gateway, stt-provider
restart: "no"    # audio-classifier, identifier, health-watchdog (optional services)
```

## 8. Resource Limits (Tier 1 - Jetson Orin Nano)
```yaml
services:
  stt-provider:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
  identifier:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
```

### 8.X Service: data-sweeper (Optional - Compliance)

**Purpose**: Automated data retention compliance  
**Schedule**: Daily cron job

```yaml
data-sweeper:
  build: ./services/data-sweeper
  container_name: data-sweeper
  volumes:
    - ./data/review:/data/review:rw
  environment:
    - RETENTION_HOURS=24
    - CRON_SCHEDULE=0 0 * * *  # Daily at midnight UTC
  restart: unless-stopped
```

**Logic**: Deletes encrypted audio snippets in `/data/review/` older than `RETENTION_HOURS`

---

## 9. Health Checks
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**Monitored by**: `health-watchdog` → Exposes `/status` endpoint for `api-gateway`

---

**See Also:**
- [Architecture Definition](architecture_definition.md) - High-level system design
- [Deployment Runbooks](../60_ops/runbooks.md) - Operational procedures
- [System Design](../system_design.md) - Section 2.3 (Messaging Core), Section 7 (Deployment)

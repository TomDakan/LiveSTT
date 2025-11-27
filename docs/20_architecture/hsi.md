# Hardware/Software Interface (HSI) Document (v7.3)

## 1. Overview
This document defines the hardware/software interface for the Live STT system (v7.3), including Docker service configurations, NATS topology, volume mounts, and hardware dependencies.

## 2. Docker Service Topology

### 2.1 Service Mesh
```yaml
services:
  nats:               # Central event bus (JetStream)
  audio-producer:     # Microphone capture (PipeWire)
  stt-provider:       # Deepgram client (Cloud Ear)
  identifier:         # Biometric ID (Edge Eye)
  identity-manager:   # Time Zipper (Hybrid Tagging)
  api-gateway:        # Web UI & WebSocket server
  nats-surveyor:      # Observability (Dev only)
```

### 2.2 Network Configuration
```yaml
networks:
  host:               # Required for PipeWire access (audio-producer)
  internal_overlay:   # For other services
```

## 3. NATS Topology

### 3.1 Broker Configuration
- **Image**: `nats:2.10-alpine`
- **Flags**: `-js` (Enable JetStream)
- **Store**: `/data/nats` (Mapped to "Black Box" loopback)

### 3.2 Subject Hierarchy
| Subject | Publisher | Subscriber(s) | Payload Format |
|---------|-----------|---------------|----------------|
| `audio.raw` | audio-producer | stt-provider, identifier | Binary PCM (16-bit, 16kHz, mono) |
| `text.transcript` | stt-provider | identity-manager | JSON: `{"text": "...", "speaker": 0}` |
| `identity.event` | identifier | identity-manager | JSON: `{"user": "Alice", "conf": 0.92}` |
| `events.merged` | identity-manager | api-gateway | JSON: `{"text": "...", "user": "Alice"}` |

## 4. Volume Mounts

### 4.1 "Black Box" Storage (`/data`)
To prevent corruption, we use a loopback filesystem with data journaling.

```bash
# Host Setup (entrypoint.sh)
mount -o loop,data=journal /data/nats.img /var/lib/nats
```

### 4.2 Application Data
```yaml
volumes:
  - ./data/lancedb:/data/lancedb  # Vector DB (Biometrics)
  - ./config:/config:ro           # Configuration
```

## 5. Hardware Dependencies

### 5.1 Audio Input (PipeWire)
- **Interface**: PipeWire (via `libpipewire`)
- **Device**: Focusrite Scarlett Solo
- **Format**: 16-bit PCM, 16kHz, mono
- **Latency**: < 10ms (Hardware Direct)

### 5.2 GPU (OpenVINO)
- **Hardware**: Intel UHD Graphics (N97)
- **Driver**: `/dev/dri` mapped to container
- **Runtime**: OpenVINO 2024.x

### 5.3 Watchdog
- **Device**: `/dev/watchdog`
- **Timeout**: 60s
- **Service**: `health-watchdog` (pings hardware WDT)

## 6. Port Mappings

| Service | Internal Port | External Port | Protocol | Purpose |
|---------|---------------|---------------|----------|---------|
| api-gateway | 8000 | 8000 | HTTP/WSS | Web UI |
| nats | 4222 | 4222 | TCP | NATS Client |
| nats | 8222 | 8222 | HTTP | NATS Monitoring |

## 7. Resource Limits (Tier 1 - NUC N97)

```yaml
services:
  identifier:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    devices:
      - /dev/dri:/dev/dri  # iGPU Access
```

---

**See Also:**
- [Architecture Definition](architecture_definition.md) - High-level system design
- [System Design v7.3](../system_design_v7.3.md) - Detailed technical specs

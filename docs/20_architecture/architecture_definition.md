# Architecture Definition Document (ADD)

## 1. System Overview
The **Live STT** system is a high-reliability, real-time speech-to-text appliance designed for edge deployment on embedded hardware (Jetson Orin Nano). It implements an event-driven microservices architecture using ZeroMQ as the central message broker, enabling decoupled communication between audio processing, transcription, and UI services.

**Key Design Principles:**
- **Failure Domain Isolation**: UI (api-gateway) and transcription (stt-provider) run in separate containers
- **Zero Data Loss**: On-disk buffering during network outages
- **Multi-Tier Hardware Support**: Jetson (Tier 1), Desktop GPU (Tier 2), CPU-only (Tier 3)

## 2. System Context (C4 Level 1)
```mermaid
C4Context
  title System Context - Live STT Appliance
  
  Person(operator, "AV Operator", "Church staff member")
  Person(admin, "System Administrator", "Manages configuration and reviews transcripts")
  
  System(livesst, "Live STT Appliance", "Real-time speech transcription appliance")
  
  System_Ext(deepgram, "Deepgram API", "Cloud STT service")
  System_Ext(balena, "Balena Cloud", "Fleet management and deployment")
  
  Rel(operator, livesst, "Views live transcripts", "WebSocket")
  Rel(admin, livesst, "Manages config, reviews QA queue", "HTTPS")
  Rel(livesst, deepgram, "Streams audio, receives transcripts", "WSS")
  Rel(balena, livesst, "Deploys updates", "Docker Registry")
```

## 3. Container Diagram (C4 Level 2)
```mermaid
C4Container
  title Container Diagram - Live STT Microservices

  Person(user, "User")
  
  Container_Boundary(appliance, "Live STT Appliance") {
    Container(gateway, "api-gateway", "FastAPI/Python", "Web UI, WebSocket server, config management")
    Container(broker, "broker", "C++ zmq_proxy", "Central event bus (XPUB/XSUB)")
    Container(producer, "audio-producer", "Python/PyAudio", "Microphone capture, RMS monitoring")
    Container(stt, "stt-provider", "Python/Deepgram SDK", "Cloud STT client, resilience, sanitizer")
    Container(classifier, "audio-classifier", "Python/TFLite", "YAMNet music detection")
    Container(identifier, "identifier", "Python/PyTorch", "Speaker biometric ID (GPU)")
    Container(watchdog, "health-watchdog", "Python", "Service health monitoring")
  }
  
  System_Ext(deepgram, "Deepgram API")
  ContainerDb(nvme, "NVMe Storage", "SQLite + Encrypted Files")
  
  Rel(user, gateway, "Views transcripts", "WSS")
  Rel(producer, broker, "Publishes audio.raw", "ZMQ PUB")
  Rel(broker, stt, "Routes audio.raw", "ZMQ SUB")
  Rel(broker, classifier, "Routes audio.raw", "ZMQ SUB")
  Rel(broker, identifier, "Routes audio.raw", "ZMQ SUB")
  Rel(stt, deepgram, "Streams PCM", "WSS")
  Rel(stt, broker, "Publishes text.transcript", "ZMQ PUB")
  Rel(broker, gateway, "Routes text.transcript", "ZMQ SUB")
  Rel(gateway, nvme, "Stores config, logs")
  Rel(stt, nvme, "Buffers audio, saves QA snippets")
```

## 4. Component List

| Service | Technology | Purpose | Resilience Strategy |
|---------|-----------|---------|---------------------|
| **broker** | C++ ZMQ | Central event bus | Stateless, instant restart |
| **audio-producer** | Python/PyAudio | Mic capture | RMS monitoring, clipping detection |
| **stt-provider** | Python/Deepgram | Cloud STT client | On-disk buffering, catch-up on reconnect |
| **api-gateway** | FastAPI | Web UI, config | Decoupled from audio path, always responsive |
| **audio-classifier** | TFLite/YAMNet | Music detection | Pause STT during music |
| **identifier** | PyTorch/SpeechBrain | Speaker ID | GPU-accelerated, optional (M12+) |
| **health-watchdog** | Python | Service monitoring | Pings all services, exposes /status |

## 5. Deployment View

### Local Development (Tier 3)
```yaml
docker-compose.dev.yml:
  - Mock audio producer (reads .wav files)
  - All services except identifier (no GPU required)
  - Mounts: ./data, ./config
```

### Production (Tier 1 - Jetson)
```yaml
BalenaOS:
  - Fleet managed via Balena Cloud
  - TPM 2.0 for key sealing
  - Public device URL for remote access
  - Volume: /data (NVMe, encrypted)
```

### Hardware Tiers
- **Tier 1 (Jetson Orin Nano)**: Full stack including identifier (GPU), TPM sealing
- **Tier 2 (Desktop GPU)**: Docker Compose, user-provided encryption key
- **Tier 3 (CPU-only)**: Dev/testing, no identifier service

## 6. Data Flow

```mermaid
sequenceDiagram
    participant Mic as audio-producer
    participant Broker as broker
    participant STT as stt-provider
    participant DG as Deepgram API
    participant UI as api-gateway
    participant User

    Mic->>Broker: PUB audio.raw (16kHz PCM)
    Broker->>STT: SUB audio.raw
    STT->>DG: WSS stream (with endpointing)
    DG-->>STT: JSON transcript
    STT->>Broker: PUB text.transcript
    Broker->>UI: SUB text.transcript
    UI->>User: WebSocket broadcast
```

## 7. Key Architectural Decisions

See [ADRs](adrs/) for detailed rationale:
- [ADR-0001](adrs/0001-zmq-broker.md): ZMQ XPUB/XSUB broker pattern
- [ADR-0002](adrs/0002-decoupled-ui.md): Splitting stt-provider from api-gateway (v6.0)
- [ADR-0003](adrs/0003-multi-tier-hardware.md): Multi-tier hardware strategy
- [ADR-0004](adrs/0004-deepgram-selection.md): Deepgram as STT provider
- [ADR-0005](adrs/0005-balenaos-deployment.md): BalenaOS for fleet management

## 8. Quality Attributes

| Attribute | Target | Implementation |
|-----------|--------|----------------|
| **Latency** | \< 500ms (mic → UI) | Direct ZMQ routing, local broker |
| **Availability** | 99.9% uptime | Decoupled services, health monitoring |
| **Resilience** | Zero data loss | On-disk buffering during outages |
| **Security** | PII encrypted at rest | AES-256 per-file, TPM key sealing |
| **Scalability** | Single-device | Optimized for edge, not distributed |

## 9. Technology Stack

- **Broker**: ZeroMQ (C++)
- **Services**: Python 3.13, FastAPI, PyAudio, Deepgram SDK
- **ML**: TensorFlow Lite (YAMNet), PyTorch (SpeechBrain)
- **Database**: SQLite
- **Deployment**: Docker Compose, BalenaOS
- **Hardware**: NVIDIA Jetson Orin Nano (Tier 1)

---

**See Also:**
- [System Design](../system_design.md) - Detailed technical specification
- [HSI](hsi.md) - Hardware/Software interface details
- [Threat Model](threat_model.md) - Security architecture

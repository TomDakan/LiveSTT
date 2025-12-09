# Architecture Definition Document (ADD)

## 1. System Overview
The **Live STT** system is a high-reliability, real-time speech-to-text appliance designed for "Industrial Split-Brain" deployment on x86 hardware (ASRock Industrial NUC). It implements a dual-stream architecture where transcription is offloaded to the cloud (Deepgram Nova-3) while biometric identification runs locally on the edge (OpenVINO), synchronized via a "Time Zipper" service.

**Key Design Principles:**
- **Split-Brain Processing**: Decoupled cloud transcription (high accuracy) and edge biometrics (low latency/privacy)
- **Industrial Reliability**: Fanless x86 hardware with Power Loss Protection (PLP) and "Black Box" filesystem
- **Event-Driven**: NATS-based messaging backbone for persistence and observability

## 2. System Context (C4 Level 1)
```mermaid
C4Context
  title System Context - Live STT Appliance (v8.0)

  Person(operator, "AV Operator", "Church staff member")
  Person(admin, "System Administrator", "Manages configuration and reviews transcripts")

  System(livesst, "Live STT Appliance", "Real-time speech transcription & identification")

  System_Ext(deepgram, "Deepgram API", "Cloud STT service (Nova-3)")
  System_Ext(balena, "Balena Cloud", "Fleet management and deployment")

  Rel(operator, livesst, "Views live transcripts", "WebSocket")
  Rel(admin, livesst, "Manages config, reviews QA queue", "HTTPS")
  Rel(livesst, deepgram, "Streams audio, receives transcripts", "WSS")
  Rel(balena, livesst, "Deploys updates", "Docker Registry")
```

## 3. Container Diagram (C4 Level 2)
```mermaid
C4Container
  title Container Diagram - Live STT Microservices (v8.0)

  Person(user, "User")

  Container_Boundary(appliance, "Live STT Appliance") {
    Container(gateway, "api-gateway", "FastAPI/Python", "Web UI, WebSocket server, config management")
    Container(broker, "NATS Server", "Go", "Central event bus with JetStream persistence")
    Container(producer, "audio-producer", "Python/PipeWire", "Microphone capture, RMS monitoring")
    Container(stt, "stt-provider", "Python/Deepgram SDK", "Cloud STT client, offline buffering")
    Container(identifier, "identifier", "Python/OpenVINO", "Speaker biometric ID (WeSpeaker)")
    Container(manager, "identity-manager", "Python", "Time Zipper (merges text + identity)")
  }

  System_Ext(deepgram, "Deepgram API")
  ContainerDb(lancedb, "LanceDB", "Vector DB for Biometrics")
  ContainerDb(blackbox, "Black Box Storage", "Loopback ext4 (data=journal)", "Crash-proof persistence")

  Rel(user, gateway, "Views transcripts", "WSS")
  Rel(producer, broker, "Publishes audio.live / audio.backfill", "NATS")
  Rel(broker, stt, "Routes audio streams", "NATS")
  Rel(broker, identifier, "Routes audio streams", "NATS")
  Rel(stt, deepgram, "Streams PCM", "WSS")
  Rel(stt, broker, "Publishes transcript.raw", "NATS")
  Rel(identifier, lancedb, "Queries embeddings")
  Rel(identifier, broker, "Publishes transcript.identity", "NATS")
  Rel(broker, manager, "Routes raw transcripts + identity", "NATS")
  Rel(manager, broker, "Publishes fused transcript.final", "NATS")
  Rel(broker, gateway, "Routes final transcripts", "NATS")
  Rel(stt, blackbox, "Buffers offline audio")
```

## 4. Component List

| Service | Technology | Purpose | Resilience Strategy |
|---------|-----------|---------|---------------------|
| **NATS** | Go | Central event bus | JetStream persistence, cluster-ready |
| **audio-producer** | Python/PipeWire | Mic capture | Ring buffer, non-blocking I/O |
| **stt-provider** | Python/Deepgram | Cloud STT client | "Black Box" buffering, auto-reconnect |
| **identifier** | Python/OpenVINO | Speaker ID | Local iGPU inference, fallback to CPU |
| **identity-manager** | Python | Sensor Fusion | Hybrid tagging strategy (no timestamp drift) |
| **api-gateway** | FastAPI | Web UI, config | Read-only NATS access, decoupled UI |

## 5. Deployment View

### Production (Industrial x86)
```yaml
BalenaOS (Generic x86):
  - Fleet managed via Balena Cloud
  - Hardware: ASRock NUC BOX-N97
  - Storage: /data (Transcend PLP NVMe)
  - Audio: Focusrite Scarlett Solo (PipeWire)
  - Watchdog: Hardware WDT enabled
```

## 6. Data Flow (Split-Brain)

```mermaid
sequenceDiagram
    participant Mic as audio-producer
    participant NATS as NATS JetStream
    participant STT as stt-provider
    participant ID as identifier
    participant Zip as identity-manager
    participant UI as api-gateway

    par Split-Brain
        Mic->>NATS: Pub audio.live (Real-time)
        Mic->>NATS: Pub audio.backfill (Buffered)
        NATS->>STT: Stream audio.live / audio.backfill
        NATS->>ID: Stream audio.live / audio.backfill
    end

    par Parallel Processing
        STT->>Deepgram: WSS Stream
        Deepgram-->>STT: Transcript (Speaker A)
        STT->>NATS: Pub transcript.raw

        ID->>OpenVINO: Inference
        OpenVINO-->>ID: Vector
        ID->>LanceDB: Lookup
        ID->>NATS: Pub transcript.identity (Speaker A = Alice)
    end

    NATS->>Zip: Sub transcript.raw + transcript.identity
    Zip->>Zip: Hybrid Tagging (Apply "Alice" to "Speaker A")
    Zip->>NATS: Pub transcript.final
    NATS->>UI: Sub transcript.final
    UI->>User: WebSocket Broadcast
```

## 7. Key Architectural Decisions

See [ADRs](adrs/) for detailed rationale:
- [ADR-0007](adrs/0007-platform-pivot-x86.md): Pivot to x86 Industrial Platform
- [ADR-0008](adrs/0008-split-brain-architecture.md): Split-Brain Architecture
- [ADR-0009](adrs/0009-nats-migration.md): Migration to NATS

## 8. Quality Attributes

| Attribute | Target | Implementation |
|-----------|--------|----------------|
| **Latency** | < 100ms (ID), < 500ms (Text) | Parallel processing, local biometrics |
| **Reliability** | Zero Corruption | PLP Hardware + "Black Box" Journaling |
| **Silence** | 0dB (Fanless) | ASRock NUC N97 (Passive Cooling) |
| **Accuracy** | > 95% WER | Deepgram Nova-3 (Cloud) |
| **Privacy** | Biometrics Local | Face/Voice vectors never leave device |

## 9. Technology Stack

- **Broker**: NATS (JetStream)
- **Services**: Python 3.13, FastAPI, PipeWire
- **ML**: OpenVINO (WeSpeaker), Deepgram Nova-3
- **Database**: LanceDB (Vectors), SQLite (Config)
- **OS**: BalenaOS (x86_64)
- **Hardware**: ASRock Industrial NUC BOX-N97

---

**See Also:**
- [System Design v7.3](system_design_v7.3.md) - Detailed technical specification
- [HSI](hsi.md) - Hardware/Software interface details
- [Threat Model](threat_model.md) - Security architecture

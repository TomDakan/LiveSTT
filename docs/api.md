# API Reference (v8.0)

## Overview
This document documents the internal APIs used for inter-service communication (NATS) and the external REST API exposed by the `api-gateway`.

---

## 1. REST API (`api-gateway`)

**Base URL**: `http://localhost:8000`
**Docs URL**: `http://localhost:8000/docs` (Swagger UI)

### Authentication
Currently, the API is open for local network access. Future versions (M7) will implement JWT auth.

### Endpoints

#### System Status
- **GET** `/health`
  - **Description**: System health check.
  - **Response**: `{"status": "ok", "services": {"nats": "ok", ...}}`

#### Transcription Management
- **GET** `/v1/transcription/status`
  - **Description**: Check if transcription is active.
- **POST** `/v1/transcription/start`
  - **Description**: Manually start transcription stream.
- **POST** `/v1/transcription/stop`
  - **Description**: Manually stop transcription stream.

#### Vocabulary Management
- **GET** `/v1/admin/phrases`
  - **Description**: List custom vocabulary.
- **POST** `/v1/admin/phrases`
  - **Description**: Add new phrase.
  - **Body**: `{"phrase": "Eucharist", "boost": 5}`
- **DELETE** `/v1/admin/phrases/{id}`
  - **Description**: Remove phrase.

#### Biometric Enrollment
- **POST** `/v1/admin/enrollment`
  - **Description**: Start enrollment session for a speaker.
  - **Body**: `{"name": "Pastor Mike"}`
- **DELETE** `/v1/admin/enrollment/{id}`
  - **Description**: Delete voiceprint and crypto-shred key.

---

## 2. WebSocket API (`api-gateway`)

**Endpoint**: `ws://localhost:8000/ws/sub`

### Client Protocol
Clients (Web UI) connect to receive real-time updates.

#### Message Types

**1. Transcript (Final)**
```json
{
  "type": "transcript",
  "payload": {
    "text": "Welcome to the service.",
    "is_final": true,
    "speaker": "Pastor Mike",
    "timestamp": 1715432100.5
  }
}
```

**2. Transcript (Interim)**
```json
{
  "type": "transcript",
  "payload": {
    "text": "Welcome to the...",
    "is_final": false,
    "speaker": "Unknown",
    "timestamp": 1715432100.6
  }
}
```

**3. System Status**
```json
{
  "type": "status",
  "payload": {
    "state": "connected",  // connected, connecting, error
    "audio_level": -20.5   // dBFS
  }
}
```

---

## 3. NATS Internal API

**Broker URL**: `nats://nats:4222`

### Subject Structure

| Subject | Publisher | Subscriber | Payload Format |
|---------|-----------|------------|----------------|
| `audio.live` | audio-producer | stt-provider, identifier | Binary PCM (16kHz, S16LE, Real-time) |
| `audio.backfill` | audio-producer | stt-provider, identifier | Binary PCM (16kHz, S16LE, Delayed) |
| `transcript.raw` | stt-provider | identity-manager | JSON (Deepgram/Text) |
| `transcript.identity` | identifier | identity-manager | JSON (OpenVINO/Who) |
| `transcript.final` | identity-manager | api-gateway | JSON (Fused Result) |
| `system.alert` | all | api-gateway | JSON |

### Message Schemas

See [Data Dictionary](../30_data/data_dictionary.md) for full schema definitions.

---

## 4. Data Models

See [Data Dictionary](../30_data/data_dictionary.md).

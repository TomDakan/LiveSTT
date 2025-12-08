# Data Dictionary (v7.3)

## Overview
This document defines all data structures, message formats, database schemas, and file formats used in the Live STT system (v7.3 Industrial Split-Brain).

---

## 1. NATS JetStream Subjects

### 1.1 `audio.raw`
**Publisher**: audio-producer
**Subscribers**: stt-provider, identifier
**Format**: Binary PCM
**Payload**:
```
Bytes 0-1599: 16-bit signed PCM samples (800 samples × 2 bytes)
Sample Rate: 16kHz
Channels: 1 (mono)
Chunk Duration: 50ms
```

### 1.2 `text.transcript`
**Publisher**: stt-provider
**Subscribers**: identity-manager
**Format**: JSON
**Schema**:
```json
{
  "text": "string - Transcript text",
  "confidence": "float - 0.0 to 1.0",
  "speaker": "int - Deepgram speaker label (0, 1)",
  "is_final": "bool",
  "start": "float - Audio timestamp (seconds)",
  "end": "float - Audio timestamp (seconds)",
  "trace_id": "string - UUID for correlation"
}
```

### 1.3 `identity.event`
**Publisher**: identifier
**Subscribers**: identity-manager
**Format**: JSON
**Schema**:
```json
{
  "user_id": "string - Enrolled name (e.g., 'Alice')",
  "confidence": "float - 0.0 to 1.0",
  "start": "float - Audio timestamp (seconds)",
  "end": "float - Audio timestamp (seconds)",
  "trace_id": "string"
}
```

### 1.4 `events.merged`
**Publisher**: identity-manager
**Subscribers**: api-gateway
**Format**: JSON
**Schema**:
```json
{
  "text": "string - Transcript text",
  "user": "string - Resolved name (e.g., 'Alice')",
  "is_final": "bool"
}
```

---

## 2. LanceDB (Biometrics)

**Location**: `/data/lancedb`
**Table**: `voiceprints`

| Column | Type | Description |
|--------|------|-------------|
| `id` | String | Speaker Name (Primary Key) |
| `vector` | Vector(256) | WeSpeaker ResNet34 embedding |
| `enrolled_at` | Timestamp | Enrollment date |
| `version` | Int | Schema version |

---

## 3. SQLite Database (`/data/config.db`)

### 3.1 Table: `phrase_set`
**Purpose**: Custom vocabulary for Deepgram API
**Owner**: api-gateway (write), stt-provider (read)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Unique ID |
| `phrase` | TEXT | Phrase text |
| `boost` | INTEGER | Weight (1-10) |

---

## 4. "Black Box" Storage

**Location**: `/data/nats` (Loopback Mount)
**Format**: NATS JetStream File Store
**Retention**:
- `audio.raw`: 60 Minutes (Configurable via `NATS_AUDIO_RETENTION`)
- `text.transcript`: 7 Days (Configurable via `NATS_TEXT_RETENTION`)
- `events.merged`: 30 Days

---

**See Also:**
- [Biometric Policy](biometric_policy.md)
- [HSI](../20_architecture/hsi.md)

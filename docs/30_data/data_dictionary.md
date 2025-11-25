# Data Dictionary

## Overview
This document defines all data structures, message formats, database schemas, and file formats used in the Live STT system.

---

## 1. ZMQ Message Topics

### 1.1 `audio.raw`
**Publisher**: audio-producer  
**Subscribers**: stt-provider, audio-classifier, identifier  
**Format**: Binary PCM  
**Payload**:
```
Bytes 0-1599: 16-bit signed PCM samples (800 samples × 2 bytes)
Sample Rate: 16kHz
Channels: 1 (mono) - Stereo input auto-downmixed via channel averaging
Chunk Duration: 50ms (800 samples / 16000 Hz)
```

### 1.2 `text.transcript`
**Publisher**: stt-provider  
**Subscribers**: api-gateway  
**Format**: JSON  
**Schema**:
```json
{
  "text": "string - Transcript text",
  "confidence": "float - 0.0 to 1.0",
  "speaker": "int - Deepgram speaker label (0, 1, ...)",
  "is_final": "bool - True if utterance is complete",
  "timestamp_ms": "int - Unix timestamp in milliseconds"
}
```

### 1.3 `system.alert`
**Publishers**: audio-producer, stt-provider, audio-classifier  
**Subscribers**: api-gateway  
**Format**: JSON  
**Schema**:
```json
{
  "type": "string - 'clipping' | 'reconnecting' | 'music' | 'error'",
  "severity": "string - 'info' | 'warn' | 'error'",
  "message": "string - Human-readable description",
  "timestamp_ms": "int"
}
```

### 1.4 `identity.event`
**Publisher**: identifier  
**Subscribers**: api-gateway  
**Format**: JSON  
**Schema**:
```json
{
  "speaker_id": "string - Enrolled speaker name (e.g., 'Tom')",
  "confidence": "float - 0.0 to 1.0",
  "timestamp_ms": "int",
  "duration_ms": "int - Length of audio chunk analyzed"
}
```

---

## 2. SQLite Database (`/data/config.db`)

### 2.1 Table: `phrase_set`
**Purpose**: Custom vocabulary for Deepgram API  
**Owner**: api-gateway (write), stt-provider (read)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique phrase ID |
| `phrase` | TEXT | NOT NULL | Phrase text (e.g., "Eucharist") |
| `boost` | INTEGER | DEFAULT 1, CHECK (1-10) | Deepgram boost weight |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When phrase was added |
| `created_by` | TEXT | | Admin username |

**Indexes**:
- `idx_phrase` on `phrase` (for lookups)

### 2.2 Table: `quality_log`
**Purpose**: Low-confidence snippet metadata  
**Owner**: stt-provider (write), api-gateway (read)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Database surrogate key |
| `snippet_id` | TEXT | UNIQUE NOT NULL | UUID for API references |
| `confidence` | REAL | NOT NULL | Original confidence score |
| `text` | TEXT | NOT NULL | Transcript text |
| `duration_ms` | INTEGER | NOT NULL | Audio chunk duration |
| `file_path` | TEXT | UNIQUE NOT NULL | Path to encrypted .wav file (e.g., `/data/review/{uuid}.enc`) |
| `encryption_key` | BLOB | NOT NULL | Per-file AES-256 key (encrypted with master key) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When snippet was saved |
| `reviewed` | BOOLEAN | DEFAULT 0 | Admin has reviewed this snippet |

**Indexes**:
- `idx_snippet_id` on `snippet_id` (for API lookups)
- `idx_confidence` on `confidence` (for filtering)
- `idx_created_at` on `created_at` (for sorting)

### 2.3 Table: `performance_log`
**Purpose**: System metrics for monitoring  
**Owner**: health-watchdog (write), api-gateway (read)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Log entry ID |
| `service` | TEXT | NOT NULL | Service name (e.g., "stt-provider") |
| `metric` | TEXT | NOT NULL | Metric name (e.g., "latency_ms") |
| `value` | REAL | NOT NULL | Metric value |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Measurement time |

**Indexes**:
- `idx_service_timestamp` on `(service, timestamp)`

### 2.4 Table: `voiceprint_enrollment`
**Purpose**: Speaker voiceprint metadata  
**Owner**: api-gateway (write), identifier (read)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `speaker_id` | TEXT | PRIMARY KEY | Speaker name (e.g., "Tom") |
| `file_path` | TEXT | NOT NULL | Path to encrypted voiceprint .wav |
| `encryption_key` | BLOB | NOT NULL | Per-file AES-256 key |
| `embedding` | BLOB | | Pre-computed voiceprint embedding (512D vector) |
| `enrolled_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When enrolled |
| `consented` | BOOLEAN | DEFAULT 0 | BIPA consent flag |

---

## 3. File Formats

### 3.1 Encrypted Audio Snippets (`/data/review/{uuid}.enc`)
**Format**: AES-256-GCM encrypted WAV  
**Structure**:
```
Bytes 0-11:  Nonce (12 bytes, random per file)
Bytes 12-27: GCM tag (16 bytes)
Bytes 28+:   Encrypted WAV data
```

**Encryption**:
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

file_key = db.get_key(snippet_id)  # 32-byte key from quality_log table
nonce = os.urandom(12)
aesgcm = AESGCM(file_key)
ciphertext = aesgcm.encrypt(nonce, wav_data, associated_data=None)
output = nonce + ciphertext  # Nonce is prepended
```

### 3.2 Buffered Audio (`/data/buffer/buffer.wav`)
**Format**: Standard WAV (unencrypted)  
**Spec**:
- Sample Rate: 16kHz
- Bit Depth: 16-bit PCM
- Channels: 1 (mono)
- Duration: Up to 4 hours (maximum)

**Note**: Deleted immediately after successful upload to Deepgram.

### 3.3 PhraseSet Seed File (`/config/initial_phrases.json`)
**Format**: JSON array  
**Schema**:
```json
[
  {
    "phrase": "string - Phrase text",
    "boost": "int - 1 to 10 (optional, default 1)"
  }
]
```

**Example**:
```json
[
  {"phrase": "Eucharist", "boost": 5},
  {"phrase": "homily", "boost": 5},
  {"phrase": "Pastor Mike", "boost": 10}
]
```

---

## 4. Environment Variables

| Variable | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `DEEPGRAM_API_KEY` | String | Yes | Deepgram API key | `a1b2c3d4...` |
| `ENCRYPTION_KEY_PATH` | String | Tier 2/3 | Path to master encryption key | `/config/master.key` |
| `TPM_SLOT` | Integer | Tier 1 | TPM PCR slot for key sealing | `1` |
| `MOCK_FILE` | String | Dev only | Path to mock audio file | `/path/to/sermon.wav` |
| `LOG_LEVEL` | String | No | Logging level (`DEBUG \| INFO \| WARNING \| ERROR \| CRITICAL`) | `INFO` (default) |

---

## 5. API Endpoints (api-gateway)

### 5.1 `GET /health`
**Response**:
```json
{
  "status": "live" | "degraded" | "reconnecting",
  "services": {
    "broker": "ok" | "down",
    "stt-provider": "ok" | "down",
    "identifier": "ok" | "down"
  }
}
```

### 5.2 `WebSocket /ws`
**Client → Server**: None (subscribe only)  
**Server → Client**:
```json
{
  "type": "transcript" | "alert" | "identity",
  "payload": { /* See ZMQ message schemas above */ }
}
```

### 5.3 `POST /auth`
**Request**:
```json
{
  "password": "string - Admin password"
}
```
**Response**:
```json
{
  "token": "string - WebSocket ticket (JWT)"
}
```

### 5.4 `GET /admin/snippets`
**Response**:
```json
[
  {
    "snippet_id": "uuid",
    "confidence": 0.78,
    "text": "...",
    "created_at": "2025-11-19T12:00:00Z",
    "reviewed": false
  }
]
```

### 5.5 `GET /admin/stream/{snippet_id}`
**Response**: Binary audio stream (decrypted on-the-fly)  
**Content-Type**: `audio/wav`

---

**See Also:**
- [ERD](erd.md) - Entity-relationship diagram
- [HSI](../20_architecture/hsi.md) - ZMQ topology details
- [Biometric Policy](biometric_policy.md) - Voiceprint data handling

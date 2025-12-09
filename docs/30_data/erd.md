# Entity-Relationship Diagram (ERD v8.0)

## Overview
This document visualizes the data model for the Live STT system, showing relationships between configuration, quality assurance, and biometric enrollment data.

---

## ERD

```mermaid
erDiagram
    PHRASE_SET ||--o{ TRANSCRIPT_EVENT : "boosts"
    QUALITY_LOG ||--|| ENCRYPTED_SNIPPET : "references"
    VOICEPRINT_ENROLLMENT ||--|| ENCRYPTED_VOICEPRINT : "references"
    VOICEPRINT_ENROLLMENT ||--o{ IDENTITY_EVENT : "identified_by"
    PERFORMANCE_LOG }o--|| SERVICE : "logs_for"

    PHRASE_SET {
        int id PK
        string phrase UK
        int boost "1-10"
        timestamp created_at
        string created_by
    }

    QUALITY_LOG {
        int id PK
        string snippet_id UK "UUID"
        float confidence "0.0-1.0"
        string text
        int duration_ms
        string file_path UK
        blob encryption_key "AES-256"
        timestamp created_at
        bool reviewed
    }

    ENCRYPTED_SNIPPET {
        string file_path PK "/data/review/{uuid}.enc"
        blob nonce "12 bytes"
        blob gcm_tag "16 bytes"
        blob ciphertext
    }

    VOICEPRINT_ENROLLMENT {
        string speaker_id PK "e.g., 'Tom'"
        string file_path FK
        blob encryption_key
        blob embedding "512D vector"
        timestamp enrolled_at
        bool consented "BIPA"
    }

    ENCRYPTED_VOICEPRINT {
        string file_path PK "/data/enrollment/{speaker}.wav.enc"
        blob nonce
        blob gcm_tag
        blob ciphertext
    }

    IDENTITY_EVENT {
        int event_id PK
        string speaker_id FK
        float confidence
        timestamp timestamp_ms
        int duration_ms
    }

    TRANSCRIPT_EVENT {
        int event_id PK
        string text
        float confidence
        int speaker "Deepgram label"
        bool is_final
        timestamp timestamp_ms
    }

    PERFORMANCE_LOG {
        int id PK
        string service FK
        string metric
        float value
        timestamp timestamp
    }

    SERVICE {
        string name PK
        string status "ok|degraded|down"
        timestamp last_ping
    }
```

---

## Key Relationships

### 1. `PHRASE_SET` → `TRANSCRIPT_EVENT`
- **Type**: One-to-Many (indirect)
- **Description**: Custom phrases in `phrase_set` are passed to Deepgram API, boosting their likelihood in transcripts
- **Enforcement**: Application logic in `stt-provider` (no foreign key)

### 2. `QUALITY_LOG` → `ENCRYPTED_SNIPPET`
- **Type**: One-to-One
- **Description**: Each low-confidence snippet has metadata in `quality_log` and encrypted audio in filesystem
- **Key**: `quality_log.file_path` references physical file path
- **Orphan Prevention**: Admin deletes snippet → `quality_log` row deleted → file deleted → encryption key crypto-shredded
- **Lookup**: API uses `snippet_id` (UUID) for external references (e.g., `/admin/snippet/{snippet_id}`)

### 3. `VOICEPRINT_ENROLLMENT` → `ENCRYPTED_VOICEPRINT`
- **Type**: One-to-One
- **Description**: Each enrolled speaker has metadata in `voiceprint_enrollment` and encrypted voiceprint in filesystem
- **Key**: `voiceprint_enrollment.file_path` references physical file path
- **Crypto-shredding**: Delete `voiceprint_enrollment.encryption_key` → file becomes permanently unrecoverable

### 4. `VOICEPRINT_ENROLLMENT` → `IDENTITY_EVENT`
- **Type**: One-to-Many
- **Description**: Each voiceprint can match multiple identity events (every time speaker is detected)
- **Key**: `identity_event.speaker_id` references `voiceprint_enrollment.speaker_id`
- **Enforcement**: Foreign key constraint in SQLite

### 5. `PERFORMANCE_LOG` → `SERVICE`
- **Type**: Many-to-One
- **Description**: Each service has many performance metrics logged over time
- **Key**: `performance_log.service` references `service.name`
- **Retention**: Logs older than 30 days automatically deleted (for disk space)

---

## Data Lifecycle

### Transcript Event (Buffered Split-Brain)
```mermaid
flowchart LR
    Mic[Mic Input] -->|Ring Buffer| A[Preroll]
    A -->|Start Session| B[audio.backfill]
    Mic -->|Start Session| C[audio.live]

    B --> D{Dual Processing}
    C --> D

    D -->|Stream| E[stt-provider]
    D -->|Stream| F[identifier]

    E -->|transcript.raw| G[identity-manager]
    F -->|transcript.identity| G

    G -->|transcript.final| H[api-gateway]
    H -->|WebSocket| I[Client Browser]
```

### Voiceprint Enrollment
```mermaid
flowchart LR
    A[Admin uploads WAV] -->|POST /admin/enrollment| B[api-gateway]
    B -->|Encrypt with file key| C[/data/enrollment/*.enc]
    B -->|Store metadata| D[voiceprint_enrollment table]
    D -->|Embedding extracted| E[identifier service]
    E -->|Publishes transcript.identity| F[broker]
```

### Crypto-Shredding (GDPR Right to Erasure)
```mermaid
flowchart LR
    A[Admin clicks Delete] -->|DELETE /admin/voiceprint/{id}| B[api-gateway]
    B -->|DELETE encryption_key| C[voiceprint_enrollment table]
    C -->|File still exists but...| D[Encrypted voiceprint]
    D -.->|Cannot decrypt without key| E[Data irretrievable]
```

---

## Indexing Strategy

| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| `phrase_set` | `idx_phrase` | `phrase` | Fast lookup for autocomplete in admin UI |
| `quality_log` | `idx_confidence` | `confidence` | Filter snippets by confidence range |
| `quality_log` | `idx_created_at` | `created_at DESC` | Sort snippets chronologically |
| `performance_log` | `idx_service_timestamp` | `(service, timestamp)` | Time-series queries for dashboards |
| `voiceprint_enrollment` | Primary Key | `speaker_id` | Enforce unique speaker names |

---

## Data Retention Policy

| Data Type | Retention Period | Rationale |
|-----------|------------------|-----------|
| **Transcripts (in-memory)** | Session only | Not persisted (privacy by design) |
| **Low-confidence snippets** | Until admin review | Deleted after correction or approval |
| **Voiceprints** | Until speaker requests deletion | BIPA compliance (consent-based) |
| **Performance logs** | 30 days | Disk space constraints on Jetson |
| **Phrase set** | Indefinite | Static configuration data |

---

**See Also:**
- [Data Dictionary](data_dictionary.md) - Schema details
- [Biometric Policy](biometric_policy.md) - Voiceprint handling procedures
- [Threat Model](../20_architecture/threat_model.md) - Crypto-shredding implementation

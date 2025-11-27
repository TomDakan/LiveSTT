# NATS Developer Tooling

## Overview
This document describes the tooling available for developing, debugging, and monitoring the NATS messaging backbone in the Live STT system.

## 1. NATS CLI (`nats-box`)

We use the official `natsio/nats-box` Docker image to interact with the NATS server. This provides a pre-configured environment with `nats`, `nats-top`, and `stan-sub` tools.

### Common Commands (via `just`)

| Command | Description | Equivalent Raw Command |
|---------|-------------|------------------------|
| `just nats-cli` | Open interactive shell | `docker run -it nats-box sh` |
| `just nats-spy` | Watch all messages | `nats sub ">"` |
| `just nats-health` | Check server status | `nats server check` |

### Manual Debugging
Inside the `nats-cli` shell:

```bash
# List all streams
nats stream ls

# View stream details
nats stream info EVENTS

# Publish a test message
nats pub audio.raw "test-data"

# Benchmark pub/sub performance
nats bench audio.raw --pub 1 --sub 1 --msgs 10000
```

## 2. Observability (NATS Surveyor)

We use **NATS Surveyor** for visual monitoring of the NATS cluster.

### Access
- **URL**: `http://localhost:8080` (when running `docker compose up`)
- **Metrics**:
  - Message throughput
  - Client connections
  - JetStream storage usage
  - Slow consumers

### Configuration
Surveyor is configured in `docker-compose.dev.yml`:
```yaml
nats-surveyor:
  image: natsio/nats-surveyor:latest
  environment:
    - SURVEYOR_SERVERS=nats://nats:4222
```

## 3. Message Tracing

All messages in the system include a `trace_id` header for distributed tracing.

### Inspecting Headers
To view headers, use the `--headers` flag with `nats sub`:

```bash
nats sub ">" --headers
```

**Output Example**:
```
[#1] Received on "text.transcript"
Nats-Msg-Id: nuid_12345
Trace-Id: 550e8400-e29b-41d4-a716-446655440000
Timestamp: 2025-11-26T12:00:00Z

{"text": "Hello world..."}
```

## 4. Structured Logging

Services log to stdout in JSON format, including the `trace_id`.

**Example Log**:
```json
{
  "level": "INFO",
  "timestamp": "2025-11-26T12:00:00Z",
  "service": "stt-provider",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Published transcript event",
  "subject": "text.transcript"
}
```

Use `docker compose logs -f | grep <trace_id>` to trace a request across all services.

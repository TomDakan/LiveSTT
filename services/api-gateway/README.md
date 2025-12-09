# API Gateway Service

The **API Gateway** acts as the bridge between the internal, asynchronous NATS mesh and the external, user-facing frontend. It consumes internal events (like fused transcripts) and pushes them to the UI via WebSockets.

## Architecture

* **Type:** Consumer (NATS) / Server (WebSocket/HTTP)
* **Input:** NATS Subscription (`transcript.final`, `system.alert`)
* **Output:** WebSocket Stream `/ws/transcripts`

## API Reference

### HTTP Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Returns service health status. |
| `GET` | `/docs` | Auto-generated Swagger UI (FastAPI default). |

### WebSocket: Real-Time Transcripts

**URL:** `ws://<host>:8000/ws/transcripts`

**Message Format (Server -> Client):**
The server pushes JSON objects as soon as transcripts are received from the internal ZMQ bus.

```json
{
  "type": "transcript",
  "payload": {
    "text": "Hello world.",
    "is_final": true,
    "confidence": 0.98
  }
}

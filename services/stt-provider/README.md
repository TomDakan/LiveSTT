# STT Provider Service

Connects to the Audio Broker, streams audio to Deepgram, and publishes transcripts.

## Architecture

* **Type:** Consumer (Audio) / Producer (Text)
* **Input:** NATS Subscription (`audio.live`, `audio.backfill`)
* **Output:** NATS Publication (`transcript.raw`)

## Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `NATS_URL` | `nats://localhost:4222` | NATS Server URL |
| `DEEPGRAM_API_KEY` | *Required* | API Key (if not using Docker Secrets) |

## Local Development

1.  **Install Dependencies:**
    ```bash
    just install
    ```

2.  **Run Locally:**
    ```bash
    # Ensure an audio broker is running first!
    uv run python src/main.py
    ```

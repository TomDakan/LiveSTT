# STT Provider Service

Connects to the Audio Broker, streams audio to Deepgram, and publishes transcripts.

## Architecture

* **Type:** Consumer (Audio) / Producer (Text)
* **Input:** ZMQ SUB `tcp://broker:5556` (Topic: `audio.raw`)
* **Output:** ZMQ PUB `tcp://broker:5555` (Topic: `text.transcript`)

## Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ZMQ_SUB_URL` | `tcp://localhost:5556` | Address of the Broker XPUB |
| `ZMQ_PUB_URL` | `tcp://localhost:5555` | Address of the Broker XSUB |
| `DEEPGRAM_API_KEY` | *Required* | API Key (if not using Docker Secrets) |

## Local Development

1.  **Install Dependencies:**
    ```bash
    pdm install
    ```

2.  **Run Locally:**
    ```bash
    # Ensure an audio broker is running first!
    pdm run python src/main.py
    ```

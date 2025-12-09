# Integration Tests

This directory contains integration tests for the Live STT system.

## End-to-End (E2E) Tests

There are two E2E test variants:

### 1. Container-based E2E Test (`test_e2e_container.py`)

Tests the full pipeline using Docker containers. This is the recommended approach for CI/CD and most development scenarios.

**Prerequisites:**
- Docker and Docker Compose installed
- `DEEPGRAM_API_KEY` environment variable set (or in `.env` file)

**Setup:**
```bash
# Start all containers
just up-build

# Or manually
docker compose up -d --build
```

**Run Test:**
```bash
# Basic run
uv run pytest tests/integration/test_e2e_container.py

# With verbose output
uv run pytest -v tests/integration/test_e2e_container.py

# With output from print statements
uv run pytest -s tests/integration/test_e2e_container.py
```

**What it tests:**
- Audio Producer → NATS → STT Provider → Deepgram API
- STT Provider → NATS → API Gateway → WebSocket client
- Full containerized deployment

### 2. Local E2E Test (`test_e2e.py`)
# TODO: This test is currently not working. But the containerized version works.
Runs services in-process (without containers). Useful for debugging and development.

**Prerequisites:**
- NATS container running (for message bus)
- `DEEPGRAM_API_KEY` environment variable set
- Python dependencies installed (`uv sync`)

**Setup:**
```bash
# Start only NATS container
docker compose up -d nats
```

**Run Test:**

**On Windows (PowerShell):**
```powershell
$env:PYTHONPATH="services/api-gateway/src;services/stt-provider/src;services/audio-producer/src;libs/messaging/src"
uv run --env-file .env pytest tests/integration/test_e2e.py
```

**On Linux/macOS (Bash):**
```bash
PYTHONPATH=services/api-gateway/src:services/stt-provider/src:services/audio-producer/src:libs/messaging/src \
  uv run --env-file .env pytest tests/integration/test_e2e.py
```

**What it tests:**
- Same pipeline as container test, but runs services as Python modules
- Useful for debugging with breakpoints
- Faster iteration during development

## Environment Variables

Both tests require:

| Variable | Description | Example |
|----------|-------------|---------|
| `DEEPGRAM_API_KEY` | API key for Deepgram STT service | `your_api_key_here` |
| `NATS_URL` (optional) | NATS server URL | `nats://localhost:4222` (default) |

Set these in:
- `.env` file in project root (recommended)
- Shell environment variables
- CI/CD secrets

## Test Audio File

Tests use `tests/data/test_audio.wav`. This should be a 5-second, 16kHz, mono, linear16 PCM WAV file with speech content.

To regenerate:
```bash
uv run python generate_audio.py
```

## Troubleshooting

### Test times out waiting for transcript

**Container test:**
1. Check container logs: `docker compose logs stt-provider`
2. Verify NATS messages: `just nats-spy` (monitors `audio.live` and `transcript.raw` topics)
3. Ensure `DEEPGRAM_API_KEY` is set correctly
4. Verify audio file exists and has speech content

**Local test:**
1. Ensure NATS container is running: `docker compose ps`
2. Check PYTHONPATH is set correctly
3. Verify `.env` file contains `DEEPGRAM_API_KEY`

### Import errors in local test

Ensure `PYTHONPATH` includes all service source directories:
- `services/api-gateway/src`
- `services/stt-provider/src`
- `services/audio-producer/src`
- `libs/messaging/src`

### Deepgram connection errors

1. Verify API key is valid: `echo $DEEPGRAM_API_KEY` (Linux/macOS) or `$env:DEEPGRAM_API_KEY` (Windows)
2. Check internet connectivity
3. Ensure you have credits/quota on your Deepgram account
4. Verify `nova-3` model is accessible with your API key

## CI/CD Integration

For automated testing, use the container-based test:

```yaml
# Example GitHub Actions workflow
- name: Run E2E Tests
  env:
    DEEPGRAM_API_KEY: ${{ secrets.DEEPGRAM_API_KEY }}
  run: |
    just up-build
    uv run pytest tests/integration/test_e2e_container.py
```



## v0.1.0 (2025-12-01)

### BREAKING CHANGE

- Requires Deepgram SDK v3+ with listen.v1 API support

### Feat

- **audio-producer**: add file-based audio source with looping support
- **stt-provider**: implement deepgram stt service with nats
- migrate stt-provider and api-gateway to NATS
- **audio-producer**: implement nats publisher and refactor mocks
- **audio-producer**: implement mock audio source and tests
- scaffold audio producer service
- Add dynamic cross-platform service starter
- **data**: add phrase mining script for M0.5
- **docker**: scaffold microservices architecture
- added build, up, and down tasks to justfile to simplify and consolidate running docker commands.
- Add Deepgram-based STT service that consumes raw audio from ZMQ and publishes transcripts.
- Add `setup_dev.py` for local environment setup and update `justfile` for argument passing and Windows shell support.

### Fix

- **justfile**: correct syntax error in start service command
- **stt-provider**: run start_listening in background task to prevent blocking
- **api-gateway**: use uvicorn directly and fix local execution
- Suppress bandit B104 warning for Docker 0.0.0.0 binding

### Refactor

- **api-gateway**: migrate to shared messaging lib and dependency injection
- remove obsolete broker service
- adopt standard src layout and shared configs
- migrate to uv workspace and consolidate tooling

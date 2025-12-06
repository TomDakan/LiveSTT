## 1.0.2 (2025-12-06)

### Fix

- **cicd**: updated release.yaml to also install alsaaudio dependency

## 1.0.1 (2025-12-06)

### Fix

- **cicd**: updated deploy and docs github actions to also install alsaaudio dependencies

## 1.0.0 (2025-12-06)

### Feat

- **cicd**: added basedpyright as a dev dependence for additional type checking
- **cicd**: implement secure build process and update docs
- **cicd**: updated main.yaml github workflow to just just qa-github
- **pre-commit**: added pre-commit as a dev dependency to enforce qa checking on commits
- **cicd**: update justfile to run tools with uv run python -m to resolve known windows issue with uv and shims
- **docker**: add cross-platform build infrastructure with .docker-context pattern

### Fix

- **cicd**: updated audiosource.py to only instantiate os-specific source classes if they necessary dependencies were successfully imported
- **cicd**: reverted just qa in main.yaml
- **cicd**: add system dependency for alsaaudio
- **cicd**: added safety_api_key environment variable to main github workflow
- **cicd**: merge from feat/cicd/secure-build-process
- **cicd**: merged from main
- **cicd**: split just qa so that we have a recipe that doesn't run safetycli. Updated just to run safety scan instead of safety check, which is deprecated
- pre-commit hook compatibility
- resolve type checking errors
- **test**: fix Windows uv canonicalization error and pytest configuration

### Refactor

- reduce complexity and add type annotations with tests

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

# Tasks

## Pending Implementation
- [/] **Audio Producer** (See: `docs/implementation_guides/01_audio_producer.md`)
    - [x] Implement `MockAudioSource` in `services/audio-producer/src/audio_producer/audiosource.py`
    - [x] Implement tests in `services/audio-producer/tests/test_audiosource.py`
    - [x] Verify with `just test`
    - [x] **NATS Integration**
        - [x] Create `docs/implementation_guides/02_nats_publisher.md`
        - [x] Scaffold `services/audio-producer/src/audio_producer/main.py`
        - [x] Refactor Mocks to `tests/mocks.py`
        - [x] Implement `NatsAudioPublisher` logic
    - [x] **Refactor Monorepo Structure** (Option 2)
        - [x] Remove PDM Workspace from root `pyproject.toml`
        - [x] Initialize PDM in `services/audio-producer`
        - [x] Update `justfile` to use service-level PDM (`test-service`)
    - [x] **Hardware Integration**
        - [x] Create `docs/implementation_guides/03_hardware_integration.md`
        - [x] Update `pyproject.toml` with `pyaudio` (Windows)
        - [x] Implement `WindowsSource` (PyAudio)
        - [x] Implement `LinuxSource` (PyAlsaAudio/PipeWire)
        - [x] Verify with `just test-service` (Mock)

## Toolchain Constraints
- **Linting/Formatting**: Ruff (via `just lint`, `just format`)
- **Type Checking**: MyPy Strict (via `just type-check`)
- **Testing**: Pytest (via `just test`)
- **Task Runner**: Just
- **Package Manager**: PDM

- [x] Define "Guide-not-Drive" Workflow
    - [x] Analyze User Request
    - [x] Propose Workflow Structure
    - [x] Refine Workflow (User writes tests)
    - [x] Establish Design Review Pattern
    - [x] Document Workflow (`docs/implementation_guides/00_workflow.md`)
- [x] Setup Project Tracking
    - [x] Update repo `task.md` with "Pending Implementation" section
    - [x] Create `docs/implementation_guides/` directory
- [x] Scaffold Milestone 2 (Audio Producer)
    - [x] Create Implementation Guide (App + Tests)
    - [x] Scaffold `services/audio-producer/src/audio_producer/audiosource.py` (Protocol Only)
    - [x] Scaffold `services/audio-producer/tests/test_audiosource.py` (Empty)

# Tasks

## Pending Implementation
- [/] **Audio Producer** (See: `docs/implementation_guides/01_audio_producer.md`)
    - [x] Implement `MockAudioSource` in `services/audio-producer/src/audiosource.py`
    - [x] Implement tests in `services/audio-producer/tests/test_audiosource.py`
    - [x] Verify with `just test`
    - [/] **NATS Integration**
        - [x] Create `docs/implementation_guides/02_nats_publisher.md`
        - [x] Scaffold `services/audio-producer/src/main.py`
        - [x] Refactor Mocks to `tests/mocks.py`
        - [ ] Implement `NatsAudioPublisher` logic in `services/audio-producer/src/main.py`
        - [ ] Implement `PyAudioSource` (Hardware Integration)

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
    - [x] Scaffold `services/audio-producer/src/audiosource.py` (Protocol Only)
    - [x] Scaffold `services/audio-producer/tests/test_audiosource.py` (Empty)

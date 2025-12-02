# Implementation Guide: STT Provider

## Objective
Implement the `stt-provider` service, which acts as the bridge between the raw audio stream (NATS) and the cloud transcription engine (Deepgram). It must be robust, handling network interruptions and API failures gracefully.

## 1. The Architecture

The service follows a "Hexagonal" or "Ports and Adapters" architecture to allow for easy testing and swapping of components.

### Core Components
1.  **`STTService`**: The main application logic. It orchestrates the flow of data.
2.  **`NatsClient` (Adapter)**: Handles communication with the NATS message bus.
3.  **`Transcriber` (Adapter)**: Handles communication with the Speech-to-Text API (Deepgram).

## 2. Interfaces (Protocols)

We define strict protocols to decouple the core logic from external dependencies.

### 2.1 `Transcriber` Protocol

Abstracts the STT engine. This allows us to mock Deepgram for unit tests.

Defined in `services/stt-provider/src/stt_provider/interfaces.py`.

::: stt_provider.interfaces.TranscriptionEvent
    options:
      show_source: true
      heading_level: 4
      show_root_heading: false
      show_root_toc_entry: false

::: stt_provider.interfaces.Transcriber
    options:
      show_source: true
      heading_level: 4
      show_root_heading: false
      show_root_toc_entry: false

### 2.2 `NatsClient` Protocol

Defined in `libs/messaging/src/messaging/nats.py`.

::: messaging.nats.NatsClient
    options:
      show_source: true
      heading_level: 4
      show_root_heading: false
      show_root_toc_entry: false

## 3. The Implementation (`DeepgramTranscriber`)

This class implements the `Transcriber` protocol using the official `deepgram-sdk`.

### Requirements
-   **Config**: API Key (from env), Audio Format (16kHz, S16LE).
-   **Behavior**:
    -   `connect()`: Opens the WebSocket connection to Deepgram.
    -   `send_audio()`: Forwards bytes to the socket.
    -   `get_events()`: Listens to the `LiveTranscriptionEvents.Transcript` event and yields our internal `TranscriptionEvent` dataclass.

## 4. The Implementation (`STTService`)

This is the "glue" code.

### Logic
1.  **Initialize**: Takes `NatsClient` and `Transcriber` as dependencies.
2.  **Run Loop**:
    -   Connects to NATS.
    -   Subscribes to `audio.raw`.
    -   Connects to Transcriber.
    -   **Ingest**: When NATS message arrives -> `transcriber.send_audio()`.
    -   **Egest**: Loops over `transcriber.get_events()` -> Publishes JSON to `text.transcript`.
3.  **Error Handling**:
    -   If Deepgram connection dies, it should attempt to reconnect without crashing the service.

## 5. Testing Strategy

### 5.1 Unit Tests (`test_stt_service.py`)
-   **Goal**: Verify logic without real NATS or Deepgram.
-   **Mocks**:
    -   `MockNatsClient`: Captures published messages.
    -   `MockTranscriber`: Simulates sending audio and receiving fake transcripts.
-   **Scenarios**:
    1.  **Happy Path**: Audio in -> Transcript out.
    2.  **Filtering**: Ensure empty transcripts are ignored.
    3.  **JSON Format**: Verify the output payload structure matches requirements.

### 5.2 Integration Tests
-   (Covered separately, but involves real NATS and real Deepgram).

## 6. Step-by-Step Implementation Plan

1.  **Define Protocols**: Create `src/stt_provider/interfaces.py`.
2.  **Create Mocks**: Create `tests/mocks.py` implementing these protocols.
3.  **Implement Service**: Create `src/stt_provider/service.py` (The logic).
4.  **Write Unit Tests**: Create `tests/test_service.py` and verify `STTService` logic.
5.  **Implement Deepgram Adapter**: Create `src/stt_provider/deepgram_adapter.py`.
6.  **Wire it up**: Update `src/stt_provider/main.py` to use the new classes.

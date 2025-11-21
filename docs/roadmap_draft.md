Here is the complete, updated roadmap for Version 6.0 (Decoupled UI Strategy). This roadmap reflects the split between stt-provider and api-gateway, the multi-architecture build strategy, and the restoration of functional requirements like Music Detection and PhraseSets.

Shutterstock

Phase 0: Foundation & Factory (M0)

Goal: Establish the build pipeline, data assets, and core infrastructure on Tier 3 (CPU) hardware before migrating to Tier 1 (GPU).

    Milestone 0: Scaffolding & Config

        Repo Init: Create Monorepo structure with 7 service directories.

        Docker Strategy: Implement the "Unified Dockerfile" pattern (ARG BASE_IMAGE) for identifier.

        Config: Create docker-compose.yml (Production) and docker-compose.dev.yml (Dev/Mock).

        Data Harvest:

            Script: Download ~20h of church YouTube audio.

            Process: Transcribe with Deepgram Base Model.

            Deliverable: initial_phrases.json seed file (Staff names, Liturgy).

Phase 1: Infrastructure & Messaging (M1-M2)

Goal: Establish the "Nervous System" (Broker) and verify audio transport.

    Milestone 1: The Core Stack (Local Dev)

        Mock Producer: Create mock-audio-producer (reads .wav, streams ZMQ).

        Broker: Implement C++ zmq_proxy container (XPUB/XSUB).

        Gateway: Implement api-gateway skeleton (FastAPI + SQLite).

        Integration Test: Verify Mock Audio -> Broker -> Gateway -> Console Log.

    Milestone 2: Latency & Hardware Validation

        Deploy: Push "Core Stack" to hardware (NUC or Jetson).

        Public URL: Enable Balena Public URL (HTTPS).

        WSS Test: Create index.html echo test to validate network latency.

        Real Audio: Swap Mock for audio-producer (PyAudio) and verify ALSA capture.

Phase 2: Core STT & Resilience (M3-M6)

Goal: Implement the decoupled transcription logic and "Zero Data Loss" safety nets.

    Milestone 3: The stt-provider Service

        Client: Implement Deepgram SDK in stt-provider.

        Config: Inject DEEPGRAM_API_KEY and initial_phrases.json.

        Data Flow:

            stt-provider subscribes to audio.raw.

            Streams to Deepgram.

            Publishes text.transcript back to Broker.

        UI: api-gateway subscribes to text.transcript and broadcasts to WebSocket clients.

    Milestone 4: Context & Quality (YAMNet)

        Service: Create audio-classifier (TFLite).

        Logic: Infer "Music/Silence" -> Publish system.alert.

        Reaction: stt-provider pauses stream on "Music" signal.

        Sanitizer: Implement "Hard Blocklist" & "Soft Allowlist" in stt-provider.

    Milestone 5: Zero Data Loss Resilience

        Buffer: Implement "Sentinel Pattern" in stt-provider.

        Logic: On disconnect -> Buffer to disk (/data/buffer.wav).

        Recovery: On reconnect -> Upload buffer -> Merge live stream.

    Milestone 6: Observability (Sidecar)

        Service: Implement health-watchdog.

        Logic: Ping Broker/Provider/Identifier every 5s via ZMQ.

        UI: api-gateway queries Watchdog to render the Status Banner ("Operational", "Degraded", "Reconnecting").

Phase 3: Security & Administration (M7-M11)

Goal: Secure the PII and build the management interfaces.

    Milestone 7: Advanced Security

        Encryption: Implement AES-256 Per-File Encryption for /data.

        Key Mgmt: Implement "User-Provided Key" (Tier 2/3) or "TPM Sealing" (Tier 1).

        WebSocket: Implement Ticket-Based Handshake (POST /auth -> Token) in api-gateway.

    Milestone 8: Admin Dashboard (SQLAdmin)

        Stack: Install sqladmin in api-gateway.

        Views: CRUD views for PhraseSet, PerformanceLog, QualityLog.

    Milestone 9: The "Review Queue" (QA)

        Trigger: stt-provider detects Low Confidence -> Saves Encrypted Snippet.

        UI: Admin Page lists snippets.

        Streaming: api-gateway decrypts on-the-fly for admin playback (GET /admin/stream/{id}).

    Milestone 10: Speaker Enrollment

        UI: Admin page to upload Voiceprint audio (e.g., "Tom.wav").

        Backend: Save encrypted .wav to /data/enrollment/.

Phase 4: Local AI & Hardware Fork (M12-M13)

Goal: Enable Biometric Identification on GPU hardware.

    Milestone 11: Infrastructure Upgrade (Tier 1/2)

        Hardware: Migrate to Jetson (Tier 1) or GPU PC (Tier 2).

        Base Image: Switch identifier Dockerfile to l4t-pytorch or pytorch/cuda.

    Milestone 12: The identifier Service

        Logic: Load SpeechBrain model.

        Process: PULL audio.raw -> Sliding Window -> Identify Speaker.

        Event: PUSH identity.event ({"name": "Tom"}) to Broker.

    Milestone 13: Correlation Engine

        Logic: api-gateway correlates Speaker 0 (Deepgram) with Tom (Local ID) based on time overlap.

        UI: Update Frontend to display names.

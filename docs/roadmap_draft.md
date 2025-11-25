Master Roadmap (v6.2)

Phase 0: Foundation & Data Strategy (M0)

Goal: Establish the build pipeline and the "Truth" datasets.

    Milestone 0: Scaffolding & Config

        Repo Init & Docker Strategy.

        just setup automation (Secrets/Data dirs).

    Milestone 0.5: The Data Harvest (New)

        Silver Mining: Download 20h YouTube auto-captions. Run mine_phrases.py to extract initial_phrases.json.

        Gold Creation:

            Download 3 services.

            Extract 15 x 3-minute clips (ffmpeg).

            Manually correct transcripts (Human in the Loop).

            Commit to tests/data/gold_standard/.

Phase 1: Infrastructure & Messaging (M1-M2)

Goal: Establish the "Nervous System".

    Milestone 1: The Core Stack

        broker (Two-Port: 5555/5556).

        mock-audio-producer (ZMQ HWM testing).

        api-gateway (UI Skeleton).

    Milestone 2: Hardware Validation

        Deploy to NUC/Jetson.

        Thermal Burn-in (stress-ng).

Phase 2: Core STT & Resilience (M3-M6)

Goal: Implement decoupled transcription.

    Milestone 3: The stt-provider

        Deepgram SDK integration.

        Regression Test: Run Gold Standard clips through the provider and calculate WER.

    Milestone 4: Context & Quality

        Music Detection (audio-classifier).

        PhraseSet Injection (using data from M0.5).

    Milestone 5: Zero Data Loss

        NVMe Buffering ("Catch Up" logic).

        Frontend Timestamp Sorting.

Phase 3: Security & Compliance (M7-M11)

Goal: Secure the PII.

    Milestone 7: data-sweeper & Encryption.

    Milestone 8: Admin Dashboard (sqladmin).

    Milestone 9: The Review Queue (QA Loop).

    Milestone 10: Speaker Enrollment (Uploads).

Phase 4: Local AI (M12-M13)

Goal: Enable Biometric Identification.

    Milestone 11: GPU Infrastructure Upgrade.

    Milestone 12: identifier Service.

    Milestone 13: Correlation Engine.

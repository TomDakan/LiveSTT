System Design Document (v6.2)

Date: November 20, 2025 Status: GOLDEN MASTER / DECOUPLED UI Target Platforms: Tier 1 (Jetson ARM64) / Tier 2 (Desktop GPU) / Tier 3 (Generic CPU) Architecture Pattern: Event-Driven Microservices (ZMQ Broker)

1. Executive Summary

This document defines the architecture for a standalone, high-availability Speech-to-Text (STT) kiosk. The system uses a Multi-Architecture, Decoupled strategy.

Key Change (v6.0): Failure Domain Isolation. The "Brain" is split into api-gateway (UI) and stt-provider (Deepgram). Key Change (v6.2): Stratified QA Strategy. Formalizes the use of "Silver" (Auto-caption) and "Gold" (Human-verified) datasets for regression testing.

2. System Architecture

2.1 High-Level Topology

    Router: A central C++ ZMQ Broker handles bidirectional traffic (tcp://broker:5555 IN, :5556 OUT).

    Isolation: Audio processing (stt-provider, identifier) is strictly separated from User Interaction (api-gateway).

    Discovery: Balena Public Device URL (HTTPS/WSS).

2.2 Hardware Tiers

(Tier 1 Jetson, Tier 2 BYOD GPU, Tier 3 CPU).

3. Component Design (Microservices)

3.1 Service: audio-producer

    Role: Audio Capture.

    Safety: Enforces ZMQ_SNDHWM=1000. Drops frames on backpressure.

3.2 Service: broker

    Role: Central Event Bus (zmq_proxy).

3.3 Service: stt-provider (The Worker)

    Role: Deepgram Integration & Resilience.

    Logic:

        Stream: Sends audio to Deepgram.

        Resilience: Buffers to NVMe/RAM on network loss.

        PhraseSet: Injects vocabulary mined from "Silver" datasets.

3.4 Service: api-gateway (The Face)

    Role: UI Server, Auth, Config.

    Logic:

        Backfill Sort: Sorts transcripts by timestamp_utc to handle recovery bursts.

        Admin UI: sqladmin for managing PhraseSets.

3.5 Service: data-sweeper

    Role: Compliance.

    Policy: cron deletes /data/review files older than 24h.

3.6 Service: identifier (GPU)

    Role: Biometric ID (Tier 1/2 only).

4. Data Strategy (v6.2)

4.1 The "Silver Standard" (Mining)

    Source: YouTube Auto-Captions (JSON3 format).

    Volume: ~20 hours.

    Purpose: Phrase Mining.

    Logic: Automated script scans for High-Frequency Proper Nouns (e.g., "Pastor Tom", "Corinthians") to seed the initial_phrases.json.

    Constraint: Never used for accuracy scoring (WER) due to inherent AI errors.

4.2 The "Gold Standard" (Validation)

    Source: Manual Correction of audio slices.

    Volume: ~1 Hour (20 x 3-minute clips).

    Composition: Stratified Sampling (30% Sermon, 30% Liturgy, 20% Announcements, 20% Transitions).

    Purpose: Regression Testing.

    Logic:

        Human corrects the text using Subtitle Edit.

        CI Pipeline runs these clips through stt-provider.

        Pass Criteria: Word Error Rate (WER) < 5% against Gold text.

5. Security & Compliance

    Encryption: AES-256 Per-File for /data/review.

    Key Mgmt: TPM (Tier 1) or Volatile Injection (Tier 2/3).

    Physical: USB ports disabled. ZMQ bound to internal Docker network only.

6. Pre-Flight Checklist

    Thermal: 60min Burn-in.

    Leak: 30min Network Disconnect Test.

    Compliance: Data retention script verified.

    Accuracy (New): Regression Test Suite (Gold Corpus) returns < 5% WER.

High-Reliability Real-Time STT Kiosk

System Design Document (v6.0)

Date: November 19, 2025 Status: GOLDEN MASTER / DECOUPLED UI Target Platforms: Tier 1 (Jetson ARM64) / Tier 2 (Desktop GPU) / Tier 3 (Generic CPU) Architecture Pattern: Event-Driven Microservices (ZMQ Broker)

1. Executive Summary

This document defines the architecture for a standalone, high-availability Speech-to-Text (STT) kiosk. The system uses a Multi-Architecture, Decoupled strategy.

Key Change (v6.0): Failure Domain Isolation. The "Brain" is split into two services: api-gateway (UI/Orchestration) and stt-provider (Deepgram/Resilience). This ensures the Kiosk UI remains live and manageable even if the transcription engine encounters a fatal error or network block.

2. System Architecture

2.1 High-Level Topology

The system runs on BalenaOS (or standard Docker) using a Reliable Broker topology.

    Router: A central C++ ZMQ Broker handles bidirectional traffic (Audio ->, Metadata <-).

    Isolation: Audio processing (stt-provider, identifier) is strictly separated from User Interaction (api-gateway).

    Discovery: Balena Public Device URL (HTTPS/WSS) + Travel Router Fallback.

2.2 Hardware Tiers

(Unchanged from v5.2: Tier 1 Jetson, Tier 2 BYOD GPU, Tier 3 CPU).

2.3 Messaging Core (The "Broker" Pattern)

    Protocol: ZeroMQ (XPUB/XSUB).

    Topology:

        Producers (Mic, STT, AI) publish events to the Broker.

        Broker broadcasts events to all subscribers.

        Consumers subscribe to specific topics (e.g., audio, transcript, alert).

    Topics:

        audio.raw: Binary PCM chunks.

        text.transcript: Finalized JSON transcripts.

        system.alert: Clipping, Music Detection, or Health alerts.

        identity.event: Biometric matches.

3. Component Design (Microservices)

3.1 Service: audio-producer

    Role: Audio Capture & Signal Monitoring.

    Logic: Captures raw PCM (16kHz). Monitors RMS. Publishes audio.raw and system.alert (Clipping).

    DX: Accepts MOCK_FILE env var.

3.2 Service: broker

    Role: Central Event Bus.

    Implementation: C++ zmq_proxy binary (scratch container).

    Resilience: restart: always. Zero application logic.

3.3 Service: stt-provider (The "Worker")

    Role: Cloud Integration, Resilience, & QA.

    Input: Subscribes to audio.raw.

    Logic:

        Deepgram Client: Manages WebSocket streaming (with endpointing).

        Resilience: Handles On-Disk Buffering and "Catch Up" logic during internet outages.

        Sanitizer: Applies Profanity Filters and PhraseSet logic.

        QA Loop: Maintains Ring Buffer. If confidence < 0.85, saves encrypted snippet to /data/review/.

    Output: Publishes text.transcript to Broker.

3.4 Service: api-gateway (The "Face")

    Role: UI Server, Auth, Config.

    Input: Subscribes to text.transcript, system.alert, identity.event.

    Logic:

        Web Server: Serves Frontend and Admin UI (FastAPI).

        Socket Manager: Broadcasts transcripts to connected clients.

        Correlation Engine: Maps Speaker 0 to Tom based on ID events.

        State Machine: Maintains system status (Live, Paused, Reconnecting) based on event stream.

        Persistence: Manages SQLite config.db.

    Benefit: Does not touch raw audio. Impossible to crash via audio buffer overflow.

3.5 Service: audio-classifier

    Role: Context Awareness (YAMNet).

    Input: Subscribes to audio.raw.

    Output: Publishes system.alert (Music Detected).

3.6 Service: identifier

    Role: Biometric ID (GPU).

    Input: Subscribes to audio.raw.

    Output: Publishes identity.event.

3.7 Service: health-watchdog

    Role: Sidecar Monitor.

    Logic: Pings Broker, Provider, and Identifier. Exposes /status to Gateway.

4. Build Strategy

Unified Dockerfile Strategy applies to identifier and stt-provider.

    stt-provider is built on a lightweight Python base.

    identifier uses the ARG BASE_IMAGE strategy for Multi-Arch GPU support.

5. Data Flow & Resilience

5.1 The "Decoupled" Resilience Model

Scenario: Deepgram API Fails / Internet Cut.

    Failure: stt-provider detects disconnect.

    Action (Worker): stt-provider buffers audio.raw to NVMe.

    Action (UI): stt-provider publishes system.alert -> {"status": "RECONNECTING"}.

    Reaction (Gateway): api-gateway receives alert, broadcasts to Clients. UI shows "Reconnecting..." banner. The Gateway remains 100% responsive.

    Recovery: stt-provider reconnects, catches up, and resumes publishing text.transcript.

6. Security Architecture (Hardened Edge)

6.1 PII & Key Management

    TPM 2.0 (Tier 1): Keys sealed to hardware.

    Crypto-Shredding: Per-file encryption for Voiceprints AND Audio Snippets.

    Scope: stt-provider handles encryption (writing snippets). api-gateway handles decryption (streaming to Admin UI). Both containers share the Master Key (injected via Supervisor).

7. Deployment & DevOps

7.1 Configuration

    docker-compose.yml: Defines the 7-service mesh.

    restart: always: Applied to Broker, Gateway, and Provider.

8. Development Roadmap (v6.0)

    Phase 0: Factory Setup: Base Images, Data Harvest (initial_phrases.json).

    Phase 1: Infrastructure (M0-M2):

        ZMQ Broker (XPUB/XSUB).

        audio-producer (Microphone).

        api-gateway (Skeleton UI).

    Phase 2: Core STT (M3-M6):

        stt-provider implementation (Deepgram).

        Inter-Service Comms: Verify text.transcript flows from Provider -> Broker -> Gateway.

        Resilience (On-Disk Buffer).

    Phase 3: Security & Admin (M7-M11):

        Admin Dashboard (sqladmin).

        QA Loop (Ring Buffer in stt-provider).

        Secure Streaming (api-gateway reads encrypted files).

    Phase 4: Local AI (M12):

        identifier Service (GPU).

        Correlation Engine (in api-gateway).

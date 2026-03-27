# Glossary

## A
- **ADR (Architecture Decision Record)**: A document that captures an important architectural decision made along with its context and consequences.
- **Audio Producer**: The microservice responsible for capturing audio from the hardware interface (ALSA/USB) and publishing it to the NATS broker.

## B
- **Backfill**: The process of uploading buffered audio to the cloud after a session start.
- **Biometric Enrollment**: The process of recording a user's voice to create a voiceprint for future identification.

## D
- **Deepgram**: The third-party API used for Speech-to-Text (STT) transcription.
- **Diarization**: The process of partitioning an audio stream into homogeneous segments according to the speaker identity (Who spoke when?).

## E
- **ECAPA-TDNN**: The neural network architecture used by SpeechBrain for speaker embedding extraction.
- **Edge Computing**: Processing data near the source of generation (the NUC device) rather than in a centralized cloud.

## G
- **Glass-to-Glass Latency**: The total time elapsed from an event occurring (sound wave) to it being visible on the display (text on screen).

## H
- **HSI (Hardware-Software Interface)**: The boundary where software interacts with physical hardware components.

## I
- **Identifier**: The microservice responsible for speaker identification using local biometric voiceprints.

## J
- **JetStream**: The NATS persistence layer used for "Black Box" buffering and store-and-forward.

## N
- **NATS**: A high-performance cloud-native messaging system (the central nervous system of Live STT).

## P
- **PCM (Pulse Code Modulation)**: The standard format for uncompressed digital audio.
- **Provisioning**: The process of setting up the hardware and software for the first time.

## R
- **RTO (Recovery Time Objective)**: The targeted duration of time and a service level within which a business process must be restored after a disaster.

## S
- **SBOM (Software Bill of Materials)**: A list of all the open source and third-party components used in the codebase.
- **SpeechBrain**: An open-source conversational AI toolkit used for the local speaker identification features.

## T
- **Tier 1/2/3**: The hardware deployment classification system used in this project (Industrial NUC / Desktop / CPU-only).

## V
- **Voiceprint**: A mathematical representation (embedding vector) of the unique characteristics of a person's voice.

## W
- **WER (Word Error Rate)**: A common metric for the performance of a speech recognition or machine translation system.
- **WebSocket**: A communication protocol that provides full-duplex communication channels over a single TCP connection.
- **WeSpeaker**: The OpenVINO-compatible toolkit used for speaker embedding extraction.

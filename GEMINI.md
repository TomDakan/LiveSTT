# GEMINI.md - Context & Architecture

> [!IMPORTANT]
> **CRITICAL INSTRUCTION FOR LLMS:**
> This file contains the GROUND TRUTH for this project's architecture and context.
> You MUST read this file before making any structural changes or answering architectural questions.
> If you are unsure about a pattern, refer to the "Architecture" section below.

## Project Identity
- **Project Name:** live-stt
- **Hardware Target:** Jetson Orin Nano
- **Architecture:** Microservices

- **IPC Method:** ZMQ


## Overview
This project aims to... (TODO: Add goal)

## Architecture
This project follows a **Microservices** pattern.


### Communication
Services communicate via **ZMQ**.


## Development Guidelines
1. **Docs-as-Code:** Update this file when architectural decisions change.
2. **Hardware Constraints:** Respect the limitations of Jetson Orin Nano.

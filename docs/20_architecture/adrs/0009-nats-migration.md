# ADR-0009: Migration from ZeroMQ to NATS

**Date**: 2025-11-26  
**Status**: ACCEPTED  
**Supersedes**: [ADR-0001](0001-zmq-broker.md)

**Context**:  
The v6.x architecture used ZeroMQ (ZMQ) for inter-service communication. While fast, ZMQ presented challenges:
1.  **No Persistence**: If a service crashed, messages were lost unless complex application-level buffering was implemented.
2.  **Opaque**: Debugging ZMQ traffic required custom tools; there was no easy way to "inspect" the bus.
3.  **Complexity**: Implementing reliable pub/sub with reconnection logic in ZMQ is non-trivial.

**Decision**:  
Migrate the messaging backbone to **NATS (with JetStream)**.

**Rationale**:
1.  **Persistence**: JetStream provides built-in message persistence, allowing services to "catch up" after a restart or network outage.
2.  **Observability**: NATS has excellent tooling (`nats-box`, `nats-surveyor`) for monitoring traffic and lag.
3.  **Simplicity**: The NATS client libraries handle reconnection and topology automatically.
4.  **Ecosystem**: NATS is a CNCF graduated project with broad language support.

**Consequences**:
-   **Positive**: drastically simplified application code (removed custom buffering logic), better debugging, "Black Box" recording capability.
-   **Negative**: Introduces a new infrastructure dependency (NATS Server).
-   **Mitigation**: NATS Server is a single static binary, extremely lightweight (<20MB), and highly reliable, fitting well within the NUC's resources.

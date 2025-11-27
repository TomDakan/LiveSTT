# Use ZeroMQ XPUB/XSUB Broker Pattern

* **Status**: SUPERSEDED by [ADR-0009](0009-nats-migration.md)
* **Date:** 2025-11-19

---

## Context

The Live STT system requires a robust inter-process communication (IPC) mechanism to route audio data and events between 7 microservices (audio-producer, stt-provider, api-gateway, etc.). The system must support:

1. **High throughput**: 16kHz PCM audio (~32 KB/s per channel)
2. **Low latency**: \< 500ms end-to-end (microphone → UI)
3. **Decoupling**: Services should not know about each other's existence
4. **Resilience**: Individual service failures should not crash the message bus
5. **Simplicity**: Minimal operational overhead (no external dependencies like Kafka/RabbitMQ)

The system is deployed on edge hardware (Jetson Orin Nano) with limited resources and must run entirely offline (except for Deepgram API connectivity).

---

## Decision

We will use **ZeroMQ (ØMQ)** with the **XPUB/XSUB proxy pattern** as the central message broker.

### Implementation
- **Broker**: Single C++ binary (`zmq_proxy`) running in a scratch Docker container
- **Topology**: Publishers connect to XSUB socket (`tcp://*:5555`), subscribers connect to XPUB socket (`tcp://*:5556`)
- **Topics**: Services publish/subscribe to topics (`audio.raw`, `text.transcript`, `system.alert`, `identity.event`)
- **Protocol**: TCP over Docker internal network

### Code Example
```cpp
// audio-broker/src/main.cpp
zmq::context_t context(1);
zmq::socket_t frontend(context, ZMQ_XSUB);
zmq::socket_t backend(context, ZMQ_XPUB);

frontend.bind("tcp://*:5555");
backend.bind("tcp://*:5556");
zmq::proxy(frontend, backend);
```

---

## Consequences

### Positive
- **Zero configuration**: No broker config files, no queues to declare, no exchanges to configure
- **Low latency**: Direct memory-to-memory transfer, no persistence layer
- **Lightweight**: Broker binary is \<1MB, uses \<10MB RAM
- **Automatic reconnection**: ZMQ handles connection drops transparently
- **Language agnostic**: Python services use `pyzmq`, C++ broker uses libzmq

### Negative
- **No persistence**: Messages are dropped if no subscribers are connected (acceptable for real-time audio)
- **No guaranteed delivery**: Fire-and-forget model (mitigated by on-disk buffering in stt-provider)
- **No built-in authentication**: Trust-based (acceptable since all services run in same Docker network)
- **Manual topic filtering**: Services must subscribe to specific topics (not a pub/sub "smart broker")

### Risks and Mitigations
- **Risk**: Broker becomes single point of failure
  - **Mitigation**: `restart: always` policy, broker is stateless so restarts are instant
- **Risk**: Topic namespace collisions
  - **Mitigation**: Structured topic naming (`category.subcategory`), documented in [HSI](../hsi.md)

### Impact on Other Decisions
- Enables [ADR-0002](0002-decoupled-ui.md) - Services communicate via broker, not direct HTTP calls
- Simplifies [Multi-Tier Hardware](0003-multi-tier-hardware.md) - ZMQ works identically on Jetson, desktop, and cloud

---

## Alternatives Considered

### Alternative 1: RabbitMQ
**Why rejected**:
- Requires separate Erlang runtime (\~100MB+ overhead)
- Persistence layer unnecessary for real-time streams
- Configuration complexity (exchanges, queues, bindings)
- Not designed for low-latency binary data

### Alternative 2: MQTT (Mosquitto)
**Why rejected**:
- Designed for IoT telemetry (small messages), not audio streaming
- QoS levels add latency
- Broker state management (subscriptions, retained messages) unnecessary

### Alternative 3: gRPC Streaming
**Why rejected**:
- Requires service discovery (services must know each other's addresses)
- HTTP/2 overhead for high-frequency messages
- No native pub/sub (would need manual fan-out logic)

### Alternative 4: Redis Pub/Sub
**Why rejected**:
- Requires Redis server (\~30MB memory baseline)
- All messages broadcast to all subscribers (no topic filtering until client-side)
- No native binary support (would need base64 encoding overhead)

---

## References

- [ZeroMQ Guide](https://zguide.zeromq.org/)
- [HSI Document](../hsi.md) - ZMQ topology details
- [System Design](../../system_design.md) - Section 2.3 (Messaging Core)

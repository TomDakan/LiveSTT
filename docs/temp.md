This document summarizes the architectural decisions, NATS topology, and Python implementation details for the Real-Time Transcription Appliance.
1. High-Level Architecture

The system follows a Store-and-Forward architecture using NATS JetStream as the central nervous system. It is designed as a Dockerized appliance where reliability and data persistence are paramount.

    Pattern: Microservices with a Shared Chassis (BaseService).

    Concurrency: Python 3.12 asyncio.TaskGroup for structured concurrency.

    Transcription: Deepgram (Cloud) via Async SDK.

    Persistence: NATS JetStream (File Storage) handles all buffering, history, and "database" needs.

2. NATS Topology & Configuration

We utilize 4 distinct data channels to separate concerns and manage retention lifecycles.
A. The Rolling Cache (PRE_BUFFER)

Captures audio when the system is "Idle". Used for the 5-minute pre-roll.

    Stream Name: PRE_BUFFER

    Subjects: preroll.audio

    Retention: Limits (Auto-delete old data)

    Max Age: 6 Minutes (5m buffer + 1m safety margin for flush operations)

    Storage: Memory (Performance)

B. The Production Pipe (AUDIO_STREAM)

Stores the actual event audio (Live + Backfilled).

    Stream Name: AUDIO_STREAM

    Subjects: audio.live.>, audio.backfill.>

    Retention: WorkQueue (Crucial: Messages exist until processed & Acked)

    Max Age: 60 Minutes (Safety net)

    Storage: File (Durability)

C. The Transcript Log (TEXT_STREAM)

Stores the resulting text. Serves as the "Database" for the web view.

    Stream Name: TEXT_STREAM

    Subjects: transcript.raw.>

    Retention: Limits

    Max Age: 7 Days (For debugging/analysis)

    Storage: File

D. System State (KV_BUCKET)

Manages configuration and active session pointers.

    Bucket: system_state

    Keys:

        session_config: JSON blob containing { session_id, status: "ACTIVE"|"IDLE" }

3. Shared Service Chassis

All microservices inherit from a base class to standardize signals, NATS connections, and heartbeats.
Python

# libs/shared-lib/src/shared_lib/service.py
import asyncio
import signal
import logging
import nats
from abc import ABC, abstractmethod

class BaseService(ABC):
    def __init__(self, service_name):
        self.stop_event = asyncio.Event()
        self.service_name = service_name
        self.nc = None
        self.js = None

    @abstractmethod
    async def run_business_logic(self, js, stop_event):
        """Child classes implement this"""
        pass

    async def start(self):
        # 1. Setup Signals
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: self.stop_event.set())

        # 2. Connect NATS
        self.nc = await nats.connect("nats://nats:4222")
        self.js = self.nc.jetstream()

        # 3. Supervisor Pattern
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._heartbeat_loop())
                tg.create_task(self.run_business_logic(self.js, self.stop_event))
                await self.stop_event.wait()
        finally:
            await self.nc.drain()

4. Ingress Service (Audio Producer)

Role: The Gatekeeper. Reads mic data, manages the "Atomic Switch" between Preroll and Live, and flushes the buffer.

Key Logic:

    Atomic Switch: Routes audio to audio.live or preroll.audio based on state. Zero-gap.

    Flush Task: Background task that moves data from PRE_BUFFER to AUDIO_STREAM (Backfill subject).

Python

class IngressService(BaseService):
    def __init__(self):
        super().__init__("ingress-01")
        self.session_id = None
        self.is_active = False

    async def run_business_logic(self, js, stop_event):
        # Start KV Watcher in background
        asyncio.create_task(self._watch_kv_state(js))

        while not stop_event.is_set():
            # 1. Read Mic (Block/Await for ~20ms chunk)
            data = await self.mic.read()

            # 2. Atomic Routing
            if self.is_active:
                # Live Lane
                await js.publish(f"audio.live.{self.session_id}", data)
            else:
                # Cache Lane
                await js.publish("preroll.audio", data)

    async def _watch_kv_state(self, js):
        # Logic to detect transition from IDLE -> ACTIVE
        # When triggered:
        # 1. Update self.session_id = new_id
        # 2. Set self.is_active = True
        # 3. Spawn background flush: asyncio.create_task(self._flush_buffer(js, new_id))
        pass

    async def _flush_buffer(self, js, session_id):
        # Pull from 'preroll.audio'
        # Publish to 'audio.backfill.{session_id}'
        # Append Header: "EOS": "true" to the last message
        pass

5. Transcriber Service (STT Provider)

Role: The Bridge. Consumes NATS, streams to Deepgram, publishes Text.

Key Logic:

    Deepgram "Always-On": Uses Keep-Alive (empty bytes) during silence to maintain context.

    Dual Lanes:

        Live Lane: High priority, runs forever while active.

        Backfill Lane: Background priority, runs until EOS.

    Shielding: Backfill crashes are caught/logged so they don't kill the Live lane.

Python

class TranscriberService(BaseService):
    async def run_business_logic(self, js, stop_event):
        session_id = await self.get_active_session_id()

        async with asyncio.TaskGroup() as tg:
            # 1. LIVE WORKER (Critical)
            # Consumes: audio.live.{session_id}
            tg.create_task(self.live_worker(js, session_id))

            # 2. BACKFILL WORKER (Resilient)
            # Consumes: audio.backfill.{session_id}
            # Wrapped in try/except to prevent crashing the group
            tg.create_task(self.safe_backfill_runner(js, session_id))

    async def live_worker(self, js, session_id):
        # Connect to Deepgram
        # PullSubscribe('audio.live.{session_id}')
        # Loop: Fetch -> Send to Deepgram -> Ack -> Sleep(0)
        # On Timeout: Send b'' (Keep Alive)
        pass

    async def safe_backfill_runner(self, js, session_id):
        # Logic: Retry loop (max 3 attempts)
        # Logic: Connect Deepgram -> Pull 'audio.backfill.{session_id}' -> Send
        # Logic: Stop when msg.header['EOS'] is seen.
        pass

6. Web Service (Display)

Role: The View. Bridges NATS to WebSockets.

Key Logic:

    Unified Stream: "History" and "Live" are just one sequence of messages.

    Scoped Subscription: Connects only to transcript.raw.{session_id}.

    Sorting: Frontend sorts messages by timestamp header (Wall Clock Time) to merge the "Backfill" and "Live" streams visually.

Python

class WebService(BaseService):
    async def websocket_endpoint(self, ws):
        await ws.accept()

        # 1. Get Session ID from KV
        session_id = await self.get_current_session()

        # 2. Subscribe (Replay everything for this session)
        sub = await self.js.subscribe(
            f"transcript.raw.{session_id}",
            ordered_consumer=True,
            config=ConsumerConfig(deliver_policy=DeliverPolicy.All)
        )

        # 3. Stream to UI
        async for msg in sub:
            payload = {
                "text": msg.data.decode(),
                "timestamp": msg.headers.get("timestamp"),
                "is_final": msg.headers.get("is_final")
            }
            await ws.send_json(payload)

7. Initialization Script

Run this once on appliance startup to configure the streams.
Python

async def init_streams(js):
    # 1. The Rolling Cache
    await js.add_stream(name="PRE_BUFFER", subjects=["preroll.audio"], config=StreamConfig(
        retention=RetentionPolicy.Limits,
        max_age=6 * 60, # 6 Minutes
        storage=StorageType.Memory
    ))

    # 2. The Production Pipe (Live + Backfill)
    await js.add_stream(name="AUDIO_STREAM", subjects=["audio.>"], config=StreamConfig(
        retention=RetentionPolicy.WorkQueue,
        max_age=60 * 60, # 60 Minutes
        storage=StorageType.File
    ))

    # 3. The Transcript Database
    await js.add_stream(name="TEXT_STREAM", subjects=["transcript.>"], config=StreamConfig(
        retention=RetentionPolicy.Limits,
        max_age=7 * 24 * 60 * 60, # 7 Days
        storage=StorageType.File
    ))

    # 4. KV Bucket
    await js.create_key_value(config=KeyValueConfig(bucket="system_state"))

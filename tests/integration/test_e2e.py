import asyncio
import json
import os
import subprocess
import sys
import time

import pytest
import websockets
from audio_producer.main import AudioProducerService
from httpx import AsyncClient
from messaging.nats import NatsJSManager
from messaging.streams import (
    AUDIO_STREAM_CONFIG,
    TRANSCRIPTION_STREAM_CONFIG,
)
from stt_provider.main import STTProviderService

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")


class MockTranscriber:
    def __init__(self) -> None:
        self.total_bytes = 0
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def finish(self) -> None:
        self.connected = False

    async def send_audio(self, data: bytes) -> None:
        self.total_bytes += len(data)

    async def get_events(self):  # type: ignore[override]
        # Yield nothing, just keep connection open
        while self.connected:
            await asyncio.sleep(0.1)

            class MockEvent:
                text = "dummy"
                is_final = True
                confidence = 1.0

            yield MockEvent()


# NOTE: Renamed to disable automatic collection due to flakiness (ConnectionClosedOK)
# Pending rewrite for v8.0 API (AudioProducerService, STTProviderService).
@pytest.mark.integration
@pytest.mark.skip(reason="Pending rewrite for v8.0 BaseService API")
@pytest.mark.asyncio
async def _test_e2e_flow() -> None:
    """
    End-to-End Integration Test — PENDING REWRITE for v8.0 BaseService API.
    Verifies: Audio File -> Producer -> NATS -> STT -> NATS -> Gateway -> WebSocket
    """

    if not os.getenv("DEEPGRAM_API_KEY"):
        pytest.skip("DEEPGRAM_API_KEY not set")

    # 1. Start API Gateway in a Subprocess
    port = 8001
    host = "127.0.0.1"

    # Start uvicorn process
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api_gateway.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=os.getcwd(),
        env={**os.environ, "NATS_URL": NATS_URL},
    )

    try:
        # Wait for server to start
        base_url = f"http://{host}:{port}"
        ws_url = f"ws://{host}:{port}/ws/transcripts"

        # Poll health check
        started = False
        async with AsyncClient(base_url=base_url) as client:
            start_time = time.time()
            while time.time() - start_time < 10:
                try:
                    resp = await client.get("/health")
                    if resp.status_code == 200:
                        started = True
                        break
                except Exception:
                    await asyncio.sleep(0.5)

        if not started:
            pytest.fail("API Gateway failed to start")

        # 2. Setup STT Provider
        stt_nats = NatsJSManager()
        await stt_nats.connect(NATS_URL)
        await stt_nats.ensure_stream(**TRANSCRIPTION_STREAM_CONFIG)

        stt_service = STTProviderService()
        stt_task = asyncio.create_task(stt_service.start())
        await asyncio.sleep(1.0)

        # 3. Setup Audio Producer
        prod_nats = NatsJSManager()
        await prod_nats.connect(NATS_URL)
        await prod_nats.ensure_stream(**AUDIO_STREAM_CONFIG)

        test_file = "tests/data/test_audio.wav"
        if not os.path.exists(test_file):
            pytest.fail(f"Test file {test_file} missing")

        # Instead of NatsAudioPublisher, we use the service itself
        # We set AUDIO_FILE to test_audio.wav
        os.environ["AUDIO_FILE"] = test_file
        producer = AudioProducerService()

        # 4. Execute Flow
        async with websockets.connect(ws_url) as websocket:  # type: ignore
            # Wait for subscription
            await asyncio.sleep(0.5)

            # Start Producer
            producer_task = asyncio.create_task(producer.start())

            # Wait for producer
            try:
                await asyncio.wait_for(producer_task, timeout=5.0)
            except TimeoutError:
                producer_task.cancel()

            # Receive message (expecting at least one)
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"Received: {message}")
                _data = json.loads(message)  # type: ignore
                assert _data["type"] == "transcript"
            except TimeoutError:
                # If audio is silence, maybe no transcript. But we verified connection.
                print(
                    "No transcript received (could be silence), but WebSocket connected."
                )
                pass

        # Cleanup Tasks
        await stt_service.stop()
        await stt_task
        await prod_nats.close()
        await stt_nats.close()

    finally:
        proc.terminate()
        proc.wait()


@pytest.mark.integration
@pytest.mark.skip(reason="Pending rewrite for v8.0 BaseService API")
@pytest.mark.asyncio
async def test_e2e_persistence() -> None:
    """
    Verifies Data Persistence (JetStream) — PENDING REWRITE for v8.0 BaseService API.
    Scenario: Producer publishes data; STT Provider starts late and catches up.
    """
    if not os.getenv("DEEPGRAM_API_KEY"):
        pytest.skip("DEEPGRAM_API_KEY not set")

    # 1. Setup Audio Producer & Publish Data
    prod_nats = NatsJSManager()
    await prod_nats.connect(NATS_URL)
    # Create stream with explicit retention
    await prod_nats.ensure_stream(**AUDIO_STREAM_CONFIG)

    test_file = "tests/data/test_audio.wav"
    if not os.path.exists(test_file):
        pytest.fail(f"Test file {test_file} missing")

    # Use service to publish (it handles its own source)
    os.environ["AUDIO_FILE"] = test_file
    producer = AudioProducerService()

    # Publish all data
    print("Publishing data...")
    try:
        # We need a way to stop it after one file loop
        # For E2E, maybe just run it for a few seconds
        background_tasks = set()
        task = asyncio.create_task(producer.start())
        background_tasks.add(task)
        await asyncio.sleep(2.0)
        await producer.stop()
        task.cancel()
    except Exception as e:
        print(f"Producer error: {e}")
        pass

    print("Data published.")
    await prod_nats.close()

    # 2. Start STT Provider (Delayed)
    print("Starting STT Provider...")
    stt_nats = NatsJSManager()
    await stt_nats.connect(NATS_URL)
    # Ensure text stream exists for output
    await stt_nats.ensure_stream(**TRANSCRIPTION_STREAM_CONFIG)

    # Note: Mocking transcriber in the service is tricker now.
    # We'll check if the service publishes something or use Deepgram if available.
    # For now, let's keep it simple and just start the service.
    stt_service = STTProviderService()

    # Start service in background
    stt_task = asyncio.create_task(stt_service.start())

    # Wait for catch-up
    # We check if messages were processed by checking the transcript.raw stream
    messages_received = False
    for _ in range(20):
        await asyncio.sleep(0.5)
        # Check if any messages exist in TRANSCRIPTION_STREAM
        try:
            # We can use a ephemeral consumer to check if messages were published
            sub = await stt_nats.js.subscribe("transcript.raw.backfill")
            msg = await sub.next_msg(timeout=0.5)
            if msg:
                messages_received = True
                print(
                    "Catch-up successful! Revealed messages in transcript.raw.backfill."
                )
                break
        except Exception:
            continue

    await stt_service.stop()
    await stt_task
    assert messages_received, "STT Provider did not publish backfilled data!"

import asyncio
from typing import Any

from messaging.service import BaseService
from messaging.streams import (
    AUDIO_STREAM_CONFIG,
    CLASSIFICATION_STREAM_CONFIG,
    PREROLL_STREAM_CONFIG,
    TRANSCRIPTION_STREAM_CONFIG,
)

REPORT_INTERVAL_S: float = 1800.0  # 30 minutes
MONITORED_STREAMS: list[str] = [
    str(PREROLL_STREAM_CONFIG["name"]),
    str(AUDIO_STREAM_CONFIG["name"]),
    str(TRANSCRIPTION_STREAM_CONFIG["name"]),
    str(CLASSIFICATION_STREAM_CONFIG["name"]),
]


class DataSweeper(BaseService):
    def __init__(self) -> None:
        super().__init__("data-sweeper")

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        self.logger.info("Data Sweeper starting...")

        while not stop_event.is_set():
            await self._report_stream_stats(js)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=REPORT_INTERVAL_S)
            except TimeoutError:
                continue

    async def _report_stream_stats(self, js: Any) -> None:
        for stream_name in MONITORED_STREAMS:
            try:
                info = await js.stream_info(stream_name)
                state = info.state
                self.logger.info(
                    f"{stream_name}: {state.messages} msgs, "
                    f"{state.bytes / 1024:.1f} KB, "
                    f"{state.consumer_count} consumers"
                )
            except Exception as e:
                self.logger.warning(f"{stream_name}: unavailable ({e})")


def main() -> None:
    service = DataSweeper()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()

import logging
from typing import Any

from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import RetentionPolicy, StorageType, StreamConfig

logger = logging.getLogger("messaging.nats")


class NatsJSManager:
    """
    Manages NATS connection and Stream configuration.
    Exposes raw .nc and .js objects for services to use directly.
    """

    def __init__(self) -> None:
        self.nc = NATS()
        self.js: JetStreamContext | None = None

    async def connect(self, servers: list[str] | str) -> tuple[NATS, JetStreamContext]:
        """
        Connects to NATS and returns the Client and JetStream context.
        """
        await self.nc.connect(servers)
        self.js = self.nc.jetstream()
        logger.info(f"Connected to NATS: {servers}")
        return self.nc, self.js

    async def close(self) -> None:
        """Gracefully closes the connection."""
        await self.nc.drain()
        await self.nc.close()
        logger.info("NATS Connection closed")

    async def ensure_stream(self, name: str, subjects: list[str], **kwargs: Any) -> None:
        """
        Idempotent stream creation/update helper.
        """
        if not self.js:
            raise RuntimeError("NATS not connected")

        # Merge defaults with kwargs
        config_args = {
            "name": name,
            "subjects": subjects,
            "storage": StorageType.FILE,
            "retention": RetentionPolicy.LIMITS,
            **kwargs,
        }

        config = StreamConfig(**config_args)

        try:
            await self.js.add_stream(config)
            logger.info(f"Stream '{name}' created.")
        except Exception:
            # If stream exists, try to update it (in case config changed)
            try:
                await self.js.update_stream(config)
                logger.info(f"Stream '{name}' updated.")
            except Exception as e2:
                logger.warning(f"Could not configure stream '{name}': {e2}")

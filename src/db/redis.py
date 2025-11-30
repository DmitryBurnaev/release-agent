import logging

import redis.asyncio as aioredis

from src.settings.db import RedisSettings, get_redis_settings
from src.utils import singleton

logger = logging.getLogger(__name__)


@singleton
class AsyncRedisConnectors:
    """
    Singleton class that handles redis connections
    """

    def __init__(self, settings: RedisSettings) -> None:
        self.redis_settings: RedisSettings = settings
        self.client: aioredis.Redis | None = None

    async def init_connection(self) -> None:
        """
        Initialize the Redis connection

        Raises:
            RuntimeError: If the Redis connection is not initialized
        """
        logger.info("Redis: Initializing connection to %s...", self.redis_settings.info)
        if self.client is None:
            self.client = aioredis.Redis(
                host=self.redis_settings.host,
                port=self.redis_settings.port,
                db=self.redis_settings.db,
                decode_responses=self.redis_settings.decode_responses,
                socket_connect_timeout=self.redis_settings.socket_connect_timeout,
                socket_timeout=self.redis_settings.socket_timeout,
                max_connections=self.redis_settings.max_connections,
            )

        await self._ping_connection()

    async def _ping_connection(self) -> None:
        """Ping the Redis connection"""
        if self.client is None:
            raise RuntimeError("Redis connection is not initialized")

        connection_info = self.redis_settings.info

        logger.info("Redis: Pinging connection to %s...", connection_info)

        try:
            await self.client.ping()
            logger.info("Redis: Connection to %s pinged successfully", connection_info)
        except aioredis.ConnectionError as e:
            logger.error("Redis: Failed to ping connection to %s: %s", connection_info, e)
            raise RuntimeError(f"Redis: Failed to ping connection: {e}") from e

    async def close_connection(self) -> None:
        """Close the Redis connection"""
        if self.client is None:
            logger.warning("Redis: Connection is not initialized, cannot close connection")
            return

        await self.client.aclose()
        self.client = None
        logger.info("Redis: Connection to %s closed successfully", self.redis_settings.info)

    @property
    def client(self) -> aioredis.Redis:
        """Get the Redis client instance from current context"""
        if self.client is None:
            logger.warning("Redis: Client is not initialized!")
            raise RuntimeError("Client is not initialized. Make sure lifespan is properly set up.")

        return self.client


_redis_connectors = AsyncRedisConnectors(get_redis_settings())


async def initialize_redis() -> None:
    """Initialize the Redis connection"""
    await _redis_connectors.init_connection()


async def close_redis() -> None:
    """Close the Redis connection"""
    await _redis_connectors.close_connection()


def get_redis_client() -> aioredis.Redis:
    """Get the Redis client instance from current context"""
    return _redis_connectors.client

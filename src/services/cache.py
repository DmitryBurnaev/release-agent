import json
import time
import logging
from typing import Protocol, Any, TypeAlias

import redis.asyncio as aioredis

from src.constants import CACHE_KEY_ACTIVE_RELEASES_PAGE
from src.utils import singleton

logger = logging.getLogger("cache")
DEFAULT_CACHE_TTL: int = 3600
CacheValueType: TypeAlias = str | list[dict[str, Any]] | dict[str, Any]


class CacheProtocol(Protocol):
    async def get(self, key: str) -> CacheValueType | None:
        pass

    async def set(self, key: str, value: CacheValueType, ttl: int | None = None) -> None:
        pass

    async def invalidate(self, key: str | None = None) -> None:
        pass

    async def invalidate_pattern(self, prefix: str) -> None:
        pass


@singleton
class InMemoryCache(CacheProtocol):
    """Simple in-memory cache with TTL per key."""

    def __init__(self) -> None:
        self._ttl: float = DEFAULT_CACHE_TTL
        self._data: dict[str, CacheValueType] = {}
        self._last_update: dict[str, float] = {}

    async def get(self, key: str) -> CacheValueType | None:
        """Get cached value for a key if not expired.

        Args:
            key: Cache key to look up

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        if key not in self._data:
            return None

        if time.monotonic() - self._last_update[key] > self._ttl:
            del self._data[key]
            del self._last_update[key]
            return None

        logger.debug("Cache: got value for key %s", key)
        return self._data[key]

    async def set(self, key: str, value: CacheValueType, ttl: int | None = None) -> None:
        """Set new cache value for key and update timestamp.

        Args:
            key: Cache key to store value
            value: Value to cache
            ttl: TTL to use (ignored for in-memory cache, uses default TTL)
        """
        self._data[key] = value
        self._last_update[key] = time.monotonic()
        logger.debug("Cache: set value for key %s | value: %s", key, value)

    async def invalidate(self, key: str | None = None) -> None:
        """Force cache invalidation.

        Args:
            key: Specific key to invalidate, if None - invalidate all cache
        """
        if key is None:
            self._data.clear()
            self._last_update.clear()
        elif key in self._data:
            del self._data[key]
            del self._last_update[key]

    async def invalidate_pattern(self, prefix: str) -> None:
        """Invalidate all cache keys starting with the prefix.

        Args:
            prefix: Prefix to match keys (e.g., "active_releases_page_")
        """
        keys_to_remove = [key for key in self._data.keys() if key.startswith(prefix)]
        for key in keys_to_remove:
            if key in self._data:
                del self._data[key]
            if key in self._last_update:
                del self._last_update[key]
        if keys_to_remove:
            logger.debug("Cache: invalidated %i keys with prefix %s", len(keys_to_remove), prefix)


@singleton
class RedisCache(CacheProtocol):
    """Redis-based cache implementation with JSON serialization and async operations."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0) -> None:
        """Initialize Redis cache client.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
        """
        self._host = host
        self._port = port
        self._db = db
        self._client: aioredis.Redis | None = None
        self._default_ttl: int = DEFAULT_CACHE_TTL

    async def _ensure_client(self) -> aioredis.Redis:
        """Ensure Redis client is initialized and connected."""
        if self._client is None:
            self._client = aioredis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            try:
                await self._client.ping()
                logger.info(
                    "Redis cache: connected to %s:%i (db=%i)", self._host, self._port, self._db
                )
            except aioredis.ConnectionError as e:
                logger.error("Redis cache: connection failed: %s", e)
                await self._client.aclose()
                self._client = None
                raise
        return self._client

    async def get(self, key: str) -> CacheValueType | None:
        """Get cached value for a key.

        Args:
            key: Cache key to look up

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        try:
            client = await self._ensure_client()
            value = await client.get(key)
            if value is None:
                return None

            logger.debug("Cache: got value for key %s", key)
            return json.loads(value)
        except (aioredis.RedisError, json.JSONDecodeError) as e:
            logger.error("Redis cache: error getting key %s: %s", key, e)
            return None

    async def set(self, key: str, value: CacheValueType, ttl: int | None = None) -> None:
        """Set new cache value for key.

        Args:
            key: Cache key to store value
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
        """
        try:
            client = await self._ensure_client()
            serialized = json.dumps(value)
            ttl_seconds = ttl if ttl is not None else self._default_ttl
            await client.setex(key, ttl_seconds, serialized)
            logger.debug("Cache: set value for key %s | ttl: %i", key, ttl_seconds)
        except (aioredis.RedisError, (TypeError, ValueError)) as e:
            logger.error("Redis cache: error setting key %s: %s", key, e)

    async def invalidate(self, key: str | None = None) -> None:
        """Force cache invalidation.

        Args:
            key: Specific key to invalidate, if None - invalidate all cache (FLUSHDB)
        """
        try:
            client = await self._ensure_client()
            if key is None:
                await client.flushdb()
                logger.debug("Cache: invalidated all keys")
            else:
                await client.delete(key)
                logger.debug("Cache: invalidated key %s", key)
        except aioredis.RedisError as e:
            logger.error("Redis cache: error invalidating key %s: %s", key, e)

    async def invalidate_pattern(self, prefix: str) -> None:
        """Invalidate all cache keys starting with the prefix.

        Args:
            prefix: Prefix to match keys (e.g., "active_releases_page_")
        """
        try:
            client = await self._ensure_client()
            pattern = f"{prefix}*"
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
                logger.debug("Cache: invalidated %i keys with prefix %s", len(keys), prefix)
        except aioredis.RedisError as e:
            logger.error("Redis cache: error invalidating pattern %s: %s", prefix, e)


def get_cache() -> CacheProtocol:
    """Get cache instance based on configuration.

    Returns:
        CacheProtocol instance (InMemoryCache or RedisCache)
    """
    from src.settings import get_app_settings

    settings = get_app_settings()
    if settings.redis.use_redis:
        try:
            return RedisCache(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
            )
        except Exception as e:
            logger.error("Failed to initialize Redis cache, falling back to InMemoryCache: %s", e)
            return InMemoryCache()

    return InMemoryCache()


async def invalidate_release_cache() -> None:
    """Invalidate cache for active releases (all pages)"""
    prefix = CACHE_KEY_ACTIVE_RELEASES_PAGE.replace("{offset}_{limit}", "")
    # Invalidate all paginated cache keys
    cache: CacheProtocol = get_cache()
    await cache.invalidate_pattern(prefix)
    logger.debug("[CACHE] Invalidated: all paginated pages with prefix %s", prefix)

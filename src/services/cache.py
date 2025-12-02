import json
import time
import logging
import contextlib
from typing import Generator, Protocol, Any, TypeAlias, Literal

import redis.asyncio as aioredis

from src.constants import CACHE_KEY_ACTIVE_RELEASES_PAGE
from src.db.redis import get_redis_client
from src.exceptions import CacheBackendError
from src.settings import get_app_settings
from src.utils import singleton, cut_string

logger = logging.getLogger(__name__)
DEFAULT_CACHE_TTL: int = 3600
CacheValueType: TypeAlias = str | list[dict[str, Any]] | dict[str, Any]
type CacheOperation = Literal["get", "set", "invalidate", "invalidate_pattern"]
type CacheBackend = Literal["redis", "memory"]


class CacheProtocol(Protocol):
    async def get(self, key: str) -> CacheValueType | None:
        pass

    async def set(self, key: str, value: CacheValueType, ttl: int | None = None) -> None:
        pass

    async def invalidate(
        self,
        key: str | None = None,
        pattern: str | Literal["*"] | None = None,
    ) -> None:
        pass


@contextlib.contextmanager
def cache_wrap_error(
    operation: CacheOperation,
    backend: CacheBackend = "redis",
) -> Generator[None, None, None]:
    """
    Context manager to wrap cache operations and raise CacheBackendError
    if any error occurs.

    :param operation: Cache operation to wrap
    :param backend: Cache backend to use (redis or memory)
    :return: Generator to yield the context manager
    :raises: CacheBackendError: If any error occurs while using the cache
    """
    logger.debug("Cache[%s:%s] start execution...", backend, operation)
    try:
        yield
    except aioredis.RedisError as exc:
        logger.error("Cache[%s:%s] execution error: %s", backend, operation, exc)
        raise CacheBackendError(f"Redis execution error: {exc}") from exc

    except (TypeError, ValueError) as exc:
        logger.error("Cache[%s:%s] common error: %s", backend, operation, exc)
        raise CacheBackendError(f"Common error: {exc}") from exc


@singleton
class InMemoryCache(CacheProtocol):
    """Simple memory cache with TTL per key."""

    def __init__(self) -> None:
        self._ttl: float = DEFAULT_CACHE_TTL
        self._data: dict[str, CacheValueType] = {}
        self._last_update: dict[str, float] = {}

    async def get(self, key: str) -> CacheValueType | None:
        """
        Get cached value for a key if not expired.

        :param key: Cache key to look up
        :return: Cached value if exists and not expired, None otherwise
        """
        if key not in self._data:
            return None

        if time.monotonic() - self._last_update[key] > self._ttl:
            del self._data[key]
            del self._last_update[key]
            return None

        logger.debug("Cache[memory]: got value for key %s", key)
        return self._data[key]

    async def set(self, key: str, value: CacheValueType, ttl: int | None = None) -> None:
        """
        Set new cache value for key and update timestamp.

        :param key: Cache key to store value
        :param value: Value to cache
        :param ttl: TTL to use (ignored for memory cache, uses default TTL)
        """
        self._data[key] = value
        self._last_update[key] = time.monotonic()
        logger.debug("Cache[memory]: set value for key %s | value: %s", key, value)

    async def invalidate(
        self,
        key: str | None = None,
        pattern: str | Literal["*"] | None = None,
    ) -> None:
        """
        Force cache invalidation for a specific key or pattern.

        :param key: Specific key to invalidate, if None - invalidate all cache
        :param pattern: Pattern to invalidate, if None - invalidate all cache
        :raises: ValueError: If key or pattern is not provided
        """
        if pattern == "*":
            logger.debug("Cache[memory]: invalidated all keys")
            self._data.clear()
            self._last_update.clear()
            return

        elif pattern:
            prefix = pattern.removesuffix("*")
            keys_to_remove = [key for key in self._data.keys() if key.startswith(prefix)]
            for key in keys_to_remove:
                if key in self._data:
                    del self._data[key]
                if key in self._last_update:
                    del self._last_update[key]

            if keys_to_remove:
                logger.debug(
                    "Cache[memory]: invalidated %i keys with prefix %s",
                    len(keys_to_remove),
                    prefix,
                )
        elif key:
            if key in self._data:
                del self._data[key]
                del self._last_update[key]

        else:
            raise ValueError("Cache[memory]: key or pattern is required for invalidation")


@singleton
class RedisCache(CacheProtocol):
    """Redis-based cache implementation with JSON serialization and async operations."""

    def __init__(self, client: aioredis.Redis) -> None:
        """Initialize Redis cache client.

        :param client: Redis client instance
        """
        self._client = client
        self._default_ttl: int = DEFAULT_CACHE_TTL

    @property
    def client(self) -> aioredis.Redis:
        """Get the Redis client instance from current context"""
        if self._client is None:
            logger.warning("Cache[redis]: Client is not initialized!")
            raise RuntimeError("Client is not initialized. Make sure lifespan is properly set up.")

        return self._client

    async def get(self, key: str) -> CacheValueType | None:
        """
        Get cached value for a key from Redis.

        :param key: Cache key to look up
        :return: Cached value if exists and not expired, None otherwise
        """
        with cache_wrap_error("get", backend="redis"):
            value = await self.client.get(key)
            if value is None:
                return None

            decoded: CacheValueType = json.loads(value)

        logger.debug(
            "Cache[redis:get] got value for key %s | value: %s",
            key,
            cut_string(str(decoded), max_length=64),
        )
        return decoded

    async def set(self, key: str, value: CacheValueType, ttl: int | None = None) -> None:
        """
        Set new cache value for key in Redis.

        :param key: Cache key to store value
        :param value: Value to cache
        :param ttl: TTL in seconds (uses default if None)
        """
        ttl_seconds = ttl or self._default_ttl
        with cache_wrap_error("set", backend="redis"):
            serialized = json.dumps(value)
            await self.client.setex(key, ttl_seconds, serialized)

        logger.debug(
            "Cache[redis:set] key %s | ttl: %i | value: %s",
            key,
            ttl_seconds,
            cut_string(serialized, max_length=64),
        )

    async def invalidate(
        self,
        key: str | None = None,
        pattern: str | Literal["*"] | None = None,
    ) -> None:
        """
        Force cache invalidation for a specific key or pattern in Redis.

        :param key: Specific key to invalidate, if None - invalidate all cache (FLUSHDB)
        :param pattern: Pattern to invalidate, if None - invalidate all cache
        :raises: ValueError: If key or pattern is not provided
        """

        with cache_wrap_error("invalidate", backend="redis"):
            if pattern == "*":
                logger.info("Cache[redis]: invalidating all keys")
                await self.client.flushdb()
                return

            if pattern:
                prefix = pattern.removesuffix("*")
                keys_to_remove = [key for key in await self.client.keys(pattern)]
                if keys_to_remove:
                    await self.client.delete(*keys_to_remove)
                    logger.debug(
                        "Cache[redis]: invalidated %i keys with prefix %s",
                        len(keys_to_remove),
                        prefix,
                    )

            elif key:
                logger.debug("Cache[redis]: invalidating key %s", key)
                await self.client.delete(key)
            else:
                raise ValueError("Cache[redis]: key or pattern is required for invalidation")


def get_cache(backend: Literal["redis", "memory"] = "redis") -> CacheProtocol:
    """Get cache instance based on configuration.

    :param backend: Cache backend to use (redis or memory)
    :return: CacheProtocol instance (InMemoryCache or RedisCache)
    """
    if backend == "memory":
        logger.debug("Cache: requested InMemoryCache")
        return InMemoryCache()

    settings = get_app_settings()

    if settings.flags.use_redis:
        logger.debug("Cache: requested RedisCache and redis is enabled")
        return RedisCache(get_redis_client())

    logger.debug("Cache: redis is disabled, returning InMemoryCache")
    return InMemoryCache()


async def invalidate_release_cache() -> None:
    """Invalidate cache for active releases (all pages)"""
    prefix = CACHE_KEY_ACTIVE_RELEASES_PAGE.replace("{offset}_{limit}", "")
    # Invalidate all paginated cache keys
    cache: CacheProtocol = get_cache()
    await cache.invalidate(pattern=f"{prefix}*")
    logger.info("[CACHE] Invalidated: all paginated pages with prefix %s", prefix)

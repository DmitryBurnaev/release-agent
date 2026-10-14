import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.constants import CACHE_KEY_DEFAULT_PRODUCT
from src.services.cache import InMemoryCache, invalidate_product_cache


class TestCache:

    @pytest.fixture
    def cache(self) -> InMemoryCache:
        return InMemoryCache()

    @pytest.mark.asyncio
    async def test_get_set(self, cache: InMemoryCache) -> None:
        # Test setting and getting value
        await cache.set("test", "value")
        result = await cache.get("test")
        assert result == "value"

        # Test getting non-existent key
        result = await cache.get("non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache: InMemoryCache, monkeypatch) -> None:  # type: ignore
        old_ttl = cache._ttl
        cache._ttl = 0.1
        await cache.set("test", "value")
        result = await cache.get("test")
        assert result == "value"

        # Verify value is gone
        time.sleep(0.2)
        result = await cache.get("test")
        assert result is None
        cache._ttl = old_ttl

    @pytest.mark.asyncio
    async def test_invalidate(self, cache: InMemoryCache) -> None:
        # Set multiple values
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Invalidate specific key
        await cache.invalidate("key1")
        result1 = await cache.get("key1")
        result2 = await cache.get("key2")
        assert result1 is None
        assert result2 == "value2"

        # Invalidate all
        await cache.invalidate(pattern="*")
        result1 = await cache.get("key1")
        result2 = await cache.get("key2")
        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_product_invalidation_clears_default_and_release_pages(self) -> None:
        cache = MagicMock()
        cache.invalidate = AsyncMock()

        with patch("src.services.cache.get_cache", return_value=cache):
            await invalidate_product_cache()

        assert cache.invalidate.await_args_list[0].kwargs == {
            "key": CACHE_KEY_DEFAULT_PRODUCT
        }
        assert cache.invalidate.await_args_list[1].kwargs == {
            "pattern": "active_releases_page_*"
        }

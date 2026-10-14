from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.constants import CACHE_KEY_DEFAULT_PRODUCT
from src.db.models import Product
from src.exceptions import InstanceLookupError
from src.services.products import ProductIdentity, get_default_product


def make_uow() -> tuple[MagicMock, MagicMock]:
    uow = MagicMock()
    uow.session = MagicMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=uow)
    context.__aexit__ = AsyncMock(return_value=None)
    return uow, context


@pytest.mark.asyncio
async def test_default_product_is_returned_from_cache_without_database() -> None:
    cache = MagicMock()
    cache.get = AsyncMock(return_value={"id": 7, "name": "podcasts"})
    cache.set = AsyncMock()
    settings = MagicMock()
    settings.flags.api_cache_enabled = True

    with (
        patch("src.services.products.get_cache", return_value=cache),
        patch("src.services.products.get_app_settings", return_value=settings),
        patch("src.services.products.SASessionUOW") as uow_factory,
    ):
        result = await get_default_product()

    assert result == ProductIdentity(id=7, name="podcasts")
    cache.get.assert_awaited_once_with(CACHE_KEY_DEFAULT_PRODUCT)
    cache.set.assert_not_awaited()
    uow_factory.assert_not_called()


@pytest.mark.asyncio
async def test_default_product_is_loaded_and_cached() -> None:
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    settings = MagicMock()
    settings.flags.api_cache_enabled = True
    _, context = make_uow()
    repository = MagicMock()
    repository.get_default_or_only = AsyncMock(
        return_value=Product(id=9, name="docker", is_default=True)
    )

    with (
        patch("src.services.products.get_cache", return_value=cache),
        patch("src.services.products.get_app_settings", return_value=settings),
        patch("src.services.products.SASessionUOW", return_value=context),
        patch("src.services.products.ProductRepository", return_value=repository),
    ):
        result = await get_default_product()

    assert result == ProductIdentity(id=9, name="docker")
    cache.set.assert_awaited_once_with(
        CACHE_KEY_DEFAULT_PRODUCT,
        {"id": 9, "name": "docker"},
    )


@pytest.mark.asyncio
async def test_missing_or_ambiguous_default_is_not_cached() -> None:
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    settings = MagicMock()
    settings.flags.api_cache_enabled = True
    _, context = make_uow()
    repository = MagicMock()
    repository.get_default_or_only = AsyncMock(return_value=None)

    with (
        patch("src.services.products.get_cache", return_value=cache),
        patch("src.services.products.get_app_settings", return_value=settings),
        patch("src.services.products.SASessionUOW", return_value=context),
        patch("src.services.products.ProductRepository", return_value=repository),
        pytest.raises(InstanceLookupError, match="Default product not found"),
    ):
        await get_default_product()

    cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_api_cache_always_reads_database() -> None:
    cache = MagicMock()
    cache.get = AsyncMock()
    cache.set = AsyncMock()
    settings = MagicMock()
    settings.flags.api_cache_enabled = False
    _, context = make_uow()
    repository = MagicMock()
    repository.get_default_or_only = AsyncMock(
        return_value=Product(id=4, name="podcasts", is_default=False)
    )

    with (
        patch("src.services.products.get_cache", return_value=cache) as get_cache,
        patch("src.services.products.get_app_settings", return_value=settings),
        patch("src.services.products.SASessionUOW", return_value=context),
        patch("src.services.products.ProductRepository", return_value=repository),
    ):
        result = await get_default_product()

    assert result == ProductIdentity(id=4, name="podcasts")
    get_cache.assert_not_called()
    cache.get.assert_not_awaited()
    cache.set.assert_not_awaited()

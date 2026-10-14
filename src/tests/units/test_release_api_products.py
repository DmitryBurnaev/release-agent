from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import Product, Release
from src.models import ReleaseCreate, ReleaseUpdate
from src.modules.api.releases import create_release, update_release
from src.services.products import ProductIdentity


def make_uow() -> MagicMock:
    uow = MagicMock()
    uow.session = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow


def make_release(product: Product) -> Release:
    return Release(
        id=10,
        product_id=product.id,
        product=product,
        version="2.0.0",
        notes="notes",
        url="",
        is_active=False,
        published_at=datetime(2026, 10, 14, tzinfo=UTC),
        created_at=datetime(2026, 10, 14, tzinfo=UTC),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"version": "2.0.0"}, {"version": "2.0.0", "product": None}])
async def test_create_release_uses_default_for_missing_or_null_product(
    payload: dict[str, object],
) -> None:
    uow = make_uow()
    product = Product(id=5, name="podcasts", is_default=True)
    release = make_release(product)
    repository = MagicMock()
    repository.create = AsyncMock(return_value=release)

    with (
        patch("src.modules.api.releases.ReleaseRepository", return_value=repository),
        patch(
            "src.modules.api.releases.get_default_product",
            new_callable=AsyncMock,
            return_value=ProductIdentity(id=5, name="podcasts"),
        ) as get_default,
        patch("src.modules.api.releases.ProductRepository") as product_repository,
        patch(
            "src.modules.api.releases.invalidate_release_cache",
            new_callable=AsyncMock,
        ),
    ):
        response = await create_release(ReleaseCreate.model_validate(payload), uow)

    assert response.product == "podcasts"
    assert repository.create.await_args.kwargs["value"]["product_id"] == 5
    get_default.assert_awaited_once_with()
    product_repository.assert_not_called()


@pytest.mark.asyncio
async def test_update_release_null_product_keeps_existing_product() -> None:
    uow = make_uow()
    product = Product(id=5, name="podcasts", is_default=True)
    release = make_release(product)
    repository = MagicMock()
    repository.get = AsyncMock(return_value=release)
    repository.update = AsyncMock()

    with (
        patch("src.modules.api.releases.ReleaseRepository", return_value=repository),
        patch("src.modules.api.releases.ProductRepository") as product_repository,
        patch(
            "src.modules.api.releases.invalidate_release_cache",
            new_callable=AsyncMock,
        ),
    ):
        response = await update_release(
            release_id=release.id,
            release_data=ReleaseUpdate(product=None, notes="updated"),
            uow=uow,
        )

    assert response.product == "podcasts"
    repository.update.assert_awaited_once_with(release, notes="updated")
    product_repository.assert_not_called()


@pytest.mark.asyncio
async def test_create_release_resolves_explicit_product_by_name() -> None:
    uow = make_uow()
    product = Product(id=8, name="docker", is_default=False)
    release = make_release(product)
    release.product_id = product.id
    release.product = product
    repository = MagicMock()
    repository.create = AsyncMock(return_value=release)
    product_repository = MagicMock()
    product_repository.get_by_name = AsyncMock(return_value=product)

    with (
        patch("src.modules.api.releases.ReleaseRepository", return_value=repository),
        patch(
            "src.modules.api.releases.ProductRepository",
            return_value=product_repository,
        ),
        patch(
            "src.modules.api.releases.get_default_product",
            new_callable=AsyncMock,
        ) as get_default,
        patch(
            "src.modules.api.releases.invalidate_release_cache",
            new_callable=AsyncMock,
        ),
    ):
        response = await create_release(
            ReleaseCreate(version="2.0.0", product="docker"),
            uow,
        )

    assert response.product == "docker"
    product_repository.get_by_name.assert_awaited_once_with("docker")
    assert repository.create.await_args.kwargs["value"]["product_id"] == 8
    get_default.assert_not_awaited()

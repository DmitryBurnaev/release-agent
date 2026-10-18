from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import Product
from src.modules.admin.views.products import ProductAdminView


def make_uow() -> tuple[MagicMock, MagicMock]:
    uow = MagicMock()
    uow.session = MagicMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=uow)
    context.__aexit__ = AsyncMock(return_value=None)
    return uow, context


@pytest.mark.asyncio
async def test_insert_default_product_switches_default_and_invalidates_cache() -> None:
    uow, context = make_uow()
    repository = MagicMock()
    repository.clear_default = AsyncMock()
    product = Product(id=2, name="podcasts", is_default=True)
    repository.create = AsyncMock(return_value=product)

    with (
        patch("src.modules.admin.views.products.SASessionUOW", return_value=context),
        patch("src.modules.admin.views.products.ProductRepository", return_value=repository),
        patch(
            "src.modules.admin.views.products.invalidate_product_cache",
            new_callable=AsyncMock,
        ) as invalidate,
    ):
        result = await ProductAdminView().insert_model(
            MagicMock(), {"name": "podcasts", "is_default": True}
        )

    assert result is product
    repository.clear_default.assert_awaited_once_with()
    repository.create.assert_awaited_once_with(value={"name": "podcasts", "is_default": True})
    assert uow.mark_for_commit.called
    invalidate.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_update_product_can_clear_default_without_switching_another() -> None:
    uow, context = make_uow()
    repository = MagicMock()
    product = Product(id=2, name="podcasts", is_default=True)
    repository.get = AsyncMock(return_value=product)
    repository.clear_default = AsyncMock()
    repository.update = AsyncMock()

    with (
        patch("src.modules.admin.views.products.SASessionUOW", return_value=context),
        patch("src.modules.admin.views.products.ProductRepository", return_value=repository),
        patch(
            "src.modules.admin.views.products.invalidate_product_cache",
            new_callable=AsyncMock,
        ) as invalidate,
    ):
        result = await ProductAdminView().update_model(
            MagicMock(), "2", {"name": "podcasts", "is_default": False}
        )

    assert result is product
    repository.clear_default.assert_not_awaited()
    repository.update.assert_awaited_once_with(product, name="podcasts", is_default=False)
    invalidate.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_update_default_product_can_rename_and_keep_default_flag() -> None:
    _, context = make_uow()
    repository = MagicMock()
    product = Product(id=2, name="default", is_default=True)
    repository.get = AsyncMock(return_value=product)
    repository.clear_default = AsyncMock()
    repository.update = AsyncMock()

    with (
        patch("src.modules.admin.views.products.SASessionUOW", return_value=context),
        patch("src.modules.admin.views.products.ProductRepository", return_value=repository),
        patch(
            "src.modules.admin.views.products.invalidate_product_cache",
            new_callable=AsyncMock,
        ),
    ):
        await ProductAdminView().update_model(
            MagicMock(), "2", {"name": "podcasts", "is_default": True}
        )

    repository.clear_default.assert_awaited_once_with(exclude_id=2)
    repository.update.assert_awaited_once_with(product, name="podcasts", is_default=True)


@pytest.mark.asyncio
async def test_failed_product_save_does_not_invalidate_cache() -> None:
    _, context = make_uow()
    repository = MagicMock()
    repository.clear_default = AsyncMock()
    repository.create = AsyncMock(side_effect=RuntimeError("save failed"))

    with (
        patch("src.modules.admin.views.products.SASessionUOW", return_value=context),
        patch("src.modules.admin.views.products.ProductRepository", return_value=repository),
        patch(
            "src.modules.admin.views.products.invalidate_product_cache",
            new_callable=AsyncMock,
        ) as invalidate,
        pytest.raises(RuntimeError, match="save failed"),
    ):
        await ProductAdminView().insert_model(MagicMock(), {"name": "podcasts", "is_default": True})

    invalidate.assert_not_awaited()
    assert context.__aexit__.await_args.args[0] is RuntimeError

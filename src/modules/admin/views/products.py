from typing import Any, cast

from starlette.requests import Request

from src.db.models import BaseModel, Product
from src.db.repositories import ProductRepository
from src.db.services import SASessionUOW
from src.modules.admin.views.base import BaseModelView
from src.services.cache import invalidate_product_cache
from src.utils import admin_get_link

__all__ = ("ProductAdminView",)


def _format_product_link(model: Any, _: Any) -> str:
    return admin_get_link(cast(BaseModel, model))


class ProductAdminView(BaseModelView, model=Product):
    """Manage products used to partition releases."""

    name = "Product"
    name_plural = "Products"
    icon = "fa-solid fa-cubes"
    column_list = (Product.id, Product.name, Product.is_default)
    column_details_list = (Product.id, Product.name, Product.is_default)
    form_columns = (Product.name, Product.is_default)
    column_labels = {
        Product.name: "Название",
        Product.is_default: "По умолчанию",
    }
    column_formatters = {Product.name: _format_product_link}

    async def insert_model(self, request: Request, data: dict[str, Any]) -> Product:
        async with SASessionUOW() as uow:
            repository = ProductRepository(session=uow.session)
            if data.get("is_default") is True:
                await repository.clear_default()
            product = await repository.create(value=data)
            uow.mark_for_commit()

        await invalidate_product_cache()
        return product

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, Any],
    ) -> Product:
        async with SASessionUOW() as uow:
            repository = ProductRepository(session=uow.session)
            product = await repository.get(int(pk))
            if data.get("is_default") is True:
                await repository.clear_default(exclude_id=product.id)
            await repository.update(product, **data)
            uow.mark_for_commit()

        await invalidate_product_cache()
        return product

    async def delete_model(self, request: Request, pk: Any) -> None:
        async with SASessionUOW() as uow:
            repository = ProductRepository(session=uow.session)
            product = await repository.get(int(pk))
            await repository.delete(product)
            uow.mark_for_commit()

        await invalidate_product_cache()

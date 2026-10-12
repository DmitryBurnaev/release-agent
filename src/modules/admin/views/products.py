import functools
from typing import Any, Callable, cast

from src.db.models import BaseModel, Product
from src.modules.admin.views.base import BaseModelView
from src.services.cache import invalidate_release_cache
from src.utils import admin_get_link

__all__ = ("ProductAdminView",)


def _format_product_link(model: Any, _: Any) -> str:
    return admin_get_link(cast(BaseModel, model))


def _invalidate_releases(func: Callable[..., Any]) -> Callable[..., Any]:
    """Invalidate product-specific release caches after product changes."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await func(*args, **kwargs)
        await invalidate_release_cache()
        return result

    return wrapper


class ProductAdminView(BaseModelView, model=Product):
    """Manage products used to partition releases."""

    name = "Product"
    name_plural = "Products"
    icon = "fa-solid fa-cubes"
    column_list = (Product.id, Product.name)
    column_details_list = (Product.id, Product.name)
    form_columns = (Product.name,)
    column_formatters = {Product.name: _format_product_link}
    update_model = _invalidate_releases(BaseModelView.update_model)
    delete_model = _invalidate_releases(BaseModelView.delete_model)

from dataclasses import dataclass
from typing import Any

from src.constants import CACHE_KEY_DEFAULT_PRODUCT
from src.db.repositories import ProductRepository
from src.db.services import SASessionUOW
from src.exceptions import InstanceLookupError
from src.services.cache import CacheProtocol, get_cache
from src.settings import get_app_settings


@dataclass(frozen=True)
class ProductIdentity:
    id: int
    name: str


async def get_default_product() -> ProductIdentity:
    """Resolve and cache the configured default product or the only product."""
    settings = get_app_settings()
    cache: CacheProtocol | None = get_cache() if settings.flags.api_cache_enabled else None

    if cache is not None:
        cached_product = _validate_cached_product(await cache.get(CACHE_KEY_DEFAULT_PRODUCT))
        if cached_product is not None:
            return cached_product

    async with SASessionUOW() as uow:
        product = await ProductRepository(session=uow.session).get_default_or_only()

    if product is None:
        raise InstanceLookupError("Default product not found")

    product_identity = ProductIdentity(id=product.id, name=product.name)
    if cache is not None:
        await cache.set(
            CACHE_KEY_DEFAULT_PRODUCT,
            {"id": product_identity.id, "name": product_identity.name},
        )
    return product_identity


def _validate_cached_product(value: Any) -> ProductIdentity | None:
    if not isinstance(value, dict):
        return None

    product_id = value.get("id")
    product_name = value.get("name")
    if (
        not isinstance(product_id, int)
        or isinstance(product_id, bool)
        or not isinstance(product_name, str)
        or not product_name
    ):
        return None

    return ProductIdentity(id=product_id, name=product_name)

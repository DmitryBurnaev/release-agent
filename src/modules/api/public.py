import logging
from typing import Any

from fastapi import APIRouter, Query

from src.constants import CACHE_KEY_ACTIVE_RELEASES_PAGE
from src.models import ReleasePublicResponse, PaginatedResponse
from src.modules.api import ErrorHandlingBaseRoute
from src.db.repositories import ReleaseRepository
from src.db.services import SASessionUOW
from src.services.cache import CacheProtocol, get_cache
from src.settings import get_app_settings

logger = logging.getLogger(__name__)
__all__ = ("public_router",)


public_router = APIRouter(
    prefix="/releases",
    tags=["public"],
    responses={404: {"description": "Not found"}},
    route_class=ErrorHandlingBaseRoute,
)


@public_router.get("/", response_model=PaginatedResponse[ReleasePublicResponse])
async def get_active_releases(
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return"),
) -> PaginatedResponse[ReleasePublicResponse]:
    """Get paginated list of active releases (public endpoint, no authentication required)"""
    logger.debug("[API] Public: Getting active releases (offset=%i, limit=%i)", offset, limit)
    settings = get_app_settings()
    cached_result: dict[str, Any] | None = None
    cache: CacheProtocol = get_cache()
    cache_key = CACHE_KEY_ACTIVE_RELEASES_PAGE.format(offset=offset, limit=limit)
    if settings.api_cache_enabled:
        cached_data = await cache.get(cache_key)
        cached_result = cached_data if cached_data and isinstance(cached_data, dict) else None

    if cached_result:
        response_result = PaginatedResponse[ReleasePublicResponse].model_validate(cached_result)
        logger.info(
            "[API] Public: Releases found in cache (offset=%i, limit=%i): %i releases | latest: %s",
            offset,
            limit,
            len(response_result.items),
            response_result.items[-1].version if response_result.items else "N/A",
        )
        return response_result

    logger.debug(
        "[API] Public: No releases in cache (offset=%i, limit=%i), getting from database",
        offset,
        limit,
    )
    # TODO: refactor to use service layer
    async with SASessionUOW() as uow:
        repo = ReleaseRepository(session=uow.session)
        releases, total = await repo.get_active_releases(offset=offset, limit=limit)
        response_result = PaginatedResponse[ReleasePublicResponse](
            items=[ReleasePublicResponse.model_validate(release) for release in releases],
            total=total,
            offset=offset,
            limit=limit,
        )
        await cache.set(cache_key, response_result.model_dump_json())
        logger.info(
            "[API] Public: Releases got from DB and cached: %i releases | total: %i | latest: %s",
            len(response_result.items),
            total,
            response_result.items[-1].version if response_result.items else "N/A",
        )

    return response_result

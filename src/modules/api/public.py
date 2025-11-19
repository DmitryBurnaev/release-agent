import logging
from typing import Any

from fastapi import APIRouter, Query

from src.constants import CACHE_KEY_ACTIVE_RELEASES_PAGE
from src.models import ReleasePublicResponse, PaginatedResponse
from src.modules.api import ErrorHandlingBaseRoute
from src.db.repositories import ReleaseRepository
from src.db.services import SASessionUOW
from src.services.cache import CacheProtocol, get_cache

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
    # TODO: enhance cache to use Redis or other cache backend
    cache: CacheProtocol = get_cache()
    cache_key = CACHE_KEY_ACTIVE_RELEASES_PAGE.format(offset=offset, limit=limit)
    cached_data = cache.get(cache_key)
    cached_result: dict[str, Any] | None = (
        cached_data if cached_data and isinstance(cached_data, dict) else None
    )

    if cached_result:
        logger.debug(
            "[API] Public: Releases found in cache (offset=%i, limit=%i): %i releases",
            offset,
            limit,
            len(cached_result.get("items", [])),
        )
        return PaginatedResponse[ReleasePublicResponse].model_validate(cached_result)

    logger.debug(
        "[API] Public: No releases in cache (offset=%i, limit=%i), getting from database",
        offset,
        limit,
    )
    # TODO: refactor to use service layer
    async with SASessionUOW() as uow:
        repo = ReleaseRepository(session=uow.session)
        releases, total = await repo.get_active_releases(offset=offset, limit=limit)
        response_releases = [ReleasePublicResponse.model_validate(release) for release in releases]
        cache.set(cache_key, response_releases)
        logger.info(
            "[API] Public: Releases cached: %i releases | total: %i",
            len(response_releases),
            total,
        )

    logger.info(
        "[API] Public: Releases asked (offset=%i, limit=%i): found %i releases | total: %i | latest: %s",
        offset,
        limit,
        len(response_releases),
        total,
        response_releases[-1].version if response_releases else "N/A",
    )
    response_result = PaginatedResponse[ReleasePublicResponse](
        items=response_releases,
        total=total,
        offset=offset,
        limit=limit,
    )
    return response_result

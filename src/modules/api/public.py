import logging
from typing import Any

from fastapi import APIRouter, Depends

from src.constants import CACHE_KEY_ACTIVE_RELEASES
from src.models import ReleaseResponse
from src.modules.api import ErrorHandlingBaseRoute
from src.db.repositories import ReleaseRepository
from src.db.services import SASessionUOW
from src.db.dependencies import get_uow_with_session
from src.services.cache import CacheProtocol, InMemoryCache

logger = logging.getLogger(__name__)
__all__ = ("public_router",)


public_router = APIRouter(
    prefix="/releases",
    tags=["public"],
    responses={404: {"description": "Not found"}},
    route_class=ErrorHandlingBaseRoute,
)


@public_router.get("/", response_model=list[ReleaseResponse])
async def get_active_releases(
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> list[ReleaseResponse]:
    """Get list of active releases (public endpoint, no authentication required)"""
    logger.debug("[API] Public: Getting active releases")
    # TODO: enhance cache to use Redis or other cache backend
    cache: CacheProtocol = InMemoryCache()
    _releases = cache.get(CACHE_KEY_ACTIVE_RELEASES)
    cached_releases: list[dict[str, Any]] = (
        _releases if _releases and isinstance(_releases, list) else []
    )
    response_result: list[ReleaseResponse] = []

    if cached_releases:
        logger.debug(
            "[API] Public: Releases found in cache: %i releases | latest: %s",
            len(cached_releases),
            cached_releases[-1].get("version"),
        )
        response_result = [ReleaseResponse.model_validate(_release) for _release in cached_releases]

    if not response_result:
        logger.debug("[API] Public: No releases in cache, getting from database")
        async with uow:
            repo = ReleaseRepository(session=uow.session)
            response_result = [
                ReleaseResponse.model_validate(db_release)
                for db_release in await repo.get_active_releases()
            ]
            cache_releases = [ReleaseResponse.model_dump(_release) for _release in response_result]
            cache.set(CACHE_KEY_ACTIVE_RELEASES, cache_releases)
            logger.info(
                "[API] Public: Releases cached: %i releases | latest: %s",
                len(cache_releases),
                cache_releases[-1].get("version"),
            )

    logger.info(
        "[API] Public: Releases asked: found %i releases (%s) | latest: %s",
        len(cache_releases),
        "cached" if cached_releases else "retrieved",
        response_result[-1].version if response_result else None,
    )
    return response_result

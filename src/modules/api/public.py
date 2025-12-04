import logging
import time
from typing import Any

from fastapi import APIRouter, Query, Request
from starlette.background import BackgroundTasks

from src.constants import CACHE_KEY_ACTIVE_RELEASES_PAGE
from src.db.clickhouse import ReleasesAnalyticsSchema
from src.models import ReleasePublicResponse, PaginatedResponse
from src.modules.api import ErrorHandlingBaseRoute
from src.db.repositories import ReleaseRepository
from src.db.services import SASessionUOW
from src.services.cache import CacheProtocol, get_cache
from src.services.analytics import AnalyticsService
from src.settings import get_app_settings
from src.settings.db import get_clickhouse_settings
from src.utils import utcnow

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
    request: Request,
    background_tasks: BackgroundTasks,
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return"),
    client_version: str | None = Query(None, description="Client version"),
    installation_id: str | None = Query(None, description="Installation ID"),
    is_corporate: bool | None = Query(None, description="Is corporate client"),
) -> PaginatedResponse[ReleasePublicResponse]:
    """Get paginated list of active releases (public endpoint, no authentication required)"""
    start_time = time.time()
    logger.debug("[API] Public: Getting active releases (offset=%i, limit=%i)", offset, limit)

    # Extract request metadata
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    settings = get_app_settings()
    cached_result: dict[str, Any] | None = None
    cache: CacheProtocol = get_cache()
    cache_key = CACHE_KEY_ACTIVE_RELEASES_PAGE.format(offset=offset, limit=limit)
    if settings.flags.api_cache_enabled:
        cached_data = await cache.get(cache_key)
        cached_result = cached_data if cached_data and isinstance(cached_data, dict) else None

    def get_latest_version(response_result: PaginatedResponse[ReleasePublicResponse]) -> str | None:
        return response_result.items[-1].version if response_result.items else None

    if cached_result:
        response_result = PaginatedResponse[ReleasePublicResponse].model_validate(cached_result)
        logger.info(
            "[API] Public: Releases found in cache (offset=%i, limit=%i): %i releases | latest: %s",
            offset,
            limit,
            len(response_result.items),
            get_latest_version(response_result) or "N/A",
        )
        response_status = 200
    else:
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
            await cache.set(cache_key, response_result.model_dump(mode="json"))
            logger.info(
                "[API] Public: Releases got from DB and cached: %i releases | total: %i | latest: %s",
                len(response_result.items),
                total,
                get_latest_version(response_result) or "N/A",
            )
        response_status = 200

    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000

    # Log request to analytics (non-blocking)
    analytics_request = ReleasesAnalyticsSchema(
        timestamp=utcnow(skip_tz=False),
        response_status=response_status,
        response_from_cache=bool(cached_result),
        client_version=client_version,
        latest_version=get_latest_version(response_result),
        installation_id=installation_id,
        is_corporate=is_corporate,
        response_time_ms=response_time_ms,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    analytics_service = AnalyticsService(clickhouse_settings=get_clickhouse_settings())
    background_tasks.add_task(analytics_service.log_request, analytics_request)

    return response_result

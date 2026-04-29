import logging
import time
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import ValidationError
from starlette.background import BackgroundTasks
from starlette.responses import PlainTextResponse

from src.constants import CACHE_KEY_ACTIVE_RELEASES_PAGE
from src.db.clickhouse import ReleasesAnalyticsSchema
from src.exceptions import InstanceLookupError
from src.models import LatestVersionResponse, ReleasePublicResponse, PaginatedResponse
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


class _LatestVersionFormat(StrEnum):
    JSON = "json"
    PLAIN = "plain"

    @classmethod
    def _missing_(cls, value: object) -> "_LatestVersionFormat | None":
        if isinstance(value, str):
            normalized_value = value.lower()
            for member in cls:
                if member.value == normalized_value:
                    return member

        return None


public_router = APIRouter(
    prefix="/releases",
    tags=["public"],
    responses={404: {"description": "Not found"}},
    route_class=ErrorHandlingBaseRoute,
)


@public_router.get("/latest", response_model=LatestVersionResponse)
async def get_latest_release_version(
    response_format: _LatestVersionFormat = Query(
        _LatestVersionFormat.JSON,
        alias="format",
        description="Response format",
    ),
) -> LatestVersionResponse | PlainTextResponse:
    """Get the latest active release version (public endpoint, no analytics tracking)."""
    offset = 0
    limit = 1
    cache_key = CACHE_KEY_ACTIVE_RELEASES_PAGE.format(offset=offset, limit=limit)
    cache: CacheProtocol = get_cache()
    response_result: PaginatedResponse[ReleasePublicResponse] | None = None

    settings = get_app_settings()
    if settings.flags.api_cache_enabled:
        response_result = _get_cached_release_page(await cache.get(cache_key))

    if response_result is None:
        logger.debug("[API] Public: Latest release not found in cache, getting from database")
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

    version = _get_latest_version(response_result)
    if version is None:
        raise InstanceLookupError("No active release found")

    if response_format == _LatestVersionFormat.PLAIN:
        return PlainTextResponse(version)

    return LatestVersionResponse(version=version)


@public_router.get("/", response_model=PaginatedResponse[ReleasePublicResponse])
async def get_active_releases(
    request: Request,
    background_tasks: BackgroundTasks,
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return"),
    current_version: str | None = Query(None, description="Current client version"),
    install_id: str | None = Query(None, description="Installation ID"),
    is_corporate: bool | None = Query(None, description="Indicates if the client is corporate"),
    is_internal: bool | None = Query(None, description="Indicates if the client is internal"),
) -> PaginatedResponse[ReleasePublicResponse]:
    """Get paginated list of active releases (public endpoint, no authentication required)"""
    start_time = time.time()
    logger.debug("[API] Public: Getting active releases (offset=%i, limit=%i)", offset, limit)

    settings = get_app_settings()
    cached_result: dict[str, Any] | None = None
    cache: CacheProtocol = get_cache()
    cache_key = CACHE_KEY_ACTIVE_RELEASES_PAGE.format(offset=offset, limit=limit)
    if settings.flags.api_cache_enabled:
        cached_data = await cache.get(cache_key)
        cached_result = cached_data if cached_data and isinstance(cached_data, dict) else None

    if cached_result:
        response_result = PaginatedResponse[ReleasePublicResponse].model_validate(cached_result)
        logger.info(
            "[API] Public: Releases found in cache (offset=%i, limit=%i): %i releases | latest: %s",
            offset,
            limit,
            len(response_result.items),
            _get_latest_version(response_result) or "N/A",
        )
        response_status = 200
    else:
        logger.debug(
            "[API] Public: No releases in cache (offset=%i, limit=%i), getting from database",
            offset,
            limit,
        )
        # TODO: cover with tests and refactor (use service layer instead)
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
                _get_latest_version(response_result) or "N/A",
            )
        response_status = 200

    # Log request to analytics (non-blocking)
    if settings.flags.api_analytics_enabled:
        logger.debug("[API] Public: Logging request to analytics")
        analytics_service = AnalyticsService(clickhouse_settings=get_clickhouse_settings())
        analytics_service.log_request_async(
            background_tasks=background_tasks,
            request=ReleasesAnalyticsSchema(
                timestamp=utcnow(skip_tz=False),
                client_version=current_version,
                client_install_id=install_id,
                client_is_corporate=is_corporate,
                client_is_internal=is_internal,
                client_ip_address=request.client.host if request.client else None,
                client_user_agent=request.headers.get("user-agent"),
                client_ref_url=request.headers.get("referer"),
                response_latest_version=_get_latest_version(response_result),
                response_status=response_status,
                response_time_ms=(time.time() - start_time) * 1000,
                response_from_cache=bool(cached_result),
            ),
        )
    else:
        logger.debug("[API] Public: Analytics disabled, skipping log request")

    return response_result


def _get_latest_version(response_result: PaginatedResponse[ReleasePublicResponse]) -> str | None:
    """Get latest release version from a paginated release response."""
    return response_result.items[0].version if response_result.items else None


def _get_cached_release_page(
    cached_data: Any,
) -> PaginatedResponse[ReleasePublicResponse] | None:
    """Validate cached release page payload and ignore unusable cache entries."""
    if not cached_data or not isinstance(cached_data, dict):
        return None

    try:
        return PaginatedResponse[ReleasePublicResponse].model_validate(cached_data)
    except ValidationError:
        logger.warning("[API] Public: Invalid active releases cache payload ignored")
        return None

import logging
from fastapi import APIRouter, Depends, status

from src.models import ReleaseCreate, ReleaseUpdate, ReleaseDetailsResponse, ReleaseResponse
from src.modules.api import ErrorHandlingBaseRoute
from src.db.repositories import ReleaseRepository
from src.db.services import SASessionUOW
from src.db.dependencies import get_uow_with_session
from src.services.cache import invalidate_release_cache
from src.utils import utcnow

__all__ = ("admin_router",)

logger = logging.getLogger(__name__)


admin_router = APIRouter(
    prefix="/releases",
    tags=["releases"],
    responses={404: {"description": "Not found"}},
    route_class=ErrorHandlingBaseRoute,
)


@admin_router.get("/", response_model=list[ReleaseResponse])
async def list_releases(
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> list[ReleaseResponse]:
    """Get list of all releases (admin endpoint, requires authentication)"""

    logger.debug("[API] Getting list of all releases")
    async with uow:
        repo = ReleaseRepository(session=uow.session)
        releases = await repo.all()
        return [ReleaseResponse.model_validate(release) for release in releases or []]


@admin_router.get("/{release_id}/", response_model=ReleaseDetailsResponse)
async def get_release(
    release_id: int,
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> ReleaseDetailsResponse:
    """Get release by ID (admin endpoint, requires authentication)"""

    logger.debug("[API] Getting release by ID: '%s'", release_id)
    async with uow:
        repo = ReleaseRepository(session=uow.session)
        release = await repo.get(release_id)

    return ReleaseDetailsResponse.model_validate(release)


@admin_router.post("/", response_model=ReleaseDetailsResponse, status_code=status.HTTP_201_CREATED)
async def create_release(
    release_data: ReleaseCreate,
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> ReleaseDetailsResponse:
    """Create a new release (admin endpoint, requires authentication)"""
    async with uow:
        repo = ReleaseRepository(session=uow.session)
        release_info = release_data.model_dump(exclude_unset=True)
        release_info.setdefault("is_active", False)
        # TODO: fix that! (default values should be provided in model)
        release_info.setdefault("notes", "")
        release_info.setdefault("url", "")
        release_info.setdefault("published_at", utcnow())
        release = await repo.create(value=release_info)
        uow.mark_for_commit()

    invalidate_release_cache()
    logger.info("[API] Release created: '%s'", release.version)
    return ReleaseDetailsResponse.model_validate(release)


@admin_router.put("/{release_id}/", response_model=ReleaseDetailsResponse)
async def update_release(
    release_id: int,
    release_data: ReleaseUpdate,
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> ReleaseDetailsResponse:
    """Update release by ID (admin endpoint, requires authentication)"""
    async with uow:
        repo = ReleaseRepository(session=uow.session)
        release = await repo.get(release_id)
        update_dict = release_data.model_dump(exclude_unset=True)
        await repo.update(release, **update_dict)
        uow.mark_for_commit()

    invalidate_release_cache()
    logger.info("[API] Release updated: '%s'", release)
    return ReleaseDetailsResponse.model_validate(release)


@admin_router.post("/{release_id}/activate/", response_model=ReleaseDetailsResponse)
async def activate_release(
    release_id: int,
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> ReleaseDetailsResponse:
    """Activate release by ID (admin endpoint, requires authentication)"""
    logger.debug("[API] Activating release by ID: '%s'", release_id)
    async with uow:
        repo = ReleaseRepository(session=uow.session)
        release = await repo.get(release_id)
        await repo.set_active([release_id], is_active=True)
        uow.mark_for_commit()

    invalidate_release_cache()
    logger.info("[API] Release activated: '%s'", release.version)
    return ReleaseDetailsResponse.model_validate(release)


@admin_router.post("/{release_id}/deactivate/", response_model=ReleaseDetailsResponse)
async def deactivate_release(
    release_id: int,
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> ReleaseDetailsResponse:
    """Deactivate release by ID (admin endpoint, requires authentication)"""
    logger.debug("[API] Deactivating release by ID: '%s'", release_id)
    async with uow:
        repo = ReleaseRepository(session=uow.session)
        release = await repo.get(release_id)
        await repo.set_active([release_id], is_active=False)
        uow.mark_for_commit()

    invalidate_release_cache()
    logger.info("[API] Release deactivated: '%s'", release.version)
    return ReleaseDetailsResponse.model_validate(release)


@admin_router.delete("/{release_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_release(
    release_id: int,
    uow: SASessionUOW = Depends(get_uow_with_session),
) -> None:
    """Delete release by ID (admin endpoint, requires authentication)"""
    logger.debug("[API] Deleting release by ID: '%s'", release_id)

    async with uow:
        repo = ReleaseRepository(session=uow.session)
        release = await repo.get(release_id)
        await repo.delete(release)
        uow.mark_for_commit()

    invalidate_release_cache()
    logger.info("[API] Release deleted: '%s'", release.version)
    return None

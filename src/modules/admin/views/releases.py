import logging
from typing import cast

from sqladmin import action
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

from src.db.repositories import ReleaseRepository
from src.db.services import SASessionUOW
from src.db.models import BaseModel, Release
from src.services.cache import invalidate_release_cache
from src.utils import admin_get_link
from src.modules.admin.views.base import BaseModelView

__all__ = ("ReleaseAdminView",)
logger = logging.getLogger(__name__)


class ReleaseAdminView(BaseModelView, model=Release):
    name = "Release"
    name_plural = "Releases"
    icon = "fa-solid fa-rocket"
    column_list = (Release.id, Release.version, Release.release_date, Release.is_active)
    form_columns = (
        Release.version,
        Release.notes,
        Release.url_link,
        Release.release_date,
        Release.is_active,
    )
    column_formatters = {
        Release.id: lambda model, a: admin_get_link(cast(BaseModel, model), target="details")
    }
    column_details_list = (
        Release.id,
        Release.version,
        Release.notes,
        Release.url_link,
        Release.release_date,
        Release.is_active,
        Release.created_at,
        Release.updated_at,
    )
    column_default_li = ()

    @action(
        name="deactivate",
        label="Deactivate",
        add_in_detail=False,
        add_in_list=True,
        confirmation_message="Are you sure you want to deactivate selected releases?",
    )
    async def deactivate_releases(self, request: Request) -> Response:
        """Deactivate releases by their IDs"""
        return await self._set_active(request, is_active=False)

    @action(
        name="activate",
        label="Activate",
        add_in_detail=True,
        add_in_list=True,
        confirmation_message="Are you sure you want to activate selected releases?",
    )
    async def activate_releases(self, request: Request) -> Response:
        """Activate releases by their IDs"""
        return await self._set_active(request, is_active=True)

    async def _set_active(self, request: Request, is_active: bool) -> Response:
        """Set active status for releases by their IDs"""
        release_ids: list[int] = [int(pk) for pk in request.query_params.get("pks", "").split(",")]
        if not release_ids:
            raise RuntimeError("No pks provided")

        logger.info(
            "[ADMIN] %s releases: %r",
            "Deactivating" if not is_active else "Activating",
            release_ids,
        )
        async with SASessionUOW() as uow:
            repo = ReleaseRepository(session=uow.session)
            await repo.set_active(release_ids, is_active=is_active)
            await uow.commit()

        invalidate_release_cache()
        return RedirectResponse(url=request.url_for("admin:list", identity=self.identity))

import logging
import datetime
from typing import cast, Any

from sqladmin import action
from sqlalchemy import Select, select, func
from wtforms import HiddenField
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

from src.db.repositories import ReleaseRepository
from src.db.services import SASessionUOW
from src.db.models import BaseModel, Release
from src.services.cache import invalidate_release_cache
from src.utils import admin_get_link
from src.modules.admin.views.base import BaseModelView
from src.modules.admin.utils import format_datetime, format_date

__all__ = ("ReleaseAdminView",)
logger = logging.getLogger(__name__)
type ReleaseSelectT = Select[tuple[Release]]


def _make_datetime_formatter(column_name: str) -> Any:
    """
    Create a formatter function for datetime columns.
    SQLAdmin expects Callable[[type, Column], Any] but passes (model_instance, column) at runtime.

    :param column_name: Name of the column to format
    :return: Formatter function compatible with SQLAdmin types
    """

    def formatter(value: Any, _: Any) -> str:
        model = cast(BaseModel, value)
        instance_value: datetime.datetime = getattr(model, column_name)
        return format_datetime(instance_value)

    return formatter


def _make_date_formatter(column_name: str) -> Any:
    """
    Create a formatter function for date columns.
    SQLAdmin expects Callable[[type, Column], Any] but passes (model_instance, column) at runtime.

    :param column_name: Name of the column to format
    :return: Formatter function compatible with SQLAdmin types
    """

    def formatter(value: Any, _: Any) -> str:
        model = cast(BaseModel, value)
        instance_value: datetime.datetime = getattr(model, column_name)
        return format_date(instance_value)

    return formatter


class ReleaseAdminView(BaseModelView, model=Release):
    name = "Release"
    name_plural = "Releases"
    icon = "fa-solid fa-rocket"
    create_template = "releases/release_create.html"
    edit_template = "releases/release_edit.html"
    details_template = "releases/release_details.html"
    column_list = (Release.id, Release.version, Release.published_at, Release.is_active)
    form_columns = (
        Release.version,
        Release.published_at,
        Release.is_active,
        Release.url,
        Release.notes,
    )
    column_labels = {
        Release.version: "Версия",
        Release.published_at: "Дата публикации",
        Release.is_active: "Активен",
        Release.url: "Ссылка на релиз",
        Release.created_at: "Создан",
        Release.updated_at: "Изменен",
    }
    column_formatters = {
        Release.id: lambda model, a: admin_get_link(cast(BaseModel, model), target="details"),
        Release.published_at: _make_date_formatter("published_at"),
        Release.created_at: _make_datetime_formatter("created_at"),
        Release.updated_at: _make_datetime_formatter("updated_at"),
    }
    column_formatters_detail = {
        Release.published_at: _make_date_formatter("published_at"),
        Release.created_at: _make_datetime_formatter("created_at"),
        Release.updated_at: _make_datetime_formatter("updated_at"),
    }
    column_details_list = (
        Release.id,
        Release.version,
        Release.is_active,
        Release.published_at,
        Release.created_at,
        Release.updated_at,
        Release.url,
    )
    column_default_li = ()
    form_overrides = dict(notes=HiddenField)
    _cached_query: ReleaseSelectT

    def list_query(self, request: Request) -> ReleaseSelectT:
        """Search licenses by requested filters"""
        request_active = request.query_params.get("active", "").lower() == "true"
        request_inactive = request.query_params.get("inactive", "").lower() == "true"
        query: ReleaseSelectT = super().list_query(request).order_by(Release.published_at.desc())
        if request_active:
            query = query.filter(Release.is_active.is_(True))
        elif request_inactive:
            query = query.filter(Release.is_active.is_(False))

        self._cached_query = query
        return query

    def count_query(self, request: Request) -> Select[tuple[int]]:
        """Calculates total number of releases (used for correct pagination)"""
        if hasattr(self, "_cached_query"):
            query = self._cached_query
        else:
            query = self.list_query(request)

        return select(func.count()).select_from(query.subquery())

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

        await invalidate_release_cache()
        return RedirectResponse(url=request.url_for("admin:list", identity=self.identity))

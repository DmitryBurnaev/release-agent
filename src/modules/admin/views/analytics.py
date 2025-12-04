from sqladmin import expose
from starlette.requests import Request
from starlette.responses import Response

from src.modules.admin.views.base import BaseAPPView
from src.settings import get_app_settings

__all__ = ("AnalyticsDashboardAdminView", "AnalyticsQueriesAdminView")


class AnalyticsDashboardAdminView(BaseAPPView):
    name = "Analytics Dashboard"
    icon = "fa-solid fa-chart-line"

    @expose("/analytics_dashboard", methods=["GET"])
    async def get_dashboard(self, request: Request) -> Response:
        settings = get_app_settings()
        base_url = settings.admin.base_url
        iframe_link = f"{base_url}/analytics/#dashboard"
        return await self.templates.TemplateResponse(
            request,
            name="analytics.html",
            context={"iframe_link": iframe_link},
        )


class AnalyticsQueriesAdminView(BaseAPPView):
    name = "Analytics Queries"
    icon = "fa-solid fa-pencil"

    @expose("/analytics_queries", methods=["GET"])
    async def get_queries(self, request: Request) -> Response:
        settings = get_app_settings()
        base_url = settings.admin.base_url
        iframe_link = f"{base_url}/analytics/#play"
        return await self.templates.TemplateResponse(
            request,
            name="analytics.html",
            context={"iframe_link": iframe_link},
        )

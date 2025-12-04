from sqladmin import expose
from starlette.requests import Request
from starlette.responses import Response

from src.modules.admin.views.base import BaseAPPView

__all__ = ("AnalyticsDashboardAdminView", "AnalyticsQueriesAdminView")


class AnalyticsDashboardAdminView(BaseAPPView):
    name = "Analytics Dashboard"
    icon = "fa-solid fa-chart-line"

    @expose("/analytics_dashboard", methods=["GET"])
    async def get_dashboard(self, request: Request) -> Response:
        return await self.templates.TemplateResponse(
            request,
            name="analytics_dashboard.html",
            context={},
        )


class AnalyticsQueriesAdminView(BaseAPPView):
    name = "Analytics Queries"
    icon = "fa-solid fa-pencil"

    @expose("/analytics_queries", methods=["GET"])
    async def get_queries(self, request: Request) -> Response:
        return await self.templates.TemplateResponse(
            request,
            name="analytics_queries.html",
            context={},
        )

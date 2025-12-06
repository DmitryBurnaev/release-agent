import logging

from sqladmin import expose
from starlette.requests import Request
from starlette.responses import Response

from src.modules.admin.views.base import BaseAPPView
from src.services.proxy import proxy
from src.settings import get_app_settings
from src.settings.db import get_clickhouse_settings

logger = logging.getLogger(__name__)
__all__ = ("AnalyticsDashboardAdminView",)


class AnalyticsDashboardAdminView(BaseAPPView):
    name = "Analytics"
    icon = "fa-solid fa-chart-line"

    @expose("/analytics", methods=["GET"])
    async def get_dashboard(self, request: Request) -> Response:
        settings = get_app_settings()
        ch_settings = get_clickhouse_settings()
        proxy_path = f"{settings.admin.base_url}/analytics-proxy"
        iframe_link = f"{proxy_path}/play?user={ch_settings.user}#"
        default_query = (
            f"SELECT * FROM {ch_settings.database}.{ch_settings.analytics_table_name} "
            f"ORDER BY timestamp DESC "
            f"LIMIT 10"
        )
        return await self.templates.TemplateResponse(
            request,
            name="analytics.html",
            context={
                "iframe_link": iframe_link,
                "default_query": default_query,
                "proxy_path": proxy_path,
            },
        )

    @expose(
        "/analytics-proxy/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    )
    async def proxy(self, request: Request) -> Response:
        """Proxy request to ClickHouse UI"""
        settings = get_app_settings()
        ch_settings = get_clickhouse_settings()
        return await proxy(
            request,
            proxy_path=f"{settings.admin.base_url}/analytics-proxy",
            proxy_url=ch_settings.http_url,
            proxy_host=ch_settings.host,
            proxy_port=ch_settings.port,
        )

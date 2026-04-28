import logging
from typing import Any

from sqladmin import expose
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.modules.admin.constants import build_default_analytics_query, build_stat_queries
from src.modules.admin.views.base import BaseAPPView
from src.services.analytics import AnalyticsService
from src.services.proxy import proxy
from src.settings import get_app_settings
from src.settings.db import get_clickhouse_settings

logger = logging.getLogger(__name__)
__all__ = (
    "AnalyticsQueryAdminView",
    "AnalyticsDashboardAdminView",
    "AnalyticsDashboardCHAdminView",
    "APIAnalyticsDashboardAdminView",
)


def _positive_int(value: str | None, default: int, *, max_value: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default

    if parsed < 1:
        return default

    return min(parsed, max_value)


def _group_by(value: str | None) -> str:
    return value if value in {"hour", "day"} else "hour"


def _default_analytics_query() -> str:
    ch = get_clickhouse_settings()
    return build_default_analytics_query(
        database=ch.database,
        table_name=ch.analytics_table_name,
        ignore_domain=ch.ignore_domain,
    )


def _stat_queries() -> list[dict[str, str]]:
    ch = get_clickhouse_settings()
    return build_stat_queries(
        database=ch.database,
        table_name=ch.analytics_table_name,
        ignore_domain=ch.ignore_domain,
    )


class AnalyticsQueryAdminView(BaseAPPView):
    name = "Analytics"
    icon = "fa-solid fa-chart-line"

    @expose("/analytics", methods=["GET"])
    async def get_analytics(self, request: Request) -> Response:
        settings = get_app_settings()
        ch = get_clickhouse_settings()
        proxy_path = f"{settings.admin.base_url}/analytics-proxy"
        iframe_link = f"{proxy_path}/play?user={ch.user}#"
        return await self.templates.TemplateResponse(
            request,
            name="analytics.html",
            context={
                "iframe_link": iframe_link,
                "default_query": _default_analytics_query(),
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
        ch = get_clickhouse_settings()
        return await proxy(
            request,
            proxy_path=f"{settings.admin.base_url}/analytics-proxy",
            proxy_url=ch.http_url,
            proxy_host=ch.host,
            proxy_port=ch.port,
        )


class AnalyticsDashboardAdminView(BaseAPPView):
    name = "Dashboard"
    icon = "fa-solid fa-chart-pie"

    @expose("/dashboard", methods=["GET"])
    async def get_dashboard(self, request: Request) -> Response:
        settings = get_app_settings()
        return await self.templates.TemplateResponse(
            request,
            name="analytics_charts.html",
            context={
                "base_url": settings.admin.base_url,
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


class AnalyticsDashboardCHAdminView(BaseAPPView):
    name = "Dashboard (CH)"
    icon = "fa-solid fa-chart-pie"

    @expose("/dashboard_ch", methods=["GET"])
    async def get_dashboard_ch(self, request: Request) -> Response:
        settings = get_app_settings()
        ch = get_clickhouse_settings()
        proxy_path = f"{settings.admin.base_url}/analytics-proxy"
        iframe_link = f"{proxy_path}/dashboard?user={ch.user}#"
        return await self.templates.TemplateResponse(
            request,
            name="analytics.html",
            context={
                "iframe_link": iframe_link,
                "default_query": _default_analytics_query(),
                "proxy_path": proxy_path,
                "stat_queries": _stat_queries(),
            },
        )


class APIAnalyticsDashboardAdminView(BaseAPPView):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        ch_settings = get_clickhouse_settings()
        self._analytics_service = AnalyticsService(ch_settings)

    @expose("/api/charts/requests-over-time", methods=["GET"])
    async def get_requests_over_time(self, request: Request) -> JSONResponse:
        """Get requests count over time for time series chart"""
        hours = _positive_int(request.query_params.get("hours"), 24, max_value=24 * 365)
        group_by = _group_by(request.query_params.get("group_by"))
        data = await self._analytics_service.get_requests_over_time(hours, group_by)
        return JSONResponse(data)

    @expose("/api/charts/by-client-version", methods=["GET"])
    async def get_by_client_version(self, request: Request) -> JSONResponse:
        """Get requests count by client version"""
        limit = _positive_int(request.query_params.get("limit"), 10, max_value=100)
        data = await self._analytics_service.get_by_client_version(limit)
        return JSONResponse(data)

    @expose("/api/charts/by-corporate", methods=["GET"])
    async def get_by_corporate(self, request: Request) -> JSONResponse:
        """Get requests count by corporate flag"""
        data = await self._analytics_service.get_by_corporate()
        return JSONResponse(data)

    @expose("/api/charts/by-response-version", methods=["GET"])
    async def get_by_response_version(self, request: Request) -> JSONResponse:
        """Get requests count by response latest version"""
        limit = _positive_int(request.query_params.get("limit"), 10, max_value=100)
        data = await self._analytics_service.get_by_response_version(limit)
        return JSONResponse(data)

    @expose("/api/charts/by-cache", methods=["GET"])
    async def get_by_cache(self, request: Request) -> JSONResponse:
        """Get requests count by cache flag"""
        data = await self._analytics_service.get_by_cache()
        return JSONResponse(data)

    @expose("/api/charts/top-ips", methods=["GET"])
    async def get_top_ips(self, request: Request) -> JSONResponse:
        """Get top IP addresses by request count"""
        limit = _positive_int(request.query_params.get("limit"), 10, max_value=100)
        data = await self._analytics_service.get_top_ips(limit)
        return JSONResponse(data)

    @expose("/api/charts/top-referers", methods=["GET"])
    async def get_top_referers(self, request: Request) -> JSONResponse:
        """Get top referer URLs by request count"""
        limit = _positive_int(request.query_params.get("limit"), 10, max_value=100)
        data = await self._analytics_service.get_top_referers(limit)
        return JSONResponse(data)

    @expose("/api/charts/by-status", methods=["GET"])
    async def get_by_status(self, request: Request) -> JSONResponse:
        """Get requests count by HTTP status code"""
        data = await self._analytics_service.get_by_status()
        return JSONResponse(data)

    @expose("/api/charts/response-time-distribution", methods=["GET"])
    async def get_response_time_distribution(self, request: Request) -> JSONResponse:
        """Get response time distribution histogram"""
        buckets = _positive_int(request.query_params.get("buckets"), 10, max_value=100)
        data = await self._analytics_service.get_response_time_distribution(buckets)
        return JSONResponse(data)

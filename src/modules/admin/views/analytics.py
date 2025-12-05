import logging

import httpx
from sqladmin import expose
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from src.constants import (
    PROXY_EXCLUDED_REQUEST_HEADERS,
    PROXY_EXCLUDED_RESPONSE_HEADERS,
)
from src.modules.admin.views.base import BaseAPPView
from src.settings import get_app_settings
from src.settings.db import get_clickhouse_settings

logger = logging.getLogger(__name__)
__all__ = ("AnalyticsDashboardAdminView", "AnalyticsQueriesAdminView")


class AnalyticsDashboardAdminView(BaseAPPView):
    name = "Analytics Dashboard"
    icon = "fa-solid fa-chart-line"

    @expose("/analytics_dashboard", methods=["GET"])
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
        base_url = settings.admin.base_url
        proxy_path = f"{base_url}/analytics-proxy"

        # Extract path parameter if present, otherwise use root
        ch_path = request.path_params.get("path")
        if ch_path is None:
            ch_path = "/"
        elif not ch_path.startswith("/"):
            ch_path = f"/{ch_path}"

        # Build target URL
        ch_settings = get_clickhouse_settings()
        ch_http_url = ch_settings.http_url
        target_url = f"{ch_http_url}{ch_path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Prepare headers for proxying
        headers: dict[str, str] = {}
        for key, value in request.headers.items():
            if key.lower() not in PROXY_EXCLUDED_REQUEST_HEADERS:
                headers[key] = value

        # Update Host header to target
        headers["Host"] = f"{ch_settings.host}:{ch_settings.port}"

        # Get request body if present
        body: bytes | None = None
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 0:
            body = await request.body()

        try:
            # Make request to ClickHouse
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    follow_redirects=False,
                )

                # Prepare response headers
                response_headers: dict[str, str] = {}
                for key, value in response.headers.items():
                    if key.lower() not in PROXY_EXCLUDED_RESPONSE_HEADERS:
                        response_headers[key] = value

                # Handle redirects
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location", "")
                    if location.startswith(ch_http_url):
                        # Rewrite redirect location to use proxy path
                        location = location.replace(ch_http_url, proxy_path)
                        response_headers["location"] = location

                # Create streaming response for large content
                if response.headers.get("content-type", "").startswith("text/"):
                    # For text content, read all at once
                    content = response.content
                    return Response(
                        content=content,
                        status_code=response.status_code,
                        headers=response_headers,
                    )
                else:
                    # For binary content, stream it
                    return StreamingResponse(
                        response.iter_bytes(),
                        status_code=response.status_code,
                        headers=response_headers,
                        media_type=response.headers.get("content-type"),
                    )

        except httpx.TimeoutException:
            logger.error("[CH-Proxy] Timeout connecting to ClickHouse UI")
            return Response(
                content=b"ClickHouse UI timeout",
                status_code=503,
                headers={"content-type": "text/plain"},
            )
        except httpx.ConnectError as e:
            logger.error("[CH-Proxy] Failed to connect to ClickHouse UI: %r", e)
            return Response(
                content=b"ClickHouse UI unavailable",
                status_code=503,
                headers={"content-type": "text/plain"},
            )
        except Exception as e:
            logger.error("[CH-Proxy] Unexpected error proxying to ClickHouse UI: %r", e)
            return Response(
                content=b"Internal proxy error",
                status_code=500,
                headers={"content-type": "text/plain"},
            )


class AnalyticsQueriesAdminView(BaseAPPView):
    name = "Analytics Queries"
    icon = "fa-solid fa-pencil"

    @expose("/analytics_queries", methods=["GET"])
    async def get_queries(self, request: Request) -> Response:
        iframe_link = "/analytics/#play"
        return await self.templates.TemplateResponse(
            request,
            name="analytics.html",
            context={"iframe_link": iframe_link},
        )

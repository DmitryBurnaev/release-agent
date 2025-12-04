import logging
import urllib.parse
from typing import Any, TYPE_CHECKING, cast

import httpx
from jinja2 import FileSystemLoader
from sqladmin import Admin, BaseView, ModelView
from sqladmin.authentication import login_required
from starlette.datastructures import FormData, URL
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, StreamingResponse

from src.constants import (
    APP_DIR,
    PROXY_EXCLUDED_REQUEST_HEADERS,
    PROXY_EXCLUDED_RESPONSE_HEADERS,
)
from src.db import session as db_session
from src.db.services import SASessionUOW
from src.modules.admin.auth import AdminAuth
from src.modules.admin.utils import get_current_error_alert
from src.modules.admin.views import (
    BaseAPPView,
    BaseModelView,
    UserAdminView,
    TokenAdminView,
    ReleaseAdminView,
)
from src.modules.admin.views.analytics import (
    AnalyticsDashboardAdminView,
    AnalyticsQueriesAdminView,
)
from src.services.counters import AdminCounter
from src.settings import get_app_settings
from src.settings.db import get_clickhouse_settings

if TYPE_CHECKING:
    from src.main import ReleaseAgentAPP
    from src.db.models import BaseModel

ADMIN_VIEWS: tuple[type[BaseView], ...] = (
    UserAdminView,
    TokenAdminView,
    ReleaseAdminView,
    AnalyticsDashboardAdminView,
    AnalyticsQueriesAdminView,
)

logger = logging.getLogger(__name__)


class AdminApp(Admin):
    """License-specific admin class."""

    custom_templates_dir = "modules/admin/templates"
    app: "ReleaseAgentAPP"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._init_jinja_templates()
        self._views: list[BaseModelView | BaseAPPView] = []  # type: ignore
        self._register_views()
        self._register_proxy_route()

    @property
    def _clickhouse_http_url(self) -> str:
        """Get ClickHouse HTTP URL from settings"""
        ch_settings = get_clickhouse_settings()
        return ch_settings.http_url

    @login_required
    async def index(self, request: Request) -> Response:
        """Index route which can be overridden to create dashboards."""
        settings = get_app_settings()
        logger.info(f"[{request.method}] Admin counter: debug mode '%s'", settings.flags.debug_mode)
        async with SASessionUOW() as uow:
            dashboard_stat = await AdminCounter().get_stat(session=uow.session)

        def get_releases_url(qs: dict[str, str | list[str]] | None = None) -> str:
            """Helper function to generate URL with query parameters"""
            list_admin_url = f"{settings.admin.base_url}/release/list"
            if qs:
                qs_string = urllib.parse.urlencode(qs)
                list_admin_url += f"?{qs_string}"

            return list_admin_url

        context = {
            "links": {
                "total": get_releases_url(),
                "active": get_releases_url({"active": "true"}),
                "inactive": get_releases_url({"inactive": "true"}),
            },
            "counts": {
                "total": dashboard_stat.total_releases,
                "active": dashboard_stat.active_releases,
                "inactive": dashboard_stat.inactive_releases,
            },
        }
        return await self.templates.TemplateResponse(request, "dashboard.html", context=context)

    @login_required
    async def create(self, request: Request) -> Response:
        response: Response = await super().create(request)
        if request.method == "GET":
            return response

        # ==== prepare custom logic ====
        identity = request.path_params["identity"]
        model_view: "BaseModelView" = cast("BaseModelView", self._find_model_view(identity))
        if model_view.custom_post_create:
            object_id = int(response.headers["location"])
            response = await model_view.handle_post_create(request, object_id)
        # ====

        return response

    def get_save_redirect_url(
        self,
        request: Request,
        form: FormData,
        model_view: ModelView,
        obj: "BaseModel",
    ) -> str | URL:
        """
        Make more flexable getting redirect URL after saving model instance
        Allows fetching created instance's ID from formed redirect response (location header)
        We have to do this to avoid overriding whole `create` method of this class
        """

        redirect_url: str | URL
        if isinstance(model_view, BaseModelView) and model_view.custom_post_create:
            # required for getting instance ID after base creation's method finished
            redirect_url = str(obj.id)
        else:
            redirect_url = super().get_save_redirect_url(request, form, model_view, obj)

        return redirect_url

    def _init_jinja_templates(self) -> None:
        """
        Init jinja templates.
        Note: we have to insert loader in the start of list in order to override default templates
        """
        templates_dir = APP_DIR / self.custom_templates_dir
        self.templates.env.loader.loaders.insert(0, FileSystemLoader(templates_dir))  # type: ignore
        self.templates.env.globals["error_alert"] = get_current_error_alert

    def _register_views(self) -> None:
        for view in ADMIN_VIEWS:
            self.add_view(view)

        for view_instance in self._views:
            view_instance.app = self.app

    def _register_proxy_route(self) -> None:
        """Register proxy route for ClickHouse UI"""
        settings = get_app_settings()
        base_url = settings.admin.base_url
        proxy_path = f"{base_url}/analytics"

        async def proxy_handler(request: Request) -> Response:
            """Handler for ClickHouse UI proxy requests"""
            # Authenticate user first
            auth_backend = self.authentication_backend
            if not await auth_backend.authenticate(request):
                return RedirectResponse(url=f"{base_url}/login", status_code=302)

            # Extract path parameter if present, otherwise use root
            ch_path = request.path_params.get("path")
            if ch_path is None:
                ch_path = "/"
            elif not ch_path.startswith("/"):
                ch_path = f"/{ch_path}"

            # Proxy the request
            return await self._proxy_clickhouse_request(request, proxy_path, ch_path)

        # Register route for all methods and paths
        self.app.add_route(
            f"{proxy_path}/{{path:path}}",
            proxy_handler,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        )
        # Also register root path
        self.app.add_route(
            proxy_path,
            proxy_handler,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        )
        self.app.add_route(
            f"{proxy_path}/",
            proxy_handler,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        )

    async def _proxy_clickhouse_request(
        self, request: Request, proxy_path: str, ch_path: str
    ) -> Response:
        """Proxy request to ClickHouse UI"""
        # Build target URL
        ch_http_url = self._clickhouse_http_url
        target_url = f"{ch_http_url}{ch_path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Prepare headers for proxying
        headers: dict[str, str] = {}
        for key, value in request.headers.items():
            if key.lower() not in PROXY_EXCLUDED_REQUEST_HEADERS:
                headers[key] = value

        # Update Host header to target
        ch_settings = get_clickhouse_settings()
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
                    ch_http_url = self._clickhouse_http_url
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


def make_admin(app: "ReleaseAgentAPP") -> Admin:
    """Create a simple admin application"""
    return AdminApp(
        app,
        base_url=app.settings.admin.base_url,
        title=app.settings.admin.title,
        session_maker=db_session.get_session_factory(),
        authentication_backend=AdminAuth(
            secret_key=app.settings.app_secret_key.get_secret_value(),
            settings=app.settings,
        ),
    )

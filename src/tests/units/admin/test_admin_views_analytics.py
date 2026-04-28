from types import SimpleNamespace
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from src.modules.admin.views.analytics import (
    APIAnalyticsDashboardAdminView,
    AnalyticsDashboardAdminView,
    AnalyticsDashboardCHAdminView,
    AnalyticsQueryAdminView,
)
from src.settings import AppSettings
from src.settings.db import ClickHouseSettings
from src.settings.log import LogSettings


@pytest.fixture
def app_settings_test() -> AppSettings:
    return AppSettings(
        app_secret_key=SecretStr("example-UStLb8mds9K"),
        log=LogSettings(format="[%(levelname)s] %(message)s"),
    )


@pytest.fixture
def app_settings() -> SimpleNamespace:
    return SimpleNamespace(admin=SimpleNamespace(base_url="/admin"))


@pytest.fixture
def clickhouse_settings() -> ClickHouseSettings:
    return ClickHouseSettings(
        host="clickhouse",
        port=8123,
        user="analytics_user",
        password=SecretStr("secret"),
        database="analytics_db",
        analytics_table_name="analytics_events",
        ignore_domain="Example.COM",
    )


@pytest.fixture
def analytics_settings(
    app_settings: SimpleNamespace,
    clickhouse_settings: ClickHouseSettings,
) -> Generator[None, Any, None]:
    with (
        patch("src.modules.admin.views.analytics.get_app_settings", return_value=app_settings),
        patch(
            "src.modules.admin.views.analytics.get_clickhouse_settings",
            return_value=clickhouse_settings,
        ),
    ):
        yield


def _mock_view_response(view: Any) -> AsyncMock:
    template_response = AsyncMock(return_value=MagicMock())
    view.templates = MagicMock()
    view.templates.TemplateResponse = template_response
    return template_response


@pytest.mark.asyncio
async def test_analytics_query_context_uses_settings(
    analytics_settings: None,
    mock_request: MagicMock,
) -> None:
    view = AnalyticsQueryAdminView()
    template_response = _mock_view_response(view)

    await view.get_analytics(mock_request)

    template_response.assert_awaited_once()
    _, kwargs = template_response.call_args
    assert kwargs["name"] == "analytics.html"

    context = kwargs["context"]
    assert context["iframe_link"] == "/admin/analytics-proxy/play?user=analytics_user#"
    assert context["proxy_path"] == "/admin/analytics-proxy"
    assert "`analytics_db`.`analytics_events`" in context["default_query"]
    assert "'example.com'" in context["default_query"]
    assert "releases.release_requests" not in context["default_query"]


@pytest.mark.asyncio
async def test_clickhouse_dashboard_context_includes_stat_queries(
    analytics_settings: None,
    mock_request: MagicMock,
) -> None:
    view = AnalyticsDashboardCHAdminView()
    template_response = _mock_view_response(view)

    await view.get_dashboard_ch(mock_request)

    _, kwargs = template_response.call_args
    context = kwargs["context"]
    assert context["iframe_link"] == "/admin/analytics-proxy/dashboard?user=analytics_user#"
    assert context["proxy_path"] == "/admin/analytics-proxy"

    stat_queries = context["stat_queries"]
    assert [query["title"] for query in stat_queries] == [
        "Unique Installations",
        "Unique Clients",
    ]
    assert all("`analytics_db`.`analytics_events`" in query["query"] for query in stat_queries)
    assert all("'example.com'" in query["query"] for query in stat_queries)
    assert all("releases.release_requests" not in query["query"] for query in stat_queries)


@pytest.mark.asyncio
async def test_internal_dashboard_context_uses_admin_base_url(
    analytics_settings: None,
    mock_request: MagicMock,
) -> None:
    view = AnalyticsDashboardAdminView()
    template_response = _mock_view_response(view)

    await view.get_dashboard(mock_request)

    _, kwargs = template_response.call_args
    assert kwargs["name"] == "analytics_charts.html"
    assert kwargs["context"] == {"base_url": "/admin"}


@pytest.mark.asyncio
async def test_chart_api_normalizes_request_parameters(
    analytics_settings: None,
) -> None:
    view = APIAnalyticsDashboardAdminView()
    service = MagicMock()
    service.get_requests_over_time = AsyncMock(return_value=[])
    service.get_top_ips = AsyncMock(return_value=[])
    view._analytics_service = service

    bad_time_request = MagicMock()
    bad_time_request.query_params = {"hours": "oops", "group_by": "minute"}
    await view.get_requests_over_time(bad_time_request)

    large_limit_request = MagicMock()
    large_limit_request.query_params = {"limit": "500"}
    await view.get_top_ips(large_limit_request)

    service.get_requests_over_time.assert_awaited_once_with(24, "hour")
    service.get_top_ips.assert_awaited_once_with(100)


def test_chart_api_view_is_hidden_from_admin_menu(
    analytics_settings: None,
    mock_request: MagicMock,
) -> None:
    view = APIAnalyticsDashboardAdminView()

    assert view.is_visible(mock_request) is False

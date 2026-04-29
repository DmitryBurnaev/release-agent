from typing import Generator, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.background import BackgroundTasks

from src.db.clickhouse import ReleasesAnalyticsSchema


def make_latest_cache_payload(version: str = "2026.3.4") -> dict[str, Any]:
    return {
        "items": [
            {
                "version": version,
                "notes": "## Latest",
                "url": None,
                "published_at": "2026-03-04T12:00:00",
            }
        ],
        "total": 1,
        "offset": 0,
        "limit": 1,
    }


@pytest.fixture(autouse=True)
def mock_log_analytics() -> Generator[MagicMock, None, None]:
    with patch("src.services.analytics.AnalyticsService.log_request_async") as mock_log:
        yield mock_log


@pytest.fixture(autouse=True)
def mock_cached_releases() -> Generator[MagicMock, None, None]:
    with patch("src.db.repositories.ReleaseRepository.get_active_releases") as mock_cache:
        mock_cache.return_value = (
            [
                {
                    "version": "2025.12.100",
                    "notes": "## Nothing here?",
                    "url": "https://test.example.com/t2",
                    "published_at": "2025-12-12T12:00:00",
                },
                {
                    "version": "2025.12.99",
                    "notes": "## What's new?",
                    "url": "https://test.example.com/t1",
                    "published_at": "2025-12-01T12:00:00",
                },
            ],
            1,
        )
        yield mock_cache


@pytest.fixture
def mock_release_cache() -> Generator[MagicMock, None, None]:
    with patch("src.modules.api.public.get_cache") as mock_get_cache:
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        mock_get_cache.return_value = cache
        yield cache


class TestPublicReleasesAPI:
    """Test public releases API endpoint with analytics logging"""

    def test_get_active_releases_without_auth(self, client: TestClient) -> None:
        """Test that public endpoint works without authentication"""
        response = client.get("/public/releases?offset=0&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data

    def test_get_active_releases_with_analytics_params(self, client: TestClient) -> None:
        """Test endpoint with analytics query parameters"""
        response = client.get(
            "/public/releases",
            params={
                "current_version": "1.0.0",
                "install_id": "test123",
                "is_corporate": True,
                "is_internal": True,
                "limit": 10,
                "offset": 0,
            },
            headers={
                "user-agent": "test_user_agent",
                "referer": "test_ref_url",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_analytics_service_called_on_request(
        self,
        mock_log_analytics: MagicMock,
        client: TestClient,
    ) -> None:
        """Test that analytics service log_request is called"""
        response = client.get(
            "/public/releases",
            params={
                "current_version": "1.0.0",
                "install_id": "test123",
                "is_corporate": True,
                "is_internal": True,
                "limit": 10,
                "offset": 0,
            },
            headers={
                "user-agent": "test_user_agent",
                "referer": "test_ref_url",
            },
        )
        assert response.status_code == 200

        # Verify analytics service was called
        mock_log_analytics.assert_called_once()

        # Verify call arguments
        call_args = mock_log_analytics.call_args
        assert call_args is not None
        kwargs: dict[str, Any] = call_args.kwargs  # type:ignore
        background_tasks = kwargs.pop("background_tasks")
        assert isinstance(background_tasks, BackgroundTasks)

        request: ReleasesAnalyticsSchema = kwargs.pop("request")
        assert isinstance(request, ReleasesAnalyticsSchema)

        assert request.client_version == "1.0.0"
        assert request.client_install_id == "test123"
        assert request.client_is_corporate is True
        assert request.client_is_internal is True
        assert request.client_ip_address is not None
        assert request.client_user_agent == "test_user_agent"
        assert request.client_ref_url == "test_ref_url"
        assert request.response_latest_version == "2025.12.100"
        assert request.response_status == 200
        assert request.response_time_ms is not None
        assert isinstance(request.response_time_ms, (int, float))

    def test_analytics_service_called_with_optional_params(
        self,
        mock_log_analytics: MagicMock,
        client: TestClient,
    ) -> None:
        """Test analytics service with optional parameters"""
        response = client.get("/public/releases?offset=0&limit=10")
        assert response.status_code == 200

        # Verify analytics service was called
        mock_log_analytics.assert_called_once()
        # Verify call arguments
        call_args = mock_log_analytics.call_args
        assert call_args is not None
        kwargs: dict[str, Any] = call_args.kwargs  # type:ignore

        request: ReleasesAnalyticsSchema = kwargs.pop("request")
        assert isinstance(request, ReleasesAnalyticsSchema)

        assert request.client_version is None
        assert request.client_install_id is None
        assert request.client_is_corporate is None

    def test_get_latest_version_json_by_default(
        self,
        mock_release_cache: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint returns JSON by default"""
        mock_release_cache.get.return_value = make_latest_cache_payload("2026.3.4")

        response = client.get("/public/releases/latest")

        assert response.status_code == 200
        assert response.json() == {"version": "2026.3.4"}
        assert response.headers["content-type"] == "application/json"

    def test_get_latest_version_plain(
        self,
        mock_release_cache: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint can return a plain text response"""
        mock_release_cache.get.return_value = make_latest_cache_payload("2026.3.4")

        response = client.get("/public/releases/latest?format=plain")

        assert response.status_code == 200
        assert response.text == "2026.3.4"
        assert response.headers["content-type"].startswith("text/plain")

    def test_get_latest_version_format_is_case_insensitive(
        self,
        mock_release_cache: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint accepts uppercase format values"""
        mock_release_cache.get.return_value = make_latest_cache_payload("2026.3.4")

        response = client.get("/public/releases/latest?format=JSON")

        assert response.status_code == 200
        assert response.json() == {"version": "2026.3.4"}

    def test_get_latest_version_uses_page_one_cache(
        self,
        mock_release_cache: MagicMock,
        mock_cached_releases: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint reads the active releases page cache first"""
        mock_release_cache.get.return_value = make_latest_cache_payload("2026.3.4")

        response = client.get("/public/releases/latest")

        assert response.status_code == 200
        mock_release_cache.get.assert_awaited_once_with("active_releases_page_0_1")
        mock_release_cache.set.assert_not_awaited()
        mock_cached_releases.assert_not_awaited()

    def test_get_latest_version_falls_back_to_database_on_cache_miss(
        self,
        mock_release_cache: MagicMock,
        mock_cached_releases: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint queries DB and caches the page on cache miss"""
        mock_release_cache.get.return_value = None

        response = client.get("/public/releases/latest")

        assert response.status_code == 200
        assert response.json() == {"version": "2025.12.100"}
        mock_cached_releases.assert_awaited_once_with(offset=0, limit=1)
        mock_release_cache.set.assert_awaited_once()
        cache_key, cache_payload = mock_release_cache.set.await_args.args
        assert cache_key == "active_releases_page_0_1"
        assert cache_payload["items"][0]["version"] == "2025.12.100"
        assert cache_payload["offset"] == 0
        assert cache_payload["limit"] == 1

    def test_get_latest_version_falls_back_to_database_on_invalid_cache(
        self,
        mock_release_cache: MagicMock,
        mock_cached_releases: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint ignores invalid cached payloads"""
        mock_release_cache.get.return_value = {"items": "invalid"}

        response = client.get("/public/releases/latest")

        assert response.status_code == 200
        assert response.json() == {"version": "2025.12.100"}
        mock_cached_releases.assert_awaited_once_with(offset=0, limit=1)
        mock_release_cache.set.assert_awaited_once()

    def test_get_latest_version_does_not_log_analytics(
        self,
        mock_log_analytics: MagicMock,
        mock_release_cache: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint does not log ClickHouse analytics"""
        mock_release_cache.get.return_value = make_latest_cache_payload("2026.3.4")

        response = client.get("/public/releases/latest")

        assert response.status_code == 200
        mock_log_analytics.assert_not_called()

    def test_get_latest_version_returns_404_without_active_releases(
        self,
        mock_release_cache: MagicMock,
        mock_cached_releases: MagicMock,
        client: TestClient,
    ) -> None:
        """Test latest version endpoint returns 404 when there are no active releases"""
        mock_release_cache.get.return_value = None
        mock_cached_releases.return_value = ([], 0)

        response = client.get("/public/releases/latest")

        assert response.status_code == 404
        assert response.json()["detail"] == "No active release found"

    def test_get_latest_version_rejects_invalid_format(self, client: TestClient) -> None:
        """Test latest version endpoint rejects unsupported response formats"""
        response = client.get("/public/releases/latest?format=xml")

        assert response.status_code == 422

    def test_latest_version_format_is_openapi_enum(self, client: TestClient) -> None:
        """Test latest version response format is documented as an enum"""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        parameters = schema["paths"]["/public/releases/latest"]["get"]["parameters"]
        format_parameter = next(param for param in parameters if param["name"] == "format")
        format_schema = format_parameter["schema"]

        if "$ref" in format_schema:
            enum_schema = schema["components"]["schemas"][format_schema["$ref"].rsplit("/", 1)[1]]
        else:
            enum_reference = format_schema["allOf"][0]["$ref"]
            enum_schema = schema["components"]["schemas"][enum_reference.rsplit("/", 1)[1]]

        assert enum_schema["type"] == "string"
        assert set(enum_schema["enum"]) == {"json", "plain"}

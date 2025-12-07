from typing import Generator, Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.background import BackgroundTasks

from src.db.clickhouse import ReleasesAnalyticsSchema


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
                    "notes": "## What's new?",
                    "url": "https://test.example.com",
                    "published_at": "2025-12-01T12:00:00",
                },
            ],
            1,
        )
        yield mock_cache


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

from typing import Generator
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from src.services.analytics import AnalyticsService
from src.db.clickhouse import ReleasesAnalyticsSchema


@pytest.fixture
def mock_analytics_service() -> Generator[MagicMock, None, None]:
    """Mock analytics service for testing"""
    mock_service = MagicMock(spec=AnalyticsService)
    mock_service.log_request = MagicMock()
    with pytest.MonkeyPatch().context() as m:
        m.setattr("src.modules.api.public.get_analytics_service", lambda: mock_service)
        yield mock_service


class TestPublicReleasesAPI:
    """Test public releases API endpoint with analytics logging"""

    def test_get_active_releases_without_auth(self, test_app) -> None:
        """Test that public endpoint works without authentication"""
        with TestClient(test_app) as client:
            response = client.get("/public/releases?offset=0&limit=10")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "offset" in data
            assert "limit" in data

    def test_get_active_releases_with_analytics_params(self, test_app) -> None:
        """Test endpoint with analytics query parameters"""
        with TestClient(test_app) as client:
            response = client.get(
                "/public/releases?offset=0&limit=10&client_version=1.0.0&installation_id=test123&is_corporate=true",
            )
            assert response.status_code == 200
            data = response.json()
            assert "items" in data

    def test_analytics_service_called_on_request(
        self,
        mock_analytics_service: MagicMock,
        test_app,
    ) -> None:
        """Test that analytics service log_request is called"""
        with TestClient(test_app) as client:
            response = client.get(
                "/public/releases?offset=0&limit=10&client_version=1.0.0&installation_id=test123&is_corporate=true",
            )
            assert response.status_code == 200

            # Verify analytics service was called
            mock_analytics_service.log_request.assert_called_once()

            # Verify call arguments
            call_args = mock_analytics_service.log_request.call_args
            assert call_args is not None
            args = call_args.args
            assert len(args) == 1
            assert isinstance(args[0], ReleasesAnalyticsSchema)

            request = args[0]
            assert request.request_path == "/public/releases"
            assert request.request_method == "GET"
            assert request.response_status == 200
            assert request.client_version == "1.0.0"
            assert request.installation_id == "test123"
            assert request.is_corporate is True
            assert request.response_time_ms is not None
            assert isinstance(request.response_time_ms, (int, float))

    def test_analytics_service_called_with_optional_params(
        self,
        mock_analytics_service: MagicMock,
        test_app,
    ) -> None:
        """Test analytics service with optional parameters"""
        with TestClient(test_app) as client:
            response = client.get("/public/releases?offset=0&limit=10")
            assert response.status_code == 200

            # Verify analytics service was called
            mock_analytics_service.log_request.assert_called_once()

            # Verify call arguments with None optional params
            call_args = mock_analytics_service.log_request.call_args
            assert call_args is not None
            args = call_args.args
            assert len(args) == 1
            assert isinstance(args[0], ReleasesAnalyticsSchema)

            request = args[0]
            assert request.client_version is None
            assert request.installation_id is None
            assert request.is_corporate is None

from datetime import datetime

from starlette.testclient import TestClient

from src.main import ReleaseAgentAPP


class TestSystemAPI:
    def test_public_health_check_requires_no_token(self, test_app: ReleaseAgentAPP) -> None:
        with TestClient(test_app) as client:
            response = client.get("/health/")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            assert client.get("/api/system/health/").status_code == 401

    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/api/system/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert isinstance(datetime.fromisoformat(data["timestamp"]), datetime)

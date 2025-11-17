from datetime import datetime

from starlette.testclient import TestClient


class TestSystemAPI:
    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/api/system/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert isinstance(datetime.fromisoformat(data["timestamp"]), datetime)

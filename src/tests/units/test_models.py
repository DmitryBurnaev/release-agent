from datetime import datetime

from src.models import HealthCheck


class TestHealthCheck:
    def test_health_check_creation(self) -> None:
        check = HealthCheck(status="ok", timestamp=datetime.now())
        assert check.status == "ok"
        assert isinstance(check.timestamp, datetime)

from datetime import datetime

import sqlalchemy as sa

from src.models import HealthCheck
from src.db.models import Product, Release


class TestHealthCheck:
    def test_health_check_creation(self) -> None:
        check = HealthCheck(status="ok", timestamp=datetime.now())
        assert check.status == "ok"
        assert isinstance(check.timestamp, datetime)


class TestProductReleaseRelation:
    def test_release_version_is_unique_per_product(self) -> None:
        unique_constraints = [
            constraint
            for constraint in Release.__table__.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        ]

        assert any(
            {column.name for column in constraint.columns} == {"product_id", "version"}
            for constraint in unique_constraints
        )

    def test_product_has_releases_relationship(self) -> None:
        assert Product.releases.property.mapper.class_ is Release

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from src.db.clickhouse import ReleasesAnalyticsSchema
from src.services.analytics_seed import (
    generate_release_request_analytics,
    seed_release_request_analytics,
)
from src.settings.db import ClickHouseSettings


def make_clickhouse_settings(**overrides: object) -> ClickHouseSettings:
    values = {
        "password": SecretStr("secret"),
    } | overrides
    return ClickHouseSettings(**values)


def test_generate_release_request_analytics_uses_configured_range() -> None:
    now = datetime(2026, 4, 28, 12, 0, tzinfo=UTC)
    rows = generate_release_request_analytics(
        rows=20,
        days_range=30,
        ignore_domain="internal.example",
        random_seed=1,
        now=now,
    )

    assert len(rows) == 20
    assert all(isinstance(row, ReleasesAnalyticsSchema) for row in rows)
    assert all(
        now - timedelta(days=30) <= row.timestamp <= now + timedelta(days=30) for row in rows
    )
    assert any(row.client_ref_url and "internal.example" in row.client_ref_url for row in rows)


@pytest.mark.asyncio
async def test_seed_release_request_analytics_inserts_generated_rows() -> None:
    settings = make_clickhouse_settings(analytics_table_name="release_requests_seed")
    client = AsyncMock()
    analytics_row = ReleasesAnalyticsSchema(
        timestamp=datetime(2026, 4, 28, 12, 30, tzinfo=UTC),
        client_version="1.2.0",
        client_install_id="install-00001",
        client_is_corporate=True,
        client_is_internal=False,
        client_ip_address="198.51.100.10",
        client_user_agent="ReleaseAgentClient/1.0",
        client_ref_url="https://customer-1.example.test/releases",
        response_latest_version="2.0.0",
        response_status=200,
        response_time_ms=42.5,
        response_from_cache=False,
    )

    with (
        patch("src.services.analytics_seed.get_clickhouse_client", return_value=client),
        patch(
            "src.services.analytics_seed.generate_release_request_analytics",
            return_value=[analytics_row],
        ) as generate_rows,
    ):
        inserted = await seed_release_request_analytics(
            settings,
            rows=1,
            days_range=30,
            random_seed=42,
        )

    assert inserted == 1
    generate_rows.assert_called_once_with(
        rows=1,
        days_range=30,
        ignore_domain=settings.ignore_domain,
        random_seed=42,
    )
    client.insert.assert_awaited_once()
    _, kwargs = client.insert.call_args
    assert kwargs["table"] == "release_requests_seed"
    column_names = list(ReleasesAnalyticsSchema.model_fields)
    assert kwargs["column_names"] == column_names
    assert kwargs["data"] == [
        [analytics_row.model_dump()[column] for column in column_names],
    ]


@pytest.mark.asyncio
async def test_seed_release_request_analytics_skips_without_rows() -> None:
    settings = make_clickhouse_settings()

    with patch("src.services.analytics_seed.get_clickhouse_client") as get_client:
        inserted = await seed_release_request_analytics(
            settings,
            rows=0,
            days_range=30,
        )

    assert inserted == 0
    get_client.assert_not_called()

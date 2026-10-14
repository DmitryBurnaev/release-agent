import logging
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from src.db.clickhouse import ReleasesAnalyticsSchema, _clickhouse_connectors
from src.settings.db import ClickHouseSettings


def test_analytics_schema_declares_requested_product_column() -> None:
    query = ReleasesAnalyticsSchema.create_table_query("release_requests")

    assert "requested_product LowCardinality(String) DEFAULT ''" in query


@pytest.mark.asyncio
async def test_analytics_table_setup_runs_idempotent_product_alter(caplog) -> None:  # type: ignore
    previous_settings = _clickhouse_connectors._clickhouse_settings
    previous_client = _clickhouse_connectors._async_client
    client = AsyncMock()
    _clickhouse_connectors._clickhouse_settings = ClickHouseSettings(
        password=SecretStr("secret"),
        analytics_table_name="release_requests",
    )
    _clickhouse_connectors._async_client = client

    try:
        with caplog.at_level(logging.INFO):
            await _clickhouse_connectors._create_analytics_table()
            await _clickhouse_connectors._create_analytics_table()
    finally:
        _clickhouse_connectors._clickhouse_settings = previous_settings
        _clickhouse_connectors._async_client = previous_client

    assert client.command.await_count == 4
    alter_queries = [client.command.await_args_list[index].args[0] for index in (1, 3)]
    assert all("ADD COLUMN IF NOT EXISTS requested_product" in query for query in alter_queries)
    assert "Ensuring requested_product column exists" in caplog.text
    assert "requested_product column is ready" in caplog.text

import logging
from typing import Any

from src.db.clickhouse import get_clickhouse_client, ReleasesAnalyticsSchema
from src.settings.db import ClickHouseSettings
from starlette.background import BackgroundTasks

logger = logging.getLogger(__name__)

__all__ = ("AnalyticsService",)


class AnalyticsService:
    """Service for logging API requests to ClickHouse"""

    def __init__(self, clickhouse_settings: ClickHouseSettings) -> None:
        self._clickhouse_settings = clickhouse_settings
        self._analytics_table_name = clickhouse_settings.analytics_table_name
        self._database = clickhouse_settings.database

    def log_request_async(
        self,
        background_tasks: BackgroundTasks,
        request: ReleasesAnalyticsSchema,
    ) -> None:
        """
        Log API request to ClickHouse asynchronously
        """
        background_tasks.add_task(self._log_request, request)

    async def _log_request(self, request: ReleasesAnalyticsSchema) -> None:
        """
        Log API request to ClickHouse

        Args:
            request: AnalyticsRequest namedtuple with request data
        """
        try:
            client = await get_clickhouse_client()
            data = request.model_dump()
            insert_columns, insert_cells = [], []
            for key, value in data.items():
                insert_columns.append(key)
                insert_cells.append(value)

            await client.insert(
                table=self._analytics_table_name,
                data=[insert_cells],
                column_names=insert_columns,
            )
            logger.info(
                "[Analytics] Logged request: latest-ver: %s | install-id: %s | status: %d",
                request.response_latest_version,
                request.client_install_id,
                request.response_status,
            )
        except Exception as e:
            # Don't fail the request if analytics logging fails
            logger.warning("[Analytics] Failed to log request: %r", e)
            raise e

    async def get_requests_over_time(
        self, hours: int = 24, group_by: str = "hour"
    ) -> list[dict[str, Any]]:
        """
        Get requests count grouped by time intervals

        Args:
            hours: Number of hours to look back
            group_by: Grouping interval ('hour' or 'day')

        Returns:
            List of dicts with 'time' and 'count' keys
        """
        client = await get_clickhouse_client()
        interval_func = "toStartOfHour" if group_by == "hour" else "toStartOfDay"
        query = f"""
            SELECT 
                {interval_func}(timestamp) as time,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            WHERE timestamp >= now() - INTERVAL {hours} HOUR
            GROUP BY time
            ORDER BY time ASC
        """
        result = await client.query(query)
        return [{"time": str(row[0]), "count": row[1]} for row in result.result_rows]

    async def get_by_client_version(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get requests count grouped by client version

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of dicts with 'version' and 'count' keys
        """
        client = await get_clickhouse_client()
        query = f"""
            SELECT 
                client_version as version,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            WHERE client_version IS NOT NULL
            GROUP BY version
            ORDER BY count DESC
            LIMIT {limit}
        """
        result = await client.query(query)
        return [{"version": row[0] or "Unknown", "count": row[1]} for row in result.result_rows]

    async def get_by_corporate(self) -> list[dict[str, Any]]:
        """
        Get requests count grouped by corporate flag

        Returns:
            List of dicts with 'is_corporate' and 'count' keys
        """
        client = await get_clickhouse_client()
        query = f"""
            SELECT 
                client_is_corporate as is_corporate,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            GROUP BY is_corporate
        """
        result = await client.query(query)
        return [
            {"is_corporate": "Corporate" if row[0] else "Non-corporate", "count": row[1]}
            for row in result.result_rows
        ]

    async def get_by_response_version(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get requests count grouped by response latest version

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of dicts with 'version' and 'count' keys
        """
        client = await get_clickhouse_client()
        query = f"""
            SELECT 
                response_latest_version as version,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            WHERE response_latest_version IS NOT NULL
            GROUP BY version
            ORDER BY count DESC
            LIMIT {limit}
        """
        result = await client.query(query)
        return [{"version": row[0] or "Unknown", "count": row[1]} for row in result.result_rows]

    async def get_by_cache(self) -> list[dict[str, Any]]:
        """
        Get requests count grouped by cache flag

        Returns:
            List of dicts with 'from_cache' and 'count' keys
        """
        client = await get_clickhouse_client()
        query = f"""
            SELECT 
                response_from_cache as from_cache,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            GROUP BY from_cache
        """
        result = await client.query(query)
        return [
            {"from_cache": "Cached" if row[0] else "Not cached", "count": row[1]}
            for row in result.result_rows
        ]

    async def get_top_ips(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get top IP addresses by request count

        Args:
            limit: Maximum number of IPs to return

        Returns:
            List of dicts with 'ip' and 'count' keys
        """
        client = await get_clickhouse_client()
        query = f"""
            SELECT 
                client_ip_address as ip,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            WHERE client_ip_address IS NOT NULL
            GROUP BY ip
            ORDER BY count DESC
            LIMIT {limit}
        """
        result = await client.query(query)
        return [{"ip": row[0] or "Unknown", "count": row[1]} for row in result.result_rows]

    async def get_top_referers(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get top referer URLs by request count

        Args:
            limit: Maximum number of referers to return

        Returns:
            List of dicts with 'referer' and 'count' keys
        """
        client = await get_clickhouse_client()
        query = f"""
            SELECT 
                client_ref_url as referer,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            WHERE client_ref_url IS NOT NULL AND client_ref_url != ''
            GROUP BY referer
            ORDER BY count DESC
            LIMIT {limit}
        """
        result = await client.query(query)
        return [{"referer": row[0] or "Unknown", "count": row[1]} for row in result.result_rows]

    async def get_by_status(self) -> list[dict[str, Any]]:
        """
        Get requests count grouped by HTTP status code

        Returns:
            List of dicts with 'status' and 'count' keys
        """
        client = await get_clickhouse_client()
        query = f"""
            SELECT 
                response_status as status,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            GROUP BY status
            ORDER BY status ASC
        """
        result = await client.query(query)
        return [{"status": row[0], "count": row[1]} for row in result.result_rows]

    async def get_response_time_distribution(self, buckets: int = 10) -> list[dict[str, Any]]:
        """
        Get response time distribution histogram

        Args:
            buckets: Number of buckets for histogram

        Returns:
            List of dicts with 'bucket' and 'count' keys
        """
        client = await get_clickhouse_client()
        # First get max response time to calculate bucket size
        max_query = f"""
            SELECT max(response_time_ms) as max_time
            FROM {self._database}.{self._analytics_table_name}
            WHERE response_time_ms IS NOT NULL
        """
        max_result = await client.query(max_query)
        if not max_result.result_rows or max_result.result_rows[0][0] is None:
            return []

        max_time = float(max_result.result_rows[0][0])
        if max_time == 0:
            return []

        bucket_size = max_time / buckets

        query = f"""
            SELECT 
                floor(response_time_ms / {bucket_size}) as bucket,
                count() as count
            FROM {self._database}.{self._analytics_table_name}
            WHERE response_time_ms IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket ASC
        """
        result = await client.query(query)
        return [{"bucket": int(row[0]), "count": row[1]} for row in result.result_rows]

import logging

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

    def log_request_async(
        self,
        background_tasks: BackgroundTasks,
        request: ReleasesAnalyticsSchema,
    ) -> None:
        """
        Log API request to ClickHouse asynchronously
        """
        background_tasks.add_task(self._log_request, request)

    def _log_request(self, request: ReleasesAnalyticsSchema) -> None:
        """
        Log API request to ClickHouse

        Args:
            request: AnalyticsRequest namedtuple with request data
        """
        try:
            client = get_clickhouse_client()
            data = request.model_dump()
            insert_columns, insert_cells = [], []
            for key, value in data.items():
                insert_columns.append(key)
                insert_cells.append(value)

            client.insert(self._analytics_table_name, [insert_cells], column_names=insert_columns)
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

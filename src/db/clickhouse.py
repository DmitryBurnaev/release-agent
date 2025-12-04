from datetime import datetime
import logging

from clickhouse_connect.driver.client import Client as ClickhouseClient
import clickhouse_connect.driver
from pydantic import BaseModel

from src.utils import singleton
from src.settings.db import ClickHouseSettings, get_clickhouse_settings

logger = logging.getLogger(__name__)

__all__ = (
    "initialize_clickhouse",
    "close_clickhouse",
    "get_clickhouse_client",
)


class ReleasesAnalyticsSchema(BaseModel):
    """Releases analytics schema for ClickHouse"""

    timestamp: datetime
    client_version: str | None
    latest_version: str | None
    installation_id: str | None
    is_corporate: bool | None
    response_status: int
    response_time_ms: float | None
    response_from_cache: bool | None
    ip_address: str | None
    user_agent: str | None

    @classmethod
    def create_table_query(cls, table_name: str) -> str:
        """Create table query for ClickHouse"""
        return f"""
            CREATE TABLE IF NOT EXISTS {table_name}
            (
                timestamp DateTime DEFAULT now(),
                client_version Nullable(String),
                latest_version Nullable(String),
                installation_id Nullable(String),
                is_corporate Nullable(Bool),
                response_status UInt16,
                response_time_ms Nullable(Float32),
                response_from_cache Nullable(Bool),
                ip_address Nullable(String),
                user_agent Nullable(String)
            )
            ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (timestamp)
        """


@singleton
class AsyncClickHouseConnectors:
    """
    Singleton class that handles ClickHouse connections
    """

    def __init__(self, settings: ClickHouseSettings) -> None:
        self._clickhouse_settings: ClickHouseSettings = settings
        self._client: ClickhouseClient | None = None

    def init_connection(self) -> None:
        """
        Initialize the ClickHouse connection

        Raises:
            RuntimeError: If the ClickHouse connection is not initialized
        """
        logger.info(
            "[CH] Initializing connection to %s...",
            self._clickhouse_settings.info,
        )
        if self._client is None:
            try:
                self._client = clickhouse_connect.get_client(
                    host=self._clickhouse_settings.host,
                    port=self._clickhouse_settings.port,
                    username=self._clickhouse_settings.user,
                    password=self._clickhouse_settings.password.get_secret_value(),
                    database=self._clickhouse_settings.database,
                    secure=self._clickhouse_settings.secure,
                    connect_timeout=self._clickhouse_settings.timeout,
                )
            except Exception as e:
                logger.error("[CH] Failed to create client: %r", e)
                raise RuntimeError(f"ClickHouse: Failed to create client: {e}") from e

        self._ping_connection()
        self._create_analytics_table()
        logger.info("[CH] ClickHouse connection initialized successfully")

    def close_connection(self) -> None:
        """Close the ClickHouse connection"""
        if self._client is None:
            logger.warning(
                "[CH] Connection is not initialized, cannot close connection",
            )
            return

        try:
            self._client.close()  # type: ignore
        except Exception as e:
            logger.error("[CH] Error during connection close: %r", e)
        else:
            logger.info(
                "[CH] Connection to %s closed successfully",
                self._clickhouse_settings.info,
            )
        finally:
            self._client = None

    @property
    def client(self) -> ClickhouseClient:
        """Get the ClickHouse client instance from current context"""
        if self._client is None:
            logger.warning("[CH] Client is not initialized!")
            raise RuntimeError(
                "Client is not initialized. Make sure lifespan is properly set up.",
            )

        return self._client

    def _ping_connection(self) -> None:
        """Ping the ClickHouse connection"""
        if self._client is None:
            raise RuntimeError("ClickHouse connection is not initialized")

        connection_info = self._clickhouse_settings.info

        logger.info("[CH] Pinging connection to %s...", connection_info)

        try:
            result = self._client.command("SELECT 1")
            if result != 1:
                raise RuntimeError("Unable to ping ClickHouse server")
        except Exception as e:
            logger.error("[CH] Failed to ping connection to %s: %s", connection_info, e)
            raise RuntimeError(f"ClickHouse: Failed to ping connection: {e}") from e

        logger.info("[CH] Connection to %s is healthy", connection_info)

    def _create_analytics_table(self) -> None:
        """
        Create analytics table in ClickHouse if it doesn't exist

        Use command method to execute DDL statement
        clickhouse-connect doesn't have a dedicated create_table method

        """
        table_name: str = self._clickhouse_settings.analytics_table_name
        try:
            create_table_query = ReleasesAnalyticsSchema.create_table_query(table_name)
            self.client.command(create_table_query)
            logger.debug(
                "[CH] Table %s created or already exists",
                table_name,
            )
        except Exception as e:
            logger.error("[CH] Failed to create table: %r", e)
            raise


_clickhouse_connectors = AsyncClickHouseConnectors(get_clickhouse_settings())


def initialize_clickhouse() -> None:
    """Initialize the ClickHouse connection"""
    _clickhouse_connectors.init_connection()


def close_clickhouse() -> None:
    """Close the ClickHouse connection"""
    _clickhouse_connectors.close_connection()


def get_clickhouse_client() -> ClickhouseClient:
    """Get the ClickHouse client instance from current context"""
    return _clickhouse_connectors.client

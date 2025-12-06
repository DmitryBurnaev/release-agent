from functools import lru_cache, cached_property

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.settings.utils import prepare_settings

__all__ = ("get_db_settings", "get_redis_settings", "get_clickhouse_settings")


class DBSettings(BaseSettings):
    """Implements settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="DB_")

    driver: str = "postgresql+asyncpg"
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    name: str = "release_agent"
    pool_min_size: int | None = Field(default_factory=lambda: None, description="Pool Min Size")
    pool_max_size: int | None = Field(default_factory=lambda: None, description="Pool Max Size")
    echo: bool = False

    @cached_property
    def dsn(self) -> str:
        return f"{self.driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    # as_cache: bool = Field(default=False, description="Enable Redis cache")
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    socket_connect_timeout: int = 5
    socket_timeout: int = 5
    decode_responses: bool = True
    max_connections: int = 5

    @cached_property
    def dsn(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"

    @cached_property
    def info(self) -> str:
        return f"{self.host}:{self.port} (db={self.db})"


@lru_cache
def get_db_settings() -> DBSettings:
    """Prepares database settings from environment variables"""
    return prepare_settings(DBSettings)


@lru_cache
def get_redis_settings() -> RedisSettings:
    """Prepares redis settings from environment variables"""
    return prepare_settings(RedisSettings)


class ClickHouseSettings(BaseSettings):
    """ClickHouse settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="CH_")

    host: str = "localhost"
    port: int = 8123
    user: str = "releases"
    password: SecretStr = Field(description="ClickHouse password")
    database: str = "releases"
    secure: bool = False
    timeout: int = 10
    analytics_table_name: str = "release_requests"

    @cached_property
    def info(self) -> str:
        """Get connection info string for logging"""
        return f"{self.host}:{self.port} (database={self.database})"

    @cached_property
    def http_url(self) -> str:
        """Get HTTP URL for ClickHouse UI"""
        schema = "https://" if self.secure else "http://"
        return f"{schema}{self.host}:{self.port}"


@lru_cache
def get_clickhouse_settings() -> ClickHouseSettings:
    """Prepares ClickHouse settings from environment variables"""
    return prepare_settings(ClickHouseSettings)

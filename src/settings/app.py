from functools import lru_cache
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo
import logging
import os

from fastapi import Depends
from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.settings.utils import prepare_settings
from src.settings.log import LogSettings

__all__ = (
    "get_app_settings",
    "AppSettings",
    "RedisSettings",
)
logger = logging.getLogger(__name__)
APP_DIR = Path(__file__).parent.parent


class FlagsSettings(BaseSettings):
    """Implements settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_prefix="FLAG_")

    offline_mode: bool = False
    debug_mode: bool = False


class AdminSettings(BaseSettings):
    """Implements settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_prefix="ADMIN_")

    username: str = Field(default_factory=lambda: "admin", description="Default admin username")
    password: SecretStr = Field(
        default_factory=lambda: SecretStr("release-admin!"),
        description="Default admin password",
    )
    session_expiration_time: int = 2 * 24 * 3600
    base_url: str = "/radm"
    title: str = "Release Agent"


class RedisSettings(BaseSettings):
    """Redis settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    use_redis: bool = Field(default=False, description="Enable Redis cache")
    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @field_validator("use_redis", mode="before")
    @classmethod
    def validate_use_redis(cls, v: str | bool | None) -> bool:
        """Support both USE_REDIS_CACHE and REDIS_USE_REDIS environment variables"""
        # Check USE_REDIS_CACHE first (without prefix)
        use_redis_cache = os.environ.get("USE_REDIS_CACHE")
        if use_redis_cache is not None:
            return use_redis_cache.lower() in ("true", "1", "yes", "on")

        # Fall back to provided value (from REDIS_USE_REDIS)
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)


class AppSettings(BaseSettings):
    """Application settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_docs_enabled: bool = False
    api_cache_enabled: bool = False
    app_secret_key: SecretStr = Field(description="Application secret key")
    app_host: str = "localhost"
    app_port: int = 8004
    jwt_algorithm: str = "HS256"
    admin: AdminSettings = Field(default_factory=AdminSettings)
    flags: FlagsSettings = Field(default_factory=FlagsSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    ui_timezone: ZoneInfo | None = Field(
        default=None,
        # validation_alias="UT_TIMEZONE",
        description="UI timezone (from env UT_TIMEZONE, e.g. 'Europe/Moscow')",
    )

    @field_validator("ui_timezone", mode="before")
    @classmethod
    def validate_timezone(cls, v: str | None) -> ZoneInfo | None:
        """Convert timezone string to ZoneInfo object"""
        if v is None or v == "":
            return None

        try:
            return ZoneInfo(v)
        except Exception as exc:
            logger.error("AppSettings: unable to convert timezone to ZoneInfo: %s", exc)
            return None


@lru_cache
def get_app_settings() -> AppSettings:
    """Prepares application settings from environment variables"""
    return prepare_settings(AppSettings)


SettingsDep = Annotated[AppSettings, Depends(get_app_settings)]

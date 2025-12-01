from functools import lru_cache
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo
import logging

from fastapi import Depends
from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.settings.utils import prepare_settings
from src.settings.log import LogSettings

__all__ = (
    "get_app_settings",
    "AppSettings",
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


class AppSettings(BaseSettings):
    """Application settings which are loaded from environment variables"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_docs_enabled: bool = False
    api_cache_enabled: bool = True
    app_secret_key: SecretStr = Field(description="Application secret key")
    app_host: str = "localhost"
    app_port: int = 8004
    jwt_algorithm: str = "HS256"
    admin: AdminSettings = Field(default_factory=AdminSettings)
    flags: FlagsSettings = Field(default_factory=FlagsSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    use_redis: bool = Field(default=True, description="Enable Redis cache backend")
    ui_timezone: ZoneInfo | None = Field(
        default=None,
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

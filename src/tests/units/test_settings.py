import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from src.settings import AppSettings, get_app_settings
from src.settings.log import LOG_LEVELS_PATTERN, LogSettings

MINIMAL_ENV_VARS = {
    "APP_SECRET_KEY": "test-key",
    "ADMIN_PASSWORD": "test-password",
}


@pytest.fixture(autouse=True)
def minimal_env_vars() -> None:
    """Overrides global MINIMAL_ENV_VARS"""
    pass


class TestAppSettings:
    @patch.dict(os.environ, MINIMAL_ENV_VARS)
    def test_default_settings(self) -> None:
        get_app_settings.cache_clear()
        settings = AppSettings(_env_file=None)  # type: ignore
        assert settings.app_host == "localhost"
        assert settings.app_port == 8004
        assert settings.app_secret_key.get_secret_value() == "test-key"
        assert settings.log.level == "INFO"
        assert settings.jwt_algorithm == "HS256"
        assert settings.admin.username == "admin"
        assert settings.admin.password.get_secret_value() == "test-password"
        assert settings.admin.session_expiration_time == 2 * 24 * 3600
        # check flags
        assert settings.flags.use_redis is True
        assert settings.flags.offline_mode is False
        assert settings.flags.api_docs_enabled is False
        assert settings.flags.api_cache_enabled is True

    @pytest.mark.parametrize("log_level", LOG_LEVELS_PATTERN.split("|"))
    def test_valid_log_levels(self, log_level: str) -> None:
        settings = AppSettings(
            app_secret_key=SecretStr("test-token"),
            log=LogSettings(level=log_level),
        )
        assert settings.log.level == log_level.upper()

    def test_invalid_log_level(self) -> None:
        with pytest.raises(ValueError):
            AppSettings(
                app_secret_key=SecretStr("test-secret"),
                log=LogSettings(level="INVALID"),
            )

    def test_log_config(self) -> None:
        settings = AppSettings(
            app_secret_key=SecretStr("test-token"),
            log=LogSettings(level="DEBUG"),
        )
        log_config = settings.log.dict_config
        assert log_config["version"] == 1
        assert "standard" in log_config["formatters"]
        assert "console" in log_config["handlers"]
        assert all(
            logger in log_config["loggers"]
            for logger in ["src", "fastapi", "uvicorn.access", "uvicorn.error"]
        )
        assert all(
            log_config["loggers"][logger]["level"] == "DEBUG"
            for logger in ["src", "fastapi", "uvicorn.access", "uvicorn.error"]
        )


class TestGetSettings:
    @patch.dict(
        os.environ,
        MINIMAL_ENV_VARS
        | {
            "LOG_LEVEL": "DEBUG",
            "APP_HOST": "0.0.0.0",
            "APP_PORT": "8081",
            "FLAG_OFFLINE_MODE": "true",
        },
    )
    def test_get_app_settings_from_env(self) -> None:
        get_app_settings.cache_clear()
        settings = get_app_settings()
        assert settings.log.level == "DEBUG"
        assert settings.app_host == "0.0.0.0"
        assert settings.app_port == 8081
        assert settings.flags.offline_mode is True

    @patch.dict(os.environ, MINIMAL_ENV_VARS | {"LOG_LEVEL": "INVALID"})
    def test_get_app_settings_validation_error(self) -> None:
        get_app_settings.cache_clear()
        with pytest.raises(Exception):
            get_app_settings()

    @patch.dict(os.environ, MINIMAL_ENV_VARS)
    def test_get_app_settings_caching(self) -> None:
        get_app_settings.cache_clear()
        settings1 = get_app_settings()
        settings2 = get_app_settings()
        assert settings1 is settings2  # Same object due to caching

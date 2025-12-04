import sys
import logging.config
from contextlib import asynccontextmanager
from typing import Any, Callable, AsyncGenerator

import uvicorn
from fastapi import FastAPI, Depends

from src.db.redis import close_redis, initialize_redis
from src.db.clickhouse import close_clickhouse, initialize_clickhouse
from src.modules.auth.dependencies import verify_api_token
from src.modules.admin.app import make_admin
from src.exceptions import AppSettingsError, StartupError
from src.settings import get_app_settings, AppSettings
from src.modules.api import system_router
from src.modules.api.public import public_router as releases_public_router
from src.modules.api.releases import admin_router as releases_router
from src.db.session import initialize_database, close_database

logger = logging.getLogger("src.main")


class ReleaseAgentAPP(FastAPI):
    """Some extra fields above FastAPI Application"""

    _settings: AppSettings
    dependency_overrides: dict[Any, Callable[[], Any]]

    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings

    @property
    def settings(self) -> AppSettings:
        return self._settings


@asynccontextmanager
async def lifespan(app: ReleaseAgentAPP) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    logger.info("Starting up application...")
    try:
        await initialize_database()
    except Exception as exc:
        raise StartupError("Failed to initialize DB connection") from exc
    else:
        logger.info("DB connection startup completed")

    # Check Redis availability if enabled
    if app.settings.flags.use_redis:
        try:
            await initialize_redis()
        except Exception as exc:
            raise StartupError("Failed to initialize Redis connection") from exc
        else:
            logger.info("Redis connection startup completed")
    else:
        logger.info("Redis is not enabled, skipping initialization")

    # Initialize ClickHouse for analytics
    try:
        initialize_clickhouse()
    except Exception as exc:
        logger.warning("Failed to initialize ClickHouse connection: %r", exc)
        logger.warning("Analytics will be disabled")
    else:
        logger.info("ClickHouse connection startup completed")

    logger.info("Setting up admin application...")
    make_admin(app)

    yield

    logger.info("===== shutdown ====")
    logger.info("Shutting down this application...")
    try:
        await close_database()
    except Exception as exc:
        logger.error("Error during application shutdown: %r", exc)
    else:
        logger.info("Application shutdown completed successfully")

    if app.settings.flags.use_redis:
        try:
            await close_redis()
        except Exception as exc:
            logger.error("Error during application shutdown: %r", exc)
        else:
            logger.info("Redis connection shutdown completed successfully")

    try:
        close_clickhouse()
    except Exception as exc:
        logger.error("Error during ClickHouse shutdown: %r", exc)
    else:
        logger.info("ClickHouse connection shutdown completed successfully")

    logger.info("=====")


def make_app(settings: AppSettings | None = None) -> ReleaseAgentAPP:
    """Forming Application instance with required settings and dependencies"""

    if settings is None:
        try:
            settings = get_app_settings()
        except AppSettingsError as exc:
            logger.error("Unable to get settings from environment: %r", exc)
            sys.exit(1)

    logging.config.dictConfig(settings.log.dict_config_any)
    logging.captureWarnings(capture=True)

    logger.info("Setting up application...")
    app = ReleaseAgentAPP(
        title="Release Agent API",
        description="API for managing releases",
        docs_url="/api/docs/" if settings.flags.api_docs_enabled else None,
        redoc_url="/api/redoc/" if settings.flags.api_docs_enabled else None,
        lifespan=lifespan,
    )
    app.set_settings(settings)

    logger.info("Setting up routes...")
    # Public routes (no authentication required)
    app.include_router(releases_public_router, prefix="/public")
    # Protected routes (authentication required)
    app.include_router(system_router, prefix="/api", dependencies=[Depends(verify_api_token)])
    app.include_router(releases_router, prefix="/api", dependencies=[Depends(verify_api_token)])

    logger.info("Application configured!")
    return app


if __name__ == "__main__":
    """Prepares App and run uvicorn instance"""
    app: ReleaseAgentAPP = make_app()
    uvicorn.run(
        app,
        host=app.settings.app_host,
        port=app.settings.app_port,
        log_config=app.settings.log.dict_config_any,
        proxy_headers=True,
    )

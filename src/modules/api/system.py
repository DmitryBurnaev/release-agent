from datetime import datetime

from fastapi import APIRouter

from src.models import HealthCheck
from src.modules.api import ErrorHandlingBaseRoute

__all__ = ("router",)


router = APIRouter(
    prefix="/system",
    tags=["system"],
    responses={404: {"description": "Not found"}},
    route_class=ErrorHandlingBaseRoute,
)


@router.get("/health/", response_model=HealthCheck)
async def health_check() -> HealthCheck:
    """Health check endpoint."""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
    )

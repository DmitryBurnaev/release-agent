from typing import Optional
from datetime import datetime
from pydantic import BaseModel

__all__ = (
    "HealthCheck",
    "ErrorResponse",
)


class HealthCheck(BaseModel):
    """Health check response model."""

    status: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Base error response model"""

    error: str
    detail: Optional[str] = None

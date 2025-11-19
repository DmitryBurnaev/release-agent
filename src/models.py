from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field

__all__ = (
    "HealthCheck",
    "ErrorResponse",
    "ReleaseResponse",
    "ReleaseDetailsResponse",
    "ReleasePublicResponse",
    "ReleaseCreate",
    "ReleaseUpdate",
)


class HealthCheck(BaseModel):
    """Health check response model."""

    status: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Base error response model"""

    error: str
    detail: Optional[str] = None


class ReleasePublicResponse(BaseModel):
    """Release public response model for API"""

    version: str
    notes: str
    url: str
    published_at: datetime

    class Config:
        from_attributes = True


class ReleaseBaseResponse(BaseModel):
    """Release details response model for API"""

    id: int
    version: str
    url: str
    published_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class ReleaseResponse(ReleaseBaseResponse):
    """Release response model for API"""


class ReleaseDetailsResponse(ReleaseBaseResponse):
    """Release details response model for API"""

    notes: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReleaseBaseModify(BaseModel):
    """Release base modify model for API"""

    notes: Optional[str] = Field(None, description="Release notes")
    url: Optional[str] = Field(None, max_length=255, description="Release URL link")
    published_at: Optional[date] = Field(None, description="Release date")


class ReleaseCreate(ReleaseBaseModify):
    """Release creation model for API"""

    version: str = Field(..., max_length=32, description="Release version")
    notes: str = Field(default_factory=str, description="Release notes")
    url: str = Field(default_factory=str, max_length=255, description="Release URL link")


class ReleaseUpdate(ReleaseBaseModify):
    """Release update model for API"""

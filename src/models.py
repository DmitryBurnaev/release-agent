from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

__all__ = (
    "HealthCheck",
    "ErrorResponse",
    "ReleaseResponse",
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


class ReleaseResponse(BaseModel):
    """Release response model for API"""

    id: int
    version: str
    notes: str
    url_link: str
    release_date: datetime
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReleaseCreate(BaseModel):
    """Release creation model for API"""

    version: str = Field(..., max_length=32, description="Release version")
    notes: str = Field(..., description="Release notes")
    url_link: str = Field(..., max_length=255, description="Release URL link")
    release_date: datetime = Field(..., description="Release date")


class ReleaseUpdate(BaseModel):
    """Release update model for API"""

    version: Optional[str] = Field(None, max_length=32, description="Release version")
    notes: Optional[str] = Field(None, description="Release notes")
    url_link: Optional[str] = Field(None, max_length=255, description="Release URL link")
    release_date: Optional[datetime] = Field(None, description="Release date")

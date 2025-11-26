from typing import Optional, Generic, TypeVar
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")

__all__ = (
    "HealthCheck",
    "ErrorResponse",
    "ReleaseResponse",
    "ReleaseDetailsResponse",
    "ReleasePublicResponse",
    "ReleaseCreate",
    "ReleaseUpdate",
    "PaginatedResponse",
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

    model_config = ConfigDict(from_attributes=True)

    version: str
    notes: str
    url: str | None
    published_at: datetime


class ReleaseBaseResponse(BaseModel):
    """Release details response model for API"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    url: str | None
    published_at: datetime
    is_active: bool


class ReleaseResponse(ReleaseBaseResponse):
    """Release response model for API"""


class ReleaseDetailsResponse(ReleaseBaseResponse):
    """Release details response model for API"""

    model_config = ConfigDict(from_attributes=True)

    notes: str
    created_at: datetime
    updated_at: Optional[datetime] = None


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


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model for API"""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    offset: int
    limit: int

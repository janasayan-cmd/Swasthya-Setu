"""Standard API response schemas and envelopes."""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Detailed error object within standard error response."""

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error description")
    request_id: str = Field(description="Correlation ID for the failed request")
    details: Any = Field(default=None, description="Optional validation or context details")


class StandardErrorResponse(BaseModel):
    """Standard error response envelope."""

    success: bool = Field(default=False)
    error: ErrorDetail


class StandardSuccessResponse(BaseModel, Generic[T]):
    """Standard success response envelope."""

    success: bool = Field(default=True)
    data: T
    request_id: str = Field(description="Correlation ID for the request")


class HealthResponse(BaseModel):
    """Liveness probe response model."""

    status: str = Field(default="ok", description="Process liveness status")
    service: str = Field(description="Service identifier")
    version: str = Field(description="Semantic version string")


class ReadinessChecks(BaseModel):
    """Individual readiness dependency checks."""

    database: str = Field(description="Status of database connectivity ('available', 'ok', or 'unavailable')")


class ReadinessResponse(BaseModel):
    """Readiness probe response model."""

    status: str = Field(description="Overall readiness status ('ready' or 'not_ready')")
    checks: ReadinessChecks

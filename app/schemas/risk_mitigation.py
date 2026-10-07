"""Phase 51: Clinical Risk Mitigation Planning & Tracking Schemas.

Defines schemas for defining, assigning, and validating risk mitigations.
Reinforces the foundational principle: MITIGATION != CONTROL and TASK COMPLETION != CONTROL EFFECTIVENESS.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class MitigationStatus(str, Enum):
    """Lifecycle status of a planned risk mitigation."""

    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    IMPLEMENTED = "IMPLEMENTED"
    VALIDATING = "VALIDATING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MitigationCreateRequest(BaseModel):
    """Request to define a structured mitigation plan for a governed risk."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    mitigation_type: str  # e.g. "VALIDATION_IMPROVEMENT", "HUMAN_REVIEW_GUARD", "SAFETY_GATE", "PROVIDER_FALLBACK"
    owner_id: str
    expected_outcome: str
    dependencies: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    validation_criteria: List[str] = Field(default_factory=list)
    expected_version: Optional[int] = None
    idempotency_key: Optional[str] = None


class MitigationRecord(BaseModel):
    """Authoritative domain record for a clinical risk mitigation."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"mit-{uuid.uuid4().hex[:12]}")
    risk_id: str
    title: str
    description: str
    mitigation_type: str
    owner_id: str
    expected_outcome: str
    dependencies: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    validation_criteria: List[str] = Field(default_factory=list)
    status: MitigationStatus = Field(default=MitigationStatus.PLANNED)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

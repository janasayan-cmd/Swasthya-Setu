"""Phase 51: Safety Change Validation Schemas.

Defines schemas for post-implementation validation, empirical safety verification,
and validation outcome tracking.
Enforces: TECHNICAL PASS != CLINICAL SAFETY PROOF and VALIDATION != PERMANENT SAFETY.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ValidationOutcome(str, Enum):
    """Outcome of safety change validation."""

    VALIDATED = "VALIDATED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"


class SafetyChangeValidationRequest(BaseModel):
    """Request to record post-implementation validation outcome."""

    model_config = ConfigDict(extra="ignore")

    outcome: ValidationOutcome
    validation_evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Pointers to automated test runs, safety gate checks, or human clinical review",
    )
    findings_summary: str = Field(min_length=5)
    notes: Optional[str] = None
    expected_change_version: Optional[int] = None
    idempotency_key: Optional[str] = None


class SafetyChangeValidationRecord(BaseModel):
    """Authoritative record of a safety change validation execution."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"val-{uuid.uuid4().hex[:12]}")
    change_id: str
    outcome: ValidationOutcome
    validator_id: str
    validator_role: str
    validation_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    findings_summary: str
    notes: Optional[str] = None
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

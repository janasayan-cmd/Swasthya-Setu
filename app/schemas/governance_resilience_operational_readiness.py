"""Phase 84: Operational Readiness Verification Schemas.

Governs multi-level operational readiness assessment and independent verification
across organizations, facilities, departments, and teams without overriding Phase 80 decisions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class OperationalReadinessScope(str, Enum):
    ORGANIZATION = "ORGANIZATION"
    FACILITY = "FACILITY"
    DEPARTMENT = "DEPARTMENT"
    TEAM = "TEAM"


class OperationalReadinessOutcome(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_READY = "NOT_READY"
    PARTIALLY_READY = "PARTIALLY_READY"
    READY_SUBJECT_TO_CONDITIONS = "READY_SUBJECT_TO_CONDITIONS"
    VERIFIED_READY = "VERIFIED_READY"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"


class OperationalReadinessRecord(BaseModel):
    readiness_id: str
    tenant_id: str
    scope_type: OperationalReadinessScope
    scope_id: str
    framework_version: int = 1
    critical_unmet_requirements: List[str] = Field(default_factory=list)
    unresolved_exceptions: List[str] = Field(default_factory=list)
    outcome: OperationalReadinessOutcome = OperationalReadinessOutcome.NOT_ASSESSED
    conditions: Optional[str] = None
    valid_until: Optional[datetime] = None
    assessor_id: str
    verifier_id: Optional[str] = None
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class AssessOperationalReadinessRequest(BaseModel):
    scope_type: OperationalReadinessScope
    scope_id: str
    framework_version: int = 1
    critical_unmet_requirements: List[str] = Field(default_factory=list)
    unresolved_exceptions: List[str] = Field(default_factory=list)
    outcome: OperationalReadinessOutcome
    conditions: Optional[str] = None
    valid_until: Optional[datetime] = None


class VerifyOperationalReadinessRequest(BaseModel):
    verified: bool
    verification_notes: Optional[str] = None
    conditions: Optional[str] = None

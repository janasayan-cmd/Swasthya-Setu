"""Phase 84: Capability Assessment Lifecycle Schemas.

Governs individual role-specific capability assessment, evidence submission,
independent assessment review, and verification gates.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class AssessmentLifecycleState(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    EVIDENCE_SUBMITTED = "EVIDENCE_SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ASSESSED = "ASSESSED"
    VERIFIED = "VERIFIED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class AssessmentOutcome(str, Enum):
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
    PARTIALLY_DEMONSTRATED = "PARTIALLY_DEMONSTRATED"
    DEMONSTRATED = "DEMONSTRATED"
    EXCEEDS_REQUIREMENT = "EXCEEDS_REQUIREMENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CapabilityAssessmentRecord(BaseModel):
    assessment_id: str
    tenant_id: str
    framework_id: str
    framework_version: int = 1
    applicable_role: str
    subject_user_id: str
    assessor_id: Optional[str] = None
    verifier_id: Optional[str] = None
    lifecycle_state: AssessmentLifecycleState = AssessmentLifecycleState.DRAFT
    assessment_outcome: AssessmentOutcome = AssessmentOutcome.INSUFFICIENT_EVIDENCE
    evidence_references: List[str] = Field(default_factory=list)
    criteria_evaluated: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: Optional[str] = None
    reviewer_comments: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    assessed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    next_assessment_due: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class CreateAssessmentRequest(BaseModel):
    framework_id: str
    framework_version: int = 1
    applicable_role: str
    subject_user_id: str
    scheduled_date: Optional[datetime] = None


class ScheduleAssessmentRequest(BaseModel):
    scheduled_date: datetime
    assessor_id: str


class SubmitAssessmentEvidenceRequest(BaseModel):
    evidence_references: List[str]
    notes: Optional[str] = None


class ReviewAssessmentRequest(BaseModel):
    assessment_outcome: AssessmentOutcome
    criteria_evaluated: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: Optional[str] = None
    reviewer_comments: Optional[str] = None


class VerifyAssessmentRequest(BaseModel):
    verified: bool
    verification_notes: Optional[str] = None
    next_assessment_due: Optional[datetime] = None

"""Phase 84: Capability Reassessment and Continuous Monitoring Schemas.

Supports event-driven and scheduled reassessment triggers to maintain fresh,
evidence-backed operational readiness without carrying forward stale outcomes.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class ReassessmentTriggerReason(str, Enum):
    FRAMEWORK_UPDATED = "FRAMEWORK_UPDATED"
    ROLE_REQUIREMENT_CHANGED = "ROLE_REQUIREMENT_CHANGED"
    DELEGATION_CHANGED = "DELEGATION_CHANGED"
    CRITICAL_PERSONNEL_CHANGED = "CRITICAL_PERSONNEL_CHANGED"
    REPEATED_UNSUCCESSFUL_DEMONSTRATION = "REPEATED_UNSUCCESSFUL_DEMONSTRATION"
    INCIDENT_FINDING = "INCIDENT_FINDING"
    PHASE81_ASSURANCE_FAILURE = "PHASE81_ASSURANCE_FAILURE"
    PHASE82_SIGNAL_DETECTED = "PHASE82_SIGNAL_DETECTED"
    PHASE83_KNOWLEDGE_SUPERSEDED = "PHASE83_KNOWLEDGE_SUPERSEDED"
    DEPENDENCY_CHANGED = "DEPENDENCY_CHANGED"
    ASSESSMENT_VALIDITY_EXPIRED = "ASSESSMENT_VALIDITY_EXPIRED"
    SCHEDULED_PERIODIC = "SCHEDULED_PERIODIC"


class ReassessmentStatus(str, Enum):
    TRIGGERED = "TRIGGERED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CapabilityReassessmentRecord(BaseModel):
    reassessment_id: str
    tenant_id: str
    subject_type: str = Field(..., description="INDIVIDUAL, TEAM, DELEGATE, or ORGANIZATION")
    subject_id: str
    trigger_reason: ReassessmentTriggerReason
    target_assessment_id: Optional[str] = None
    notes: Optional[str] = None
    status: ReassessmentStatus = ReassessmentStatus.TRIGGERED
    scheduled_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class TriggerReassessmentRequest(BaseModel):
    subject_type: str
    subject_id: str
    trigger_reason: ReassessmentTriggerReason
    target_assessment_id: Optional[str] = None
    notes: Optional[str] = None


class CompleteReassessmentRequest(BaseModel):
    outcome_notes: str

"""Phase 70: Auditor Assignment & Independence Verification Schemas.

Defines schemas for:
- Auditor roster assignments and specific roles
- Independence evaluations and conflict-of-interest declarations
- Mitigation tracking and historical assignment preservation
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AuditorRole(str, Enum):
    """Functional role of an auditor on a clinical safety audit."""

    LEAD_AUDITOR = "LEAD_AUDITOR"
    SUPPORTING_AUDITOR = "SUPPORTING_AUDITOR"
    INDEPENDENT_REVIEWER = "INDEPENDENT_REVIEWER"
    SUBJECT_MATTER_EXPERT = "SUBJECT_MATTER_EXPERT"
    AUTHORIZED_OBSERVER = "AUTHORIZED_OBSERVER"
    PROGRAMME_OWNER = "PROGRAMME_OWNER"


class IndependenceStatus(str, Enum):
    """Independence verification status of an assigned auditor."""

    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED_INDEPENDENT = "VERIFIED_INDEPENDENT"
    CONFLICT_IDENTIFIED = "CONFLICT_IDENTIFIED"
    MITIGATION_APPROVED = "MITIGATION_APPROVED"
    REASSIGNED = "REASSIGNED"


class AuditorAssignmentRecord(BaseModel):
    """Domain record representing an auditor assigned to an audit."""

    model_config = ConfigDict(extra="ignore")

    assignment_id: str = Field(default_factory=lambda: f"gasn-{uuid.uuid4().hex[:12]}")
    audit_id: str
    auditor_id: str
    auditor_name: Optional[str] = None
    auditor_role: AuditorRole = AuditorRole.SUPPORTING_AUDITOR

    independence_status: IndependenceStatus = IndependenceStatus.PENDING_REVIEW
    declared_conflicts: List[str] = Field(default_factory=list)
    conflict_mitigation: Optional[str] = None

    independence_reviewed_by: Optional[str] = None
    independence_reviewed_at: Optional[datetime] = None
    independence_review_rationale: Optional[str] = None

    assigned_by: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    reassignment_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssignAuditorRequest(BaseModel):
    """Request payload to assign an auditor with conflict declaration."""

    model_config = ConfigDict(extra="ignore")

    auditor_id: str
    auditor_name: Optional[str] = None
    auditor_role: Optional[AuditorRole] = AuditorRole.SUPPORTING_AUDITOR
    declared_conflicts: Optional[List[str]] = Field(default_factory=list)
    conflict_mitigation: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IndependenceReviewRequest(BaseModel):
    """Request payload to review and confirm independence or approve mitigation."""

    model_config = ConfigDict(extra="ignore")

    independence_status: IndependenceStatus  # VERIFIED_INDEPENDENT, CONFLICT_IDENTIFIED, MITIGATION_APPROVED, REASSIGNED
    review_rationale: str
    conflict_mitigation: Optional[str] = None

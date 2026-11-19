"""Phase 69: Compliance Finding and Gap Identification Schemas.

Defines schemas for:
- 18 explicit compliance gap categories
- Policy-driven compliance gap prioritization
- Governed human review and resolution records
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ComplianceGapCategory(str, Enum):
    """Controlled categories of compliance deficiencies and gaps."""

    REQUIREMENT_NOT_IMPLEMENTED = "REQUIREMENT_NOT_IMPLEMENTED"
    CONTROL_NOT_IMPLEMENTED = "CONTROL_NOT_IMPLEMENTED"
    CONTROL_NOT_VERIFIED = "CONTROL_NOT_VERIFIED"
    CONTROL_EFFECTIVENESS_UNVERIFIED = "CONTROL_EFFECTIVENESS_UNVERIFIED"
    REQUIRED_EVIDENCE_MISSING = "REQUIRED_EVIDENCE_MISSING"
    REQUIRED_EVIDENCE_UNAVAILABLE = "REQUIRED_EVIDENCE_UNAVAILABLE"
    EVIDENCE_INVALIDATED = "EVIDENCE_INVALIDATED"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    POLICY_VERSION_MISMATCH = "POLICY_VERSION_MISMATCH"
    REQUIREMENT_MAPPING_MISSING = "REQUIREMENT_MAPPING_MISSING"
    REQUIRED_REVIEW_OVERDUE = "REQUIRED_REVIEW_OVERDUE"
    APPROVAL_MISSING = "APPROVAL_MISSING"
    AUTHORIZATION_NONCONFORMANCE = "AUTHORIZATION_NONCONFORMANCE"
    AUDIT_TRACEABILITY_GAP = "AUDIT_TRACEABILITY_GAP"
    RETENTION_NONCONFORMANCE = "RETENTION_NONCONFORMANCE"
    PRIVACY_CONTROL_EXCEPTION = "PRIVACY_CONTROL_EXCEPTION"
    CROSS_WORKFLOW_INCONSISTENCY = "CROSS_WORKFLOW_INCONSISTENCY"
    ASSESSMENT_DEPENDENCY_FAILURE = "ASSESSMENT_DEPENDENCY_FAILURE"


class CompliancePriority(str, Enum):
    """Governance priority for a compliance finding."""

    ROUTINE = "ROUTINE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"
    UNCLASSIFIED = "UNCLASSIFIED"


class ComplianceReviewOutcome(str, Enum):
    """Controlled outcomes of a formal review on a compliance finding."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ADDITIONAL_EVIDENCE_REQUIRED = "ADDITIONAL_EVIDENCE_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    CORRECTIVE_ACTION_REQUIRED = "CORRECTIVE_ACTION_REQUIRED"
    SPECIALIST_REVIEW_REQUIRED = "SPECIALIST_REVIEW_REQUIRED"
    GOVERNANCE_ESCALATION_REQUIRED = "GOVERNANCE_ESCALATION_REQUIRED"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


class ComplianceFindingRecord(BaseModel):
    """Domain record representing an identified compliance gap."""

    model_config = ConfigDict(extra="ignore")

    finding_id: str = Field(default_factory=lambda: f"gfnd-{uuid.uuid4().hex[:12]}")
    assessment_id: str
    requirement_id: str
    control_id: Optional[str] = None
    gap_category: ComplianceGapCategory
    priority: CompliancePriority = CompliancePriority.HIGH
    title: str
    description: str

    evidence_refs: List[str] = Field(default_factory=list)
    source_workflow_refs: List[str] = Field(default_factory=list)
    assigned_owner_id: Optional[str] = None
    assigned_owner_role: Optional[str] = None

    # Resolution tracking
    is_resolved: bool = False
    resolution_rationale: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    # Review tracking
    review_outcome: Optional[ComplianceReviewOutcome] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_rationale: Optional[str] = None
    recommended_action: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewFindingRequest(BaseModel):
    """Request payload to conduct human governance review on a compliance finding."""

    model_config = ConfigDict(extra="ignore")

    review_outcome: ComplianceReviewOutcome
    review_rationale: str
    recommended_action: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ResolveFindingRequest(BaseModel):
    """Request payload to formally resolve a compliance finding."""

    model_config = ConfigDict(extra="ignore")

    resolution_rationale: str
    supporting_evidence_refs: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

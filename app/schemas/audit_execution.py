"""Phase 70: Audit Criteria, Evidence Requests & Test Execution Schemas.

Defines schemas for:
- Traceable audit criteria mapped to Phase 69 requirements and controls
- Structured evidence requests, submissions, and acceptance/rejection reviews
- Audit test procedures, sampling, observations, and outcomes
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ===========================================================================
# 1. Audit Criteria
# ===========================================================================

class AuditCriterionRecord(BaseModel):
    """Domain model tracking a specific evaluation criterion within an audit."""

    model_config = ConfigDict(extra="ignore")

    criterion_id: str = Field(default_factory=lambda: f"gcrt-{uuid.uuid4().hex[:12]}")
    audit_id: str
    criterion_code: str  # e.g. "CRT-SAF-001"
    title: str
    description: str

    source_framework_id: Optional[str] = None  # Phase 69 framework ref
    source_requirement_id: Optional[str] = None  # Phase 69 requirement ref
    source_control_id: Optional[str] = None  # Control ref

    expected_evidence_description: str
    sampling_strategy: Optional[str] = None
    is_active: bool = True

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateAuditCriterionRequest(BaseModel):
    """Request payload to register an audit criterion."""

    model_config = ConfigDict(extra="ignore")

    criterion_code: str
    title: str
    description: str
    source_framework_id: Optional[str] = None
    source_requirement_id: Optional[str] = None
    source_control_id: Optional[str] = None
    expected_evidence_description: str
    sampling_strategy: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ===========================================================================
# 2. Evidence Requests
# ===========================================================================

class EvidenceRequestStatus(str, Enum):
    """Lifecycle state of an audit evidence request."""

    DRAFT = "DRAFT"
    REQUESTED = "REQUESTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PARTIALLY_ACCEPTED = "PARTIALLY_ACCEPTED"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class AuditEvidenceRequestRecord(BaseModel):
    """Domain model tracking a formal evidence request directed to auditees."""

    model_config = ConfigDict(extra="ignore")

    request_id: str = Field(default_factory=lambda: f"gevq-{uuid.uuid4().hex[:12]}")
    audit_id: str
    criterion_id: Optional[str] = None
    description: str

    responsible_auditee_id: str
    responsible_auditee_role: str
    requested_by: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: Optional[datetime] = None
    status: EvidenceRequestStatus = EvidenceRequestStatus.REQUESTED

    submitted_evidence_refs: List[str] = Field(default_factory=list)
    auditee_notes: Optional[str] = None
    submission_timestamp: Optional[datetime] = None

    review_outcome: Optional[str] = None  # ACCEPTED, REJECTED, PARTIALLY_ACCEPTED
    review_comments: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateEvidenceRequest(BaseModel):
    """Request payload to issue an evidence request to an auditee."""

    model_config = ConfigDict(extra="ignore")

    criterion_id: Optional[str] = None
    description: str
    responsible_auditee_id: str
    responsible_auditee_role: str
    due_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SubmitEvidenceRequest(BaseModel):
    """Request payload for auditee to submit requested evidence."""

    model_config = ConfigDict(extra="ignore")

    submitted_evidence_refs: List[str]  # Phase 69 evidence IDs or audit artifact refs
    auditee_notes: Optional[str] = None


class ReviewEvidenceRequest(BaseModel):
    """Request payload for auditor to evaluate submitted evidence."""

    model_config = ConfigDict(extra="ignore")

    review_outcome: str  # ACCEPTED, REJECTED, PARTIALLY_ACCEPTED
    review_comments: str


# ===========================================================================
# 3. Audit Test Execution
# ===========================================================================

class AuditTestOutcome(str, Enum):
    """Outcome of an audit test procedure."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIALLY_PASSED = "PARTIALLY_PASSED"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"


class AuditTestRecord(BaseModel):
    """Domain model tracking an audit test procedure and outcome."""

    model_config = ConfigDict(extra="ignore")

    test_id: str = Field(default_factory=lambda: f"gtst-{uuid.uuid4().hex[:12]}")
    audit_id: str
    criterion_id: str
    test_procedure: str
    sampling_approach: Optional[str] = None
    sample_selection_reference: Optional[str] = None

    outcome: AuditTestOutcome = AuditTestOutcome.NOT_STARTED
    observations: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    auditor_notes: Optional[str] = None

    executed_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateAuditTestRequest(BaseModel):
    """Request payload to establish a test procedure against a criterion."""

    model_config = ConfigDict(extra="ignore")

    criterion_id: str
    test_procedure: str
    sampling_approach: Optional[str] = None
    sample_selection_reference: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ExecuteAuditTestRequest(BaseModel):
    """Request payload to record observations and outcome for an audit test."""

    model_config = ConfigDict(extra="ignore")

    outcome: AuditTestOutcome
    observations: str
    evidence_refs: Optional[List[str]] = Field(default_factory=list)
    auditor_notes: Optional[str] = None


class ReviewAuditTestRequest(BaseModel):
    """Request payload for lead auditor or reviewer to sign off on test execution."""

    model_config = ConfigDict(extra="ignore")

    review_comments: str
    confirmed_outcome: Optional[AuditTestOutcome] = None

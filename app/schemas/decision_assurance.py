"""Phase 68: Governance Decision Assurance Schemas.

Defines schemas for governance decision registration, assurance verification,
authorization integrity, and assurance lifecycle models.

Mandatory Governance Invariants:
1. A recorded decision is not automatically a valid decision.
2. A valid authentication session does not prove authorization for a specific decision.
3. A user's role does not prove authority over the specific organization, facility, or resource.
4. Historical authorization evidence cannot be inferred from current permissions.
5. Unknown authorization evidence must not be treated as valid authorization.
6. A decision assurance result does not replace clinical review.
7. A decision that fails assurance must not be silently deleted or rewritten.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AssuranceLifecycleState(str, Enum):
    """Explicit lifecycle states for Phase 68 decision assurance verification runs."""

    NOT_EVALUATED = "NOT_EVALUATED"
    PENDING = "PENDING"
    EVALUATING = "EVALUATING"
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_LIMITATIONS = "VERIFIED_WITH_LIMITATIONS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    AUTHORIZATION_UNVERIFIABLE = "AUTHORIZATION_UNVERIFIABLE"
    AUTHORIZATION_INVALID = "AUTHORIZATION_INVALID"
    SEPARATION_OF_DUTIES_VIOLATION = "SEPARATION_OF_DUTIES_VIOLATION"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    PROVENANCE_INCOMPLETE = "PROVENANCE_INCOMPLETE"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    SOURCE_VERSION_MISMATCH = "SOURCE_VERSION_MISMATCH"
    DECISION_CONFLICT = "DECISION_CONFLICT"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"
    OWNER_REVIEW_PENDING = "OWNER_REVIEW_PENDING"
    SUPERSEDED = "SUPERSEDED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


class DecisionSourcePhase(str, Enum):
    """Authoritative source safety phases that record governance decisions."""

    PHASE_49 = "PHASE_49"
    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"
    PHASE_51 = "PHASE_51"
    PHASE_51_GOVERNANCE = "PHASE_51_GOVERNANCE"
    PHASE_52 = "PHASE_52"
    PHASE_52_ASSURANCE = "PHASE_52_ASSURANCE"
    PHASE_54 = "PHASE_54"
    PHASE_54_CONTROLLED_ACTION = "PHASE_54_CONTROLLED_ACTION"
    PHASE_55 = "PHASE_55"
    PHASE_55_EFFECTIVENESS = "PHASE_55_EFFECTIVENESS"
    PHASE_58 = "PHASE_58"
    PHASE_58_VERIFICATION = "PHASE_58_VERIFICATION"
    PHASE_59 = "PHASE_59"
    PHASE_60 = "PHASE_60"
    PHASE_61 = "PHASE_61"
    PHASE_62 = "PHASE_62"
    PHASE_63 = "PHASE_63"
    PHASE_63_RISK_REVIEW = "PHASE_63_RISK_REVIEW"
    PHASE_64 = "PHASE_64"
    PHASE_64_RISK_HANDOFF = "PHASE_64_RISK_HANDOFF"
    PHASE_65 = "PHASE_65"
    PHASE_65_COMPLETION = "PHASE_65_COMPLETION"
    PHASE_66 = "PHASE_66"
    PHASE_66_POST_CLOSURE = "PHASE_66_POST_CLOSURE"
    PHASE_67 = "PHASE_67"
    PHASE_67_GOVERNANCE_ESCALATION = "PHASE_67_GOVERNANCE_ESCALATION"


class EvidenceAssuranceStatus(str, Enum):
    """Integrity status for decision-supporting evidence."""

    EVIDENCE_VALID = "EVIDENCE_VALID"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    EVIDENCE_INVALIDATED = "EVIDENCE_INVALIDATED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    EVIDENCE_PROVENANCE_INCOMPLETE = "EVIDENCE_PROVENANCE_INCOMPLETE"
    EVIDENCE_REVIEW_REQUIRED = "EVIDENCE_REVIEW_REQUIRED"


class AuthorizationVerificationStatus(str, Enum):
    """Verification outcomes for historical decision authorization."""

    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    HISTORICAL_UNVERIFIABLE = "HISTORICAL_UNVERIFIABLE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"


class SeparationOfDutiesStatus(str, Enum):
    """Verification outcome for independent review and approval separation."""

    COMPLIANT = "COMPLIANT"
    SELF_APPROVAL_DETECTED = "SELF_APPROVAL_DETECTED"
    INDEPENDENT_REVIEW_MISSING = "INDEPENDENT_REVIEW_MISSING"
    INVALID_DELEGATION = "INVALID_DELEGATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GovernanceDecisionRegisterRecord(BaseModel):
    """Logical reference record for an authoritative governance decision in the safety ecosystem."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str = Field(default_factory=lambda: f"gdr-{uuid.uuid4().hex[:12]}")
    source_phase: DecisionSourcePhase
    source_record_id: str
    source_version: str = "v1.0.0"
    decision_type: str
    decision_title: str
    decision_outcome: str

    # Tenant scoping
    organization_id: str
    facility_id: str
    patient_id: Optional[str] = None

    # Decision-maker context at decision time
    decided_by_id: str
    decided_by_role: str
    decided_by_scope: str = "facility"
    is_automated: bool = False
    service_identity: Optional[str] = None
    decided_at: datetime

    # Authoritative links & evidence
    requester_id: Optional[str] = None
    approver_id: Optional[str] = None
    authorization_evidence_ref: Optional[str] = None
    policy_reference: str = "gov-policy-v1"
    policy_version: str = "v1.0.0"
    policy_effective_date: Optional[datetime] = None
    supporting_evidence_refs: List[str] = Field(default_factory=list)
    rationale: str
    related_decision_ids: List[str] = Field(default_factory=list)

    # Status in source system
    source_status: str = "ACTIVE"
    is_superseded: bool = False
    superseded_by: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RegisterDecisionRequest(BaseModel):
    """Request payload to register a decision reference in Phase 68."""

    model_config = ConfigDict(extra="ignore")

    source_phase: DecisionSourcePhase
    source_record_id: str
    source_version: Optional[str] = "v1.0.0"
    decision_type: str
    decision_title: str
    decision_outcome: str
    decided_by_id: str
    decided_by_role: str
    decided_by_scope: Optional[str] = "facility"
    is_automated: Optional[bool] = False
    service_identity: Optional[str] = None
    decided_at: datetime
    requester_id: Optional[str] = None
    approver_id: Optional[str] = None
    authorization_evidence_ref: Optional[str] = None
    policy_reference: Optional[str] = "gov-policy-v1"
    policy_version: Optional[str] = "v1.0.0"
    policy_effective_date: Optional[datetime] = None
    supporting_evidence_refs: Optional[List[str]] = Field(default_factory=list)
    rationale: str
    patient_id: Optional[str] = None
    related_decision_ids: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DecisionAssuranceRecord(BaseModel):
    """Authoritative outcome of an assurance evaluation on a recorded governance decision."""

    model_config = ConfigDict(extra="ignore")

    assurance_id: str = Field(default_factory=lambda: f"gass-{uuid.uuid4().hex[:12]}")
    decision_id: str
    organization_id: str
    facility_id: str
    lifecycle_state: AssuranceLifecycleState = AssuranceLifecycleState.PENDING

    # Evaluation results across the 5 dimensions
    provenance_verified: bool = False
    provenance_details: Dict[str, Any] = Field(default_factory=dict)

    authorization_status: AuthorizationVerificationStatus = AuthorizationVerificationStatus.HISTORICAL_UNVERIFIABLE
    authorization_details: Dict[str, Any] = Field(default_factory=dict)

    separation_of_duties_status: SeparationOfDutiesStatus = SeparationOfDutiesStatus.NOT_APPLICABLE
    separation_details: Dict[str, Any] = Field(default_factory=dict)

    policy_compliance_verified: bool = False
    policy_details: Dict[str, Any] = Field(default_factory=dict)

    evidence_assurance_status: EvidenceAssuranceStatus = EvidenceAssuranceStatus.EVIDENCE_MISSING
    evidence_details: Dict[str, Any] = Field(default_factory=dict)

    cross_workflow_consistent: bool = True
    consistency_details: Dict[str, Any] = Field(default_factory=dict)

    # Findings summary
    findings_count: int = 0
    critical_findings_count: int = 0
    limitations: List[str] = Field(default_factory=list)
    assurance_rationale: Optional[str] = None

    evaluated_by: str = "system"
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    policy_version: str = "v1.0.0"
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TriggerDecisionAssuranceRequest(BaseModel):
    """Request payload to initiate or re-run a decision assurance verification."""

    model_config = ConfigDict(extra="ignore")

    policy_version: Optional[str] = "v1.0.0"
    verification_reason: Optional[str] = "Routine governance decision integrity verification"
    force_deep_check: bool = False
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DecisionAssuranceSummaryResponse(BaseModel):
    """High-level summary response for a decision assurance status."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str
    assurance_id: str
    lifecycle_state: AssuranceLifecycleState
    authorization_status: AuthorizationVerificationStatus
    separation_of_duties_status: SeparationOfDutiesStatus
    evidence_assurance_status: EvidenceAssuranceStatus
    cross_workflow_consistent: bool
    findings_count: int
    evaluated_at: datetime

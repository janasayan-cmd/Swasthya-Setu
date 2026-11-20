"""Phase 74: Drift, Sustainability, Exceptions & Operational Consequences Schemas.

Defines schemas and models for:
- Implementation drift signal logging, human review, and disposition
- Multi-dimensional operational sustainability assessments
- Operational exceptions lifecycle with expiry tracking
- Unintended operational consequence logging and routing to authoritative workflows (Phases 49, 54, 59, 63, 67, 72)
- Adoption escalations
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.governance_change_adoption_registration import OperationalScope


# -----------------------------------------------------------------------------
# Implementation Drift
# -----------------------------------------------------------------------------


class DriftSignalClassification(str, Enum):
    """Classification of an observed implementation drift signal."""
    POTENTIAL_DRIFT = "POTENTIAL_DRIFT"
    CONFIRMED_DEVIATION = "CONFIRMED_DEVIATION"
    INCOMPLETE_ADOPTION = "INCOMPLETE_ADOPTION"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    STALE_MONITORING = "STALE_MONITORING"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNAPPROVED_DEVIATION = "UNAPPROVED_DEVIATION"
    APPROVED_EXCEPTION = "APPROVED_EXCEPTION"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class DriftSignalStatus(str, Enum):
    """Lifecycle status of a drift signal."""
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    DISPOSED = "DISPOSED"
    ESCALATED = "ESCALATED"


class DriftDisposition(str, Enum):
    """Formal disposition recorded following human review of a drift signal."""
    CONFIRMED_DEVIATION = "CONFIRMED_DEVIATION"
    FALSE_ALARM = "FALSE_ALARM"
    APPROVED_EXCEPTION = "APPROVED_EXCEPTION"
    ACCEPTABLE_VARIATION = "ACCEPTABLE_VARIATION"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"


class ImplementationDriftSignalRecord(BaseModel):
    """Authoritative record of an implementation drift signal."""
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    registration_id: str
    tenant_id: str
    baseline_version: str
    title: str
    description: str
    classification: DriftSignalClassification = DriftSignalClassification.POTENTIAL_DRIFT
    source_type: str = "MANUAL_OBSERVATION"  # AUTOMATED_SCAN, AUDIT_EVENT, SUPERVISOR_REPORT, INCIDENT_REFERRAL, MANUAL_OBSERVATION
    observed_at: str
    evidence_reference: Optional[str] = None
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    status: DriftSignalStatus = DriftSignalStatus.OPEN
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    disposition: Optional[DriftDisposition] = None
    disposed_by: Optional[str] = None
    disposed_at: Optional[str] = None
    disposition_notes: Optional[str] = None
    created_at: str
    updated_at: str


class LogDriftSignalRequest(BaseModel):
    """Request payload to log a drift signal."""
    model_config = ConfigDict(extra="forbid")

    baseline_version: str
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    classification: DriftSignalClassification = DriftSignalClassification.POTENTIAL_DRIFT
    source_type: str = Field(default="MANUAL_OBSERVATION")
    observed_at: str
    evidence_reference: Optional[str] = None
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)


class ReviewDriftSignalRequest(BaseModel):
    """Request payload to record review of a drift signal."""
    model_config = ConfigDict(extra="forbid")

    review_notes: str = Field(..., min_length=5)


class DisposeDriftSignalRequest(BaseModel):
    """Request payload to record formal disposition of a drift signal."""
    model_config = ConfigDict(extra="forbid")

    disposition: DriftDisposition
    disposition_notes: str = Field(..., min_length=5)


# -----------------------------------------------------------------------------
# Sustainability Assessments
# -----------------------------------------------------------------------------


class SustainabilityDisposition(str, Enum):
    """Authoritative operational disposition of a sustainability evaluation."""
    SUSTAINED_ADOPTION = "SUSTAINED_ADOPTION"
    PARTIALLY_SUSTAINED = "PARTIALLY_SUSTAINED"
    NOT_SUSTAINED = "NOT_SUSTAINED"
    SUSTAINABILITY_CONCERN = "SUSTAINABILITY_CONCERN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PENDING = "PENDING"
    REQUIRES_ESCALATION = "REQUIRES_ESCALATION"


class SustainabilityAssessmentStatus(str, Enum):
    """Approval lifecycle of a sustainability assessment."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SustainabilityAssessmentRecord(BaseModel):
    """Authoritative evaluation of ongoing operational sustainability."""
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    registration_id: str
    tenant_id: str
    baseline_version: str
    monitoring_period: str
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    dimension_scores: Dict[str, str] = Field(
        default_factory=dict,
        description="Dimensions such as ownership, staff_awareness, training_maintenance, workflow_integration, evidence_continuity"
    )
    evidence_references: List[str] = Field(default_factory=list)
    unresolved_limitations: List[str] = Field(default_factory=list)
    disposition: SustainabilityDisposition = SustainabilityDisposition.PENDING
    status: SustainabilityAssessmentStatus = SustainabilityAssessmentStatus.DRAFT
    assessor_id: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_comments: Optional[str] = None
    follow_up_requirements: List[str] = Field(default_factory=list)
    clinical_safety_notice: str = (
        "Operational sustainability assessment only. Does not replace Phase 55 clinical effectiveness."
    )
    created_at: str
    updated_at: str


class CreateSustainabilityAssessmentRequest(BaseModel):
    """Request payload to create a sustainability assessment."""
    model_config = ConfigDict(extra="forbid")

    baseline_version: str
    monitoring_period: str = Field(..., min_length=3)
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    dimension_scores: Dict[str, str] = Field(default_factory=dict)
    evidence_references: List[str] = Field(default_factory=list)
    unresolved_limitations: List[str] = Field(default_factory=list)
    disposition: SustainabilityDisposition = SustainabilityDisposition.PENDING
    follow_up_requirements: List[str] = Field(default_factory=list)


class SubmitSustainabilityAssessmentRequest(BaseModel):
    """Request payload to submit a sustainability assessment for approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveSustainabilityAssessmentRequest(BaseModel):
    """Request payload to approve a sustainability assessment."""
    model_config = ConfigDict(extra="forbid")

    approval_comments: Optional[str] = None


# -----------------------------------------------------------------------------
# Adoption Exceptions
# -----------------------------------------------------------------------------


class AdoptionExceptionCategory(str, Enum):
    """Category of operational adoption exception."""
    OPERATIONAL_LIMITATION = "OPERATIONAL_LIMITATION"
    UNAVAILABLE_DEPENDENCY = "UNAVAILABLE_DEPENDENCY"
    RESOURCE_CONSTRAINT = "RESOURCE_CONSTRAINT"
    TEMPORARY_DEVIATION = "TEMPORARY_DEVIATION"
    CONFLICTING_REQUIREMENT = "CONFLICTING_REQUIREMENT"
    EVIDENCE_COLLECTION_IMPOSSIBLE = "EVIDENCE_COLLECTION_IMPOSSIBLE"
    DRIFT_EXCEPTION = "DRIFT_EXCEPTION"


class AdoptionExceptionStatus(str, Enum):
    """Lifecycle status of an adoption exception."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class AdoptionExceptionRecord(BaseModel):
    """Authoritative record for an operational adoption exception."""
    model_config = ConfigDict(extra="forbid")

    exception_id: str
    registration_id: str
    tenant_id: str
    baseline_version: str
    category: AdoptionExceptionCategory
    title: str
    description: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    risk_reference: Optional[str] = None
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    responsible_owner_id: str
    requested_duration_days: int = 30
    review_date: str
    expiry_date: Optional[str] = None
    authorization_reference: Optional[str] = None
    status: AdoptionExceptionStatus = AdoptionExceptionStatus.DRAFT
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    resolution_requirements: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CreateAdoptionExceptionRequest(BaseModel):
    """Request payload to create an adoption exception."""
    model_config = ConfigDict(extra="forbid")

    baseline_version: str
    category: AdoptionExceptionCategory
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    risk_reference: Optional[str] = None
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    responsible_owner_id: str
    requested_duration_days: int = Field(default=30, ge=1, le=365)
    review_date: str
    resolution_requirements: List[str] = Field(default_factory=list)


class SubmitAdoptionExceptionRequest(BaseModel):
    """Request payload to submit an exception for review."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ReviewAdoptionExceptionRequest(BaseModel):
    """Request payload to review an adoption exception."""
    model_config = ConfigDict(extra="forbid")

    approved: bool
    authorization_reference: Optional[str] = None
    expiry_date: Optional[str] = None
    review_notes: Optional[str] = None


class EscalateAdoptionExceptionRequest(BaseModel):
    """Request payload to escalate an exception (e.g. to Phase 67)."""
    model_config = ConfigDict(extra="forbid")

    escalation_reason: str = Field(..., min_length=5)
    destination_workflow: str = Field(default="PHASE_67_GOVERNANCE_EXCEPTION")


# -----------------------------------------------------------------------------
# Operational Consequences
# -----------------------------------------------------------------------------


class RoutingDestination(str, Enum):
    """Authoritative destination workflows for unintended operational consequences."""
    PHASE_49_INCIDENTS = "PHASE_49_INCIDENTS"
    PHASE_54_CAPA = "PHASE_54_CAPA"
    PHASE_59_SURVEILLANCE = "PHASE_59_SURVEILLANCE"
    PHASE_63_RISK_REVIEW = "PHASE_63_RISK_REVIEW"
    PHASE_67_GOVERNANCE_EXCEPTION = "PHASE_67_GOVERNANCE_EXCEPTION"
    PHASE_72_MANAGEMENT_REVIEW = "PHASE_72_MANAGEMENT_REVIEW"
    PHASE_73_IMPLEMENTATION = "PHASE_73_IMPLEMENTATION"


class ConsequenceSeverity(str, Enum):
    """Severity classification of an unintended consequence."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConsequenceStatus(str, Enum):
    """Status of an unintended consequence."""
    REPORTED = "REPORTED"
    UNDER_EVALUATION = "UNDER_EVALUATION"
    ROUTED = "ROUTED"
    RESOLVED = "RESOLVED"


class OperationalConsequenceRecord(BaseModel):
    """Record of an unintended operational consequence routed to existing authoritative workflows."""
    model_config = ConfigDict(extra="forbid")

    consequence_id: str
    registration_id: str
    tenant_id: str
    title: str
    description: str
    severity: ConsequenceSeverity = ConsequenceSeverity.MEDIUM
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    reported_by: str
    reported_at: str
    status: ConsequenceStatus = ConsequenceStatus.REPORTED
    routed_destination: Optional[RoutingDestination] = None
    destination_reference: Optional[str] = None
    routing_notes: Optional[str] = None
    routed_by: Optional[str] = None
    routed_at: Optional[str] = None
    created_at: str
    updated_at: str


class ReportConsequenceRequest(BaseModel):
    """Request payload to report an unintended operational consequence."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    severity: ConsequenceSeverity = ConsequenceSeverity.MEDIUM
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)


class RouteConsequenceRequest(BaseModel):
    """Request payload to route a consequence to an authoritative workflow."""
    model_config = ConfigDict(extra="forbid")

    routed_destination: RoutingDestination
    destination_reference: str = Field(..., min_length=2)
    routing_notes: str = Field(..., min_length=5)


# -----------------------------------------------------------------------------
# Adoption Escalations
# -----------------------------------------------------------------------------


class EscalationUrgency(str, Enum):
    """Urgency level of an adoption escalation."""
    ROUTINE = "ROUTINE"
    PRIORITY = "PRIORITY"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class AdoptionEscalationRecord(BaseModel):
    """Authoritative record for an adoption-level escalation."""
    model_config = ConfigDict(extra="forbid")

    escalation_id: str
    registration_id: str
    tenant_id: str
    title: str
    reason: str
    urgency: EscalationUrgency = EscalationUrgency.PRIORITY
    escalated_to_destination: str = "MANAGEMENT_REVIEW"
    escalated_by: str
    escalated_at: str
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved: bool = False
    created_at: str
    updated_at: str


class CreateAdoptionEscalationRequest(BaseModel):
    """Request payload to create an adoption escalation."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=255)
    reason: str = Field(..., min_length=5)
    urgency: EscalationUrgency = EscalationUrgency.PRIORITY
    escalated_to_destination: str = Field(default="MANAGEMENT_REVIEW")

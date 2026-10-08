"""Phase 62: Clinical Safety Risk Signal Consolidation, Cross-Domain Correlation & Governed Risk Assessment Schemas.

Non-Negotiable Architectural Invariants:
- FINDING != RISK
- RISK INDICATOR != CONFIRMED RISK
- RISK ASSESSMENT != INCIDENT INVESTIGATION
- RISK ASSESSMENT != ROOT CAUSE ANALYSIS
- RISK ASSESSMENT != CLINICAL DIAGNOSIS
- RISK ASSESSMENT != TREATMENT DECISION
- CORRELATION != CAUSATION
- PATTERN != INCIDENT
- FREQUENCY != SEVERITY
- SYSTEM RISK != PATIENT RISK
- AI ASSESSMENT != GOVERNED DECISION
- RISK PRIORITY != CLINICAL URGENCY
- UNKNOWN / INSUFFICIENT_DATA / CONFLICTED != SAFE
- ABSENCE OF RISK INDICATOR != ABSENCE OF RISK
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssessmentLifecycleState(str, Enum):
    """Lifecycle states of cross-domain safety risk assessment."""

    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    ELIGIBLE = "ELIGIBLE"
    GROUPING = "GROUPING"
    CONSOLIDATED = "CONSOLIDATED"
    PARTIALLY_CONSOLIDATED = "PARTIALLY_CONSOLIDATED"
    CONFLICTED = "CONFLICTED"
    ASSESSMENT_NOT_READY = "ASSESSMENT_NOT_READY"
    ASSESSMENT_READY = "ASSESSMENT_READY"
    ASSESSMENT_BLOCKED = "ASSESSMENT_BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    ROUTING_REQUIRED = "ROUTING_REQUIRED"
    ROUTED = "ROUTED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class FindingEligibilityStatus(str, Enum):
    """Eligibility status of an input finding entering Phase 62 consolidation."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    DUPLICATE = "DUPLICATE"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    PRIVACY_RESTRICTED = "PRIVACY_RESTRICTED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    INVALID_PROVENANCE = "INVALID_PROVENANCE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CrossDomainCorrelationOutcome(str, Enum):
    """Cross-domain correlation relationship strength."""

    STRONGLY_RELATED = "STRONGLY_RELATED"
    POSSIBLY_RELATED = "POSSIBLY_RELATED"
    WEAKLY_RELATED = "WEAKLY_RELATED"
    NOT_RELATED = "NOT_RELATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED = "CONFLICTED"


class EvidenceReconciliationState(str, Enum):
    """Reconciliation status across diverse authoritative evidence sources."""

    CONSISTENT = "CONSISTENT"
    PARTIALLY_CONSISTENT = "PARTIALLY_CONSISTENT"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    SCOPE_CONFLICT = "SCOPE_CONFLICT"
    PROVENANCE_CONFLICT = "PROVENANCE_CONFLICT"


class AssessmentReadinessState(str, Enum):
    """Readiness of consolidated risk context for authoritative governed assessment."""

    ASSESSMENT_NOT_READY = "ASSESSMENT_NOT_READY"
    ASSESSMENT_READY = "ASSESSMENT_READY"
    ASSESSMENT_BLOCKED = "ASSESSMENT_BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    CONFLICT_REQUIRES_REVIEW = "CONFLICT_REQUIRES_REVIEW"


class RiskPriority(str, Enum):
    """System and governance routing priority (NOT clinical triage emergency)."""

    ROUTINE = "ROUTINE"
    REVIEW = "REVIEW"
    HIGH_PRIORITY_REVIEW = "HIGH_PRIORITY_REVIEW"
    URGENT_GOVERNANCE_REVIEW = "URGENT_GOVERNANCE_REVIEW"
    CRITICAL_ESCALATION = "CRITICAL_ESCALATION"
    UNKNOWN_PRIORITY = "UNKNOWN_PRIORITY"


class RiskUncertaintyState(str, Enum):
    """Uncertainty quantification of consolidated risk context."""

    LOW_UNCERTAINTY = "LOW_UNCERTAINTY"
    MODERATE_UNCERTAINTY = "MODERATE_UNCERTAINTY"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED_EVIDENCE = "CONFLICTED_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class HumanRiskReviewDecision(str, Enum):
    """Human review outcomes for governed safety risk assessment."""

    ACKNOWLEDGE = "ACKNOWLEDGE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    REASSESS = "REASSESS"
    ESCALATE = "ESCALATE"
    ROUTE_TO_INCIDENT = "ROUTE_TO_INCIDENT"
    ROUTE_TO_ASSURANCE = "ROUTE_TO_ASSURANCE"
    ROUTE_TO_EFFECTIVENESS = "ROUTE_TO_EFFECTIVENESS"
    ROUTE_TO_GOVERNANCE = "ROUTE_TO_GOVERNANCE"
    ROUTE_TO_ACTION = "ROUTE_TO_ACTION"
    ROUTE_TO_LEARNING = "ROUTE_TO_LEARNING"
    ROUTE_TO_IMPROVEMENT = "ROUTE_TO_IMPROVEMENT"
    REJECT_RISK_CHARACTERIZATION = "REJECT_RISK_CHARACTERIZATION"


class RiskRoutingDestination(str, Enum):
    """Authoritative downstream destinations for consolidated risk findings."""

    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    PHASE_60_REASSESSMENT = "PHASE_60_REASSESSMENT"
    PHASE_61_REANALYSIS = "PHASE_61_REANALYSIS"
    PHASE_59_SURVEILLANCE = "PHASE_59_SURVEILLANCE"
    PHASE_49_INCIDENT_REVIEW = "PHASE_49_INCIDENT_REVIEW"
    PHASE_52_ASSURANCE_REVIEW = "PHASE_52_ASSURANCE_REVIEW"
    PHASE_55_EFFECTIVENESS_REVIEW = "PHASE_55_EFFECTIVENESS_REVIEW"
    PHASE_51_GOVERNANCE_REVIEW = "PHASE_51_GOVERNANCE_REVIEW"
    PHASE_54_CONTROLLED_ACTION_REVIEW = "PHASE_54_CONTROLLED_ACTION_REVIEW"
    PHASE_50_SAFETY_LEARNING = "PHASE_50_SAFETY_LEARNING"
    PHASE_56_SAFETY_IMPROVEMENT = "PHASE_56_SAFETY_IMPROVEMENT"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    MULTI_ROUTE = "MULTI_ROUTE"
    BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# Scope & Finding Models
# ---------------------------------------------------------------------------


class RiskAssessmentScope(BaseModel):
    """Operational scope boundary for safety risk assessment."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    department: Optional[str] = None
    workflow: Optional[str] = None
    safety_control_id: Optional[str] = None
    version: Optional[str] = None
    environment: str = "production"
    rollout_id: Optional[str] = None
    change_id: Optional[str] = None


class ConsolidatedSourceFindingReference(BaseModel):
    """Preserved source finding from Phase 60, Phase 61, or upstream safety phases."""

    model_config = ConfigDict(extra="ignore")

    finding_id: str
    source_phase: str = "PHASE_61"
    finding_type: str = "PATTERN"
    title: str = "Surveillance Finding"
    description: str = ""
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "v1.0.0"
    eligibility_status: FindingEligibilityStatus = FindingEligibilityStatus.ELIGIBLE
    eligibility_reason: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CrossDomainCorrelationLink(BaseModel):
    """Cross-domain relationship connecting distinct safety entities."""

    model_config = ConfigDict(extra="ignore")

    link_id: str = Field(default_factory=lambda: f"lnk-{uuid.uuid4().hex[:8]}")
    source_domain: str
    target_domain: str
    dimension: str
    relationship: CrossDomainCorrelationOutcome = CrossDomainCorrelationOutcome.STRONGLY_RELATED
    confidence: float = 1.0
    uncertainty: RiskUncertaintyState = RiskUncertaintyState.LOW_UNCERTAINTY
    evidence_references: List[str] = Field(default_factory=list)
    analytical_note: str = (
        "Cross-domain correlation indicates shared architectural context and does not prove causation."
    )


class ReconciledEvidenceItem(BaseModel):
    """Authoritative evidence item evaluated for consistency."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: f"evd-{uuid.uuid4().hex[:8]}")
    source_phase: str
    source_record_id: str
    status: str = "VALIDATED"
    is_conflicted: bool = False
    reconciliation_state: EvidenceReconciliationState = EvidenceReconciliationState.CONSISTENT
    description: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsolidatedRiskContext(BaseModel):
    """Consolidated representation of multiple related analytical findings."""

    model_config = ConfigDict(extra="ignore")

    context_id: str = Field(default_factory=lambda: f"ctx-{uuid.uuid4().hex[:8]}")
    concern_summary: str
    affected_scope: RiskAssessmentScope
    observation_window_hours: float = 720.0
    supporting_finding_ids: List[str] = Field(default_factory=list)
    counter_evidence_ids: List[str] = Field(default_factory=list)
    reconciliation_state: EvidenceReconciliationState = EvidenceReconciliationState.CONSISTENT
    assurance_status: Optional[str] = None
    effectiveness_status: Optional[str] = None
    incident_references: List[str] = Field(default_factory=list)
    surveillance_status: str = "ACTIVE"
    analytical_note: str = (
        "Consolidated risk context represents systemic evidence and is not a clinical diagnosis or incident investigation."
    )


class GovernedRiskCharacterization(BaseModel):
    """Categorical risk characterization under approved safety governance."""

    model_config = ConfigDict(extra="ignore")

    characterization_id: str = Field(default_factory=lambda: f"rc-{uuid.uuid4().hex[:8]}")
    primary_category: str = "SAFETY_CONTROL_INTEGRITY"
    persistence: str = "RECURRENT"
    recurrence_count: int = 1
    system_severity: str = "HIGH"
    evidence_strength: str = "STRONG"
    exposure: str = "LOCALIZED"
    priority: RiskPriority = RiskPriority.HIGH_PRIORITY_REVIEW
    notes: Optional[str] = None


class RiskAssessmentReviewRecord(BaseModel):
    """Human review disposition record for governed risk assessment."""

    model_config = ConfigDict(extra="ignore")

    review_id: str = Field(default_factory=lambda: f"rev-{uuid.uuid4().hex[:8]}")
    reviewed_by: str
    reviewer_role: str
    decision: HumanRiskReviewDecision
    reason: str
    resulting_routes: List[RiskRoutingDestination] = Field(default_factory=list)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_ai_agent: bool = False


class RiskAssessmentRoutingRecord(BaseModel):
    """Record dispatching consolidated risk findings to authoritative downstream phases."""

    model_config = ConfigDict(extra="ignore")

    routing_id: str = Field(default_factory=lambda: f"rtg-{uuid.uuid4().hex[:8]}")
    destination: RiskRoutingDestination
    status: str = "ROUTED"
    routed_by: str
    reason: str
    routed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target_reference: Optional[str] = None
    target_phase: str = "PHASE_UNKNOWN"


class RiskAssessmentHistoryEntry(BaseModel):
    """Immutable audit entry in the risk assessment lifecycle."""

    model_config = ConfigDict(extra="ignore")

    entry_id: str = Field(default_factory=lambda: f"hst-{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    actor_id: str
    actor_role: str
    previous_state: Optional[str] = None
    new_state: str
    details: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Primary Aggregate Record
# ---------------------------------------------------------------------------


class SafetyRiskAssessmentRecord(BaseModel):
    """Aggregate record representing a cross-domain safety risk assessment."""

    model_config = ConfigDict(extra="ignore")

    assessment_id: str = Field(default_factory=lambda: f"sra-{uuid.uuid4().hex[:10]}")
    organization_id: str
    scope: RiskAssessmentScope
    lifecycle_state: AssessmentLifecycleState = AssessmentLifecycleState.RECEIVED
    readiness_state: AssessmentReadinessState = AssessmentReadinessState.ASSESSMENT_NOT_READY

    source_findings: List[ConsolidatedSourceFindingReference] = Field(default_factory=list)
    excluded_findings: List[ConsolidatedSourceFindingReference] = Field(default_factory=list)
    correlations: List[CrossDomainCorrelationLink] = Field(default_factory=list)
    evidence_items: List[ReconciledEvidenceItem] = Field(default_factory=list)

    risk_context: Optional[ConsolidatedRiskContext] = None
    characterization: Optional[GovernedRiskCharacterization] = None

    overall_uncertainty: RiskUncertaintyState = RiskUncertaintyState.LOW_UNCERTAINTY
    requires_human_review: bool = False
    requires_escalation: bool = False
    requires_reassessment: bool = False
    has_unresolved_conflicts: bool = False

    reviews: List[RiskAssessmentReviewRecord] = Field(default_factory=list)
    routings: List[RiskAssessmentRoutingRecord] = Field(default_factory=list)
    history: List[RiskAssessmentHistoryEntry] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    idempotency_key: Optional[str] = None
    version: str = "v1.0.0"


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------


class CreateRiskAssessmentRequest(BaseModel):
    """Request payload to initiate a cross-domain risk assessment."""

    model_config = ConfigDict(extra="ignore")

    assessment_id: Optional[str] = None
    scope: Optional[RiskAssessmentScope] = None
    findings: Optional[List[Dict[str, Any]]] = None
    purpose: str = "CROSS_DOMAIN_RISK_CONSOLIDATION"
    idempotency_key: Optional[str] = None
    version: str = "v1.0.0"


class ConsolidateFindingsRequest(BaseModel):
    """Request payload to consolidate source findings into risk context."""

    model_config = ConfigDict(extra="ignore")

    concern_summary: Optional[str] = None


class ReconcileEvidenceRequest(BaseModel):
    """Request payload to reconcile evidence and identify inconsistencies."""

    model_config = ConfigDict(extra="ignore")

    external_evidence: Optional[List[Dict[str, Any]]] = None


class ExecuteRiskAssessmentRequest(BaseModel):
    """Request payload to execute governed risk characterization."""

    model_config = ConfigDict(extra="ignore")

    is_async: bool = False


class ReviewRiskAssessmentRequest(BaseModel):
    """Request payload for human safety risk assessment review."""

    model_config = ConfigDict(extra="ignore")

    decision: HumanRiskReviewDecision
    reason: str
    resulting_routes: Optional[List[RiskRoutingDestination]] = None
    is_ai: bool = False


class RouteRiskAssessmentRequest(BaseModel):
    """Request payload to route assessment to authoritative downstream phases."""

    model_config = ConfigDict(extra="ignore")

    destinations: List[RiskRoutingDestination]
    reason: str
    target_reference: Optional[str] = None


class ReassessRiskAssessmentRequest(BaseModel):
    """Request payload to request Phase 60 reassessment for source signals."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    signal_ids: Optional[List[str]] = None


class ReanalyzeRiskAssessmentRequest(BaseModel):
    """Request payload to request Phase 61 reanalysis for source findings."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    finding_ids: Optional[List[str]] = None

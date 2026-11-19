"""Phase 67: Governance Exception and Ingestion Schemas.

Defines schemas for normalized cross-workflow governance exceptions, classification,
provenance preservation, and aggregation contracts.

Mandatory Governance Invariants:
1. An escalation is not automatically a confirmed incident.
2. A high-priority exception does not independently establish clinical severity.
3. Resolving one finding does not automatically resolve related findings.
4. A governance escalation cannot override an authoritative decision owned by another phase.
5. Missing, unavailable, or contradictory information must remain visible.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ExceptionCategory(str, Enum):
    """Controlled exception categories for Phase 67 governance exceptions."""

    UNRESOLVED_SAFETY_FINDING = "UNRESOLVED_SAFETY_FINDING"
    MATERIAL_INTEGRITY_CHANGE = "MATERIAL_INTEGRITY_CHANGE"
    CONFLICTING_AUTHORITATIVE_DECISIONS = "CONFLICTING_AUTHORITATIVE_DECISIONS"
    RISK_DISPOSITION_REVIEW_REQUIRED = "RISK_DISPOSITION_REVIEW_REQUIRED"
    HANDOFF_OUTCOME_CONFLICT = "HANDOFF_OUTCOME_CONFLICT"
    COMPLETION_REQUIREMENT_BLOCKED = "COMPLETION_REQUIREMENT_BLOCKED"
    POST_CLOSURE_REASSESSMENT_REQUIRED = "POST_CLOSURE_REASSESSMENT_REQUIRED"
    REQUIRED_APPROVAL_OVERDUE = "REQUIRED_APPROVAL_OVERDUE"
    GOVERNANCE_ACTION_FAILED = "GOVERNANCE_ACTION_FAILED"
    EFFECTIVENESS_REVIEW_FAILED = "EFFECTIVENESS_REVIEW_FAILED"
    ASSURANCE_REVIEW_BLOCKED = "ASSURANCE_REVIEW_BLOCKED"
    INCIDENT_ESCALATION_REQUIRED = "INCIDENT_ESCALATION_REQUIRED"
    SURVEILLANCE_THRESHOLD_ESCALATION = "SURVEILLANCE_THRESHOLD_ESCALATION"
    AUTHORIZATION_CONFLICT = "AUTHORIZATION_CONFLICT"
    EVIDENCE_INTEGRITY_EXCEPTION = "EVIDENCE_INTEGRITY_EXCEPTION"
    POLICY_COMPLIANCE_EXCEPTION = "POLICY_COMPLIANCE_EXCEPTION"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    MANUAL_GOVERNANCE_REVIEW = "MANUAL_GOVERNANCE_REVIEW"


class GovernancePriority(str, Enum):
    """Governance routing priority levels. Distinct from clinical severity."""

    ROUTINE = "ROUTINE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"
    UNCLASSIFIED = "UNCLASSIFIED"


class ExceptionSourcePhase(str, Enum):
    """Authoritative source phases that can emit or originate governance exceptions."""

    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"
    PHASE_51_GOVERNANCE = "PHASE_51_GOVERNANCE"
    PHASE_52_ASSURANCE = "PHASE_52_ASSURANCE"
    PHASE_54_CONTROLLED_ACTION = "PHASE_54_CONTROLLED_ACTION"
    PHASE_55_EFFECTIVENESS = "PHASE_55_EFFECTIVENESS"
    PHASE_58_VERIFICATION = "PHASE_58_VERIFICATION"
    PHASE_59_SURVEILLANCE = "PHASE_59_SURVEILLANCE"
    PHASE_60_TRIAGE = "PHASE_60_TRIAGE"
    PHASE_62_RISK_CONTEXT = "PHASE_62_RISK_CONTEXT"
    PHASE_63_RISK_REVIEW = "PHASE_63_RISK_REVIEW"
    PHASE_64_HANDOFF = "PHASE_64_HANDOFF"
    PHASE_65_COMPLETION = "PHASE_65_COMPLETION"
    PHASE_66_POST_CLOSURE = "PHASE_66_POST_CLOSURE"
    MANUAL = "MANUAL"


class ExceptionLifecycleState(str, Enum):
    """Lifecycle status of a governance exception record."""

    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    RECONCILED = "RECONCILED"
    DISMISSED = "DISMISSED"
    SUPERSEDED = "SUPERSEDED"


class GovernanceExceptionRecord(BaseModel):
    """Normalized domain record for an authoritative governance exception."""

    model_config = ConfigDict(extra="ignore")

    exception_id: str = Field(default_factory=lambda: f"gex-{uuid.uuid4().hex[:12]}")
    escalation_id: Optional[str] = None
    category: ExceptionCategory
    source_phase: ExceptionSourcePhase
    source_record_id: str
    source_version: str = "v1.0.0"

    # Scoping
    organization_id: str
    facility_id: str
    patient_id: Optional[str] = None

    # Priority & Severity
    source_severity: str = "MEDIUM"
    governance_priority: GovernancePriority = GovernancePriority.UNCLASSIFIED
    lifecycle_state: ExceptionLifecycleState = ExceptionLifecycleState.ACTIVE

    # Context & Materiality
    title: str
    description: str
    is_material: bool = True
    materiality_rationale: Optional[str] = None
    policy_reference: str = "gov-policy-v1"
    policy_version: str = "v1.0.0"

    # Cross-workflow linkages
    related_workflow_ids: List[str] = Field(default_factory=list)
    dependency_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)

    # Resolution
    resolution_status: str = "UNRESOLVED"
    resolved_at: Optional[datetime] = None
    resolution_rationale: Optional[str] = None

    # Audit & Provenance
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestGovernanceExceptionRequest(BaseModel):
    """Request payload to ingest a governance exception into Phase 67."""

    model_config = ConfigDict(extra="ignore")

    category: ExceptionCategory
    source_phase: ExceptionSourcePhase
    source_record_id: str
    source_version: Optional[str] = "v1.0.0"
    source_severity: Optional[str] = "MEDIUM"
    title: str
    description: str
    is_material: bool = True
    materiality_rationale: Optional[str] = None
    policy_reference: Optional[str] = "gov-policy-v1"
    policy_version: Optional[str] = "v1.0.0"
    patient_id: Optional[str] = None
    related_workflow_ids: Optional[List[str]] = Field(default_factory=list)
    dependency_refs: Optional[List[str]] = Field(default_factory=list)
    evidence_refs: Optional[List[str]] = Field(default_factory=list)
    escalation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReviewGovernanceExceptionRequest(BaseModel):
    """Request payload to record an evaluation or review on a governance exception."""

    model_config = ConfigDict(extra="ignore")

    new_state: ExceptionLifecycleState
    rationale: str
    dismissal_reason: Optional[str] = None
    reconciliation_evidence: Optional[List[str]] = Field(default_factory=list)


class ExceptionAggregationRequest(BaseModel):
    """Request payload to aggregate exceptions into a target escalation."""

    model_config = ConfigDict(extra="ignore")

    exception_ids: List[str]
    aggregation_reason: str


class ExceptionSeparationRequest(BaseModel):
    """Request payload to separate an incorrectly grouped exception."""

    model_config = ConfigDict(extra="ignore")

    exception_id: str
    separation_reason: str
    new_escalation_required: bool = False

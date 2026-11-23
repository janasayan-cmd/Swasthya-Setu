"""Phase 87: Disruption Impact Assessment Schemas.

Defines schemas for evaluating the direct and indirect impacts of a disruption
on critical governance capabilities, responsibilities, resources, and continuity objectives.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_disruption_common import (
    MANDATORY_DISRUPTION_IMPACT_DISCLAIMER,
    AssessmentReviewStatus,
    ImpactCertainty,
    ImpactSeverity,
)


class DirectImpactFinding(BaseModel):
    finding_id: str
    resource_id: str
    resource_name: Optional[str] = None
    affected_capability_ref: str
    affected_responsibility_ref: Optional[str] = None
    dependency_type: str
    severity: ImpactSeverity = ImpactSeverity.HIGH
    certainty: ImpactCertainty = ImpactCertainty.POTENTIAL
    operating_capacity_remaining_pct: Optional[float] = None
    fallback_available: bool = False
    fallback_resource_id: Optional[str] = None
    fallback_readiness: Optional[str] = None
    explanation: str
    evidence_refs: List[str] = Field(default_factory=list)


class IndirectImpactFinding(BaseModel):
    finding_id: str
    root_resource_id: str
    intermediate_resource_id: str
    affected_capability_ref: str
    affected_responsibility_ref: Optional[str] = None
    propagation_hops: int = 1
    severity: ImpactSeverity = ImpactSeverity.MEDIUM
    certainty: ImpactCertainty = ImpactCertainty.CONDITIONAL
    explanation: str
    evidence_refs: List[str] = Field(default_factory=list)


class DisruptionImpactAssessmentRecord(BaseModel):
    assessment_id: str
    tenant_id: str
    scenario_id: str
    assessment_name: str
    dependency_graph_version: str = "1.0"
    assessment_timestamp: datetime = Field(default_factory=datetime.utcnow)
    affected_capability_refs: List[str] = Field(default_factory=list)
    affected_responsibility_refs: List[str] = Field(default_factory=list)
    affected_resource_refs: List[str] = Field(default_factory=list)
    direct_findings: List[DirectImpactFinding] = Field(default_factory=list)
    indirect_findings: List[IndirectImpactFinding] = Field(default_factory=list)
    potential_operational_consequences: List[str] = Field(default_factory=list)
    available_fallback_refs: List[str] = Field(default_factory=list)
    remaining_limitations: List[str] = Field(default_factory=list)
    uncertainty_indicators: List[str] = Field(default_factory=list)
    evidence_freshness_hours: Optional[float] = None
    mtpd_exceeded: bool = False
    rto_exceeded: bool = False
    evidence_refs: List[str] = Field(default_factory=list)
    overall_impact_severity: ImpactSeverity = ImpactSeverity.HIGH
    review_status: AssessmentReviewStatus = AssessmentReviewStatus.DRAFT
    assessment_version: int = 1
    assessed_by: str
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    challenge_notes: Optional[str] = None
    challenged_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class CreateImpactAssessmentRequest(BaseModel):
    scenario_id: str
    assessment_name: str
    dependency_graph_version: str = "1.0"


class RunImpactAssessmentRequest(BaseModel):
    include_indirect_dependencies: bool = True
    max_propagation_depth: int = Field(default=3, ge=1, le=10)
    override_duration_hours: Optional[float] = None


class AssessmentReviewRequest(BaseModel):
    review_status: AssessmentReviewStatus  # e.g. APPROVED or CHALLENGED
    review_notes: str
    approval_ref: Optional[str] = None


class AssessmentChallengeRequest(BaseModel):
    challenge_notes: str
    evidence_refs: List[str] = Field(default_factory=list)


class AssessmentEvidenceRequest(BaseModel):
    requested_evidence_description: str
    target_capabilities: List[str] = Field(default_factory=list)

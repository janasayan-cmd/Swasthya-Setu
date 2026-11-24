"""Phase 88: Recovery Recommendation, Management Decision & Continuity Handoff Schemas.

Defines schemas for preparing recovery recommendation packages, submitting them to Phase 72
Management Review, and handing approved strategies over to Phase 80 Continuity Operations.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    ContinuityHandoffStatus,
    RecommendationLifecycleStatus,
)


class ManagementDecisionOutcomeRecord(BaseModel):
    decision_reference_id: str
    decision_status: str  # APPROVED, REJECTED, MODIFIED, DEFERRED
    decision_maker_ref: str
    decision_timestamp: datetime = Field(default_factory=datetime.utcnow)
    decision_rationale: str
    approved_option_id: Optional[str] = None
    stipulations: List[str] = Field(default_factory=list)


class ContinuityHandoffRecord(BaseModel):
    handoff_id: str
    tenant_id: str
    recommendation_id: str
    approved_decision_ref: str
    selected_strategy_id: str
    source_scenario_id: Optional[str] = None
    source_impact_assessment_id: Optional[str] = None
    approved_recovery_sequence_id: Optional[str] = None
    required_resource_refs: List[str] = Field(default_factory=list)
    required_role_refs: List[str] = Field(default_factory=list)
    authorization_prerequisites: List[str] = Field(default_factory=list)
    operational_limitations: List[str] = Field(default_factory=list)
    status: ContinuityHandoffStatus = ContinuityHandoffStatus.PREPARED
    handoff_timestamp: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledgement_timestamp: Optional[datetime] = None
    receiving_continuity_workflow_ref: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class RecoveryRecommendationRecord(BaseModel):
    recommendation_id: str
    tenant_id: str
    recommendation_name: str
    impact_assessment_id: Optional[str] = None
    comparison_id: Optional[str] = None
    recommended_option_id: str
    alternative_option_ids: List[str] = Field(default_factory=list)
    executive_summary: str
    feasibility_findings: List[str] = Field(default_factory=list)
    resource_requirements: List[str] = Field(default_factory=list)
    known_limitations: List[str] = Field(default_factory=list)
    unresolved_assumptions: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    lifecycle_status: RecommendationLifecycleStatus = RecommendationLifecycleStatus.DRAFT
    prepared_by: str
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    challenge_notes: Optional[str] = None
    challenged_by: Optional[str] = None
    management_decision_submission_id: Optional[str] = None
    management_decision: Optional[ManagementDecisionOutcomeRecord] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class CreateRecoveryRecommendationRequest(BaseModel):
    recommendation_name: str
    impact_assessment_id: Optional[str] = None
    comparison_id: Optional[str] = None
    recommended_option_id: str
    alternative_option_ids: List[str] = Field(default_factory=list)
    executive_summary: str


class SubmitRecommendationReviewRequest(BaseModel):
    submission_notes: Optional[str] = None


class ChallengeRecommendationRequest(BaseModel):
    challenge_notes: str
    evidence_refs: List[str] = Field(default_factory=list)


class SubmitRecommendationDecisionRequest(BaseModel):
    management_review_cycle_ref: str
    notes: Optional[str] = None


class CreateContinuityHandoffRequest(BaseModel):
    recommendation_id: str
    approved_decision_ref: str
    selected_strategy_id: str


class AcknowledgeContinuityHandoffRequest(BaseModel):
    receiving_continuity_workflow_ref: str
    acknowledgement_notes: Optional[str] = None

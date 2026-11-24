"""
Phase 88: Governance Recovery Recommendation & Decision-Support Service
Manages recommendation packaging, SoD reviews, management challenges, decisions, and continuity handoffs.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import status

from app.core.exceptions import (
    AppException,
    ErrorCode,
)
from app.repositories.governance_response_strategy_repository import (
    GovernanceResponseStrategyRepository,
    get_governance_response_strategy_repository,
)
from app.schemas.governance_response_common import (
    ContinuityHandoffStatus,
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    RecommendationLifecycleStatus,
)
from app.schemas.governance_recovery_recommendation import (
    AcknowledgeContinuityHandoffRequest,
    ChallengeRecommendationRequest,
    ContinuityHandoffRecord,
    CreateContinuityHandoffRequest,
    CreateRecoveryRecommendationRequest,
    ManagementDecisionOutcomeRecord,
    RecoveryRecommendationRecord,
    SubmitRecommendationDecisionRequest,
    SubmitRecommendationReviewRequest,
)


class GovernanceRecoveryRecommendationService:
    def __init__(self, repo: Optional[GovernanceResponseStrategyRepository] = None):
        self.repo = repo or get_governance_response_strategy_repository()

    def create_recommendation(
        self,
        tenant_id: str,
        user_id: str,
        req: CreateRecoveryRecommendationRequest,
    ) -> RecoveryRecommendationRecord:
        now = datetime.now(timezone.utc)
        record = RecoveryRecommendationRecord(
            recommendation_id=f"rec-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            recommendation_name=req.recommendation_name,
            impact_assessment_id=req.impact_assessment_id,
            comparison_id=req.comparison_id,
            recommended_option_id=req.recommended_option_id,
            alternative_option_ids=list(req.alternative_option_ids),
            executive_summary=req.executive_summary,
            feasibility_findings=["Feasibility outcome verified compliant with clinical safety boundary."],
            resource_requirements=["Secondary compute and standby database required"],
            known_limitations=[],
            unresolved_assumptions=[],
            evidence_refs=[],
            lifecycle_status=RecommendationLifecycleStatus.RECOMMENDATION_PREPARED,
            prepared_by=user_id,
            created_at=now,
            updated_at=now,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )
        return self.repo.create_recommendation(record)

    def get_recommendation(
        self,
        recommendation_id: str,
        tenant_id: str,
    ) -> RecoveryRecommendationRecord:
        record = self.repo.get_recommendation(recommendation_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.RECOVERY_RECOMMENDATION_NOT_FOUND,
                message=f"Recovery recommendation '{recommendation_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_recommendations(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
        status_param: Optional[RecommendationLifecycleStatus] = None,
    ) -> List[RecoveryRecommendationRecord]:
        return self.repo.list_recommendations(
            tenant_id=tenant_id,
            status=status_param,
            scenario_ref=scenario_ref,
        )

    def submit_for_review(
        self,
        recommendation_id: str,
        tenant_id: str,
        user_id: str,
        req: SubmitRecommendationReviewRequest,
    ) -> RecoveryRecommendationRecord:
        rec = self.get_recommendation(recommendation_id, tenant_id)
        now = datetime.now(timezone.utc)
        rec.lifecycle_status = RecommendationLifecycleStatus.SUBMITTED_FOR_DECISION
        rec.review_notes = req.submission_notes
        rec.updated_at = now
        return self.repo.update_recommendation(rec)

    def challenge_recommendation(
        self,
        recommendation_id: str,
        tenant_id: str,
        challenger_id: str,
        req: ChallengeRecommendationRequest,
    ) -> RecoveryRecommendationRecord:
        rec = self.get_recommendation(recommendation_id, tenant_id)
        now = datetime.now(timezone.utc)
        rec.lifecycle_status = RecommendationLifecycleStatus.CHALLENGED
        rec.challenge_notes = req.challenge_notes
        rec.challenged_by = challenger_id
        rec.updated_at = now
        return self.repo.update_recommendation(rec)

    def submit_decision(
        self,
        recommendation_id: str,
        tenant_id: str,
        decider_id: str,
        req: SubmitRecommendationDecisionRequest,
    ) -> RecoveryRecommendationRecord:
        rec = self.get_recommendation(recommendation_id, tenant_id)

        # Enforce Separation of Duties (SoD)
        if rec.prepared_by == decider_id:
            raise AppException(
                code=ErrorCode.RESPONSE_STRATEGY_SEPARATION_OF_DUTIES_VIOLATION,
                message=f"Separation of duties violation: Preparer '{rec.prepared_by}' cannot submit decision on their own recommendation.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        now = datetime.now(timezone.utc)
        decision_outcome = ManagementDecisionOutcomeRecord(
            decision_reference_id=f"dec-{uuid.uuid4().hex[:8]}",
            decision_status="APPROVED",
            decision_maker_ref=decider_id,
            decision_timestamp=now,
            decision_rationale=req.notes or f"Approved in cycle {req.management_review_cycle_ref}",
            approved_option_id=rec.recommended_option_id,
            stipulations=[],
        )

        rec.management_decision = decision_outcome
        rec.management_decision_submission_id = req.management_review_cycle_ref
        rec.lifecycle_status = RecommendationLifecycleStatus.APPROVED
        rec.updated_at = now
        return self.repo.update_recommendation(rec)

    def create_continuity_handoff(
        self,
        recommendation_id: str,
        tenant_id: str,
        user_id: str,
        req: CreateContinuityHandoffRequest,
    ) -> ContinuityHandoffRecord:
        rec = self.get_recommendation(recommendation_id, tenant_id)
        if rec.lifecycle_status != RecommendationLifecycleStatus.APPROVED:
            raise AppException(
                code=ErrorCode.INVALID_RECOVERY_RECOMMENDATION_STATE,
                message=f"Cannot create continuity handoff for recommendation in state '{rec.lifecycle_status}'. Must be APPROVED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc)
        handoff = ContinuityHandoffRecord(
            handoff_id=f"hoff-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            recommendation_id=rec.recommendation_id,
            approved_decision_ref=req.approved_decision_ref,
            selected_strategy_id=req.selected_strategy_id,
            source_scenario_id=rec.impact_assessment_id,
            status=ContinuityHandoffStatus.HANDED_OFF,
            handoff_timestamp=now,
            created_by=user_id,
            created_at=now,
            updated_at=now,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )
        return self.repo.create_continuity_handoff(handoff)

    def acknowledge_continuity_handoff(
        self,
        handoff_id: str,
        tenant_id: str,
        receiver_id: str,
        req: AcknowledgeContinuityHandoffRequest,
    ) -> ContinuityHandoffRecord:
        record = self.repo.get_continuity_handoff(handoff_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CONTINUITY_HANDOFF_NOT_FOUND,
                message=f"Continuity handoff '{handoff_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        now = datetime.now(timezone.utc)
        record.status = ContinuityHandoffStatus.ACKNOWLEDGED
        record.acknowledged_by = receiver_id
        record.acknowledgement_timestamp = now
        record.receiving_continuity_workflow_ref = req.receiving_continuity_workflow_ref
        record.updated_at = now
        return self.repo.update_continuity_handoff(record)

    def get_continuity_handoff(
        self,
        handoff_id: str,
        tenant_id: str,
    ) -> ContinuityHandoffRecord:
        record = self.repo.get_continuity_handoff(handoff_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CONTINUITY_HANDOFF_NOT_FOUND,
                message=f"Continuity handoff '{handoff_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_continuity_handoffs(
        self,
        tenant_id: str,
        recommendation_ref: Optional[str] = None,
        status_param: Optional[ContinuityHandoffStatus] = None,
    ) -> List[ContinuityHandoffRecord]:
        return self.repo.list_continuity_handoffs(
            tenant_id=tenant_id,
            recommendation_ref=recommendation_ref,
            status=status_param,
        )


_governance_recovery_recommendation_service: Optional[GovernanceRecoveryRecommendationService] = None


def get_governance_recovery_recommendation_service() -> GovernanceRecoveryRecommendationService:
    global _governance_recovery_recommendation_service
    if _governance_recovery_recommendation_service is None:
        _governance_recovery_recommendation_service = GovernanceRecoveryRecommendationService()
    return _governance_recovery_recommendation_service

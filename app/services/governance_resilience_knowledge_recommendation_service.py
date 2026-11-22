"""Phase 83: Capability Development Recommendation Service.

Manages proactive advisory recommendations for continuous preparedness capability
development, targeted drills, training, and institutional strengthening.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_knowledge_repository import (
    GovernanceResilienceKnowledgeRepository,
    get_governance_resilience_knowledge_repository,
)
from app.schemas.governance_resilience_knowledge_recommendations import (
    CapabilityActivityType,
    ProposeCapabilityRecommendationRequest,
    RecommendationPriority,
    RecommendationStatus,
    ResilienceCapabilityRecommendationRecord,
    UpdateRecommendationStatusRequest,
)


class GovernanceResilienceKnowledgeRecommendationService:
    """Service managing capability development recommendations for continuous preparedness."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    def propose_recommendation(
        self,
        tenant_id: str,
        user_id: str,
        request: ProposeCapabilityRecommendationRequest,
    ) -> ResilienceCapabilityRecommendationRecord:
        rec_id = f"rcr-{uuid.uuid4().hex[:10]}"
        rec = ResilienceCapabilityRecommendationRecord(
            recommendation_id=rec_id,
            tenant_id=tenant_id,
            activity_type=request.activity_type,
            priority=request.priority,
            title=request.title,
            rationalization=request.rationalization,
            target_capabilities=request.target_capabilities,
            target_roles=request.target_roles,
            target_facilities=request.target_facilities,
            linked_learning_gap_ids=request.linked_learning_gap_ids,
            linked_knowledge_ids=request.linked_knowledge_ids,
            status=RecommendationStatus.PROPOSED,
            proposed_by=user_id,
        )
        return self.repository.save_recommendation(rec)

    def get_recommendation(
        self, tenant_id: str, recommendation_id: str
    ) -> ResilienceCapabilityRecommendationRecord:
        rec = self.repository.get_recommendation(recommendation_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CAPABILITY_RECOMMENDATION_NOT_FOUND,
                message=f"Capability development recommendation '{recommendation_id}' not found.",
                status_code=404,
            )
        return rec

    def update_recommendation_status(
        self,
        tenant_id: str,
        recommendation_id: str,
        user_id: str,
        request: UpdateRecommendationStatusRequest,
    ) -> ResilienceCapabilityRecommendationRecord:
        rec = self.get_recommendation(tenant_id, recommendation_id)

        rec.status = request.status
        if request.notes:
            rec.completion_notes = request.notes
        if request.scheduled_date:
            rec.scheduled_date = request.scheduled_date
        if request.status == RecommendationStatus.COMPLETED:
            rec.completed_at = datetime.utcnow()
        elif request.status == RecommendationStatus.ACCEPTED:
            rec.approved_by = user_id

        return self.repository.save_recommendation(rec)

    def list_recommendations(
        self,
        tenant_id: str,
        status: Optional[RecommendationStatus] = None,
        activity_type: Optional[CapabilityActivityType] = None,
        priority: Optional[RecommendationPriority] = None,
    ) -> List[ResilienceCapabilityRecommendationRecord]:
        return self.repository.list_recommendations(
            tenant_id=tenant_id,
            status=status,
            activity_type=activity_type,
            priority=priority,
        )


_recommendation_service = GovernanceResilienceKnowledgeRecommendationService()


def get_governance_resilience_knowledge_recommendation_service() -> GovernanceResilienceKnowledgeRecommendationService:
    return _recommendation_service

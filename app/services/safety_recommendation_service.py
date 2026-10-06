"""Phase 50: Safety Learning Recommendation Service.

Generates structured preventive improvement candidates, manages recommendation
lifecycles, enforces human-review gates, and prevents AI autonomous approval.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import (
    AISafetyLearningAuthorityProhibitedException,
    SafetyLearningInvalidStateException,
    SafetyLearningNotFoundException,
    SafetyLearningResultStaleException,
)
from app.repositories.safety_learning_repository import (
    SafetyLearningRepository,
    safety_learning_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.safety_recommendation import (
    RecommendationReviewRequest,
    RecommendationStatus,
    RecommendationType,
    SafetyRecommendation,
)
from app.services.audit_service import AuditService, audit_service

logger = logging.getLogger("app.safety_recommendation_service")


class SafetyRecommendationService:
    """Service governing safety-learning candidate recommendations and human-review workflows."""

    def __init__(
        self,
        repository: Optional[SafetyLearningRepository] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_learning_repository
        self.audit_service = audit_svc or audit_service

    def create_recommendation(
        self,
        recommendation_type: RecommendationType,
        title: str,
        description: str,
        rationale_summary: str,
        affected_subsystem: str,
        analysis_id: Optional[str] = None,
        pattern_id: Optional[str] = None,
        evidence_references: Optional[List[Dict[str, Any]]] = None,
    ) -> SafetyRecommendation:
        """Create a candidate preventive improvement in REVIEW_REQUIRED state."""
        rec = SafetyRecommendation(
            analysis_id=analysis_id,
            pattern_id=pattern_id,
            recommendation_type=recommendation_type,
            title=title,
            description=description,
            rationale_summary=rationale_summary,
            affected_subsystem=affected_subsystem,
            status=RecommendationStatus.REVIEW_REQUIRED,
            evidence_references=evidence_references or [],
            limitations=[
                "Analytical recommendation only. Does not constitute deployment or clinical instruction.",
                "Subject to human review and controlled change governance.",
            ],
        )
        return self.repository.save_recommendation(rec)

    async def review_recommendation(
        self,
        recommendation_id: str,
        request: RecommendationReviewRequest,
        reviewer_id: str,
        reviewer_role: str,
        request_id: Optional[str] = None,
    ) -> SafetyRecommendation:
        """Human safety officer review of a candidate recommendation."""
        rec = self.repository.get_recommendation(recommendation_id)
        if not rec:
            raise SafetyLearningNotFoundException(f"Recommendation '{recommendation_id}' not found.")

        # Guard: AI cannot autonomously approve/reject recommendations
        if "AI" in reviewer_role.upper() or "BOT" in reviewer_role.upper() or "MODEL" in reviewer_role.upper():
            raise AISafetyLearningAuthorityProhibitedException(
                "AI agents cannot review or approve safety learning recommendations. Human officer review required."
            )

        now = datetime.now(timezone.utc)
        # Check staleness
        if now - rec.created_at > timedelta(days=settings.SAFETY_LEARNING_STALE_EVALUATION_DAYS):
            rec.status = RecommendationStatus.STALE
            self.repository.save_recommendation(rec)
            raise SafetyLearningResultStaleException(
                f"Recommendation '{recommendation_id}' is older than {settings.SAFETY_LEARNING_STALE_EVALUATION_DAYS} days and is marked STALE. Re-analysis required."
            )

        decision_upper = request.decision.upper()
        if decision_upper == "ACCEPT":
            rec.status = RecommendationStatus.ACCEPTED
            event_type = AuditEventType.SAFETY_LEARNING_RECOMMENDATION_ACCEPTED
        elif decision_upper == "REJECT":
            rec.status = RecommendationStatus.REJECTED
            event_type = AuditEventType.SAFETY_LEARNING_RECOMMENDATION_REJECTED
        else:
            rec.status = RecommendationStatus.DEFERRED
            event_type = AuditEventType.SAFETY_LEARNING_RECOMMENDATION_REVIEWED

        rec.reviewed_by_id = reviewer_id
        rec.reviewed_by_role = reviewer_role
        rec.reviewed_at = now
        rec.review_notes = request.notes
        rec.updated_at = now

        self.repository.save_recommendation(rec)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=event_type,
                    outcome="ALLOW",
                    actor_id=reviewer_id,
                    action=f"safety_learning:recommendation:{decision_upper.lower()}",
                    resource_type="safety_recommendation",
                    resource_id=rec.id,
                    metadata={
                        "recommendation_id": rec.id,
                        "decision": decision_upper,
                        "recommendation_type": rec.recommendation_type.value,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for recommendation review %s: %s", rec.id, ex)

        return rec

    def get_recommendation(self, rec_id: str) -> Optional[SafetyRecommendation]:
        """Retrieve recommendation by ID."""
        return self.repository.get_recommendation(rec_id)

    def list_recommendations(self) -> List[SafetyRecommendation]:
        """List all recommendations."""
        return self.repository.list_recommendations()


# Global singleton
safety_recommendation_service = SafetyRecommendationService()

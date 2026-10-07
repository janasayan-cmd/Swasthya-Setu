"""Phase 55: Action Effectiveness Human Review Service.

Governs human oversight sign-off on effectiveness determinations.
Enforces separation of duties and strictly prevents AI agents from finalizing decisions.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    EffectivenessEvaluationRecord,
    EffectivenessLifecycleState,
    EffectivenessState,
    HumanReviewOutcome,
    HumanReviewRecord,
)


class ActionEffectivenessReviewService:
    """Service for processing and recording human review decisions."""

    def process_review(
        self,
        evaluation: EffectivenessEvaluationRecord,
        reviewer_id: str,
        reviewer_role: str,
        decision: HumanReviewOutcome,
        rationale: str,
        limitations: Optional[str] = None,
        is_ai_agent: bool = False,
    ) -> EffectivenessEvaluationRecord:
        """Process human review decision and transition evaluation state."""
        if is_ai_agent:
            raise AppException(
                code=ErrorCode.REVIEW_DENIED,
                message="AI agents cannot submit or authorize human oversight reviews.",
                status_code=403,
            )

        if not reviewer_id:
            raise AppException(
                code=ErrorCode.REVIEW_DENIED,
                message="Reviewer ID must be provided.",
                status_code=400,
            )

        if not rationale or len(rationale.strip()) < 10:
            raise AppException(
                code=ErrorCode.REVIEW_DENIED,
                message="Review rationale must be at least 10 characters.",
                status_code=400,
            )

        review_record = HumanReviewRecord(
            review_id=f"rev-{uuid.uuid4().hex[:8]}",
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            rationale=rationale.strip(),
            limitations=limitations,
            evidence_references=[e.evidence_id for e in evaluation.evidence_items],
            created_at=datetime.now(timezone.utc),
        )
        evaluation.reviews.append(review_record)
        evaluation.requires_human_review = False

        if decision in (HumanReviewOutcome.ACCEPT, HumanReviewOutcome.ACCEPT_WITH_LIMITATIONS):
            evaluation.lifecycle_state = EffectivenessLifecycleState.EFFECTIVENESS_ACCEPTED
            evaluation.is_sustained = True
        elif decision == HumanReviewOutcome.REQUEST_MORE_EVIDENCE:
            evaluation.lifecycle_state = EffectivenessLifecycleState.EVIDENCE_COLLECTION
            evaluation.effectiveness_state = EffectivenessState.EVIDENCE_PENDING
        elif decision in (HumanReviewOutcome.REASSESS, HumanReviewOutcome.ESCALATE):
            evaluation.lifecycle_state = EffectivenessLifecycleState.REQUIRES_REASSESSMENT
            evaluation.effectiveness_state = EffectivenessState.REQUIRES_REASSESSMENT
        elif decision == HumanReviewOutcome.REJECT:
            evaluation.lifecycle_state = EffectivenessLifecycleState.FAILED
            evaluation.effectiveness_state = EffectivenessState.FAILED
        elif decision == HumanReviewOutcome.REOPEN:
            evaluation.lifecycle_state = EffectivenessLifecycleState.REOPENED
            evaluation.reopened_count += 1

        evaluation.version += 1
        evaluation.updated_at = datetime.now(timezone.utc)
        return evaluation

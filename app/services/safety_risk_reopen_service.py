"""Phase 63: Clinical Safety Risk Review Reopen Service.

Orchestrates reopening of completed reviews upon receipt of material new evidence,
surveillance triggers, or failed follow-ups. Preserves prior disposition and history.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_review import (
    ReviewHistoryEntry,
    ReviewLifecycleState,
    SafetyRiskReviewRecord,
)
from app.schemas.user import AuthenticatedUserContext


class SafetyRiskReopenService:
    """Manages reopening completed reviews while preserving historical decisions."""

    @classmethod
    def reopen_review(
        cls,
        review: SafetyRiskReviewRecord,
        reason: str,
        user: AuthenticatedUserContext,
        new_evidence_reference: Optional[str] = None,
    ) -> SafetyRiskReviewRecord:
        """Reopen a completed review under governed policy."""
        if review.state not in (ReviewLifecycleState.COMPLETED, ReviewLifecycleState.FOLLOW_UP_REQUIRED, ReviewLifecycleState.MONITORING):
            raise AppException(
                code=ErrorCode.INVALID_REVIEW_STATE,
                message=f"Cannot reopen review in state '{review.state.value}'. Only completed, monitoring, or follow-up reviews can be reopened.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_EVIDENCE,
                message="Substantive reasoning is required to reopen a closed risk review.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        prev_state = review.state
        review.state = ReviewLifecycleState.REVIEW_IN_PROGRESS
        review.is_reopened = True
        review.reopen_count += 1
        review.reopen_reason = reason

        history_entry = ReviewHistoryEntry(
            from_state=prev_state,
            to_state=ReviewLifecycleState.REVIEW_IN_PROGRESS,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="REOPEN_REVIEW",
            details={
                "reason": reason,
                "new_evidence_reference": new_evidence_reference,
                "reopen_count": review.reopen_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        review.history.append(history_entry)

        return review

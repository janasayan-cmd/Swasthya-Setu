"""Phase 63: Clinical Safety Risk Reassessment Service.

Orchestrates reassessment requests when new evidence, version shifts, scope changes,
or surveillance indicators invalidate existing risk context assumptions.
Preserves historical reviews immutably.
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


class SafetyRiskReassessmentService:
    """Manages governed reassessment triggers and history preservation."""

    @classmethod
    def request_reassessment(
        cls,
        review: SafetyRiskReviewRecord,
        reason: str,
        user: AuthenticatedUserContext,
    ) -> SafetyRiskReviewRecord:
        """Flag review for reassessment without overwriting existing audit history."""
        if not reason or len(reason.strip()) < 5:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_EVIDENCE,
                message="Substantive reasoning is required to trigger risk reassessment.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        prev_state = review.state
        review.state = ReviewLifecycleState.REASSESSMENT_REQUIRED
        review.requires_reassessment = True

        history_entry = ReviewHistoryEntry(
            from_state=prev_state,
            to_state=ReviewLifecycleState.REASSESSMENT_REQUIRED,
            actor_id=user.user_id,
            actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            action="REQUEST_REASSESSMENT",
            details={"reason": reason, "timestamp": datetime.now(timezone.utc).isoformat()},
        )
        review.history.append(history_entry)

        return review

"""Phase 65: Safety Completion Review Service.

Processes completion review submissions and enforces separation of duties.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.safety_completion_review import (
    CompletionReviewDecision,
    CompletionReviewRecord,
    SubmitCompletionReviewRequest,
)
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext


class SafetyCompletionReviewService:
    """Manages governed review submissions and reviewer authorization."""

    @staticmethod
    def process_review(
        completion: SafetyWorkflowCompletionRecord,
        request: SubmitCompletionReviewRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionReviewRecord:
        """Validate and record an authorized completion review."""
        # 1. State check: Must be in a reviewable state
        valid_states = {
            CompletionLifecycleState.READY,
            CompletionLifecycleState.READY_WITH_LIMITATIONS,
            CompletionLifecycleState.REVIEW_PENDING,
            CompletionLifecycleState.REVIEW_IN_PROGRESS,
        }
        if completion.state not in valid_states and completion.readiness_state not in ("READY", "READY_WITH_LIMITATIONS"):
            raise AppException(
                code=ErrorCode.COMPLETION_NOT_READY,
                message=f"Cannot review workflow in state '{completion.state.value}'. Must be READY or READY_WITH_LIMITATIONS.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Separation of Duties: Preparer cannot be the Reviewer
        if completion.created_by == user.user_id and user.role != UserRole.ADMIN:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Separation of duties violation: The completion preparer cannot act as the completion reviewer.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 3. Role check: Must be Doctor or Admin
        if user.role not in (UserRole.ADMIN, UserRole.DOCTOR):
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Only authorized clinical safety reviewers or administrators may review completion workflows.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 4. Prohibited claims acknowledgment
        if not request.acknowledged_prohibited_claims:
            raise AppException(
                code=ErrorCode.COMPLETION_BLOCKED,
                message="Review rejected: Acknowledgment of non-negotiable architectural safety invariants is mandatory.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Build review record
        review_record = CompletionReviewRecord(
            completion_id=completion.completion_id,
            reviewer_id=user.user_id,
            reviewer_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            decision=request.decision,
            reasoning=request.reasoning,
            limitations=request.limitations or [],
            action_items=request.action_items or [],
            package_revision=f"v{completion.version}.0.0",
            reviewed_at=datetime.now(timezone.utc),
            metadata=request.metadata or {},
        )

        # 6. Advance lifecycle state
        if request.decision in (CompletionReviewDecision.APPROVED, CompletionReviewDecision.APPROVED_WITH_LIMITATIONS):
            completion.state = CompletionLifecycleState.COMPLETION_AUTHORIZATION_PENDING
        elif request.decision == CompletionReviewDecision.REJECTED:
            completion.state = CompletionLifecycleState.BLOCKED
            completion.blocking_reason = f"Review rejected by {user.user_id}: {request.reasoning}"
        elif request.decision == CompletionReviewDecision.REASSESSMENT_REQUIRED:
            completion.state = CompletionLifecycleState.REASSESSMENT_REQUIRED
        else:
            completion.state = CompletionLifecycleState.NOT_READY

        completion.reviewed_at = datetime.now(timezone.utc)
        completion.review = review_record.model_dump()
        completion.history.append({
            "action": "COMPLETION_REVIEW_SUBMITTED",
            "actor_id": user.user_id,
            "decision": request.decision.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return review_record

"""Phase 65: Safety Completion Reopen Service.

Handles post-closure workflow reopening while strictly preserving closure history.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.safety_completion_action import (
    CompletionReopenRecord,
    ReopenCompletionWorkflowRequest,
)
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext


class SafetyCompletionReopenService:
    """Manages governed reopening of closed coordination workflows."""

    VALID_REOPEN_TRIGGERS = {
        "MATERIAL_NEW_OUTCOME",
        "INVALIDATED_OUTCOME",
        "CONFLICTED_EVIDENCE",
        "DESTINATION_WORKFLOW_REOPENED",
        "SOURCE_DISPOSITION_SUPERSEDED",
        "FOLLOW_UP_FAILED",
        "SIGNIFICANT_POST_CLOSURE_SIGNAL",
        "COMPLETION_PACKAGE_INCORRECT",
        "REASSESSMENT_REQUESTED",
    }

    @staticmethod
    def process_reopen(
        completion: SafetyWorkflowCompletionRecord,
        request: ReopenCompletionWorkflowRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionReopenRecord:
        """Validate and execute controlled workflow reopening."""
        # 1. State check: Must be CLOSED, POST_CLOSURE_MONITORING, or REOPEN_REQUIRED
        valid_reopenable_states = {
            CompletionLifecycleState.CLOSED,
            CompletionLifecycleState.POST_CLOSURE_MONITORING,
            CompletionLifecycleState.REOPEN_REQUIRED,
            CompletionLifecycleState.STALE,
        }
        if completion.state not in valid_reopenable_states:
            raise AppException(
                code=ErrorCode.INVALID_COMPLETION_STATE,
                message=f"Workflow in state '{completion.state.value}' cannot be reopened.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Trigger check
        if request.reopen_trigger not in SafetyCompletionReopenService.VALID_REOPEN_TRIGGERS:
            raise AppException(
                code=ErrorCode.COMPLETION_BLOCKED,
                message=f"Invalid reopen trigger: '{request.reopen_trigger}'. Must be an authorized trigger.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Role check
        if user.role not in (UserRole.ADMIN, UserRole.DOCTOR):
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Only administrators or clinical reviewers may reopen closed safety workflows.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 4. Build reopen record preserving closure reference
        closure_id = completion.closure.get("closure_id") if completion.closure else None
        reopen_record = CompletionReopenRecord(
            completion_id=completion.completion_id,
            previous_state=completion.state.value,
            reopened_by=user.user_id,
            reopened_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            reason=request.reason,
            reopen_trigger=request.reopen_trigger,
            reopened_at=datetime.now(timezone.utc),
            preserved_closure_id=closure_id,
            metadata=request.metadata or {},
        )

        # 5. Transition state
        completion.state = CompletionLifecycleState.REOPENED
        completion.readiness_state = "REASSESSMENT_REQUIRED"
        completion.reopened_at = datetime.now(timezone.utc)
        completion.reopen_history.append(reopen_record.model_dump())
        completion.history.append({
            "action": "WORKFLOW_REOPENED",
            "actor_id": user.user_id,
            "trigger": request.reopen_trigger,
            "preserved_closure_id": closure_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return reopen_record

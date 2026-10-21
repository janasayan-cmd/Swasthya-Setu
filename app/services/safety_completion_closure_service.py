"""Phase 65: Safety Completion Closure Service.

Executes controlled workflow closure and establishes post-closure monitoring linkages.
Non-Negotiable Invariants:
- WORKFLOW CLOSURE != RISK ACCEPTANCE (Phase 51 owns risk acceptance)
- WORKFLOW CLOSURE != EFFECTIVENESS CONFIRMATION (Phase 55 owns effectiveness)
- WORKFLOW CLOSURE != INCIDENT CLOSURE (Phase 49 owns incident closure)
- WORKFLOW CLOSURE != SAFETY ASSURANCE (Phase 52 owns safety assurance)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.safety_completion_action import (
    CloseCompletionWorkflowRequest,
    CompletionClosureRecord,
)
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext


class SafetyCompletionClosureService:
    """Manages controlled closure of safety completion coordination workflows."""

    @staticmethod
    def process_closure(
        completion: SafetyWorkflowCompletionRecord,
        request: CloseCompletionWorkflowRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionClosureRecord:
        """Validate and execute controlled workflow closure."""
        # 1. State check: Must be in CLOSURE_PENDING (cannot bypass readiness/review/authorization)
        if completion.state == CompletionLifecycleState.CLOSED:
            raise AppException(
                code=ErrorCode.COMPLETION_ALREADY_CLOSED,
                message="Workflow is already closed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if completion.state != CompletionLifecycleState.CLOSURE_PENDING:
            raise AppException(
                code=ErrorCode.COMPLETION_AUTHORIZATION_REQUIRED,
                message=(
                    f"Workflow in state '{completion.state.value}' cannot be closed directly. "
                    "Readiness evaluation, approved review, and completion authorization are mandatory first."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Invariants acknowledgment
        if not request.acknowledged_closure_invariants:
            raise AppException(
                code=ErrorCode.COMPLETION_BLOCKED,
                message="Closure rejected: Acknowledging that workflow closure does not equal risk acceptance or clinical safety guarantee is mandatory.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Role check: Admin only
        if user.role != UserRole.ADMIN:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Only administrators may close a clinical safety coordination workflow.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 4. Build closure record
        closure_record = CompletionClosureRecord(
            completion_id=completion.completion_id,
            closed_by=user.user_id,
            closed_by_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            closed_at=datetime.now(timezone.utc),
            post_closure_monitoring_registered=request.post_closure_monitoring_registered,
            monitoring_reference=request.monitoring_reference,
            closure_notes=request.closure_notes,
            metadata=request.metadata or {},
        )

        # 5. Transition state
        if request.post_closure_monitoring_registered:
            completion.state = CompletionLifecycleState.POST_CLOSURE_MONITORING
        else:
            completion.state = CompletionLifecycleState.CLOSED

        completion.closed_at = datetime.now(timezone.utc)
        completion.closure = closure_record.model_dump()
        completion.history.append({
            "action": "WORKFLOW_CLOSED",
            "actor_id": user.user_id,
            "post_closure_monitoring": request.post_closure_monitoring_registered,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return closure_record

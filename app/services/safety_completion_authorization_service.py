"""Phase 65: Safety Completion Authorization Service.

Records authoritative completion authorization decisions and enforces separation of duties.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.safety_completion_action import (
    AuthorizeCompletionRequest,
    CompletionAuthorizationRecord,
)
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext


class SafetyCompletionAuthorizationService:
    """Manages governed completion authorization."""

    @staticmethod
    def process_authorization(
        completion: SafetyWorkflowCompletionRecord,
        request: AuthorizeCompletionRequest,
        user: AuthenticatedUserContext,
    ) -> CompletionAuthorizationRecord:
        """Validate and record completion authorization."""
        # 1. State check: Must be in COMPLETION_AUTHORIZATION_PENDING
        if completion.state != CompletionLifecycleState.COMPLETION_AUTHORIZATION_PENDING:
            raise AppException(
                code=ErrorCode.COMPLETION_REVIEW_REQUIRED,
                message=(
                    f"Workflow in state '{completion.state.value}' cannot be authorized. "
                    "Approved completion review is required first."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Separation of Duties: Reviewer cannot be Authorizer (unless explicitly ADMIN with override)
        reviewer_id = completion.review.get("reviewer_id") if completion.review else None
        if reviewer_id and reviewer_id == user.user_id and user.role != UserRole.ADMIN:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Separation of duties violation: The completion reviewer cannot also act as the authorizer.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 3. Role check: Must be Admin or specialized Clinical Safety Officer
        if user.role != UserRole.ADMIN:
            raise AppException(
                code=ErrorCode.ACCESS_DENIED,
                message="Only authorized administrators may grant completion authorization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # 4. Limitations check
        if completion.readiness_state == "READY_WITH_LIMITATIONS" and not request.permit_limitations:
            raise AppException(
                code=ErrorCode.COMPLETION_BLOCKED,
                message="Authorization rejected: Workflow has documented limitations but 'permit_limitations' was not set.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Build authorization record
        auth_record = CompletionAuthorizationRecord(
            completion_id=completion.completion_id,
            authorizer_id=user.user_id,
            authorizer_role=user.role.value if hasattr(user.role, "value") else str(user.role),
            authorized_at=datetime.now(timezone.utc),
            permit_limitations=request.permit_limitations,
            explicit_waivers=request.explicit_waivers or [],
            authorizer_notes=request.authorizer_notes,
            package_revision=f"v{completion.version}.0.0",
            metadata=request.metadata or {},
        )

        completion.state = CompletionLifecycleState.CLOSURE_PENDING
        completion.authorized_at = datetime.now(timezone.utc)
        completion.authorization = auth_record.model_dump()
        completion.history.append({
            "action": "COMPLETION_AUTHORIZED",
            "actor_id": user.user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return auth_record

"""Phase 54: Safety Action Approval Service.

Manages human governance reviews, approval envelopes, validity windows,
and stale approval invalidations.

Core Invariants:
- RECOMMENDATION != DECISION
- DECISION != APPROVAL
- APPROVAL != EXECUTION
- AI CANNOT APPROVE ACTIONS
- A STALE APPROVAL MUST NOT AUTHORIZE EXECUTION
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_action import (
    ActionApprovalDecision,
    ActionApprovalRecord,
    ActionApprovalState,
    ActionLifecycleState,
    SafetyActionApproveRequest,
    SafetyActionRecord,
)


class SafetyActionApprovalService:
    """Governs approval workflows and temporal validity of safety action authorizations."""

    def submit_approval(
        self,
        action: SafetyActionRecord,
        request: SafetyActionApproveRequest,
        approver_id: str,
        approver_role: str,
    ) -> ActionApprovalRecord:
        """Process a formal human approval decision."""
        # AI caller restriction (Section 35)
        if "AI" in approver_role.upper() or approver_id.startswith("ai-"):
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_APPROVAL_DENIED,
                message="AI agents are strictly prohibited from approving safety actions.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=request.validity_hours or 168)

        state = (
            ActionApprovalState.APPROVED
            if request.decision == ActionApprovalDecision.APPROVE
            else ActionApprovalState.REJECTED
        )

        approval = ActionApprovalRecord(
            action_version=action.material_version,
            approver_id=approver_id,
            approver_role=approver_role,
            decision=request.decision,
            reason=request.reason,
            limitations=request.limitations,
            approved_at=now,
            expires_at=expires_at,
            state=state,
        )

        return approval

    def check_approval_freshness(self, action: SafetyActionRecord) -> None:
        """Verify that an action has a valid, non-stale, non-expired approval."""
        if not action.approval:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_APPROVAL_REQUIRED,
                message="Action requires explicit human approval prior to execution.",
                status_code=400,
            )

        if action.approval.state != ActionApprovalState.APPROVED:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_APPROVAL_DENIED,
                message=f"Action approval is in non-executable state: {action.approval.state.value}.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        if action.approval.expires_at and now > action.approval.expires_at:
            action.approval.state = ActionApprovalState.EXPIRED
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_APPROVAL_STALE,
                message="Action approval has expired. Re-approval required.",
                status_code=409,
            )

        if action.approval.action_version < action.material_version or action.approval.state == ActionApprovalState.STALE:
            action.approval.state = ActionApprovalState.STALE
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_APPROVAL_STALE,
                message=f"Approval version ({action.approval.action_version}) is stale compared to material action version ({action.material_version}).",
                status_code=409,
            )


# Global singleton
safety_action_approval_service = SafetyActionApprovalService()

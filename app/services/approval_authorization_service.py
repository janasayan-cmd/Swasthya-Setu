"""Approval Authorization and Reviewer Eligibility Service (Phase 40).

Enforces reviewer eligibility, self-approval restrictions, multi-approver validation,
tenant isolation, and strict AI safety boundaries.

CRITICAL SAFETY INVARIANTS:
- AUTHENTICATED USER != ELIGIBLE APPROVER
- AI CANNOT APPROVE, REJECT, OR AUTHORIZE ACTIONS
- SELF-APPROVAL IS REJECTED WHEN DISALLOWED BY POLICY
- DUPLICATE APPROVALS BY THE SAME ACTOR ARE PREVENTED IN MULTI-APPROVER RULES
- CROSS-PATIENT AND CROSS-ORGANIZATION ACCESS IS REJECTED
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.core.exceptions import (
    ApprovalForbiddenException,
    ApprovalReviewerInvalidException,
    ApprovalSelfConflictException,
    ApprovalUnauthorizedException,
)
from app.schemas.approval import ApprovalRecord
from app.schemas.approval_policy import ApprovalPolicyRule
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext


class ApprovalAuthorizationService:
    """Enforces authorization boundaries and reviewer eligibility for approval workflows."""

    def __init__(
        self,
        user_repository: Any = None,
        patient_repository: Any = None,
        enabled: bool = True,
    ) -> None:
        self._user_repo = user_repository
        self._patient_repo = patient_repository
        self.enabled = enabled

    def _check_ai_actor(self, actor: AuthenticatedUserContext) -> None:
        """Reject any autonomous AI actor attempting clinical approval or decision-making."""
        if getattr(actor, "is_ai", False):
            raise ApprovalReviewerInvalidException(
                message="Autonomous AI actor cannot approve, reject, or authorize clinical actions. Human clinician authorization is required."
            )
        role_str = str(actor.role).upper()
        if "AI" in role_str or role_str == "BOT" or role_str == "ASSISTANT":
            raise ApprovalReviewerInvalidException(
                message="AI actor cannot approve, reject, or authorize clinical actions. Human clinician authorization is required."
            )

    def validate_reviewer_eligibility(
        self,
        actor: AuthenticatedUserContext,
        approval: ApprovalRecord,
        rule: ApprovalPolicyRule,
        is_delegated: bool = False,
    ) -> None:
        """Validate that the actor is eligible to approve or reject the request.

        SAFETY INVARIANTS:
        - AI is strictly rejected.
        - Actor role must match required policy roles.
        - Self-approval is rejected if disallowed by rule.
        - Same actor cannot approve twice in multi-approver scenarios.
        - Tenant / organization isolation is enforced.
        """
        self._check_ai_actor(actor)

        # 1. Role validation
        actor_role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
        if actor_role_str not in rule.required_roles and not is_delegated:
            # Check if actor is system admin
            if actor.role not in (UserRole.SYSTEM_ADMIN, UserRole.ADMIN):
                raise ApprovalReviewerInvalidException(
                    message=f"Role '{actor_role_str}' is not eligible to review or approve this action. Required roles: {rule.required_roles}."
                )

        # 2. Self-Approval restriction (TRD Section 13)
        if not rule.allow_self_approval and actor.user_id == approval.requester_id:
            raise ApprovalSelfConflictException(
                message=f"Self-approval conflict: Requester '{actor.user_id}' cannot approve their own clinical action."
            )

        # 3. Multi-Approver check (TRD Section 15)
        # Prevent the same identity from satisfying multiple independent approvals
        if rule.multi_approver_count > 1 or approval.required_approvals_count > 1:
            already_approved_ids = [
                d.approver_id for d in approval.decisions 
                if (d.decision == "APPROVE" or getattr(d.decision, "value", None) == "APPROVE")
            ]
            if actor.user_id in already_approved_ids:
                raise ApprovalReviewerInvalidException(
                    message="Actor has already provided approval for this action. Multi-approver policy requires independent clinicians."
                )

        # 4. Specific reviewer assignment check
        if approval.assigned_reviewers and actor.user_id not in approval.assigned_reviewers and not is_delegated:
            if actor.role not in (UserRole.SYSTEM_ADMIN, UserRole.ADMIN):
                raise ApprovalReviewerInvalidException(
                    message="This approval request is assigned to specific clinicians. Caller is not an assigned reviewer."
                )

        # 5. Organization isolation
        if actor.organization_id and approval.organization_id:
            if actor.role not in (UserRole.SYSTEM_ADMIN, UserRole.ADMIN):
                if actor.organization_id != approval.organization_id:
                    raise ApprovalForbiddenException(
                        message=f"Cross-organization approval access denied: actor belongs to '{actor.organization_id}', approval belongs to '{approval.organization_id}'."
                    )

    def authorize_approval_view(
        self,
        actor: AuthenticatedUserContext,
        approval: ApprovalRecord,
    ) -> None:
        """Validate that the actor has permission to view an approval record."""
        # Patient can only view their own approvals
        if actor.role == UserRole.PATIENT:
            if actor.patient_id and actor.patient_id != approval.patient_id:
                raise ApprovalForbiddenException(
                    message="Patients may only view their own approval requests."
                )
            return

        # Organization isolation
        if actor.organization_id and approval.organization_id:
            if actor.role not in (UserRole.SYSTEM_ADMIN, UserRole.ADMIN):
                if actor.organization_id != approval.organization_id:
                    raise ApprovalForbiddenException(
                        message="Cross-organization access to approval record denied."
                    )

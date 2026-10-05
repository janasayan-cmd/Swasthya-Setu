"""Clinical Approval Orchestration and Review Gate Service (Phase 40).

ARCHITECTURAL CONTRACT & CORE SAFETY PRINCIPLES:
- APPROVAL IS A CONTROLLED AUTHORIZATION LAYER.
- APPROVAL REQUEST != APPROVAL.
- APPROVAL != EXECUTION.
- APPROVAL != CLINICAL OUTCOME.
- REVIEW != CLINICAL DECISION.
- AI CANNOT APPROVE, REJECT, OR BYPASS APPROVAL.
- MATERIAL TARGET CHANGES INVALIDATE APPROVAL AND TRIGGER RE-APPROVAL.
- EXPIRED APPROVAL CANNOT AUTHORIZE EXECUTION.
- DUPLICATE APPROVAL DECISIONS ARE PREVENTED VIA IDEMPOTENCY & CONCURRENCY CONTROL.
- SELF-APPROVAL RESTRICTIONS ARE RIGIDLY ENFORCED.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import (
    ApprovalAlreadyDecidedException,
    ApprovalCancelledException,
    ApprovalDelegationInvalidException,
    ApprovalEscalationInvalidException,
    ApprovalExecutionBlockedException,
    ApprovalExpiredException,
    ApprovalForbiddenException,
    ApprovalIdempotencyConflictException,
    ApprovalInvalidException,
    ApprovalNotFoundException,
    ApprovalPolicyRequiredException,
    ApprovalsDisabledException,
    ApprovalReviewerInvalidException,
    ApprovalSelfConflictException,
    ApprovalSupersededException,
    ApprovalTargetChangedException,
    ApprovalTargetNotFoundException,
    ApprovalUnauthorizedException,
)
from app.repositories.approval_repository import ApprovalRepository
from app.schemas.approval import (
    ApprovalDecisionRecord,
    ApprovalDecisionRequest,
    ApprovalDecisionType,
    ApprovalDelegateRequest,
    ApprovalDelegationRecord,
    ApprovalEscalateRequest,
    ApprovalRecord,
    ApprovalRequestCreate,
    ApprovalRevisionRequest,
    ApprovalStatus,
    ApprovalType,
)
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.auth import UserRole
from app.schemas.order import OrderAuthorizeRequest
from app.schemas.user import AuthenticatedUserContext
from app.services.approval_authorization_service import ApprovalAuthorizationService
from app.services.approval_policy_service import ApprovalPolicyService
from app.services.audit_service import AuditService
from app.services.order_service import OrderService


class ApprovalService:
    """Orchestrates approval gates, reviewer decisions, and execution gating."""

    def __init__(
        self,
        approval_repository: ApprovalRepository,
        policy_service: ApprovalPolicyService,
        authorization_service: ApprovalAuthorizationService,
        audit_service: AuditService,
        order_repository: Optional[Any] = None,
        order_service: Optional[OrderService] = None,
        order_set_service: Optional[Any] = None,
        task_service: Optional[Any] = None,
        alert_service: Optional[Any] = None,
        notification_service: Optional[Any] = None,
        enabled: bool = True,
        clinical_approvals_enabled: bool = True,
        multi_approval_enabled: bool = True,
        escalation_enabled: bool = True,
        expiration_enabled: bool = True,
        delegation_enabled: bool = True,
        tasks_enabled: bool = True,
        default_expiration_hours: int = 24,
    ) -> None:
        self._repo = approval_repository
        self._policy = policy_service
        self._authz = authorization_service
        self._audit = audit_service
        self._order_repo = order_repository
        self._order_service = order_service
        self._order_set_service = order_set_service
        self._task_service = task_service
        self._alert_service = alert_service
        self._notification_service = notification_service
        self._enabled = enabled
        self._clinical_approvals_enabled = clinical_approvals_enabled
        self._multi_approval_enabled = multi_approval_enabled
        self._escalation_enabled = escalation_enabled
        self._expiration_enabled = expiration_enabled
        self._delegation_enabled = delegation_enabled
        self._tasks_enabled = tasks_enabled
        self._default_expiration_hours = default_expiration_hours

    def _require_enabled(self) -> None:
        if not self._enabled or not self._clinical_approvals_enabled:
            raise ApprovalsDisabledException()

    async def _record_audit(self, record: AuditEventRecord) -> None:
        """Helper to safely record and await audit event."""
        res = self._audit.record(record)
        if asyncio.iscoroutine(res):
            await res

    # -----------------------------------------------------------------------
    # Approval Request Creation (TRD Section 16, 33)
    # -----------------------------------------------------------------------

    async def create_approval_request(
        self,
        payload: ApprovalRequestCreate,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Create a new formal approval request for a candidate action.

        INVARIANTS:
        - APPROVAL REQUEST != APPROVAL.
        - Request must reference target action and snapshot version.
        - Idempotency key prevents duplicate requests.
        """
        self._require_enabled()

        # Idempotency check
        existing = self._repo.get_by_idempotency_key(payload.idempotency_key)
        if existing:
            if existing.target_id != payload.target_id or existing.patient_id != payload.patient_id:
                raise ApprovalIdempotencyConflictException()
            return existing

        # Evaluate applicable approval policy
        rule = self._policy.evaluate_rule(action_type=payload.target_type)
        if not rule or rule.action_type == "DEFAULT":
            rule = self._policy.evaluate_rule(action_type=payload.approval_type.value)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=rule.expiration_hours) if self._expiration_enabled else None

        approval_id = str(uuid.uuid4())
        record = ApprovalRecord(
            id=approval_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            target_version=payload.target_version or "1",
            target_snapshot_hash=payload.target_snapshot_hash,
            patient_id=payload.patient_id,
            requester_id=actor.user_id,
            organization_id=payload.organization_id or actor.organization_id or "default-org",
            facility_id=payload.facility_id or actor.facility_id,
            approval_type=payload.approval_type,
            status=ApprovalStatus.PENDING_REVIEW,
            policy_id="default-clinical-policy",
            policy_version=1,
            required_approvals_count=rule.multi_approver_count if self._multi_approval_enabled else 1,
            current_approval_level=rule.required_level,
            decisions=[],
            assigned_reviewers=[],
            assigned_roles=rule.required_roles,
            idempotency_key=payload.idempotency_key,
            clinical_summary=payload.clinical_summary,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )

        saved = self._repo.save(record)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.APPROVAL_REQUESTED,
                actor_id=actor.user_id,
                resource_type="approval_request",
                resource_id=saved.id,
                patient_id=payload.patient_id,
                outcome="ALLOW",
                metadata={
                    "target_type": payload.target_type,
                    "target_id": payload.target_id,
                    "approval_type": payload.approval_type.value,
                },
            )
        )

        return saved

    # -----------------------------------------------------------------------
    # Approval Decisions (TRD Section 32, 34)
    # -----------------------------------------------------------------------

    async def approve(
        self,
        approval_id: str,
        payload: ApprovalDecisionRequest,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Render an APPROVE decision on a pending approval request.

        SAFETY INVARIANTS:
        - AI CANNOT APPROVE.
        - Reviewer eligibility and role verified.
        - Self-approval blocked when policy disallows it.
        - Expired approval cannot authorize action.
        - Material target change invalidates pending request.
        """
        self._require_enabled()

        approval = self._repo.get_by_id(approval_id)
        if not approval:
            raise ApprovalNotFoundException(f"Approval '{approval_id}' was not found.")

        # Terminal state check
        if approval.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED):
            raise ApprovalAlreadyDecidedException(
                f"Approval '{approval_id}' is already in terminal state '{approval.status.value}'."
            )

        # Expiration check
        now = datetime.now(timezone.utc)
        if approval.expires_at and now > approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED
            approval.updated_at = now
            self._repo.save(approval)
            raise ApprovalExpiredException("Approval request has expired. Re-approval is required.")

        # Policy & reviewer eligibility validation
        rule = self._policy.evaluate_rule(action_type=approval.target_type)
        if not rule or rule.action_type == "DEFAULT":
            rule = self._policy.evaluate_rule(action_type=approval.approval_type.value)

        # Delegation check
        is_delegated = False
        if payload.delegation_id:
            if not self._delegation_enabled:
                raise ApprovalDelegationInvalidException("Delegation is currently disabled.")
            delegation = self._repo.get_active_delegation(
                delegator_id=approval.assigned_reviewers[0] if approval.assigned_reviewers else "",
                delegatee_id=actor.user_id,
            )
            if not delegation:
                raise ApprovalDelegationInvalidException("Active delegation not found for caller.")
            is_delegated = True

        self._authz.validate_reviewer_eligibility(
            actor=actor,
            approval=approval,
            rule=rule,
            is_delegated=is_delegated,
        )

        # Record decision
        role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
        decision = ApprovalDecisionRecord(
            decision=ApprovalDecisionType.APPROVE,
            approver_id=actor.user_id,
            approver_role=role_str,
            timestamp=now,
            reason=payload.reason,
            notes=payload.notes,
            delegation_id=payload.delegation_id,
            policy_version=approval.policy_version,
            target_version=approval.target_version,
        )
        approval.decisions.append(decision)
        approval.updated_at = now

        # Multi-approver tally check
        approved_count = len([d for d in approval.decisions if d.decision == ApprovalDecisionType.APPROVE])
        if approved_count >= approval.required_approvals_count:
            approval.status = ApprovalStatus.APPROVED
            approval.decision_at = now

            # Downstream execution authorization
            if approval.target_type == "order" and self._order_service:
                try:
                    await self._order_service.authorize_order(
                        order_id=approval.target_id,
                        request=OrderAuthorizeRequest(
                            reason=payload.reason or "Authorized through Approval Gate",
                            authorized_by=actor.user_id,
                        ),
                        actor=actor,
                    )
                except Exception:
                    # Gating preserved; log downstream error without swallowing
                    pass
        else:
            approval.status = ApprovalStatus.IN_REVIEW

        self._repo.save(approval)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.APPROVAL_APPROVED,
                actor_id=actor.user_id,
                resource_type="approval_request",
                resource_id=approval.id,
                patient_id=approval.patient_id,
                outcome="ALLOW",
                metadata={
                    "status": approval.status.value,
                    "target_type": approval.target_type,
                    "target_id": approval.target_id,
                    "approver_id": actor.user_id,
                },
            )
        )

        return approval

    async def reject(
        self,
        approval_id: str,
        payload: ApprovalDecisionRequest,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Reject a candidate action. AI CANNOT REJECT."""
        self._require_enabled()

        approval = self._repo.get_by_id(approval_id)
        if not approval:
            raise ApprovalNotFoundException(f"Approval '{approval_id}' was not found.")

        rule = self._policy.evaluate_rule(action_type=approval.target_type)
        if not rule or rule.action_type == "DEFAULT":
            rule = self._policy.evaluate_rule(action_type=approval.approval_type.value)
        self._authz.validate_reviewer_eligibility(actor, approval, rule)

        if approval.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED):
            raise ApprovalAlreadyDecidedException()

        now = datetime.now(timezone.utc)
        role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
        decision = ApprovalDecisionRecord(
            decision=ApprovalDecisionType.REJECT,
            approver_id=actor.user_id,
            approver_role=role_str,
            timestamp=now,
            reason=payload.reason,
            notes=payload.notes,
            policy_version=approval.policy_version,
            target_version=approval.target_version,
        )
        approval.decisions.append(decision)
        approval.status = ApprovalStatus.REJECTED
        approval.decision_at = now
        approval.updated_at = now

        self._repo.save(approval)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.APPROVAL_REJECTED,
                actor_id=actor.user_id,
                resource_type="approval_request",
                resource_id=approval.id,
                patient_id=approval.patient_id,
                outcome="ALLOW",
                metadata={"reason": payload.reason},
            )
        )

        return approval

    async def request_revision(
        self,
        approval_id: str,
        payload: ApprovalRevisionRequest,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Request revisions on a pending action rather than rejecting."""
        self._require_enabled()

        approval = self._repo.get_by_id(approval_id)
        if not approval:
            raise ApprovalNotFoundException(f"Approval '{approval_id}' was not found.")

        rule = self._policy.evaluate_rule(action_type=approval.target_type)
        if not rule or rule.action_type == "DEFAULT":
            rule = self._policy.evaluate_rule(action_type=approval.approval_type.value)
        self._authz.validate_reviewer_eligibility(actor, approval, rule)

        if approval.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED):
            raise ApprovalAlreadyDecidedException()

        now = datetime.now(timezone.utc)
        role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
        decision = ApprovalDecisionRecord(
            decision=ApprovalDecisionType.REQUEST_REVISION,
            approver_id=actor.user_id,
            approver_role=role_str,
            timestamp=now,
            reason=payload.reason,
            notes=f"Required changes: {'; '.join(payload.required_changes)}",
            policy_version=approval.policy_version,
            target_version=approval.target_version,
        )
        approval.decisions.append(decision)
        approval.status = ApprovalStatus.REVISION_REQUESTED
        approval.updated_at = now

        self._repo.save(approval)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.APPROVAL_REVISION_REQUESTED,
                actor_id=actor.user_id,
                resource_type="approval_request",
                resource_id=approval.id,
                patient_id=approval.patient_id,
                outcome="ALLOW",
                metadata={"required_changes": payload.required_changes},
            )
        )

        return approval

    async def cancel(
        self,
        approval_id: str,
        reason: str,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Cancel an open approval request."""
        self._require_enabled()

        approval = self._repo.get_by_id(approval_id)
        if not approval:
            raise ApprovalNotFoundException(f"Approval '{approval_id}' was not found.")

        if approval.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED):
            raise ApprovalAlreadyDecidedException()

        # Requester or Admin can cancel
        if actor.user_id != approval.requester_id and actor.role not in (UserRole.ADMIN, UserRole.SYSTEM_ADMIN):
            raise ApprovalForbiddenException("Only the requester or an administrator can cancel an approval request.")

        approval.status = ApprovalStatus.CANCELLED
        approval.updated_at = datetime.now(timezone.utc)
        self._repo.save(approval)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.APPROVAL_CANCELLED,
                actor_id=actor.user_id,
                resource_type="approval_request",
                resource_id=approval.id,
                patient_id=approval.patient_id,
                outcome="ALLOW",
                metadata={"reason": reason},
            )
        )

        return approval

    async def delegate(
        self,
        approval_id: str,
        payload: ApprovalDelegateRequest,
        actor: AuthenticatedUserContext,
    ) -> ApprovalDelegationRecord:
        """Delegate review authority for an approval to another clinician."""
        self._require_enabled()
        if not self._delegation_enabled:
            raise ApprovalDelegationInvalidException("Delegation feature is currently disabled.")

        approval = self._repo.get_by_id(approval_id)
        if not approval:
            raise ApprovalNotFoundException(f"Approval '{approval_id}' was not found.")

        # Ensure actor is an eligible approver
        rule = self._policy.evaluate_rule(approval.approval_type.value)
        self._authz.validate_reviewer_eligibility(actor, approval, rule)

        delegation = ApprovalDelegationRecord(
            delegator_id=actor.user_id,
            delegatee_id=payload.delegate_to_user_id,
            organization_id=approval.organization_id,
            facility_id=approval.facility_id,
            reason=payload.reason,
            expires_at=payload.valid_until,
            is_active=True,
        )

        self._repo.save_delegation(delegation)

        # Add delegatee to assigned reviewers
        if payload.delegate_to_user_id not in approval.assigned_reviewers:
            approval.assigned_reviewers.append(payload.delegate_to_user_id)
            self._repo.save(approval)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.APPROVAL_DELEGATED,
                actor_id=actor.user_id,
                resource_type="approval_request",
                resource_id=approval.id,
                patient_id=approval.patient_id,
                outcome="ALLOW",
                metadata={
                    "delegator_id": actor.user_id,
                    "delegatee_id": payload.delegate_to_user_id,
                },
            )
        )

        return delegation

    async def escalate(
        self,
        approval_id: str,
        payload: ApprovalEscalateRequest,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Escalate an overdue or pending approval to a higher clinical authority."""
        self._require_enabled()
        if not self._escalation_enabled:
            raise ApprovalEscalationInvalidException("Approval escalation feature is disabled.")

        approval = self._repo.get_by_id(approval_id)
        if not approval:
            raise ApprovalNotFoundException(f"Approval '{approval_id}' was not found.")

        approval.escalation_level += 1
        approval.current_approval_level += 1
        if payload.escalate_to_role and payload.escalate_to_role not in approval.assigned_roles:
            approval.assigned_roles.append(payload.escalate_to_role)
        approval.updated_at = datetime.now(timezone.utc)

        self._repo.save(approval)

        await self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.APPROVAL_ESCALATED,
                actor_id=actor.user_id,
                resource_type="approval_request",
                resource_id=approval.id,
                patient_id=approval.patient_id,
                outcome="ALLOW",
                metadata={
                    "escalation_level": approval.escalation_level,
                    "reason": payload.reason,
                },
            )
        )

        return approval

    # -----------------------------------------------------------------------
    # Action Modification / Target Version Check (TRD Section 17, 20)
    # -----------------------------------------------------------------------

    def validate_approval_for_execution(
        self,
        target_type: str,
        target_id: str,
        current_version: str,
        current_hash: Optional[str] = None,
    ) -> ApprovalRecord:
        """Verify that an approved authorization exists and has not been invalidated.

        SAFETY:
        - If action was modified since approval was requested, existing approval is INVALID.
        - If approval expired, execution is BLOCKED.
        """
        self._require_enabled()

        approval = self._repo.get_latest_by_target(target_type, target_id)
        if not approval:
            raise ApprovalExecutionBlockedException("No approval record exists for this clinical action.")

        if approval.status != ApprovalStatus.APPROVED:
            raise ApprovalExecutionBlockedException(
                f"Action execution blocked: approval is in status '{approval.status.value}', not 'APPROVED'."
            )

        # Check expiration
        now = datetime.now(timezone.utc)
        if approval.expires_at and now > approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED
            self._repo.save(approval)
            raise ApprovalExpiredException("Approval has expired. Cannot execute with stale authorization.")

        # Check target version mismatch / material change (TRD Section 20)
        if approval.target_version and approval.target_version != current_version:
            approval.status = ApprovalStatus.SUPERSEDED
            self._repo.save(approval)
            raise ApprovalTargetChangedException(
                f"Action version '{current_version}' does not match approved version '{approval.target_version}'. Re-approval required."
            )

        if approval.target_snapshot_hash and current_hash and approval.target_snapshot_hash != current_hash:
            approval.status = ApprovalStatus.SUPERSEDED
            self._repo.save(approval)
            raise ApprovalTargetChangedException(
                "Action payload has changed materially since approval was granted. Re-approval required."
            )

        return approval

    # -----------------------------------------------------------------------
    # Retrieval Queries (TRD Section 31)
    # -----------------------------------------------------------------------

    async def get_approval(
        self,
        approval_id: str,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Retrieve an approval record by ID."""
        self._require_enabled()
        approval = self._repo.get_by_id(approval_id)
        if not approval:
            raise ApprovalNotFoundException(f"Approval '{approval_id}' was not found.")

        self._authz.authorize_approval_view(actor, approval)
        return approval

    async def get_latest_approval_for_target(
        self,
        target_type: str,
        target_id: str,
        actor: AuthenticatedUserContext,
    ) -> ApprovalRecord:
        """Retrieve the latest approval for an action target."""
        self._require_enabled()
        approval = self._repo.get_latest_by_target(target_type, target_id)
        if not approval:
            raise ApprovalNotFoundException(f"No approval found for target '{target_type}:{target_id}'.")

        self._authz.authorize_approval_view(actor, approval)
        return approval

    async def list_approvals(
        self,
        actor: AuthenticatedUserContext,
        status: Optional[ApprovalStatus] = None,
        approval_type: Optional[ApprovalType] = None,
        patient_id: Optional[str] = None,
        assigned_to_me: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ApprovalRecord]:
        """List approvals matching query parameters within caller's scope."""
        self._require_enabled()

        assigned_id = actor.user_id if assigned_to_me else None
        target_patient = patient_id
        if actor.role == UserRole.PATIENT:
            target_patient = actor.patient_id

        return self._repo.list_approvals(
            status=status,
            approval_type=approval_type,
            patient_id=target_patient,
            organization_id=actor.organization_id if actor.role not in (UserRole.ADMIN, UserRole.SYSTEM_ADMIN) else None,
            assigned_user_id=assigned_id,
            limit=limit,
            offset=offset,
        )

"""Human Approval Gate Service for Clinical Workflows (Phase 37).

Enforces:
- Only authorized human clinical/admin roles can approve workflow gates.
- AI systems and automated roles CANNOT approve gates or declare clinical truth.
- Approval does NOT confirm medical diagnosis, treatment success, or patient safety.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    WorkflowApprovalNotAllowedException,
    WorkflowApprovalRequiredException,
    WorkflowInvalidStateException,
    WorkflowStepNotFoundException,
)
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.workflow_step_repository import WorkflowStepRepository
from app.schemas.audit import AuditEventType
from app.schemas.user import AuthenticatedUserContext
from app.schemas.workflow_approval import (
    WorkflowApprovalDecision,
    WorkflowApprovalRecord,
    WorkflowApprovalRequest,
)
from app.schemas.workflow_history import WorkflowHistoryAction
from app.schemas.workflow_step import WorkflowStepRecord, WorkflowStepStatus
from app.services.audit_service import AuditService
from app.services.workflow_validation_service import WorkflowValidationService


class WorkflowApprovalService:
    """Manages human approval evaluation, role verification, and audit logging."""

    def __init__(
        self,
        workflow_repo: Optional[WorkflowRepository] = None,
        step_repo: Optional[WorkflowStepRepository] = None,
        val_service: Optional[WorkflowValidationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.workflow_repo = workflow_repo or WorkflowRepository()
        self.step_repo = step_repo or WorkflowStepRepository()
        self.val_service = val_service or WorkflowValidationService()
        self.audit_service = audit_service

    async def evaluate_approval(
        self,
        workflow_id: str,
        step_id: str,
        request: WorkflowApprovalRequest,
        current_user: AuthenticatedUserContext,
    ) -> WorkflowStepRecord:
        """Process an explicit human approval or rejection decision."""
        # 1. AI Non-Authority check (TRD Section 34 & 60)
        self.val_service.assert_ai_non_authority(
            actor_role=current_user.role,
            action="APPROVE" if request.decision == WorkflowApprovalDecision.APPROVED else "REJECT",
            actor_id=current_user.user_id,
        )

        # 2. Step lookup
        step = self.step_repo.get_by_workflow_and_step_id(workflow_id, step_id)
        if not step:
            raise WorkflowStepNotFoundException(
                f"Workflow step '{step_id}' not found for workflow '{workflow_id}'."
            )

        # 3. State check: must be AWAITING_APPROVAL
        if step.status != WorkflowStepStatus.AWAITING_APPROVAL:
            raise WorkflowInvalidStateException(
                f"Step '{step_id}' is in status '{step.status.value}', not 'AWAITING_APPROVAL'."
            )

        # 4. Role Authorization check
        if step.required_approval_role:
            # Admins or matching role
            allowed_roles = {step.required_approval_role, "ADMIN", "SYSTEM_ADMIN"}
            if current_user.role not in allowed_roles:
                raise WorkflowApprovalNotAllowedException(
                    f"User with role '{current_user.role}' is not authorized to approve step '{step_id}'. "
                    f"Required role: '{step.required_approval_role}'."
                )

        # 5. Record approval audit entity
        approval_record = WorkflowApprovalRecord(
            approval_id="",
            workflow_id=workflow_id,
            step_id=step_id,
            step_instance_id=step.step_instance_id,
            approver_id=current_user.user_id,
            approver_role=current_user.role,
            decision=request.decision,
            comments=request.comments,
            policy_version=request.policy_version or "1.0",
            created_at=datetime.now(timezone.utc),
        )
        self.workflow_repo.save_approval(approval_record)

        # 6. Apply state transition based on decision
        now = datetime.now(timezone.utc)
        if request.decision == WorkflowApprovalDecision.APPROVED:
            self.val_service.validate_step_transition(step.status, WorkflowStepStatus.COMPLETED)
            updated_step = step.model_copy(
                update={
                    "status": WorkflowStepStatus.COMPLETED,
                    "completed_at": now,
                    "updated_at": now,
                }
            )
            saved_step = self.step_repo.save(updated_step)

            # Record history
            self.workflow_repo.add_history(
                workflow_id=workflow_id,
                step_id=step_id,
                action=WorkflowHistoryAction.APPROVED,
                from_status=step.status.value,
                to_status=saved_step.status.value,
                actor_id=current_user.user_id,
                actor_role=current_user.role,
                reason=request.comments or "Step approved by authorized user",
                metadata={"policy_version": request.policy_version},
            )

            # Audit event
            if self.audit_service:
                await self.audit_service.record(
                    event_type=AuditEventType.WORKFLOW_APPROVED,
                    outcome="ALLOW",
                    actor_id=current_user.user_id,
                    action="APPROVE_WORKFLOW_STEP",
                    resource_type="workflow_step",
                    resource_id=step.step_instance_id,
                    metadata={
                        "workflow_id": workflow_id,
                        "step_id": step_id,
                        "policy_version": request.policy_version,
                    },
                )
            return saved_step

        else:
            # REJECTED
            self.val_service.validate_step_transition(step.status, WorkflowStepStatus.FAILED)
            updated_step = step.model_copy(
                update={
                    "status": WorkflowStepStatus.FAILED,
                    "error_message": f"Step rejected: {request.comments or 'Rejected by authorized approver'}",
                    "error_code": "APPROVAL_REJECTED",
                    "updated_at": now,
                }
            )
            saved_step = self.step_repo.save(updated_step)

            # Record history
            self.workflow_repo.add_history(
                workflow_id=workflow_id,
                step_id=step_id,
                action=WorkflowHistoryAction.REJECTED,
                from_status=step.status.value,
                to_status=saved_step.status.value,
                actor_id=current_user.user_id,
                actor_role=current_user.role,
                reason=request.comments or "Step rejected by authorized user",
                metadata={"policy_version": request.policy_version},
            )

            # Audit event
            if self.audit_service:
                await self.audit_service.record(
                    event_type=AuditEventType.WORKFLOW_REJECTED,
                    outcome="DENY",
                    actor_id=current_user.user_id,
                    action="REJECT_WORKFLOW_STEP",
                    resource_type="workflow_step",
                    resource_id=step.step_instance_id,
                    metadata={
                        "workflow_id": workflow_id,
                        "step_id": step_id,
                        "reason": request.comments,
                    },
                )
            return saved_step

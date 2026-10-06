"""Core Clinical Workflow Orchestration Service (Phase 37).

Orchestrates:
- Multi-step workflow definitions and instances
- Step dependency graphs and deterministic action dispatching
- Human approval gates (doctors/admins)
- Task completion callbacks (Phase 36)
- Wait-for-event and domain event hooks
- Pause, resume, and cancellation mechanics
- Full provenance, history audit trails, and multi-tenant security scoping
- Strict preservation of clinical safety boundaries (TRD Section 60)
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.core.exceptions import (
    WorkflowAccessDeniedException,
    WorkflowAlreadyCancelledException,
    WorkflowAlreadyCompletedException,
    WorkflowCannotCancelException,
    WorkflowCannotResumeException,
    WorkflowDuplicateException,
    WorkflowInvalidStateException,
    WorkflowNotFoundException,
    WorkflowOperationNotAllowedException,
)
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.workflow_step_repository import WorkflowStepRepository
from app.schemas.alert import AlertRecord
from app.schemas.audit import AuditEventType
from app.schemas.notification import NotificationCreate, NotificationType
from app.schemas.task import TaskCancelRequest, TaskStatus
from app.schemas.user import AuthenticatedUserContext
from app.schemas.workflow import (
    WorkflowCancelRequest,
    WorkflowCreate,
    WorkflowFilter,
    WorkflowListResponse,
    WorkflowPauseRequest,
    WorkflowProvenance,
    WorkflowRecord,
    WorkflowResumeRequest,
    WorkflowStatus,
)
from app.schemas.workflow_history import WorkflowHistoryAction
from app.schemas.workflow_step import (
    WorkflowStepActionType,
    WorkflowStepRecord,
    WorkflowStepStatus,
)
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService
from app.services.workflow_approval_service import WorkflowApprovalService
from app.services.workflow_definition_service import WorkflowDefinitionService
from app.services.workflow_step_service import WorkflowStepService
from app.services.workflow_validation_service import WorkflowValidationService

logger = logging.getLogger(__name__)


class WorkflowService:
    """Master domain service coordinating clinical workflow orchestration."""

    def __init__(
        self,
        workflow_repo: Optional[WorkflowRepository] = None,
        step_repo: Optional[WorkflowStepRepository] = None,
        def_service: Optional[WorkflowDefinitionService] = None,
        step_service: Optional[WorkflowStepService] = None,
        val_service: Optional[WorkflowValidationService] = None,
        approval_service: Optional[WorkflowApprovalService] = None,
        task_service: Optional[TaskService] = None,
        alert_service: Optional[AlertService] = None,
        notification_service: Optional[NotificationService] = None,
        audit_service: Optional[AuditService] = None,
        repository: Optional[WorkflowRepository] = None,
    ) -> None:
        self.workflow_repo = workflow_repo or repository or WorkflowRepository()
        self.step_repo = step_repo or WorkflowStepRepository()
        self.def_service = def_service or WorkflowDefinitionService()
        self.val_service = val_service or WorkflowValidationService()
        self.task_service = task_service
        self.alert_service = alert_service
        self.notification_service = notification_service
        self.audit_service = audit_service

        self.step_service = step_service or WorkflowStepService(
            step_repo=self.step_repo,
            val_service=self.val_service,
            task_service=self.task_service,
            alert_service=self.alert_service,
            notification_service=self.notification_service,
            audit_service=self.audit_service,
        )

        self.approval_service = approval_service or WorkflowApprovalService(
            workflow_repo=self.workflow_repo,
            step_repo=self.step_repo,
            val_service=self.val_service,
            audit_service=self.audit_service,
        )

        self._execution_lock = threading.RLock()

    async def create_workflow(
        self,
        workflow_type: str,
        steps: List[WorkflowStepRecord],
        patient_id: Optional[str] = None,
        initiating_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowRecord:
        """Initialize a new multi-step asynchronous workflow (Phase 22 backward compatibility)."""
        import uuid
        wf_id = f"WF-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        for s in steps:
            s.workflow_id = wf_id
            if not s.name and s.step_name:
                s.name = s.step_name
            if not s.step_id:
                s.step_id = s.name or f"step-{s.order}"

        workflow = WorkflowRecord(
            workflow_id=wf_id,
            definition_id="DOCUMENT_TO_PRESCRIPTION_PIPELINE",
            definition_version="1.0",
            name=workflow_type,
            workflow_type=workflow_type,
            initiating_user_id=initiating_user_id,
            status=WorkflowStatus.RUNNING,
            patient_id=patient_id,
            correlation_id=f"CORR-{wf_id}",
            steps=steps,
            context=metadata or {},
            provenance=WorkflowProvenance(
                source_event_id="MANUAL",
                source_event_type="USER_ACTION",
                initiated_by=initiating_user_id or "system",
                definition_id="DOCUMENT_TO_PRESCRIPTION_PIPELINE",
                definition_version="1.0",
                correlation_id=f"CORR-{wf_id}",
            ),
        )
        saved = await self.workflow_repo.create(workflow)

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.WORKFLOW_STARTED,
                outcome="ALLOW",
                actor_id=initiating_user_id,
                action=f"workflow:create:{workflow_type}",
                resource_type="workflow",
                resource_id=saved.id,
                metadata={"workflow_id": saved.id, "step_count": len(steps)},
            )
        return saved

    async def advance_step(
        self,
        workflow_id: str,
        step_order: int,
        step_status: WorkflowStepStatus,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> WorkflowRecord:
        """Update individual workflow step and advance pipeline (Phase 22 backward compatibility)."""
        workflow = await self.workflow_repo.get(workflow_id)
        if not workflow:
            raise WorkflowNotFoundException(workflow_id=workflow_id)

        target_step: Optional[WorkflowStepRecord] = None
        for step in workflow.steps:
            if step.order == step_order:
                target_step = step
                break

        if not target_step:
            raise WorkflowInvalidStateException(
                workflow_id=workflow_id,
                current_state=workflow.status.value,
                attempted_action=f"advance_step_order_{step_order}",
            )

        now = datetime.now(timezone.utc)
        target_step.status = step_status
        target_step.result = result
        target_step.error_message = error_message

        if step_status == WorkflowStepStatus.RUNNING:
            target_step.started_at = now
            workflow.status = WorkflowStatus.RUNNING
        elif step_status == WorkflowStepStatus.COMPLETED:
            target_step.completed_at = now
        elif step_status == WorkflowStepStatus.FAILED:
            target_step.completed_at = now
            if target_step.required:
                workflow.status = WorkflowStatus.PARTIALLY_FAILED

        all_done = all(s.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.SKIPPED, WorkflowStepStatus.FAILED) for s in workflow.steps)
        if all_done:
            has_required_failures = any(s.status == WorkflowStepStatus.FAILED and s.required for s in workflow.steps)
            if has_required_failures:
                workflow.status = WorkflowStatus.PARTIALLY_FAILED
            else:
                workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = now

            if self.audit_service:
                await self.audit_service.record(
                    event_type=(
                        AuditEventType.WORKFLOW_COMPLETED
                        if workflow.status == WorkflowStatus.COMPLETED
                        else AuditEventType.WORKFLOW_FAILED
                    ),
                    outcome="ALLOW" if workflow.status == WorkflowStatus.COMPLETED else "DENY",
                    actor_id=workflow.initiating_user_id,
                    action=f"workflow:finish:{workflow.name}",
                    resource_type="workflow",
                    resource_id=workflow.id,
                    metadata={"status": workflow.status.value},
                )

        return await self.workflow_repo.update(workflow)

    async def start_workflow(
        self,
        payload: WorkflowCreate,
        current_user: AuthenticatedUserContext,
    ) -> WorkflowRecord:
        """Instantiate and begin executing a workflow idempotently."""
        if not settings.WORKFLOWS_ENABLED:
            raise WorkflowOperationNotAllowedException("Clinical workflow orchestration is disabled.")

        # 1. Retrieve approved workflow definition
        definition = self.def_service.get_definition(
            definition_id=payload.workflow_definition,
            version=payload.workflow_version,
        )

        # 2. Idempotency Check by client key
        if payload.idempotency_key:
            existing = self.workflow_repo.get_by_idempotency_key(payload.idempotency_key)
            if existing:
                steps = self.step_repo.list_by_workflow_id(existing.workflow_id)
                return existing.model_copy(update={"steps": steps})

        # 3. Idempotency Check by logical identity
        existing_logical = self.workflow_repo.get_by_logical_identity(
            source_type=payload.source_type,
            source_id=payload.source_id,
            definition_id=definition.definition_id,
            definition_version=definition.version,
            patient_id=payload.patient_id,
        )
        if existing_logical:
            steps = self.step_repo.list_by_workflow_id(existing_logical.workflow_id)
            return existing_logical.model_copy(update={"steps": steps})

        # 4. Construct WorkflowRecord
        now = datetime.now(timezone.utc)
        correlation_id = payload.correlation_id or f"CORR-{definition.definition_id}-{now.strftime('%Y%m%d%H%M%S')}"

        provenance = WorkflowProvenance(
            source_event_id=payload.source_id,
            source_event_type=payload.source_type,
            initiated_by=current_user.user_id,
            definition_id=definition.definition_id,
            definition_version=definition.version,
            correlation_id=correlation_id,
            created_at=now,
        )

        workflow = WorkflowRecord(
            workflow_id="",
            definition_id=definition.definition_id,
            definition_version=definition.version,
            name=definition.name,
            category=definition.category,
            status=WorkflowStatus.CREATED,
            patient_id=payload.patient_id,
            encounter_id=payload.encounter_id,
            resource_id=payload.resource_id,
            facility_id=payload.facility_id or current_user.facility_id,
            correlation_id=correlation_id,
            source_event_id=payload.source_id,
            source_event_type=payload.source_type,
            idempotency_key=payload.idempotency_key,
            provenance=provenance,
            context=payload.initial_context or {},
            created_at=now,
            updated_at=now,
        )
        saved_wf = self.workflow_repo.save(workflow)

        # 5. Instantiate steps
        created_steps = []
        for step_def in definition.steps:
            s = self.step_service.create_step_instance(saved_wf, step_def)
            created_steps.append(s)

        # 6. Audit & History recording
        self.workflow_repo.add_history(
            workflow_id=saved_wf.workflow_id,
            action=WorkflowHistoryAction.CREATED,
            to_status=WorkflowStatus.CREATED.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason="Workflow instance created from definition",
            metadata={"definition_id": definition.definition_id, "version": definition.version},
        )

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.WORKFLOW_CREATED,
                outcome="ALLOW",
                actor_id=current_user.user_id,
                action="CREATE_WORKFLOW",
                resource_type="workflow",
                resource_id=saved_wf.workflow_id,
                metadata={"definition_id": definition.definition_id, "correlation_id": correlation_id},
            )

        # 7. Transition CREATED -> READY -> advance
        self.val_service.validate_workflow_transition(saved_wf.status, WorkflowStatus.READY)
        saved_wf = saved_wf.model_copy(update={"status": WorkflowStatus.READY})
        saved_wf = self.workflow_repo.save(saved_wf)

        # Advance workflow to execute initial steps
        advanced_wf = await self.advance_workflow(saved_wf.workflow_id, current_user)
        return advanced_wf

    async def advance_workflow(
        self,
        workflow_id: str,
        current_user: AuthenticatedUserContext,
    ) -> WorkflowRecord:
        """Evaluate step dependencies, execute active steps, and determine overall lifecycle progression."""
        with self._execution_lock:
            workflow = self.workflow_repo.get_by_id(workflow_id)
            if not workflow:
                raise WorkflowNotFoundException(f"Workflow '{workflow_id}' not found.")

            # Do not advance terminal or paused workflows
            if workflow.status in {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.CANCELLED,
                WorkflowStatus.EXPIRED,
                WorkflowStatus.PAUSED,
            }:
                steps = self.step_repo.list_by_workflow_id(workflow.workflow_id)
                return workflow.model_copy(update={"steps": steps})

            # Transition READY -> RUNNING if needed
            if workflow.status == WorkflowStatus.READY:
                self.val_service.validate_workflow_transition(workflow.status, WorkflowStatus.RUNNING)
                now = datetime.now(timezone.utc)
                workflow = workflow.model_copy(
                    update={
                        "status": WorkflowStatus.RUNNING,
                        "started_at": now,
                        "updated_at": now,
                    }
                )
                workflow = self.workflow_repo.save(workflow)

                self.workflow_repo.add_history(
                    workflow_id=workflow.workflow_id,
                    action=WorkflowHistoryAction.STARTED,
                    from_status=WorkflowStatus.READY.value,
                    to_status=WorkflowStatus.RUNNING.value,
                    actor_id=current_user.user_id,
                    actor_role=current_user.role,
                    reason="Workflow execution started",
                )

            steps = self.step_repo.list_by_workflow_id(workflow_id)

            # Execute eligible steps
            for step in steps:
                if step.status in {WorkflowStepStatus.PENDING, WorkflowStepStatus.READY, WorkflowStepStatus.BLOCKED}:
                    # Step might now be unblocked
                    await self.step_service.execute_step(
                        workflow=workflow,
                        step=step,
                        all_steps=steps,
                        system_user=current_user,
                    )

            # Reload updated steps
            steps = self.step_repo.list_by_workflow_id(workflow_id)

            # Evaluate composite workflow status
            has_failed = any(s.status == WorkflowStepStatus.FAILED for s in steps)
            has_awaiting_approval = any(s.status == WorkflowStepStatus.AWAITING_APPROVAL for s in steps)
            has_waiting = any(s.status == WorkflowStepStatus.WAITING for s in steps)
            has_running = any(s.status in {WorkflowStepStatus.RUNNING, WorkflowStepStatus.READY} for s in steps)
            all_completed = all(
                s.status in {WorkflowStepStatus.COMPLETED, WorkflowStepStatus.SKIPPED} for s in steps
            )

            now = datetime.now(timezone.utc)
            new_status = workflow.status
            current_active_step = None

            for s in steps:
                if s.status in {
                    WorkflowStepStatus.RUNNING,
                    WorkflowStepStatus.AWAITING_APPROVAL,
                    WorkflowStepStatus.WAITING,
                }:
                    current_active_step = s.step_id
                    break

            if has_failed:
                failed_step = next(s for s in steps if s.status == WorkflowStepStatus.FAILED)
                new_status = WorkflowStatus.FAILED
                workflow = workflow.model_copy(
                    update={
                        "status": new_status,
                        "current_step_id": failed_step.step_id,
                        "failure_reason": failed_step.error_message or "Step execution failed",
                        "error_code": failed_step.error_code or "STEP_FAILED",
                        "updated_at": now,
                    }
                )
                self.workflow_repo.save(workflow)
                self.workflow_repo.add_history(
                    workflow_id=workflow.workflow_id,
                    step_id=failed_step.step_id,
                    action=WorkflowHistoryAction.FAILED,
                    to_status=WorkflowStatus.FAILED.value,
                    actor_id=current_user.user_id,
                    actor_role=current_user.role,
                    reason=failed_step.error_message,
                )
                return workflow.model_copy(update={"steps": steps})

            elif has_awaiting_approval:
                new_status = WorkflowStatus.AWAITING_APPROVAL
            elif has_waiting:
                new_status = WorkflowStatus.WAITING
            elif all_completed:
                new_status = WorkflowStatus.COMPLETED
            elif has_running:
                new_status = WorkflowStatus.RUNNING

            if new_status != workflow.status:
                self.val_service.validate_workflow_transition(workflow.status, new_status)
                update_fields: Dict[str, Any] = {
                    "status": new_status,
                    "current_step_id": current_active_step,
                    "updated_at": now,
                }
                if new_status == WorkflowStatus.COMPLETED:
                    update_fields["completed_at"] = now

                prev_status = workflow.status
                workflow = workflow.model_copy(update=update_fields)
                workflow = self.workflow_repo.save(workflow)

                action_map = {
                    WorkflowStatus.COMPLETED: WorkflowHistoryAction.COMPLETED,
                    WorkflowStatus.WAITING: WorkflowHistoryAction.STEP_STARTED,
                    WorkflowStatus.AWAITING_APPROVAL: WorkflowHistoryAction.APPROVAL_REQUESTED,
                }
                action = action_map.get(new_status, WorkflowHistoryAction.STEP_STARTED)

                self.workflow_repo.add_history(
                    workflow_id=workflow.workflow_id,
                    action=action,
                    from_status=prev_status.value,
                    to_status=new_status.value,
                    actor_id=current_user.user_id,
                    actor_role=current_user.role,
                    reason=f"Workflow advanced to {new_status.value}",
                )

                if new_status == WorkflowStatus.COMPLETED and self.audit_service:
                    await self.audit_service.record(
                        event_type=AuditEventType.WORKFLOW_COMPLETED,
                        outcome="ALLOW",
                        actor_id=current_user.user_id,
                        action="COMPLETE_WORKFLOW",
                        resource_type="workflow",
                        resource_id=workflow.workflow_id,
                        metadata={"definition_id": workflow.definition_id},
                    )

            return workflow.model_copy(update={"steps": steps})

    async def handle_task_completion(
        self, task_id: str, current_user: AuthenticatedUserContext
    ) -> Optional[WorkflowRecord]:
        """Callback invoked when a Phase 36 clinical task reaches COMPLETED status."""
        step = self.step_repo.get_by_task_id(task_id)
        if not step:
            return None

        # Mark step completed
        self.step_service.handle_task_completed(step, task_id)

        # Advance parent workflow
        return await self.advance_workflow(step.workflow_id, current_user)

    async def handle_domain_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        current_user: AuthenticatedUserContext,
    ) -> List[WorkflowRecord]:
        """Deliver an external domain event to unblock waiting workflows."""
        affected_workflows = []
        for wf in self.workflow_repo._workflows.values():
            if wf.status == WorkflowStatus.WAITING:
                steps = self.step_repo.list_by_workflow_id(wf.workflow_id)
                for step in steps:
                    if step.status == WorkflowStepStatus.WAITING and step.waiting_for_event == event_name:
                        self.step_service.handle_event_received(step, event_name)
                        advanced = await self.advance_workflow(wf.workflow_id, current_user)
                        affected_workflows.append(advanced)
        return affected_workflows

    async def pause_workflow(
        self,
        workflow_id: str,
        request: WorkflowPauseRequest,
        current_user: AuthenticatedUserContext,
    ) -> WorkflowRecord:
        """Pause execution of a running or waiting workflow."""
        workflow = await self.get_workflow(workflow_id, current_user)

        self.val_service.validate_workflow_transition(workflow.status, WorkflowStatus.PAUSED)

        now = datetime.now(timezone.utc)
        updated = workflow.model_copy(update={"status": WorkflowStatus.PAUSED, "updated_at": now})
        saved = self.workflow_repo.save(updated)

        self.workflow_repo.add_history(
            workflow_id=saved.workflow_id,
            action=WorkflowHistoryAction.PAUSED,
            from_status=workflow.status.value,
            to_status=WorkflowStatus.PAUSED.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.reason,
        )

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.WORKFLOW_PAUSED,
                outcome="ALLOW",
                actor_id=current_user.user_id,
                action="PAUSE_WORKFLOW",
                resource_type="workflow",
                resource_id=saved.workflow_id,
                metadata={"reason": request.reason},
            )

        steps = self.step_repo.list_by_workflow_id(workflow_id)
        return saved.model_copy(update={"steps": steps})

    async def resume_workflow(
        self,
        workflow_id: str,
        request: WorkflowResumeRequest,
        current_user: AuthenticatedUserContext,
    ) -> WorkflowRecord:
        """Resume execution of a paused workflow."""
        workflow = await self.get_workflow(workflow_id, current_user)

        if workflow.status != WorkflowStatus.PAUSED:
            raise WorkflowCannotResumeException(
                f"Cannot resume workflow '{workflow_id}' in state '{workflow.status.value}'. Must be 'PAUSED'."
            )

        self.val_service.validate_workflow_transition(workflow.status, WorkflowStatus.RUNNING)

        now = datetime.now(timezone.utc)
        updated = workflow.model_copy(update={"status": WorkflowStatus.RUNNING, "updated_at": now})
        saved = self.workflow_repo.save(updated)

        self.workflow_repo.add_history(
            workflow_id=saved.workflow_id,
            action=WorkflowHistoryAction.RESUMED,
            from_status=WorkflowStatus.PAUSED.value,
            to_status=WorkflowStatus.RUNNING.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.reason or "Workflow resumed",
        )

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.WORKFLOW_RESUMED,
                outcome="ALLOW",
                actor_id=current_user.user_id,
                action="RESUME_WORKFLOW",
                resource_type="workflow",
                resource_id=saved.workflow_id,
                metadata={"reason": request.reason},
            )

        # Advance resumed workflow
        return await self.advance_workflow(saved.workflow_id, current_user)

    async def cancel_workflow(
        self,
        workflow_id: str,
        request: WorkflowCancelRequest,
        current_user: AuthenticatedUserContext,
    ) -> WorkflowRecord:
        """Cancel an active workflow instance without deleting execution history."""
        workflow = await self.get_workflow(workflow_id, current_user)

        if workflow.status == WorkflowStatus.COMPLETED:
            raise WorkflowAlreadyCompletedException("Cannot cancel a completed workflow.")
        if workflow.status == WorkflowStatus.CANCELLED:
            raise WorkflowAlreadyCancelledException("Workflow is already cancelled.")

        self.val_service.validate_workflow_transition(workflow.status, WorkflowStatus.CANCELLED)

        now = datetime.now(timezone.utc)
        updated = workflow.model_copy(
            update={
                "status": WorkflowStatus.CANCELLED,
                "failure_reason": f"Cancelled: {request.reason}",
                "updated_at": now,
            }
        )
        saved = self.workflow_repo.save(updated)

        # Cancel steps that are not terminal
        steps = self.step_repo.list_by_workflow_id(workflow_id)
        for s in steps:
            if s.status not in {WorkflowStepStatus.COMPLETED, WorkflowStepStatus.SKIPPED, WorkflowStepStatus.CANCELLED}:
                cancelled_s = s.model_copy(
                    update={"status": WorkflowStepStatus.CANCELLED, "updated_at": now}
                )
                self.step_repo.save(cancelled_s)

                # Optionally cancel pending tasks if requested
                if request.cancel_pending_tasks and s.related_task_id and self.task_service:
                    try:
                        await self.task_service.cancel_task(
                            task_id=s.related_task_id,
                            request=TaskCancelRequest(reason=f"Parent workflow {workflow_id} cancelled"),
                            current_user=current_user,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to cancel child task {s.related_task_id}: {e}")

        self.workflow_repo.add_history(
            workflow_id=saved.workflow_id,
            action=WorkflowHistoryAction.CANCELLED,
            from_status=workflow.status.value,
            to_status=WorkflowStatus.CANCELLED.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.reason,
        )

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.WORKFLOW_CANCELLED,
                outcome="ALLOW",
                actor_id=current_user.user_id,
                action="CANCEL_WORKFLOW",
                resource_type="workflow",
                resource_id=saved.workflow_id,
                metadata={"reason": request.reason},
            )

        updated_steps = self.step_repo.list_by_workflow_id(workflow_id)
        return saved.model_copy(update={"steps": updated_steps})

    async def get_workflow(
        self, workflow_id: str, current_user: AuthenticatedUserContext
    ) -> WorkflowRecord:
        """Fetch workflow instance enforcing patient BOLA and multi-tenant facility scoping."""
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise WorkflowNotFoundException(f"Workflow '{workflow_id}' not found.")

        # Patient BOLA check
        if current_user.role == "PATIENT":
            if not workflow.patient_id or (
                workflow.patient_id != current_user.patient_id
                and workflow.patient_id != current_user.user_id
            ):
                raise WorkflowAccessDeniedException(
                    f"Patient is not authorized to access workflow '{workflow_id}'."
                )

        # Facility scoping for non-admin clinical staff
        if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN", "PATIENT"}:
            if (
                current_user.facility_id
                and workflow.facility_id
                and current_user.facility_id != workflow.facility_id
            ):
                raise WorkflowAccessDeniedException(
                    f"Staff member is not authorized to access workflow in facility '{workflow.facility_id}'."
                )

        steps = self.step_repo.list_by_workflow_id(workflow_id)
        return workflow.model_copy(update={"steps": steps})

    async def list_workflows(
        self,
        filters: WorkflowFilter,
        current_user: AuthenticatedUserContext,
    ) -> WorkflowListResponse:
        """List workflows matching filter criteria with mandatory security scoping."""
        scoped_patient_id: Optional[str] = None
        scoped_facility_id: Optional[str] = None

        if current_user.role == "PATIENT":
            scoped_patient_id = current_user.patient_id or current_user.user_id
        elif current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            scoped_facility_id = current_user.facility_id

        workflows, total = self.workflow_repo.list_workflows(
            filters=filters,
            scoped_patient_id=scoped_patient_id,
            scoped_facility_id=scoped_facility_id,
        )

        populated = []
        for wf in workflows:
            steps = self.step_repo.list_by_workflow_id(wf.workflow_id)
            populated.append(wf.model_copy(update={"steps": steps}))

        return WorkflowListResponse(
            items=populated,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            has_more=(filters.page * filters.page_size) < total,
        )

    async def get_workflow_steps(
        self, workflow_id: str, current_user: AuthenticatedUserContext
    ) -> List[WorkflowStepRecord]:
        """Fetch all step instances for an authorized workflow."""
        await self.get_workflow(workflow_id, current_user)
        return self.step_repo.list_by_workflow_id(workflow_id)

    async def get_workflow_history(
        self, workflow_id: str, current_user: AuthenticatedUserContext
    ) -> List[Any]:
        """Fetch complete immutable transition history for an authorized workflow."""
        await self.get_workflow(workflow_id, current_user)
        return self.workflow_repo.get_history(workflow_id)

    async def get_workflow_approvals(
        self, workflow_id: str, current_user: AuthenticatedUserContext
    ) -> List[Any]:
        """Fetch all recorded approval gate decisions for an authorized workflow."""
        await self.get_workflow(workflow_id, current_user)
        return self.workflow_repo.get_approvals(workflow_id)

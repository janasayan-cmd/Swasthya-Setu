"""Step orchestration and execution engine for Clinical Workflows (Phase 37).

Responsibilities:
- Step lifecycle transitions
- Dependency graph evaluation
- Deterministic action dispatching (Task creation, notification, wait-for-event, approval gate)
- Bounded retries with idempotency protection
- Integration with TaskService (Phase 36), AlertService (Phase 35), NotificationService (Phase 29)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    WorkflowOperationNotAllowedException,
    WorkflowStepBlockedException,
    WorkflowStepNotFoundException,
)
from app.repositories.workflow_step_repository import WorkflowStepRepository
from app.schemas.audit import AuditEventType
from app.schemas.notification import NotificationCreate, NotificationType
from app.schemas.task import TaskCategory, TaskCreate, TaskPriority, TaskProvenance
from app.schemas.user import AuthenticatedUserContext
from app.schemas.workflow import WorkflowRecord
from app.schemas.workflow_step import (
    WorkflowStepActionType,
    WorkflowStepRecord,
    WorkflowStepStatus,
)
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService
from app.services.workflow_validation_service import WorkflowValidationService

logger = logging.getLogger(__name__)


class WorkflowStepService:
    """Coordinates execution, dependency resolution, and lifecycle updates for workflow steps."""

    def __init__(
        self,
        step_repo: Optional[WorkflowStepRepository] = None,
        val_service: Optional[WorkflowValidationService] = None,
        task_service: Optional[TaskService] = None,
        alert_service: Optional[AlertService] = None,
        notification_service: Optional[NotificationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.step_repo = step_repo or WorkflowStepRepository()
        self.val_service = val_service or WorkflowValidationService()
        self.task_service = task_service
        self.alert_service = alert_service
        self.notification_service = notification_service
        self.audit_service = audit_service

    def create_step_instance(
        self,
        workflow: WorkflowRecord,
        step_def: Any,
    ) -> WorkflowStepRecord:
        """Instantiate a runtime step record from its workflow definition configuration."""
        step = WorkflowStepRecord(
            step_instance_id="",
            workflow_id=workflow.workflow_id,
            step_id=step_def.step_id,
            name=step_def.name,
            order=step_def.order,
            action_type=step_def.action_type,
            action_config=step_def.action_config,
            status=WorkflowStepStatus.PENDING,
            dependencies=step_def.dependencies,
            approval_required=step_def.approval_required,
            required_approval_role=step_def.required_approval_role,
            max_retries=step_def.max_retries,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return self.step_repo.save(step)

    async def execute_step(
        self,
        workflow: WorkflowRecord,
        step: WorkflowStepRecord,
        all_steps: List[WorkflowStepRecord],
        system_user: AuthenticatedUserContext,
    ) -> WorkflowStepRecord:
        """Evaluate dependencies and execute step action idempotently."""
        # 1. Dependency validation
        if not self.val_service.are_dependencies_satisfied(step, all_steps):
            if step.status != WorkflowStepStatus.PENDING:
                self.val_service.validate_step_transition(step.status, WorkflowStepStatus.BLOCKED)
                step = step.model_copy(update={"status": WorkflowStepStatus.BLOCKED})
                return self.step_repo.save(step)
            return step

        # If step was BLOCKED or PENDING, promote to READY
        if step.status in {WorkflowStepStatus.PENDING, WorkflowStepStatus.BLOCKED}:
            self.val_service.validate_step_transition(step.status, WorkflowStepStatus.READY)
            step = step.model_copy(update={"status": WorkflowStepStatus.READY})
            step = self.step_repo.save(step)

        # Transition READY -> RUNNING
        if step.status == WorkflowStepStatus.READY:
            self.val_service.validate_step_transition(step.status, WorkflowStepStatus.RUNNING)
            now = datetime.now(timezone.utc)
            step = step.model_copy(
                update={"status": WorkflowStepStatus.RUNNING, "started_at": now, "updated_at": now}
            )
            step = self.step_repo.save(step)

        # 2. Check clinical action boundaries (TRD Section 17)
        self.val_service.assert_clinical_action_boundary(
            action_type=step.action_type.value,
            action_payload=step.action_config,
        )

        try:
            # 3. Action Dispatch
            if step.action_type == WorkflowStepActionType.HUMAN_APPROVAL:
                # Transition step to AWAITING_APPROVAL gate
                self.val_service.validate_step_transition(step.status, WorkflowStepStatus.AWAITING_APPROVAL)
                step = step.model_copy(
                    update={
                        "status": WorkflowStepStatus.AWAITING_APPROVAL,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                return self.step_repo.save(step)

            elif step.action_type == WorkflowStepActionType.WAIT_FOR_EVENT:
                event_name = step.action_config.get("event_name", "GENERIC_EVENT")
                self.val_service.validate_step_transition(step.status, WorkflowStepStatus.WAITING)
                step = step.model_copy(
                    update={
                        "status": WorkflowStepStatus.WAITING,
                        "waiting_for_event": event_name,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                return self.step_repo.save(step)

            elif step.action_type == WorkflowStepActionType.CREATE_TASK:
                # Delegate to Phase 36 Task Service
                if self.task_service:
                    task_category_str = step.action_config.get(
                        "task_category", TaskCategory.CLINICAL_TASK.value
                    )
                    try:
                        task_category = TaskCategory(task_category_str)
                    except ValueError:
                        task_category = TaskCategory.CLINICAL_TASK

                    priority_str = step.action_config.get("priority", TaskPriority.NORMAL.value)
                    try:
                        task_priority = TaskPriority(priority_str)
                    except ValueError:
                        task_priority = TaskPriority.NORMAL

                    task_create = TaskCreate(
                        title=step.action_config.get("task_title", f"Workflow Task: {step.name}"),
                        description=f"Action required for workflow step '{step.name}' in {workflow.name}.",
                        category=task_category,
                        priority=task_priority,
                        provenance=TaskProvenance(
                            source_type="WORKFLOW_STEP",
                            source_id=step.step_instance_id,
                            source_system="WORKFLOW_ORCHESTRATION",
                            source_event_id=workflow.correlation_id,
                        ),
                        patient_id=workflow.patient_id,
                        encounter_id=workflow.encounter_id,
                        facility_id=workflow.facility_id,
                        idempotency_key=f"TASK-WF-{workflow.workflow_id}-{step.step_id}",
                    )
                    created_task = await self.task_service.create_task(
                        payload=task_create, current_user=system_user
                    )
                    self.val_service.validate_step_transition(step.status, WorkflowStepStatus.WAITING)
                    step = step.model_copy(
                        update={
                            "status": WorkflowStepStatus.WAITING,
                            "related_task_id": created_task.id,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                    return self.step_repo.save(step)
                else:
                    # If no task service configured, complete deterministically
                    self.val_service.validate_step_transition(step.status, WorkflowStepStatus.COMPLETED)
                    step = step.model_copy(
                        update={
                            "status": WorkflowStepStatus.COMPLETED,
                            "completed_at": datetime.now(timezone.utc),
                        }
                    )
                    return self.step_repo.save(step)

            elif step.action_type == WorkflowStepActionType.SEND_NOTIFICATION:
                if self.notification_service:
                    try:
                        notif = NotificationCreate(
                            recipient_id=workflow.patient_id or system_user.user_id,
                            recipient_type="PATIENT" if workflow.patient_id else "SYSTEM",
                            notification_type=NotificationType.WORKFLOW_STARTED,
                            priority="NORMAL",
                            title=f"Workflow Update: {workflow.name}",
                            body=f"Step '{step.name}' processed successfully.",
                            variables={
                                "workflow_id": workflow.workflow_id,
                                "step_name": step.name,
                            },
                            facility_id=workflow.facility_id,
                        )
                        await self.notification_service.send_notification(notif)
                    except Exception as e:
                        logger.warning(f"Workflow notification failed: {e}")

                self.val_service.validate_step_transition(step.status, WorkflowStepStatus.COMPLETED)
                step = step.model_copy(
                    update={
                        "status": WorkflowStepStatus.COMPLETED,
                        "completed_at": datetime.now(timezone.utc),
                    }
                )
                return self.step_repo.save(step)

            elif step.action_type in {
                WorkflowStepActionType.REQUEST_DOCUMENT_PROCESSING,
                WorkflowStepActionType.REQUEST_NORMALIZATION,
                WorkflowStepActionType.DOMAIN_ACTION,
            }:
                # Deterministic domain coordination actions
                self.val_service.validate_step_transition(step.status, WorkflowStepStatus.COMPLETED)
                step = step.model_copy(
                    update={
                        "status": WorkflowStepStatus.COMPLETED,
                        "completed_at": datetime.now(timezone.utc),
                    }
                )
                return self.step_repo.save(step)

            else:
                self.val_service.validate_step_transition(step.status, WorkflowStepStatus.COMPLETED)
                step = step.model_copy(
                    update={
                        "status": WorkflowStepStatus.COMPLETED,
                        "completed_at": datetime.now(timezone.utc),
                    }
                )
                return self.step_repo.save(step)

        except Exception as ex:
            logger.error(f"Error executing step {step.step_id} in {workflow.workflow_id}: {ex}")
            # Bounded retry handling
            if step.retry_count < step.max_retries:
                step = step.model_copy(
                    update={
                        "status": WorkflowStepStatus.READY,
                        "retry_count": step.retry_count + 1,
                        "error_message": str(ex),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                return self.step_repo.save(step)
            else:
                self.val_service.validate_step_transition(step.status, WorkflowStepStatus.FAILED)
                step = step.model_copy(
                    update={
                        "status": WorkflowStepStatus.FAILED,
                        "error_message": str(ex),
                        "error_code": "STEP_EXECUTION_FAILED",
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                return self.step_repo.save(step)

    def handle_task_completed(
        self, step: WorkflowStepRecord, task_id: str
    ) -> WorkflowStepRecord:
        """Unblock step when its linked Phase 36 task has completed."""
        if step.related_task_id != task_id:
            return step

        if step.status in {WorkflowStepStatus.WAITING, WorkflowStepStatus.RUNNING}:
            self.val_service.validate_step_transition(step.status, WorkflowStepStatus.COMPLETED)
            step = step.model_copy(
                update={
                    "status": WorkflowStepStatus.COMPLETED,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            return self.step_repo.save(step)

        return step

    def handle_event_received(
        self, step: WorkflowStepRecord, event_name: str
    ) -> WorkflowStepRecord:
        """Unblock step waiting for a specific domain event."""
        if step.status == WorkflowStepStatus.WAITING and step.waiting_for_event == event_name:
            self.val_service.validate_step_transition(step.status, WorkflowStepStatus.COMPLETED)
            step = step.model_copy(
                update={
                    "status": WorkflowStepStatus.COMPLETED,
                    "waiting_for_event": None,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            return self.step_repo.save(step)

        return step

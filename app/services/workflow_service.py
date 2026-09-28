"""Workflow Orchestration Service (Phase 22).

Coordinates multi-step asynchronous processing pipelines while enforcing:
- Explicit stage state transitions.
- Preservation of previous stages upon partial failure.
- Fail-safe clinical boundaries (e.g., safety checks never convert to fake CLEAR).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import WorkflowInvalidStateException, WorkflowNotFoundException
from app.core.logging import get_logger
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.audit import AuditEventType
from app.schemas.workflow import StepStatus, WorkflowRecord, WorkflowResponse, WorkflowStatus, WorkflowStep
from app.services.audit_service import AuditService
from app.services.base import BaseService

logger = get_logger("app.services.workflow")


class WorkflowService(BaseService[WorkflowRepository]):
    """Orchestrates multi-stage background pipelines with state persistence and partial failure containment."""

    def __init__(
        self,
        repository: WorkflowRepository,
        audit_service: AuditService,
    ) -> None:
        super().__init__(repository=repository)
        self.workflow_repo = repository
        self.audit_service = audit_service

    async def create_workflow(
        self,
        workflow_type: str,
        steps: List[WorkflowStep],
        patient_id: Optional[str] = None,
        initiating_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowRecord:
        """Initialize a new multi-step asynchronous workflow."""
        workflow = WorkflowRecord(
            workflow_type=workflow_type,
            patient_id=patient_id,
            initiating_user_id=initiating_user_id,
            status=WorkflowStatus.PENDING,
            current_step_index=0,
            steps=steps,
            metadata=metadata or {},
        )
        saved = await self.workflow_repo.create(workflow)

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

    async def get_workflow(self, workflow_id: str) -> WorkflowRecord:
        """Fetch workflow record by ID."""
        record = await self.workflow_repo.get(workflow_id)
        if not record:
            raise WorkflowNotFoundException(workflow_id=workflow_id)
        return record

    async def advance_step(
        self,
        workflow_id: str,
        step_order: int,
        step_status: StepStatus,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> WorkflowRecord:
        """Update the state of an individual workflow stage and advance pipeline."""
        workflow = await self.get_workflow(workflow_id)

        target_step: Optional[WorkflowStep] = None
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

        if step_status == StepStatus.RUNNING:
            target_step.started_at = now
            workflow.status = WorkflowStatus.RUNNING
        elif step_status == StepStatus.COMPLETED:
            target_step.completed_at = now
        elif step_status == StepStatus.FAILED:
            target_step.completed_at = now
            if target_step.required:
                workflow.status = WorkflowStatus.PARTIALLY_FAILED
                logger.warning(
                    f"Required workflow step '{target_step.step_name}' failed in workflow {workflow_id}. Setting PARTIALLY_FAILED."
                )

        # Check overall pipeline completion if not already marked partially failed
        all_done = all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.FAILED) for s in workflow.steps)
        if all_done:
            has_required_failures = any(s.status == StepStatus.FAILED and s.required for s in workflow.steps)
            if has_required_failures:
                workflow.status = WorkflowStatus.PARTIALLY_FAILED
            else:
                workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = now

            await self.audit_service.record(
                event_type=(
                    AuditEventType.WORKFLOW_COMPLETED
                    if workflow.status == WorkflowStatus.COMPLETED
                    else AuditEventType.WORKFLOW_FAILED
                ),
                outcome="ALLOW" if workflow.status == WorkflowStatus.COMPLETED else "DENY",
                actor_id=workflow.initiating_user_id,
                action=f"workflow:finish:{workflow.workflow_type}",
                resource_type="workflow",
                resource_id=workflow.id,
                metadata={"status": workflow.status.value},
            )

        return await self.workflow_repo.update(workflow)

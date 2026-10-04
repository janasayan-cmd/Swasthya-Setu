"""Validation service for Workflow state transitions and clinical safety boundaries (Phase 37).

Enforces:
- Explicit state transition maps (no arbitrary status jumps).
- Non-authoritative clinical boundary (workflow does not diagnose, prescribe, mutate medications/allergies/triage).
- AI non-authority (AI suggestions cannot bypass approval gates or declare clinical truth).
"""

from __future__ import annotations

from typing import Dict, List, Set

from app.core.exceptions import (
    WorkflowApprovalNotAllowedException,
    WorkflowInvalidStateException,
    WorkflowInvalidTransitionException,
    WorkflowOperationNotAllowedException,
)
from app.schemas.workflow import WorkflowStatus
from app.schemas.workflow_step import WorkflowStepRecord, WorkflowStepStatus


class WorkflowValidationService:
    """Validates workflow state machines, dependency graphs, and clinical boundaries."""

    # Explicit workflow lifecycle transition graph
    VALID_WORKFLOW_TRANSITIONS: Dict[WorkflowStatus, Set[WorkflowStatus]] = {
        WorkflowStatus.CREATED: {WorkflowStatus.READY, WorkflowStatus.CANCELLED},
        WorkflowStatus.READY: {
            WorkflowStatus.RUNNING,
            WorkflowStatus.PAUSED,
            WorkflowStatus.BLOCKED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.FAILED,
        },
        WorkflowStatus.RUNNING: {
            WorkflowStatus.WAITING,
            WorkflowStatus.AWAITING_APPROVAL,
            WorkflowStatus.BLOCKED,
            WorkflowStatus.PAUSED,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        },
        WorkflowStatus.WAITING: {
            WorkflowStatus.RUNNING,
            WorkflowStatus.AWAITING_APPROVAL,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.PAUSED,
            WorkflowStatus.BLOCKED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.EXPIRED,
        },
        WorkflowStatus.AWAITING_APPROVAL: {
            WorkflowStatus.RUNNING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.PAUSED,
            WorkflowStatus.BLOCKED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.EXPIRED,
        },
        WorkflowStatus.PAUSED: {
            WorkflowStatus.RUNNING,
            WorkflowStatus.CANCELLED,
        },
        WorkflowStatus.BLOCKED: {
            WorkflowStatus.READY,
            WorkflowStatus.RUNNING,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.FAILED,
        },
        WorkflowStatus.COMPLETED: set(),  # Terminal state
        WorkflowStatus.FAILED: {WorkflowStatus.RUNNING},  # May be retried
        WorkflowStatus.CANCELLED: set(),  # Terminal state
        WorkflowStatus.EXPIRED: set(),  # Terminal state
    }

    # Explicit step lifecycle transition graph
    VALID_STEP_TRANSITIONS: Dict[WorkflowStepStatus, Set[WorkflowStepStatus]] = {
        WorkflowStepStatus.PENDING: {
            WorkflowStepStatus.READY,
            WorkflowStepStatus.SKIPPED,
            WorkflowStepStatus.CANCELLED,
            WorkflowStepStatus.BLOCKED,
        },
        WorkflowStepStatus.READY: {
            WorkflowStepStatus.RUNNING,
            WorkflowStepStatus.BLOCKED,
            WorkflowStepStatus.CANCELLED,
            WorkflowStepStatus.SKIPPED,
        },
        WorkflowStepStatus.RUNNING: {
            WorkflowStepStatus.WAITING,
            WorkflowStepStatus.AWAITING_APPROVAL,
            WorkflowStepStatus.COMPLETED,
            WorkflowStepStatus.FAILED,
            WorkflowStepStatus.CANCELLED,
        },
        WorkflowStepStatus.WAITING: {
            WorkflowStepStatus.RUNNING,
            WorkflowStepStatus.COMPLETED,
            WorkflowStepStatus.FAILED,
            WorkflowStepStatus.CANCELLED,
        },
        WorkflowStepStatus.AWAITING_APPROVAL: {
            WorkflowStepStatus.COMPLETED,
            WorkflowStepStatus.FAILED,
            WorkflowStepStatus.CANCELLED,
        },
        WorkflowStepStatus.BLOCKED: {
            WorkflowStepStatus.READY,
            WorkflowStepStatus.CANCELLED,
            WorkflowStepStatus.FAILED,
        },
        WorkflowStepStatus.COMPLETED: set(),  # Terminal state
        WorkflowStepStatus.FAILED: {WorkflowStepStatus.READY, WorkflowStepStatus.RUNNING},  # Retry
        WorkflowStepStatus.SKIPPED: set(),  # Terminal state
        WorkflowStepStatus.CANCELLED: set(),  # Terminal state
    }

    # Forbidden direct clinical mutation targets inside workflow orchestration layer
    FORBIDDEN_CLINICAL_ACTIONS: Set[str] = {
        "MODIFY_DIAGNOSIS",
        "APPLY_TREATMENT",
        "PRESCRIBE_MEDICATION",
        "ALTER_MEDICATION_ORDER",
        "ALTER_ALLERGY_RECORD",
        "MODIFY_TRIAGE_LEVEL",
        "DISPATCH_EMERGENCY_SERVICES",
    }

    def validate_workflow_transition(
        self, from_status: WorkflowStatus, to_status: WorkflowStatus
    ) -> None:
        """Ensure workflow state transition follows authoritative lifecycle model."""
        if from_status == to_status:
            return

        allowed = self.VALID_WORKFLOW_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise WorkflowInvalidTransitionException(
                f"Invalid workflow transition from '{from_status.value}' to '{to_status.value}'."
            )

    def validate_step_transition(
        self, from_status: WorkflowStepStatus, to_status: WorkflowStepStatus
    ) -> None:
        """Ensure step state transition follows authoritative lifecycle model."""
        if from_status == to_status:
            return

        allowed = self.VALID_STEP_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise WorkflowInvalidTransitionException(
                f"Invalid workflow step transition from '{from_status.value}' to '{to_status.value}'."
            )

    def assert_clinical_action_boundary(self, action_type: str, action_payload: dict) -> None:
        """Enforce TRD Section 17 & 60: Orchestrator must not directly execute clinical mutations."""
        action_name = str(action_payload.get("action", "")).upper()
        if action_name in self.FORBIDDEN_CLINICAL_ACTIONS or action_type in self.FORBIDDEN_CLINICAL_ACTIONS:
            raise WorkflowOperationNotAllowedException(
                f"Forbidden clinical mutation '{action_name or action_type}': "
                f"Workflow orchestrator cannot perform direct clinical mutations. "
                f"Must coordinate through authorized clinical tasks or domain events."
            )

    def assert_ai_non_authority(
        self, actor_role: str, action: str, actor_id: Optional[str] = None
    ) -> None:
        """Enforce TRD Section 34 & 60: AI output cannot bypass human approval or act as clinical authority."""
        normalized_role = str(actor_role).upper()
        normalized_id = str(actor_id or "").upper()
        if (
            "AI" in normalized_role
            or "MODEL" in normalized_role
            or "AUTOMATION" in normalized_role
            or "AI" in normalized_id
            or "MODEL" in normalized_id
            or "BOT" in normalized_id
        ):
            if action in {"APPROVE", "REJECT", "VERIFY", "MODIFY_DEFINITION", "DECLARE_CLINICAL_SAFETY"}:
                raise WorkflowApprovalNotAllowedException(
                    f"AI role or actor '{actor_id or actor_role}' is not authorized to perform clinical approval or modification action '{action}'."
                )

    def are_dependencies_satisfied(
        self, step: WorkflowStepRecord, all_steps: List[WorkflowStepRecord]
    ) -> bool:
        """Check whether all prerequisite dependencies for this step have met their required status."""
        if not step.dependencies:
            return True

        step_map = {s.step_id: s for s in all_steps}
        for dep in step.dependencies:
            prereq = step_map.get(dep.depends_on_step_id)
            if not prereq:
                return False
            if prereq.status != dep.required_status:
                return False

        return True

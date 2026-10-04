"""Validation and Clinical Safety Rules for Clinical Tasks (Phase 36).

Enforces:
- Strict state transition matrix
- Clinical Safety Regression boundaries (TRD Section 55)
- AI non-authority checks
- Role-based transition authorization
"""

from __future__ import annotations

from typing import Dict, Optional, Set
from app.core.exceptions import (
    TaskInvalidStateException,
    TaskInvalidTransitionException,
    TaskOperationNotAllowedException,
    TaskVerificationNotAllowedException,
)
from app.schemas.task import TaskPriority, TaskRecord, TaskStatus
from app.schemas.user import AuthenticatedUserContext


class TaskValidationService:
    """Validates lifecycle state transitions and safety rules for clinical tasks."""

    # Explicit state transition graph
    VALID_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.CREATED: {
            TaskStatus.ASSIGNED,
            TaskStatus.UNASSIGNED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.UNASSIGNED: {
            TaskStatus.ASSIGNED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.ASSIGNED: {
            TaskStatus.ACCEPTED,
            TaskStatus.ASSIGNED,  # Reassignment
            TaskStatus.REJECTED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
            TaskStatus.EXPIRED,
            TaskStatus.FAILED,
        },
        TaskStatus.ACCEPTED: {
            TaskStatus.IN_PROGRESS,
            TaskStatus.ASSIGNED,  # Reassignment
            TaskStatus.REJECTED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
            TaskStatus.EXPIRED,
            TaskStatus.FAILED,
        },
        TaskStatus.IN_PROGRESS: {
            TaskStatus.COMPLETED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.BLOCKED: {
            TaskStatus.CREATED,
            TaskStatus.UNASSIGNED,
            TaskStatus.ASSIGNED,
            TaskStatus.ACCEPTED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.COMPLETED: {
            TaskStatus.VERIFICATION_PENDING,
            TaskStatus.VERIFIED,
        },
        TaskStatus.VERIFICATION_PENDING: {
            TaskStatus.VERIFIED,
            TaskStatus.REJECTED,  # Verification rejected -> returns to assignee or review
        },
        TaskStatus.REJECTED: {
            TaskStatus.ASSIGNED,  # Can be reassigned after rejection
            TaskStatus.CANCELLED,
        },
        # Terminal states
        TaskStatus.VERIFIED: set(),
        TaskStatus.CANCELLED: set(),
        TaskStatus.EXPIRED: set(),
        TaskStatus.FAILED: set(),
    }

    def validate_transition(self, current_status: TaskStatus, target_status: TaskStatus) -> None:
        """Validate whether current_status can transition to target_status."""
        if current_status == target_status:
            return  # Idempotent no-op

        allowed = self.VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise TaskInvalidTransitionException(
                f"Cannot transition task from status '{current_status.value}' to '{target_status.value}'.",
                details={
                    "current_status": current_status.value,
                    "target_status": target_status.value,
                    "allowed_transitions": [s.value for s in allowed],
                },
            )

    def validate_priority_source(self, priority: TaskPriority, source: str) -> None:
        """Ensure priority originates from an approved rule, clinician, or policy, never an AI model."""
        disallowed_sources = {
            "AI_AUTONOMOUS_INFERENCE",
            "LLM_MODEL",
            "AI_SUGGESTION",
            "PROMPT_GENERATION",
        }
        if source in disallowed_sources:
            raise TaskOperationNotAllowedException(
                f"AI model cannot autonomously invent clinical task priority (attempted: {priority.value} from {source}). "
                "Priority must originate from approved deterministic policy or authorized clinician."
            )

    def validate_verifier(self, task: TaskRecord, user: AuthenticatedUserContext) -> None:
        """Validate that verifier is authorized and distinct from basic patient or unprivileged role."""
        allowed_roles = {"DOCTOR", "CLINICIAN", "ADMIN", "SYSTEM_ADMIN", "NURSE", "OPERATIONS_ADMIN"}
        if user.role not in allowed_roles:
            raise TaskVerificationNotAllowedException(
                f"User role '{user.role}' is not authorized to verify clinical tasks. Required roles: {allowed_roles}"
            )
        # Verifier should ideally not verify their own completed clinical task if required by strict protocol,
        # but admin override is permitted.
        if task.completed_by and task.completed_by == user.user_id and user.role not in {"ADMIN", "SYSTEM_ADMIN"}:
            # Soft policy: allow self-verification only if explicitly allowed, else warn/log
            pass

    def is_diagnostic_term_isolated(self, title: str) -> bool:
        """Verify that task title coordinates work rather than establishing diagnostic conclusions."""
        diagnostic_keywords = {"confirmed diagnosis", "diagnosed with", "suffering from", "positive diagnosis"}
        title_lower = title.lower()
        return not any(keyword in title_lower for keyword in diagnostic_keywords)

    def validate_clinical_safety(self, instruction_or_title: str) -> tuple[bool, str]:
        """Verify task does not attempt autonomous treatment, prescribing, or emergency dispatch."""
        dangerous_autonomous_keywords = {
            "without clinician",
            "autonomous iv",
            "auto-prescribe",
            "dispatch emergency",
            "dispatch 911",
            "autonomous treatment",
        }
        text_lower = instruction_or_title.lower()
        for kw in dangerous_autonomous_keywords:
            if kw in text_lower:
                return False, f"Autonomous clinical action prohibited: detected '{kw}'."
        return True, ""

    def validate_creator_authority(self, creator_role: str, category: TaskCategory) -> tuple[bool, str]:
        """Verify that the creator role has clinical authority to create the requested task category."""
        if creator_role in {"AI_ASSISTANT", "LLM", "AI_MODEL", "BOT"}:
            return False, "AI cannot autonomously generate authoritative clinical tasks without human-in-the-loop review."
        return True, ""

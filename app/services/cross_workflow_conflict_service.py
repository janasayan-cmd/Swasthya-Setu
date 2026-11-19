"""Phase 67: Cross-Workflow Decision Conflict Service.

Detects, tracks, and manages conflicting authoritative governance decisions across
independent safety phases without silently choosing a winning record or overriding
authoritative ownership.

Mandatory Invariants:
1. A conflict between workflows must not be silently resolved by choosing the newest record.
2. A governance escalation cannot override an authoritative decision owned by another phase.
3. Both contradictory source records and versions must remain permanently auditable.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_escalation_repository import (
    GovernanceEscalationRepository,
    get_governance_escalation_repository,
)
from app.schemas.governance_decision_coordination import (
    ConflictSeverity,
    CrossWorkflowConflictRecord,
)
from app.schemas.governance_escalation import (
    EscalationHistoryRecord,
    EscalationLifecycleState,
)
from app.schemas.user import AuthenticatedUserContext


class CrossWorkflowConflictService:
    """Service detecting, recording, and resolving cross-workflow decision conflicts."""

    def __init__(
        self,
        repository: Optional[GovernanceEscalationRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_escalation_repository()

    def record_conflict(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        conflict_type: str,
        severity: ConflictSeverity,
        source_phase_a: str,
        source_record_id_a: str,
        source_state_a: str,
        source_version_a: str,
        source_phase_b: str,
        source_record_id_b: str,
        source_state_b: str,
        source_version_b: str,
        description: str,
    ) -> CrossWorkflowConflictRecord:
        """Explicitly capture a detected conflict between two authoritative workflows."""
        escalation = self.repository.get_escalation(escalation_id)
        if not escalation:
            raise AppException(
                code=ErrorCode.GOVERNANCE_ESCALATION_NOT_FOUND,
                message=f"Governance escalation {escalation_id} not found.",
                status_code=404,
            )
        if escalation.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot record conflict across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = CrossWorkflowConflictRecord(
            escalation_id=escalation_id,
            conflict_type=conflict_type,
            severity=severity,
            is_material=True,
            source_phase_a=source_phase_a,
            source_record_id_a=source_record_id_a,
            source_state_a=source_state_a,
            source_version_a=source_version_a,
            source_phase_b=source_phase_b,
            source_record_id_b=source_record_id_b,
            source_state_b=source_state_b,
            source_version_b=source_version_b,
            description=description,
            is_resolved=False,
            detected_at=now,
        )

        self.repository.save_conflict(record)

        # Mark escalation as conflicted
        prev_state = escalation.lifecycle_state
        if record.conflict_id not in escalation.conflicting_decision_ids:
            escalation.conflicting_decision_ids.append(record.conflict_id)

        if escalation.lifecycle_state not in {
            EscalationLifecycleState.CLOSED,
            EscalationLifecycleState.CANCELLED,
        }:
            escalation.lifecycle_state = EscalationLifecycleState.CONFLICTED

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=escalation.lifecycle_state,
                action="RECORD_DECISION_CONFLICT",
                performed_by=user.user_id,
                performed_at=now,
                rationale=f"Detected cross-workflow contradiction between {source_phase_a} and {source_phase_b}.",
                details={
                    "conflict_id": record.conflict_id,
                    "source_a": f"{source_phase_a}:{source_record_id_a}:{source_state_a}",
                    "source_b": f"{source_phase_b}:{source_record_id_b}:{source_state_b}",
                },
            )
        )

        return record

    def resolve_conflict(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        conflict_id: str,
        resolution_rationale: str,
    ) -> CrossWorkflowConflictRecord:
        """Resolve a recorded conflict through authorized governance reconciliation."""
        escalation = self.repository.get_escalation(escalation_id)
        if not escalation or escalation.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_ESCALATION_NOT_FOUND,
                message=f"Governance escalation {escalation_id} not found.",
                status_code=404,
            )

        conflicts = self.repository.list_conflicts(escalation_id)
        target_conflict: Optional[CrossWorkflowConflictRecord] = None
        for c in conflicts:
            if c.conflict_id == conflict_id:
                target_conflict = c
                break

        if not target_conflict:
            raise AppException(
                code=ErrorCode.DECISION_CONFLICT_UNRESOLVED,
                message=f"Conflict {conflict_id} not found on escalation {escalation_id}.",
                status_code=404,
            )

        now = datetime.now(timezone.utc)
        target_conflict.is_resolved = True
        target_conflict.resolution_rationale = resolution_rationale
        target_conflict.resolved_by = user.user_id
        target_conflict.resolved_at = now

        self.repository.save_conflict(target_conflict)

        # Check if any unresolved conflicts remain
        remaining_unresolved = any(
            not c.is_resolved for c in self.repository.list_conflicts(escalation_id)
        )
        if not remaining_unresolved and escalation.lifecycle_state == EscalationLifecycleState.CONFLICTED:
            escalation.lifecycle_state = EscalationLifecycleState.REVIEW_IN_PROGRESS
            self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=EscalationLifecycleState.CONFLICTED,
                to_state=escalation.lifecycle_state,
                action="RESOLVE_DECISION_CONFLICT",
                performed_by=user.user_id,
                performed_at=now,
                rationale=resolution_rationale,
                details={"conflict_id": conflict_id},
            )
        )

        return target_conflict


# Global singleton
_global_conflict_service = CrossWorkflowConflictService()


def get_cross_workflow_conflict_service() -> CrossWorkflowConflictService:
    """Dependency provider for cross workflow conflict service."""
    return _global_conflict_service

"""Phase 67: Governance Exception Aggregation Service.

Manages controlled aggregation, grouping, correlation, and authorized separation
of governance exceptions across safety workflows.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_escalation_repository import (
    GovernanceEscalationRepository,
    get_governance_escalation_repository,
)
from app.schemas.governance_escalation import (
    EscalationHistoryRecord,
    EscalationLifecycleState,
    GovernanceEscalationRecord,
)
from app.schemas.governance_exception import (
    ExceptionAggregationRequest,
    ExceptionSeparationRequest,
    GovernanceExceptionRecord,
)
from app.schemas.user import AuthenticatedUserContext


class GovernanceExceptionAggregationService:
    """Service handling aggregation and separation of governance exceptions."""

    def __init__(
        self,
        repository: Optional[GovernanceEscalationRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_escalation_repository()

    def aggregate_exceptions(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: ExceptionAggregationRequest,
    ) -> GovernanceEscalationRecord:
        """Aggregate specified exceptions into the target escalation."""
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
                message="Cannot aggregate exceptions across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        aggregated_count = 0

        for ex_id in payload.exception_ids:
            exception = self.repository.get_exception(ex_id)
            if not exception:
                raise AppException(
                    code=ErrorCode.GOVERNANCE_EXCEPTION_NOT_FOUND,
                    message=f"Governance exception {ex_id} not found.",
                    status_code=404,
                )
            if exception.organization_id != user.organization_id:
                raise AppException(
                    code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                    message="Cannot group exceptions from another organization.",
                    status_code=403,
                )

            # Prevent cross-patient contamination if patients are distinct and non-null
            if (
                escalation.patient_id
                and exception.patient_id
                and escalation.patient_id != exception.patient_id
            ):
                raise AppException(
                    code=ErrorCode.EXCEPTION_AGGREGATION_INVALID,
                    message="Cannot aggregate exceptions belonging to different patients.",
                    status_code=400,
                )

            # Associate exception
            exception.escalation_id = escalation_id
            self.repository.save_exception(exception)

            if ex_id not in escalation.aggregated_exception_ids:
                escalation.aggregated_exception_ids.append(ex_id)
                aggregated_count += 1

            # Inherit related workflow IDs
            for w_id in exception.related_workflow_ids:
                if w_id not in escalation.related_workflow_ids:
                    escalation.related_workflow_ids.append(w_id)

        self.repository.save_escalation(escalation)

        # Audit event
        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=escalation.lifecycle_state,
                to_state=escalation.lifecycle_state,
                action="AGGREGATE_EXCEPTIONS",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.aggregation_reason,
                details={
                    "aggregated_exceptions": payload.exception_ids,
                    "newly_aggregated_count": aggregated_count,
                },
            )
        )

        return escalation

    def separate_exception(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: ExceptionSeparationRequest,
    ) -> GovernanceEscalationRecord:
        """Separate an incorrectly grouped exception from an escalation."""
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
                message="Cannot access escalation across tenant boundaries.",
                status_code=403,
            )

        exception = self.repository.get_exception(payload.exception_id)
        if not exception:
            raise AppException(
                code=ErrorCode.GOVERNANCE_EXCEPTION_NOT_FOUND,
                message=f"Governance exception {payload.exception_id} not found.",
                status_code=404,
            )

        if payload.exception_id in escalation.aggregated_exception_ids:
            escalation.aggregated_exception_ids.remove(payload.exception_id)
            self.repository.save_escalation(escalation)

        # Unlink exception
        exception.escalation_id = None
        self.repository.save_exception(exception)

        now = datetime.now(timezone.utc)
        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=escalation.lifecycle_state,
                to_state=escalation.lifecycle_state,
                action="SEPARATE_EXCEPTION",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.separation_reason,
                details={"separated_exception_id": payload.exception_id},
            )
        )

        return escalation


# Global singleton
_global_aggregation_service = GovernanceExceptionAggregationService()


def get_governance_exception_aggregation_service() -> GovernanceExceptionAggregationService:
    """Dependency provider for aggregation service."""
    return _global_aggregation_service

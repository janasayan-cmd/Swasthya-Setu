"""Phase 79: Strategic Execution Exceptions Service.

Manages strategic execution exceptions and coordinates routing to authoritative
governance workflows (Phase 67 Escalation, Phase 63 Risk, Phase 49 Incident, Phase 54 CAPA).
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_execution_exceptions import (
    CreateExecutionExceptionRequest,
    EscalateExecutionExceptionRequest,
    ExecutionExceptionCategory,
    ExecutionExceptionStatus,
    ResolveExecutionExceptionRequest,
    StrategicExecutionExceptionRecord,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


_VALID_ESCALATION_DESTINATIONS = {
    "PHASE_67_ESCALATION": ExecutionExceptionStatus.ESCALATED_PHASE_67,
    "PHASE_63_RISK": ExecutionExceptionStatus.ESCALATED_PHASE_63,
    "PHASE_49_INCIDENT": ExecutionExceptionStatus.ESCALATED_PHASE_49,
    "PHASE_54_CAPA": ExecutionExceptionStatus.ESCALATED_PHASE_54,
    "PHASE_72_MANAGEMENT_REVIEW": ExecutionExceptionStatus.UNDER_REVIEW,
    "PHASE_78_ROADMAP_REVISION": ExecutionExceptionStatus.UNDER_REVIEW,
}


class GovernanceStrategyExecutionExceptionsService:
    """Manages strategic execution exceptions, authoritative escalations, and resolution evidence."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def create_exception(
        self,
        tenant_id: str,
        request: CreateExecutionExceptionRequest,
    ) -> StrategicExecutionExceptionRecord:
        exc_id = f"SEE-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = StrategicExecutionExceptionRecord(
            exception_id=exc_id,
            tenant_id=tenant_id,
            category=request.category,
            affected_roadmap_ids=request.affected_roadmap_ids,
            affected_objective_ids=request.affected_objective_ids or [],
            evidence_references=request.evidence_references or [],
            detection_source=request.detection_source,
            impact_description=request.impact_description,
            responsible_owner_id=request.responsible_owner_id,
            escalation_destination=None,
            escalation_reference=None,
            status=ExecutionExceptionStatus.OPEN,
            resolution_evidence=None,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_exception(record)

    def escalate_exception(
        self,
        tenant_id: str,
        exception_id: str,
        request: EscalateExecutionExceptionRequest,
    ) -> StrategicExecutionExceptionRecord:
        exc = self.repository.get_exception(exception_id)
        if not exc or exc.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_EXECUTION_EXCEPTION_NOT_FOUND,
                message=f"Strategic execution exception '{exception_id}' was not found.",
                status_code=404,
            )

        dest = request.escalation_destination.strip()
        if dest not in _VALID_ESCALATION_DESTINATIONS:
            raise AppException(
                code=ErrorCode.STRATEGY_EXECUTION_CLINICAL_SAFETY_BOUNDARY_VIOLATION,
                message=f"Invalid escalation destination '{dest}'. Must be one of {sorted(_VALID_ESCALATION_DESTINATIONS.keys())}.",
                status_code=400,
            )

        new_status = _VALID_ESCALATION_DESTINATIONS[dest]
        esc_ref = request.escalation_reference or f"ESC-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        updated = exc.model_copy(
            update={
                "status": new_status,
                "escalation_destination": dest,
                "escalation_reference": esc_ref,
                "updated_at": now_str,
            }
        )
        return self.repository.save_exception(updated)

    def resolve_exception(
        self,
        tenant_id: str,
        exception_id: str,
        request: ResolveExecutionExceptionRequest,
    ) -> StrategicExecutionExceptionRecord:
        exc = self.repository.get_exception(exception_id)
        if not exc or exc.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_EXECUTION_EXCEPTION_NOT_FOUND,
                message=f"Strategic execution exception '{exception_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = exc.model_copy(
            update={
                "status": ExecutionExceptionStatus.RESOLVED,
                "resolution_evidence": request.resolution_evidence,
                "updated_at": now_str,
            }
        )
        return self.repository.save_exception(updated)

    def get_exception(
        self,
        tenant_id: str,
        exception_id: str,
    ) -> StrategicExecutionExceptionRecord:
        exc = self.repository.get_exception(exception_id)
        if not exc or exc.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_EXECUTION_EXCEPTION_NOT_FOUND,
                message=f"Strategic execution exception '{exception_id}' was not found.",
                status_code=404,
            )
        return exc

    def list_exceptions(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[ExecutionExceptionCategory] = None,
        status: Optional[ExecutionExceptionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicExecutionExceptionRecord]:
        return self.repository.list_exceptions(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            category=category,
            status=status,
            skip=skip,
            limit=limit,
        )

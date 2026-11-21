"""Phase 79: Strategic Assumption Monitoring Service.

Tracks and validates planning assumptions underpinning approved strategic roadmaps,
identifying invalidated or expired assumptions that require strategic review.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_assumption import (
    AssumptionCategory,
    AssumptionStatus,
    CreateAssumptionRequest,
    StrategicAssumptionRecord,
    ValidateAssumptionRequest,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyAssumptionService:
    """Manages strategic planning assumptions, validation lifecycle, and review triggers."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def register_assumption(
        self,
        tenant_id: str,
        request: CreateAssumptionRequest,
    ) -> StrategicAssumptionRecord:
        assumption_id = f"SSA-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = StrategicAssumptionRecord(
            assumption_id=assumption_id,
            tenant_id=tenant_id,
            roadmap_id=request.roadmap_id,
            category=request.category,
            description=request.description,
            source_rationale=request.source_rationale,
            owner_id=request.owner_id,
            validation_method=request.validation_method,
            last_validated_date=None,
            expected_review_date=request.expected_review_date,
            status=AssumptionStatus.PROPOSED,
            impact_if_invalidated=request.impact_if_invalidated,
            supporting_evidence_reference=None,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_assumption(record)

    def validate_assumption(
        self,
        tenant_id: str,
        assumption_id: str,
        request: ValidateAssumptionRequest,
    ) -> StrategicAssumptionRecord:
        assumption = self.repository.get_assumption(assumption_id)
        if not assumption or assumption.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ASSUMPTION_NOT_FOUND,
                message=f"Strategic assumption '{assumption_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = assumption.model_copy(
            update={
                "status": request.status,
                "last_validated_date": now_str,
                "supporting_evidence_reference": request.supporting_evidence_reference or assumption.supporting_evidence_reference,
                "updated_at": now_str,
            }
        )
        return self.repository.save_assumption(updated)

    def get_assumption(
        self,
        tenant_id: str,
        assumption_id: str,
    ) -> StrategicAssumptionRecord:
        assumption = self.repository.get_assumption(assumption_id)
        if not assumption or assumption.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ASSUMPTION_NOT_FOUND,
                message=f"Strategic assumption '{assumption_id}' was not found.",
                status_code=404,
            )
        return assumption

    def list_assumptions(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[AssumptionCategory] = None,
        status: Optional[AssumptionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicAssumptionRecord]:
        return self.repository.list_assumptions(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            category=category,
            status=status,
            skip=skip,
            limit=limit,
        )

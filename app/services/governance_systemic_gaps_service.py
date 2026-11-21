"""Phase 77: Systemic Governance Gaps Service.

Identifies, tracks, confirms, and coordinates remediation of cross-dimension
and cross-facility systemic governance capability gaps.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_maturity_framework import CLINICAL_SAFETY_DISCLAIMER
from app.schemas.governance_systemic_gaps import (
    ConfirmGapRequest,
    GapStatus,
    IdentifyGapRequest,
    RouteGapRequest,
    SystemicGovernanceGapRecord,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceSystemicGapsService:
    """Manages the identification, human confirmation, and routing of systemic gaps."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def identify_gap(
        self,
        tenant_id: str,
        identified_by: str,
        request: IdentifyGapRequest,
    ) -> SystemicGovernanceGapRecord:
        now = _get_utc_now_str()
        gap = SystemicGovernanceGapRecord(
            gap_id=f"gap-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            title=request.title,
            description=request.description,
            classification=request.classification,
            status=GapStatus.POTENTIAL_GAP,
            impacted_dimensions=request.impacted_dimensions,
            impacted_scopes=request.impacted_scopes or [],
            originating_assessment_ids=request.originating_assessment_ids or [],
            identified_by=identified_by,
            identified_at=now,
            confirmed_by=None,
            confirmed_at=None,
            confirmation_notes=None,
            improvement_plan_id=None,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )
        return self.repository.save_gap(gap)

    def confirm_gap(
        self,
        tenant_id: str,
        gap_id: str,
        confirmer_id: str,
        request: ConfirmGapRequest,
    ) -> SystemicGovernanceGapRecord:
        gap = self.repository.get_gap(gap_id)
        if not gap or gap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.SYSTEMIC_GAP_NOT_FOUND,
                message=f"Systemic gap '{gap_id}' was not found.",
                status_code=404,
            )

        if gap.status != GapStatus.POTENTIAL_GAP:
            raise AppException(
                code=ErrorCode.INVALID_SYSTEMIC_GAP_STATE,
                message=f"Gap in status '{gap.status.value}' cannot be confirmed. Only POTENTIAL_GAP can be confirmed.",
                status_code=400,
            )

        now = _get_utc_now_str()
        gap = gap.model_copy(
            update={
                "status": GapStatus.CONFIRMED_GAP,
                "confirmed_by": confirmer_id,
                "confirmed_at": now,
                "confirmation_notes": request.confirmation_notes,
            }
        )
        return self.repository.save_gap(gap)

    def route_gap(
        self,
        tenant_id: str,
        gap_id: str,
        request: RouteGapRequest,
    ) -> SystemicGovernanceGapRecord:
        gap = self.repository.get_gap(gap_id)
        if not gap or gap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.SYSTEMIC_GAP_NOT_FOUND,
                message=f"Systemic gap '{gap_id}' was not found.",
                status_code=404,
            )

        # Check plan exists
        plan = self.repository.get_plan(request.improvement_plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.IMPROVEMENT_PLAN_NOT_FOUND,
                message=f"Improvement plan '{request.improvement_plan_id}' was not found.",
                status_code=404,
            )

        gap = gap.model_copy(
            update={
                "status": GapStatus.ADDRESSED_IN_PLAN,
                "improvement_plan_id": request.improvement_plan_id,
            }
        )
        return self.repository.save_gap(gap)

    def get_gap(
        self,
        tenant_id: str,
        gap_id: str,
    ) -> SystemicGovernanceGapRecord:
        gap = self.repository.get_gap(gap_id)
        if not gap or gap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.SYSTEMIC_GAP_NOT_FOUND,
                message=f"Systemic gap '{gap_id}' was not found.",
                status_code=404,
            )
        return gap

    def list_gaps(
        self,
        tenant_id: str,
        status: Optional[GapStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SystemicGovernanceGapRecord]:
        return self.repository.list_gaps(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
        )

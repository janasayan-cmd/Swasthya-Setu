"""Phase 80: Governance Continuity Requirements Service.

Manages defining, approving, and maintaining continuity targets (RTO, RPO, MTPD, MBCO),
staffing coverage, communication channels, and manual alternatives.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_requirement import (
    ApproveContinuityRequirementRequest,
    ContinuityRequirementStatus,
    CreateContinuityRequirementRequest,
    GovernanceContinuityRequirementRecord,
    SubmitContinuityRequirementRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityRequirementService:
    """Manages governance continuity requirements, approved recovery targets, and manual criteria."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_requirement(
        self,
        tenant_id: str,
        request: CreateContinuityRequirementRequest,
    ) -> GovernanceContinuityRequirementRecord:
        cap = self.repository.get_capability(request.capability_id)
        if not cap or cap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_CAPABILITY_NOT_FOUND,
                message=f"Governance capability '{request.capability_id}' was not found.",
                status_code=404,
            )

        req_id = f"GCR-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = GovernanceContinuityRequirementRecord(
            requirement_id=req_id,
            tenant_id=tenant_id,
            capability_id=request.capability_id,
            required_operating_hours=request.required_operating_hours,
            max_acceptable_interruption_hours=request.max_acceptable_interruption_hours,
            recovery_time_objective_hours=request.recovery_time_objective_hours,
            recovery_point_objective_hours=request.recovery_point_objective_hours,
            maximum_tolerable_period_disruption_hours=request.maximum_tolerable_period_disruption_hours,
            minimum_continuity_objective=request.minimum_continuity_objective,
            required_staffing_coverage=request.required_staffing_coverage,
            required_role_availability=request.required_role_availability or [],
            required_communication_channels=request.required_communication_channels or [],
            required_supporting_systems=request.required_supporting_systems or [],
            required_escalation_arrangements=request.required_escalation_arrangements,
            required_manual_alternatives=request.required_manual_alternatives,
            evidence_required_to_verify=request.evidence_required_to_verify,
            status=ContinuityRequirementStatus.DRAFT,
            approved_by=None,
            approval_reference=None,
            version=1,
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        saved = self.repository.save_requirement(record)

        # Link requirement reference on capability
        updated_cap = cap.model_copy(update={"continuity_requirement_id": req_id})
        self.repository.save_capability(updated_cap)

        return saved

    def submit_requirement(
        self,
        tenant_id: str,
        requirement_id: str,
        request: SubmitContinuityRequirementRequest,
    ) -> GovernanceContinuityRequirementRecord:
        req = self.repository.get_requirement(requirement_id)
        if not req or req.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_REQUIREMENT_NOT_FOUND,
                message=f"Continuity requirement '{requirement_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = req.model_copy(
            update={
                "status": ContinuityRequirementStatus.SUBMITTED,
                "updated_at": now_str,
            }
        )
        return self.repository.save_requirement(updated)

    def approve_requirement(
        self,
        tenant_id: str,
        approver_id: str,
        requirement_id: str,
        request: ApproveContinuityRequirementRequest,
    ) -> GovernanceContinuityRequirementRecord:
        req = self.repository.get_requirement(requirement_id)
        if not req or req.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_REQUIREMENT_NOT_FOUND,
                message=f"Continuity requirement '{requirement_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = req.model_copy(
            update={
                "status": ContinuityRequirementStatus.APPROVED,
                "approved_by": approver_id,
                "approval_reference": request.approval_reference,
                "updated_at": now_str,
            }
        )
        return self.repository.save_requirement(updated)

    def get_requirement(
        self,
        tenant_id: str,
        requirement_id: str,
    ) -> GovernanceContinuityRequirementRecord:
        req = self.repository.get_requirement(requirement_id)
        if not req or req.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_REQUIREMENT_NOT_FOUND,
                message=f"Continuity requirement '{requirement_id}' was not found.",
                status_code=404,
            )
        return req

    def get_requirement_by_capability(
        self,
        tenant_id: str,
        capability_id: str,
    ) -> Optional[GovernanceContinuityRequirementRecord]:
        return self.repository.get_requirement_by_capability(tenant_id, capability_id)

    def list_requirements(
        self,
        tenant_id: str,
        status: Optional[ContinuityRequirementStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityRequirementRecord]:
        return self.repository.list_requirements(tenant_id, status=status, skip=skip, limit=limit)

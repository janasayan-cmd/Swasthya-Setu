"""Phase 80: Alternative Governance Operating Arrangements Service.

Tracks authorized temporary operating arrangements during disruptions,
preventing emergency bypasses of clinical decision authority.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_arrangements import (
    AlternativeOperatingArrangementRecord,
    ArrangementVerificationStatus,
    CreateAlternativeArrangementRequest,
    DeactivateAlternativeArrangementRequest,
    UpdateAlternativeArrangementRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityArrangementsService:
    """Manages alternative operating arrangements, expiration tracking, and deactivation."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_alternative_arrangement(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateAlternativeArrangementRequest,
    ) -> AlternativeOperatingArrangementRecord:
        act = self.repository.get_activation(request.activation_id)
        if not act or act.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ACTIVATION_NOT_FOUND,
                message=f"Continuity activation '{request.activation_id}' was not found.",
                status_code=404,
            )

        arr_id = f"GOA-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = AlternativeOperatingArrangementRecord(
            arrangement_id=arr_id,
            tenant_id=tenant_id,
            activation_id=request.activation_id,
            affected_capability_id=request.affected_capability_id,
            description=request.description,
            authorized_procedure_reference=request.authorized_procedure_reference,
            responsible_owner_id=request.responsible_owner_id,
            activation_time=now_str,
            expiry_or_review_time=request.expiry_or_review_time,
            evidence_capture_requirements=request.evidence_capture_requirements,
            data_reconciliation_requirements=request.data_reconciliation_requirements,
            security_restrictions=request.security_restrictions,
            deactivation_conditions=request.deactivation_conditions,
            verification_status=ArrangementVerificationStatus.ACTIVE,
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_arrangement(record)

    def update_arrangement(
        self,
        tenant_id: str,
        arrangement_id: str,
        request: UpdateAlternativeArrangementRequest,
    ) -> AlternativeOperatingArrangementRecord:
        arr = self.repository.get_arrangement(arrangement_id)
        if not arr or arr.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ALTERNATIVE_ARRANGEMENT_NOT_FOUND,
                message=f"Alternative operating arrangement '{arrangement_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = arr.model_copy(
            update={
                "verification_status": request.verification_status if request.verification_status is not None else arr.verification_status,
                "expiry_or_review_time": request.extended_expiry_time if request.extended_expiry_time is not None else arr.expiry_or_review_time,
                "updated_at": now_str,
            }
        )
        return self.repository.save_arrangement(updated)

    def deactivate_arrangement(
        self,
        tenant_id: str,
        deactivator_id: str,
        arrangement_id: str,
        request: DeactivateAlternativeArrangementRequest,
    ) -> AlternativeOperatingArrangementRecord:
        arr = self.repository.get_arrangement(arrangement_id)
        if not arr or arr.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ALTERNATIVE_ARRANGEMENT_NOT_FOUND,
                message=f"Alternative operating arrangement '{arrangement_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = arr.model_copy(
            update={
                "verification_status": ArrangementVerificationStatus.DEACTIVATED,
                "updated_at": now_str,
            }
        )
        return self.repository.save_arrangement(updated)

    def get_arrangement(
        self,
        tenant_id: str,
        arrangement_id: str,
    ) -> AlternativeOperatingArrangementRecord:
        arr = self.repository.get_arrangement(arrangement_id)
        if not arr or arr.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ALTERNATIVE_ARRANGEMENT_NOT_FOUND,
                message=f"Alternative operating arrangement '{arrangement_id}' was not found.",
                status_code=404,
            )
        return arr

    def list_arrangements(
        self,
        tenant_id: str,
        activation_id: Optional[str] = None,
        verification_status: Optional[ArrangementVerificationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AlternativeOperatingArrangementRecord]:
        return self.repository.list_arrangements(
            tenant_id=tenant_id,
            activation_id=activation_id,
            verification_status=verification_status,
            skip=skip,
            limit=limit,
        )

"""Phase 80: Governance Recovery Coordination and Verification Service.

Monitors capability restoration, distinguishes technical restoration from operational
restoration, and coordinates verified sign-offs.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_recovery import (
    CreateRecoveryRecordRequest,
    GovernanceRecoveryRecord,
    RecoveryStatus,
    UpdateRecoveryStatusRequest,
    VerifyRecoveryRestorationRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityRecoveryService:
    """Manages governance recovery milestones, technical vs. operational restoration, and verification."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_recovery_record(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateRecoveryRecordRequest,
    ) -> GovernanceRecoveryRecord:
        dis = self.repository.get_disruption(request.disruption_id)
        if not dis or dis.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DISRUPTION_NOT_FOUND,
                message=f"Disruption '{request.disruption_id}' was not found.",
                status_code=404,
            )

        cap = self.repository.get_capability(request.capability_id)
        if not cap or cap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_CAPABILITY_NOT_FOUND,
                message=f"Governance capability '{request.capability_id}' was not found.",
                status_code=404,
            )

        rec_id = f"GCR-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        initial_milestones = []
        if request.initial_milestone:
            initial_milestones.append({
                "milestone": request.initial_milestone,
                "recorded_at": now_str,
                "recorded_by": author_id,
            })

        record = GovernanceRecoveryRecord(
            recovery_id=rec_id,
            tenant_id=tenant_id,
            disruption_id=request.disruption_id,
            capability_id=request.capability_id,
            pre_disruption_operating_state=request.pre_disruption_operating_state,
            recovery_start_time=now_str,
            recovery_milestones=initial_milestones,
            recovery_status=RecoveryStatus.IN_PROGRESS,
            evidence_of_restored_functionality="",
            responsible_verifier_id=None,
            verification_timestamp=None,
            verification_notes=None,
            outstanding_limitations="",
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_recovery_record(record)

    def update_recovery_status(
        self,
        tenant_id: str,
        updater_id: str,
        recovery_id: str,
        request: UpdateRecoveryStatusRequest,
    ) -> GovernanceRecoveryRecord:
        rec = self.repository.get_recovery_record(recovery_id)
        if not rec or rec.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_RECOVERY_NOT_FOUND,
                message=f"Governance recovery record '{recovery_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        milestones = list(rec.recovery_milestones)
        milestones.append({
            "milestone": request.milestone_description,
            "status": request.recovery_status.value,
            "recorded_at": now_str,
            "recorded_by": updater_id,
        })

        updated = rec.model_copy(
            update={
                "recovery_status": request.recovery_status,
                "recovery_milestones": milestones,
                "evidence_of_restored_functionality": request.evidence_notes or rec.evidence_of_restored_functionality,
                "outstanding_limitations": request.outstanding_limitations or rec.outstanding_limitations,
                "updated_at": now_str,
            }
        )
        return self.repository.save_recovery_record(updated)

    def verify_recovery_restoration(
        self,
        tenant_id: str,
        verifier_id: str,
        recovery_id: str,
        request: VerifyRecoveryRestorationRequest,
    ) -> GovernanceRecoveryRecord:
        rec = self.repository.get_recovery_record(recovery_id)
        if not rec or rec.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_RECOVERY_NOT_FOUND,
                message=f"Governance recovery record '{recovery_id}' was not found.",
                status_code=404,
            )

        dis = self.repository.get_disruption(rec.disruption_id)
        # Separation of duties: disruption coordinator cannot verify their own recovery
        if dis and verifier_id == dis.responsible_coordinator_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Disruption coordinators cannot verify their own operational recovery restoration.",
                status_code=403,
            )

        now_str = _get_utc_now_str()
        updated = rec.model_copy(
            update={
                "recovery_status": RecoveryStatus.VERIFIED,
                "responsible_verifier_id": verifier_id,
                "verification_timestamp": now_str,
                "verification_notes": request.verification_notes,
                "evidence_of_restored_functionality": f"Verified with reference: {request.verification_evidence_reference}",
                "outstanding_limitations": request.outstanding_limitations or rec.outstanding_limitations,
                "updated_at": now_str,
            }
        )
        return self.repository.save_recovery_record(updated)

    def get_recovery_record(
        self,
        tenant_id: str,
        recovery_id: str,
    ) -> GovernanceRecoveryRecord:
        rec = self.repository.get_recovery_record(recovery_id)
        if not rec or rec.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_RECOVERY_NOT_FOUND,
                message=f"Governance recovery record '{recovery_id}' was not found.",
                status_code=404,
            )
        return rec

    def list_recovery_records(
        self,
        tenant_id: str,
        disruption_id: Optional[str] = None,
        recovery_status: Optional[RecoveryStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceRecoveryRecord]:
        return self.repository.list_recovery_records(
            tenant_id=tenant_id,
            disruption_id=disruption_id,
            recovery_status=recovery_status,
            skip=skip,
            limit=limit,
        )

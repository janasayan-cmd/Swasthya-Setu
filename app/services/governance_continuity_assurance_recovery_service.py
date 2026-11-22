"""Phase 81: Recovery Performance Assurance Service.

Evaluates actual recovery records against approved RTO, RPO, MTPD, and MBCO targets.
Distinguishes technical restoration from verified governance capability restoration.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    governance_continuity_repository,
)
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_recovery import (
    AssessRecoveryPerformanceRequest,
    RecoveryPerformanceAssuranceRecord,
    RestorationStage,
    TargetPerformanceOutcome,
)


class GovernanceContinuityAssuranceRecoveryService:
    """Domain service for assessing recovery performance against approved metrics."""

    def __init__(self, repo=None, phase80_repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository
        self.phase80_repo = phase80_repo or governance_continuity_repository

    def assess_recovery(
        self,
        req: AssessRecoveryPerformanceRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> RecoveryPerformanceAssuranceRecord:
        get_fn = getattr(self.phase80_repo, "get_recovery_record", None) or getattr(self.phase80_repo, "get_recovery", None)
        rec_phase80 = get_fn(req.recovery_id) if get_fn else None
        if not rec_phase80 or rec_phase80.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_RECOVERY_NOT_FOUND,
                message=f"Phase 80 Recovery Record {req.recovery_id} not found",
                status_code=404,
            )

        assessment_id = f"RPA-{uuid.uuid4().hex[:8].upper()}"

        d_detected = req.disruption_detected_at

        det_to_req = (
            (req.activation_requested_at - d_detected).total_seconds() / 60.0
            if req.activation_requested_at else None
        )
        act_appr = (
            (req.activation_approved_at - req.activation_requested_at).total_seconds() / 60.0
            if (req.activation_approved_at and req.activation_requested_at) else None
        )
        arr_estab = (
            (req.arrangements_established_at - req.activation_approved_at).total_seconds() / 60.0
            if (req.arrangements_established_at and req.activation_approved_at) else None
        )
        t_tech = (
            (req.technical_restored_at - d_detected).total_seconds() / 60.0
            if req.technical_restored_at else None
        )
        t_oper = (
            (req.operational_restored_at - d_detected).total_seconds() / 60.0
            if req.operational_restored_at else None
        )
        t_gov = (
            (req.governance_verified_at - d_detected).total_seconds() / 60.0
            if req.governance_verified_at else None
        )
        t_rec = (
            (req.reconciliation_completed_at - d_detected).total_seconds() / 60.0
            if req.reconciliation_completed_at else None
        )

        if req.governance_verified_at:
            current_stage = RestorationStage.VERIFIED_GOVERNANCE_RESTORATION
            is_verified = True
        elif req.operational_restored_at:
            current_stage = RestorationStage.OPERATIONAL_RESTORATION
            is_verified = False
        elif req.technical_restored_at:
            current_stage = RestorationStage.TECHNICAL_RESTORATION
            is_verified = False
        else:
            current_stage = RestorationStage.FUNCTIONAL_RESTORATION
            is_verified = False

        deviations = []
        rto_outcome = TargetPerformanceOutcome.TARGET_NOT_DEFINED
        if req.approved_rto_minutes is not None:
            effective_duration = t_oper or t_tech
            if effective_duration is not None:
                if effective_duration <= req.approved_rto_minutes:
                    rto_outcome = TargetPerformanceOutcome.MET_WITHIN_TARGET
                elif effective_duration <= req.approved_rto_minutes * 1.5:
                    rto_outcome = TargetPerformanceOutcome.EXCEEDED_TARGET
                    deviations.append(f"RTO exceeded by {effective_duration - req.approved_rto_minutes:.1f} minutes")
                else:
                    rto_outcome = TargetPerformanceOutcome.SIGNIFICANT_BREACH
                    deviations.append(f"Significant RTO breach: {effective_duration:.1f}m vs target {req.approved_rto_minutes}m")
            else:
                rto_outcome = TargetPerformanceOutcome.INSUFFICIENT_TIMESTAMPS

        mtpd_outcome = TargetPerformanceOutcome.TARGET_NOT_DEFINED
        if req.approved_mtpd_minutes is not None:
            effective_duration = t_gov or t_oper or t_tech
            if effective_duration is not None:
                if effective_duration <= req.approved_mtpd_minutes:
                    mtpd_outcome = TargetPerformanceOutcome.MET_WITHIN_TARGET
                else:
                    mtpd_outcome = TargetPerformanceOutcome.SIGNIFICANT_BREACH
                    deviations.append(f"MTPD exceeded: {effective_duration:.1f}m vs maximum tolerable {req.approved_mtpd_minutes}m")

        record = RecoveryPerformanceAssuranceRecord(
            assessment_id=assessment_id,
            recovery_id=req.recovery_id,
            capability_id=req.capability_id,
            disruption_detected_at=req.disruption_detected_at,
            detection_to_activation_request_minutes=det_to_req,
            activation_approval_duration_minutes=act_appr,
            arrangement_establishment_duration_minutes=arr_estab,
            time_to_technical_restoration_minutes=t_tech,
            time_to_operational_restoration_minutes=t_oper,
            time_to_governance_verification_minutes=t_gov,
            time_to_reconciliation_minutes=t_rec,
            approved_rto_minutes=req.approved_rto_minutes,
            rto_outcome=rto_outcome,
            approved_mtpd_minutes=req.approved_mtpd_minutes,
            mtpd_outcome=mtpd_outcome,
            current_restoration_stage=current_stage,
            is_governance_verified=is_verified,
            deviations=deviations,
            limitations="Technical restoration does not equal operational or governance capability restoration.",
            evaluated_by=actor_id,
            evaluated_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_recovery_assessment(record)

    def get_recovery_assessment(self, assessment_id: str, tenant_id: str = "default") -> RecoveryPerformanceAssuranceRecord:
        rec = self.repo.get_recovery_assessment(assessment_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.RECOVERY_PERFORMANCE_NOT_FOUND,
                message=f"Recovery assessment {assessment_id} not found",
                status_code=404,
            )
        return rec

    def list_recovery_assessments(
        self,
        tenant_id: str = "default",
        recovery_id: Optional[str] = None,
    ) -> List[RecoveryPerformanceAssuranceRecord]:
        return self.repo.list_recovery_assessments(tenant_id, recovery_id)


# Module-level instance
governance_continuity_assurance_recovery_service = GovernanceContinuityAssuranceRecoveryService()

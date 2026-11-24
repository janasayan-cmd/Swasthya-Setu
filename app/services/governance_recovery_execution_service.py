"""
Phase 88: Governance Recovery Execution Tracking & Verification Service
Tracks operational execution progress, milestone achievements, deviations, and restoration verification.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from app.core.exceptions import (
    AppException,
    ErrorCode,
)
from app.repositories.governance_response_strategy_repository import (
    GovernanceResponseStrategyRepository,
    get_governance_response_strategy_repository,
)
from app.schemas.governance_response_common import (
    ExecutionTrackingStatus,
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
)
from app.schemas.governance_recovery_execution import (
    ExecutionMilestoneProgress,
    RecoveryExecutionTrackingRecord,
    ReportExecutionDeviationRequest,
    SubmitRestorationVerificationRequest,
    UpdateExecutionProgressRequest,
)


class GovernanceRecoveryExecutionService:
    def __init__(self, repo: Optional[GovernanceResponseStrategyRepository] = None):
        self.repo = repo or get_governance_response_strategy_repository()

    def create_execution_tracking(
        self,
        tenant_id: str,
        user_id: str,
        handoff_id: str,
        strategy_id: str,
    ) -> RecoveryExecutionTrackingRecord:
        now = datetime.now(timezone.utc)
        record = RecoveryExecutionTrackingRecord(
            execution_id=f"track-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            handoff_id=handoff_id,
            strategy_id=strategy_id,
            status=ExecutionTrackingStatus.PLANNED,
            progress_pct=0.0,
            milestones=[
                ExecutionMilestoneProgress(milestone_id="m1", milestone_name="Initiation & Notification", status="PENDING"),
                ExecutionMilestoneProgress(milestone_id="m2", milestone_name="Infrastructure Rerouting", status="PENDING"),
                ExecutionMilestoneProgress(milestone_id="m3", milestone_name="Clinical Capability Verification", status="PENDING"),
            ],
            reported_deviations=[],
            blocked_activities=[],
            capability_restoration_evidence_ref=None,
            restoration_verified_by=None,
            restoration_verified_at=None,
            created_by=user_id,
            created_at=now,
            updated_at=now,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )
        return self.repo.create_execution_tracking(record)

    def get_execution_tracking(
        self,
        execution_id: str,
        tenant_id: str,
    ) -> RecoveryExecutionTrackingRecord:
        record = self.repo.get_execution_tracking(execution_id, tenant_id)
        if not record:
            raise AppException(
                ErrorCode.RECOVERY_EXECUTION_TRACKING_NOT_FOUND,
                f"Recovery execution tracking '{execution_id}' not found.",
            )
        return record

    def list_execution_tracking(
        self,
        tenant_id: str,
        recommendation_ref: Optional[str] = None,
        status: Optional[ExecutionTrackingStatus] = None,
    ) -> List[RecoveryExecutionTrackingRecord]:
        return self.repo.list_execution_trackings(
            tenant_id=tenant_id,
            recommendation_ref=recommendation_ref,
            status=status,
        )

    def update_execution_progress(
        self,
        execution_id: str,
        tenant_id: str,
        user_id: str,
        req: UpdateExecutionProgressRequest,
    ) -> RecoveryExecutionTrackingRecord:
        record = self.get_execution_tracking(execution_id, tenant_id)
        record.progress_pct = req.progress_pct
        record.status = ExecutionTrackingStatus.IN_PROGRESS
        record.updated_at = datetime.now(timezone.utc)
        return self.repo.update_execution_tracking(record)

    def report_execution_deviation(
        self,
        execution_id: str,
        tenant_id: str,
        user_id: str,
        req: ReportExecutionDeviationRequest,
    ) -> RecoveryExecutionTrackingRecord:
        record = self.get_execution_tracking(execution_id, tenant_id)
        record.reported_deviations.append(f"{req.deviation_description} (Root Cause: {req.root_cause_explanation})")
        record.status = ExecutionTrackingStatus.DEVIATION_REPORTED
        record.updated_at = datetime.now(timezone.utc)
        return self.repo.update_execution_tracking(record)

    def submit_restoration_verification(
        self,
        execution_id: str,
        tenant_id: str,
        verifier_id: str,
        req: SubmitRestorationVerificationRequest,
    ) -> RecoveryExecutionTrackingRecord:
        record = self.get_execution_tracking(execution_id, tenant_id)
        now = datetime.now(timezone.utc)
        record.capability_restoration_evidence_ref = req.restoration_evidence_ref
        record.restoration_verified_by = verifier_id
        record.restoration_verified_at = now
        record.status = ExecutionTrackingStatus.VERIFIED_RESTORED
        record.progress_pct = 100.0
        record.updated_at = now
        return self.repo.update_execution_tracking(record)


_governance_recovery_execution_service: Optional[GovernanceRecoveryExecutionService] = None


def get_governance_recovery_execution_service() -> GovernanceRecoveryExecutionService:
    global _governance_recovery_execution_service
    if _governance_recovery_execution_service is None:
        _governance_recovery_execution_service = GovernanceRecoveryExecutionService()
    return _governance_recovery_execution_service

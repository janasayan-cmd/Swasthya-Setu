"""Phase 84: Capability Reassessment and Monitoring Service.

Triggers, schedules, and tracks capability reassessments following framework updates,
personnel changes, exercise failures, or expired competency validities.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_capability_reassessment import (
    CapabilityReassessmentRecord,
    CompleteReassessmentRequest,
    ReassessmentStatus,
    TriggerReassessmentRequest,
)


class GovernanceResilienceCapabilityReassessmentService:
    """Service managing reassessment triggers, scheduling, and completion workflows."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def trigger_reassessment(
        self,
        tenant_id: str,
        user_id: str,
        request: TriggerReassessmentRequest,
    ) -> CapabilityReassessmentRecord:
        reassessment_id = f"rea-{uuid.uuid4().hex[:10]}"
        record = CapabilityReassessmentRecord(
            reassessment_id=reassessment_id,
            tenant_id=tenant_id,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            trigger_reason=request.trigger_reason,
            target_assessment_id=request.target_assessment_id,
            notes=request.notes,
            status=ReassessmentStatus.TRIGGERED,
        )
        return self.repository.save_reassessment(record)

    def get_reassessment(
        self, tenant_id: str, reassessment_id: str
    ) -> CapabilityReassessmentRecord:
        record = self.repository.get_reassessment(reassessment_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPABILITY_REASSESSMENT_NOT_FOUND,
                message=f"Capability reassessment record '{reassessment_id}' not found.",
                status_code=404,
            )
        return record

    def complete_reassessment(
        self,
        tenant_id: str,
        reassessment_id: str,
        user_id: str,
        request: CompleteReassessmentRequest,
    ) -> CapabilityReassessmentRecord:
        record = self.get_reassessment(tenant_id, reassessment_id)

        if record.status in [ReassessmentStatus.COMPLETED, ReassessmentStatus.CANCELLED]:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_REASSESSMENT_STATE,
                message=f"Reassessment is already in terminal state '{record.status}'.",
                status_code=400,
            )

        record.status = ReassessmentStatus.COMPLETED
        record.completed_at = datetime.utcnow()
        if request.outcome_notes:
            record.notes = f"{record.notes or ''} [Completed: {request.outcome_notes}]".strip()

        return self.repository.save_reassessment(record)

    def list_reassessments(
        self,
        tenant_id: str,
        status: Optional[ReassessmentStatus] = None,
    ) -> List[CapabilityReassessmentRecord]:
        return self.repository.list_reassessments(tenant_id=tenant_id, status=status)


_reassessment_service = GovernanceResilienceCapabilityReassessmentService()


def get_governance_resilience_capability_reassessment_service() -> GovernanceResilienceCapabilityReassessmentService:
    return _reassessment_service

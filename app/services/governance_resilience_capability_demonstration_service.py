"""Phase 84: Practical Capability Demonstration Service.

Tracks and evaluates evidence-backed demonstrations (tabletops, exercises, simulations)
linked to Phase 80/81 without duplicating exercise execution.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_capability_demonstration import (
    CapabilityDemonstrationRecord,
    DemonstrationOutcome,
    DemonstrationReviewStatus,
    RecordDemonstrationRequest,
    ReviewDemonstrationRequest,
)


class GovernanceResilienceCapabilityDemonstrationService:
    """Service tracking practical demonstrations and observations."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def record_demonstration(
        self,
        tenant_id: str,
        user_id: str,
        request: RecordDemonstrationRequest,
    ) -> CapabilityDemonstrationRecord:
        demo_id = f"dem-{uuid.uuid4().hex[:10]}"
        record = CapabilityDemonstrationRecord(
            demonstration_id=demo_id,
            tenant_id=tenant_id,
            capability_id=request.capability_id,
            assessment_id=request.assessment_id,
            scenario_reference=request.scenario_reference,
            participant_user_id=request.participant_user_id,
            team_reference=request.team_reference,
            method=request.method,
            expected_behavior=request.expected_behavior,
            observed_behavior=request.observed_behavior,
            evidence_references=request.evidence_references,
            outcome=request.outcome,
            review_status=DemonstrationReviewStatus.RECORDED,
            assessor_observations=request.assessor_observations,
            limitations=request.limitations,
            reassessment_recommended=request.reassessment_recommended,
            recorded_by=user_id,
        )
        return self.repository.save_demonstration(record)

    def get_demonstration(
        self, tenant_id: str, demonstration_id: str
    ) -> CapabilityDemonstrationRecord:
        record = self.repository.get_demonstration(demonstration_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPABILITY_DEMONSTRATION_NOT_FOUND,
                message=f"Capability demonstration '{demonstration_id}' not found.",
                status_code=404,
            )
        return record

    def review_demonstration(
        self,
        tenant_id: str,
        demonstration_id: str,
        reviewer_id: str,
        request: ReviewDemonstrationRequest,
    ) -> CapabilityDemonstrationRecord:
        record = self.get_demonstration(tenant_id, demonstration_id)

        # Participant cannot review their own demonstration
        if reviewer_id == record.participant_user_id:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Participant cannot independently review their own capability demonstration.",
                status_code=400,
            )

        record.review_status = request.review_status
        record.reviewed_by = reviewer_id
        if request.reviewer_notes:
            record.assessor_observations = f"{record.assessor_observations or ''} [Review: {request.reviewer_notes}]".strip()

        return self.repository.save_demonstration(record)

    def list_demonstrations(
        self,
        tenant_id: str,
        capability_id: Optional[str] = None,
        participant_user_id: Optional[str] = None,
        outcome: Optional[DemonstrationOutcome] = None,
    ) -> List[CapabilityDemonstrationRecord]:
        return self.repository.list_demonstrations(
            tenant_id=tenant_id,
            capability_id=capability_id,
            participant_user_id=participant_user_id,
            outcome=outcome,
        )


_demonstration_service = GovernanceResilienceCapabilityDemonstrationService()


def get_governance_resilience_capability_demonstration_service() -> GovernanceResilienceCapabilityDemonstrationService:
    return _demonstration_service

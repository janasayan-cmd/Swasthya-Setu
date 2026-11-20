"""Phase 73: Approved Management Decision Intake Service.

Handles:
- Ingesting approved decisions from Phase 72
- Validating decision approval status and authorization integrity
- Quarantining or rejecting draft, rejected, withdrawn, or superseded decisions
- Preventing duplicate conflicting intake
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_management_review_repository import (
    GovernanceManagementReviewRepository,
    get_governance_management_review_repository,
)
from app.repositories.governance_decision_implementation_repository import (
    GovernanceDecisionImplementationRepository,
    get_governance_decision_implementation_repository,
)
from app.schemas.management_review_decisions import ManagementDecisionStatus
from app.schemas.decision_implementation_intake import (
    DecisionIntakeRecord,
    DecisionIntakeRequest,
    DecisionIntakeStatus,
)


class DecisionIntakeService:
    """Service governing decision intake into Phase 73 implementation tracking."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
        review_repository: Optional[GovernanceManagementReviewRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )
        self.review_repository = (
            review_repository or get_governance_management_review_repository()
        )

    def ingest_decision(
        self,
        request: DecisionIntakeRequest,
        ingested_by: str,
        organization_id: str,
    ) -> DecisionIntakeRecord:
        """Validates and ingests an approved Phase 72 decision."""
        # 1. Fetch decision from Phase 72
        decision = self.review_repository.get_decision(request.decision_id)
        if not decision:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.MANAGEMENT_DECISION_NOT_FOUND,
                message=f"Management decision '{request.decision_id}' not found in Phase 72 records.",
            )

        # 2. Idempotency check: if already ingested with accepted status, return it
        existing = self.repository.get_intake_by_decision(request.decision_id)
        if existing and existing.intake_status == DecisionIntakeStatus.INTAKE_ACCEPTED:
            return existing

        # 3. Validation: Decision must be APPROVED
        if decision.status != ManagementDecisionStatus.APPROVED:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.DECISION_NOT_ELIGIBLE_FOR_IMPLEMENTATION,
                message=(
                    f"Decision '{request.decision_id}' is in status '{decision.status.value}'. "
                    f"Only APPROVED management decisions can be ingested for implementation."
                ),
            )

        # 4. Validation: Cannot ingest superseded decisions
        if decision.superseded_by_id or decision.status == ManagementDecisionStatus.SUPERSEDED:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.DECISION_NOT_ELIGIBLE_FOR_IMPLEMENTATION,
                message=(
                    f"Decision '{request.decision_id}' has been superseded by '{decision.superseded_by_id}' "
                    f"and cannot enter new implementation intake."
                ),
            )

        # 5. Create intake record
        intake = DecisionIntakeRecord(
            decision_id=decision.decision_id,
            source_review_id=decision.review_id,
            decision_version=1,
            decision_title=decision.title,
            decision_category=decision.category.value,
            decision_rationale=decision.rationale,
            decided_by_id=decision.decided_by_id,
            decided_by_role=decision.decided_by_role,
            decided_at=decision.decided_at,
            effective_date=request.effective_date,
            supporting_evidence_refs=decision.supporting_evidence_refs,
            assigned_management_owner=request.assigned_management_owner or decision.decided_by_id,
            required_outcome=request.required_outcome,
            conditions_and_limitations=request.conditions_and_limitations or [],
            supersession_status="ACTIVE",
            intake_status=DecisionIntakeStatus.INTAKE_ACCEPTED,
            organization_id=organization_id,
            facility_id=decision.facility_id,
            ingested_by=ingested_by,
            metadata=request.metadata or {},
        )

        return self.repository.save_intake(intake)

    def get_intake(self, intake_id: str) -> DecisionIntakeRecord:
        """Retrieves an intake record by ID."""
        record = self.repository.get_intake(intake_id)
        if not record:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.NOT_FOUND,
                message=f"Decision intake record '{intake_id}' not found.",
            )
        return record

    def list_intakes(
        self,
        organization_id: str,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DecisionIntakeRecord]:
        """Lists decision intake records."""
        return self.repository.list_intakes(
            organization_id=organization_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

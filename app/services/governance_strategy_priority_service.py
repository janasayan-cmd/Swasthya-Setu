"""Phase 78: Governance Strategic Priority Service.

Manages evidence-backed strategic priority proposals and accountable human review workflows.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER
from app.schemas.governance_strategy_priority import (
    GovernanceStrategyPriorityRecord,
    PriorityReviewOutcome,
    ProposePriorityRequest,
    ReviewPriorityRequest,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyPriorityService:
    """Manages strategic priority proposals derived from verified governance evidence."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def propose_priority(
        self,
        tenant_id: str,
        proposer_id: str,
        request: ProposePriorityRequest,
    ) -> GovernanceStrategyPriorityRecord:
        now = _get_utc_now_str()
        priority = GovernanceStrategyPriorityRecord(
            priority_id=f"gsp-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            title=request.title,
            strategic_rationale=request.strategic_rationale,
            potential_impact=request.potential_impact,
            urgency=request.urgency,
            evidence_references=request.evidence_references,
            proposed_priority_level=request.proposed_priority_level,
            status=PriorityReviewOutcome.PROPOSED,
            proposed_by=proposer_id,
            reviewed_by=None,
            review_outcome=None,
            review_notes=None,
            linked_objective_id=request.linked_objective_id,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_priority(priority)

    def review_priority(
        self,
        tenant_id: str,
        priority_id: str,
        reviewer_id: str,
        request: ReviewPriorityRequest,
    ) -> GovernanceStrategyPriorityRecord:
        priority = self.repository.get_priority(priority_id)
        if not priority or priority.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_PRIORITY_NOT_FOUND,
                message=f"Strategic priority '{priority_id}' was not found.",
                status_code=404,
            )

        if priority.status not in (PriorityReviewOutcome.PROPOSED, PriorityReviewOutcome.REVIEWED):
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_PRIORITY_STATE,
                message=f"Priority in status '{priority.status.value}' cannot be reviewed.",
                status_code=400,
            )

        # Separation of duties: proposer cannot review their own priority proposal
        if priority.proposed_by == reviewer_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Proposer cannot review their own strategic priority proposal.",
                status_code=403,
            )

        now = _get_utc_now_str()
        priority = priority.model_copy(
            update={
                "status": request.outcome,
                "reviewed_by": reviewer_id,
                "review_outcome": request.outcome,
                "review_notes": request.review_notes,
                "updated_at": now,
            }
        )
        return self.repository.save_priority(priority)

    def get_priority(
        self,
        tenant_id: str,
        priority_id: str,
    ) -> GovernanceStrategyPriorityRecord:
        priority = self.repository.get_priority(priority_id)
        if not priority or priority.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_PRIORITY_NOT_FOUND,
                message=f"Strategic priority '{priority_id}' was not found.",
                status_code=404,
            )
        return priority

    def list_priorities(
        self,
        tenant_id: str,
        status: Optional[PriorityReviewOutcome] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyPriorityRecord]:
        return self.repository.list_priorities(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
        )

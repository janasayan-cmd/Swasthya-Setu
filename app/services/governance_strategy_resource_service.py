"""Phase 78: Governance Resource Proposal Service.

Tracks estimated resource and financial investment requirements without
independent financial execution or autonomous budget allocation.
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
from app.schemas.governance_strategy_resource import (
    CreateResourceProposalRequest,
    GovernanceResourceProposalRecord,
    InvestmentReviewStatus,
    RecordApprovalReferenceRequest,
    ReviewResourceProposalRequest,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyResourceService:
    """Manages strategic resource proposals and external governance approval references."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def create_proposal(
        self,
        tenant_id: str,
        proposer_id: str,
        request: CreateResourceProposalRequest,
    ) -> GovernanceResourceProposalRecord:
        roadmap = self.repository.get_roadmap(request.roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Parent roadmap '{request.roadmap_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        proposal_id = f"grp-{uuid.uuid4().hex[:12]}"
        proposal = GovernanceResourceProposalRecord(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            roadmap_id=request.roadmap_id,
            related_objective_id=request.related_objective_id,
            title=request.title,
            rationale=request.rationale,
            proposed_financial_investment=request.proposed_financial_investment,
            currency=request.currency,
            staffing_requirements=request.staffing_requirements or "",
            technology_requirements=request.technology_requirements or "",
            training_requirements=request.training_requirements or "",
            external_service_dependencies=request.external_service_dependencies or "",
            funding_assumptions=request.funding_assumptions or "",
            expected_strategic_contribution=request.expected_strategic_contribution or "",
            status=InvestmentReviewStatus.PROPOSED,
            proposed_by=proposer_id,
            reviewed_by=None,
            approval_reference=None,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        saved_prop = self.repository.save_resource_proposal(proposal)

        # Append to roadmap's resource_proposal_ids
        if proposal_id not in roadmap.resource_proposal_ids:
            rp_ids = list(roadmap.resource_proposal_ids)
            rp_ids.append(proposal_id)
            roadmap = roadmap.model_copy(update={"resource_proposal_ids": rp_ids, "updated_at": now})
            self.repository.save_roadmap(roadmap)

        return saved_prop

    def review_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
        reviewer_id: str,
        request: ReviewResourceProposalRequest,
    ) -> GovernanceResourceProposalRecord:
        proposal = self.repository.get_resource_proposal(proposal_id)
        if not proposal or proposal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_RESOURCE_PROPOSAL_NOT_FOUND,
                message=f"Resource proposal '{proposal_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: proposer cannot review own investment proposal
        if proposal.proposed_by == reviewer_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Proposer cannot review their own resource proposal.",
                status_code=403,
            )

        now = _get_utc_now_str()
        proposal = proposal.model_copy(
            update={
                "status": request.status,
                "reviewed_by": reviewer_id,
                "updated_at": now,
            }
        )
        return self.repository.save_resource_proposal(proposal)

    def record_approval(
        self,
        tenant_id: str,
        proposal_id: str,
        request: RecordApprovalReferenceRequest,
    ) -> GovernanceResourceProposalRecord:
        proposal = self.repository.get_resource_proposal(proposal_id)
        if not proposal or proposal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_RESOURCE_PROPOSAL_NOT_FOUND,
                message=f"Resource proposal '{proposal_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        proposal = proposal.model_copy(
            update={
                "status": request.status,
                "approval_reference": request.approval_reference,
                "updated_at": now,
            }
        )
        return self.repository.save_resource_proposal(proposal)

    def get_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
    ) -> GovernanceResourceProposalRecord:
        proposal = self.repository.get_resource_proposal(proposal_id)
        if not proposal or proposal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_RESOURCE_PROPOSAL_NOT_FOUND,
                message=f"Resource proposal '{proposal_id}' was not found.",
                status_code=404,
            )
        return proposal

    def list_proposals(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[InvestmentReviewStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceResourceProposalRecord]:
        return self.repository.list_resource_proposals(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            status=status,
            skip=skip,
            limit=limit,
        )

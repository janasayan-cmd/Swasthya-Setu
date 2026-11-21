"""Phase 79: Strategic Adaptation Proposal and Follow-Through Service.

Coordinates evidence-backed strategic adaptation proposals, enforces separation
of duties during review, links authoritative Phase 72/78 decisions, and reconciles
downstream execution follow-through.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_adaptation import (
    AdaptationFollowThroughRecord,
    AdaptationProposalStatus,
    AdaptationProposalType,
    CreateAdaptationProposalRequest,
    LinkAuthoritativeDecisionRequest,
    ReviewAdaptationProposalRequest,
    StrategicAdaptationProposalRecord,
    SubmitAdaptationProposalRequest,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyAdaptationService:
    """Manages strategic adaptation proposals, separation of duties, and downstream follow-through."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def create_adaptation_proposal(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateAdaptationProposalRequest,
    ) -> StrategicAdaptationProposalRecord:
        proposal_id = f"SAP-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = StrategicAdaptationProposalRecord(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            source_roadmap_id=request.source_roadmap_id,
            proposal_type=request.proposal_type,
            affected_objective_ids=request.affected_objective_ids or [],
            affected_milestone_ids=request.affected_milestone_ids or [],
            supporting_signal_ids=request.supporting_signal_ids or [],
            proposed_change_description=request.proposed_change_description,
            rationale=request.rationale,
            expected_benefits=request.expected_benefits,
            potential_negative_consequences=request.potential_negative_consequences,
            resource_implications=request.resource_implications,
            uncertainty_limitations=request.uncertainty_limitations or "",
            requesting_owner_id=author_id,
            status=AdaptationProposalStatus.DRAFT,
            review_notes=None,
            authoritative_decision_reference=None,
            authoritative_roadmap_revision_id=None,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_adaptation_proposal(record)

    def submit_adaptation_proposal(
        self,
        tenant_id: str,
        author_id: str,
        proposal_id: str,
        request: SubmitAdaptationProposalRequest,
    ) -> StrategicAdaptationProposalRecord:
        proposal = self.repository.get_adaptation_proposal(proposal_id)
        if not proposal or proposal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ADAPTATION_PROPOSAL_NOT_FOUND,
                message=f"Strategic adaptation proposal '{proposal_id}' was not found.",
                status_code=404,
            )

        if proposal.status != AdaptationProposalStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_ADAPTATION_PROPOSAL_STATE,
                message=f"Proposal '{proposal_id}' cannot be submitted from status '{proposal.status}'.",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        notes = request.submission_notes or proposal.review_notes
        updated = proposal.model_copy(
            update={
                "status": AdaptationProposalStatus.SUBMITTED,
                "review_notes": notes,
                "updated_at": now_str,
            }
        )
        return self.repository.save_adaptation_proposal(updated)

    def review_adaptation_proposal(
        self,
        tenant_id: str,
        reviewer_id: str,
        proposal_id: str,
        request: ReviewAdaptationProposalRequest,
    ) -> StrategicAdaptationProposalRecord:
        proposal = self.repository.get_adaptation_proposal(proposal_id)
        if not proposal or proposal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ADAPTATION_PROPOSAL_NOT_FOUND,
                message=f"Strategic adaptation proposal '{proposal_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: proposer/requesting owner cannot review own proposal
        if reviewer_id == proposal.requesting_owner_id:
            raise AppException(
                code=ErrorCode.STRATEGY_EXECUTION_SEPARATION_OF_DUTIES_VIOLATION,
                message="Proposers cannot review or disposition their own strategic adaptation proposals.",
                status_code=403,
            )

        if proposal.status not in (
            AdaptationProposalStatus.SUBMITTED,
            AdaptationProposalStatus.UNDER_REVIEW,
        ):
            raise AppException(
                code=ErrorCode.INVALID_ADAPTATION_PROPOSAL_STATE,
                message=f"Proposal '{proposal_id}' is not in reviewable status (currently '{proposal.status}').",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        updated = proposal.model_copy(
            update={
                "status": request.status,
                "review_notes": request.review_notes,
                "updated_at": now_str,
            }
        )
        return self.repository.save_adaptation_proposal(updated)

    def link_authoritative_decision(
        self,
        tenant_id: str,
        proposal_id: str,
        request: LinkAuthoritativeDecisionRequest,
    ) -> StrategicAdaptationProposalRecord:
        proposal = self.repository.get_adaptation_proposal(proposal_id)
        if not proposal or proposal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ADAPTATION_PROPOSAL_NOT_FOUND,
                message=f"Strategic adaptation proposal '{proposal_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated_proposal = proposal.model_copy(
            update={
                "status": AdaptationProposalStatus.APPROVED_AUTHORITATIVE,
                "authoritative_decision_reference": request.phase72_decision_reference or proposal.authoritative_decision_reference,
                "authoritative_roadmap_revision_id": request.phase78_revision_reference or proposal.authoritative_roadmap_revision_id,
                "updated_at": now_str,
            }
        )
        saved_proposal = self.repository.save_adaptation_proposal(updated_proposal)

        # Update or create follow-through record
        existing_ft = self.repository.get_followthrough_by_proposal(tenant_id, proposal_id)
        if existing_ft:
            updated_ft = existing_ft.model_copy(
                update={
                    "phase72_decision_reference": request.phase72_decision_reference or existing_ft.phase72_decision_reference,
                    "phase78_revision_reference": request.phase78_revision_reference or existing_ft.phase78_revision_reference,
                    "phase73_implementation_reference": request.phase73_implementation_reference or existing_ft.phase73_implementation_reference,
                    "status": request.status,
                    "updated_at": now_str,
                }
            )
            self.repository.save_adaptation_followthrough(updated_ft)
        else:
            ft_id = f"AFT-{uuid.uuid4().hex[:8].upper()}"
            new_ft = AdaptationFollowThroughRecord(
                followthrough_id=ft_id,
                tenant_id=tenant_id,
                proposal_id=proposal_id,
                phase72_decision_reference=request.phase72_decision_reference,
                phase78_revision_reference=request.phase78_revision_reference,
                phase73_implementation_reference=request.phase73_implementation_reference,
                phase75_portfolio_reference=None,
                phase74_adoption_reference=None,
                phase76_benefit_reference=None,
                phase77_maturity_reference=None,
                status=request.status,
                verification_notes="Initialized follow-through from authoritative decision linkage.",
                disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
                updated_at=now_str,
            )
            self.repository.save_adaptation_followthrough(new_ft)

        return saved_proposal

    def get_adaptation_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
    ) -> StrategicAdaptationProposalRecord:
        proposal = self.repository.get_adaptation_proposal(proposal_id)
        if not proposal or proposal.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ADAPTATION_PROPOSAL_NOT_FOUND,
                message=f"Strategic adaptation proposal '{proposal_id}' was not found.",
                status_code=404,
            )
        return proposal

    def list_adaptation_proposals(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[AdaptationProposalStatus] = None,
        proposal_type: Optional[AdaptationProposalType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicAdaptationProposalRecord]:
        return self.repository.list_adaptation_proposals(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            status=status,
            proposal_type=proposal_type,
            skip=skip,
            limit=limit,
        )

    def get_followthrough_by_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
    ) -> Optional[AdaptationFollowThroughRecord]:
        return self.repository.get_followthrough_by_proposal(tenant_id, proposal_id)

    def list_adaptation_followthroughs(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AdaptationFollowThroughRecord]:
        return self.repository.list_adaptation_followthroughs(tenant_id, skip=skip, limit=limit)

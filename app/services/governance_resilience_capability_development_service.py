"""Phase 84: Capability Development and Remediation Service.

Coordinates remediation proposals, supervised practical drills, and training plans
linked to validated capability gaps and Phase 83 capability development recommendations.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_capability_development import (
    ApproveDevelopmentProposalRequest,
    CapabilityDevelopmentProposalRecord,
    CompleteDevelopmentProposalRequest,
    ProposalStatus,
    ProposeDevelopmentRequest,
    ReviewDevelopmentProposalRequest,
)


class GovernanceResilienceCapabilityDevelopmentService:
    """Service managing capability remediation interventions and development proposals."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def propose_development(
        self,
        tenant_id: str,
        user_id: str,
        request: ProposeDevelopmentRequest,
    ) -> CapabilityDevelopmentProposalRecord:
        proposal_id = f"cdp-{uuid.uuid4().hex[:10]}"
        record = CapabilityDevelopmentProposalRecord(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            linked_gap_id=request.linked_gap_id,
            target_capability_id=request.target_capability_id,
            target_role_or_team=request.target_role_or_team,
            proposed_intervention=request.proposed_intervention,
            rationalization=request.rationalization,
            expected_improvement=request.expected_improvement,
            assigned_owner=request.assigned_owner,
            target_completion_date=request.target_completion_date,
            status=ProposalStatus.PROPOSED,
            proposed_by=user_id,
        )
        return self.repository.save_development_proposal(record)

    def get_proposal(
        self, tenant_id: str, proposal_id: str
    ) -> CapabilityDevelopmentProposalRecord:
        record = self.repository.get_development_proposal(proposal_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPABILITY_DEVELOPMENT_PROPOSAL_NOT_FOUND,
                message=f"Capability development proposal '{proposal_id}' not found.",
                status_code=404,
            )
        return record

    def review_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
        reviewer_id: str,
        request: ReviewDevelopmentProposalRequest,
    ) -> CapabilityDevelopmentProposalRecord:
        record = self.get_proposal(tenant_id, proposal_id)
        record.status = request.status
        return self.repository.save_development_proposal(record)

    def approve_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
        approver_id: str,
        request: ApproveDevelopmentProposalRequest,
    ) -> CapabilityDevelopmentProposalRecord:
        record = self.get_proposal(tenant_id, proposal_id)

        # Proposer cannot approve own proposal
        if approver_id == record.proposed_by:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Proposer cannot independently approve their own development proposal.",
                status_code=400,
            )

        record.status = ProposalStatus.APPROVED
        record.approved_by = approver_id
        return self.repository.save_development_proposal(record)

    def complete_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
        user_id: str,
        request: CompleteDevelopmentProposalRequest,
    ) -> CapabilityDevelopmentProposalRecord:
        record = self.get_proposal(tenant_id, proposal_id)

        if record.status not in [ProposalStatus.APPROVED, ProposalStatus.IN_PROGRESS]:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_DEVELOPMENT_PROPOSAL_STATE,
                message=f"Proposal must be APPROVED or IN_PROGRESS before completion. Current: '{record.status}'.",
                status_code=400,
            )

        record.status = ProposalStatus.COMPLETED
        record.completion_evidence = request.completion_evidence
        record.completed_at = datetime.utcnow()
        return self.repository.save_development_proposal(record)

    def list_proposals(
        self,
        tenant_id: str,
        status: Optional[ProposalStatus] = None,
    ) -> List[CapabilityDevelopmentProposalRecord]:
        return self.repository.list_development_proposals(tenant_id=tenant_id, status=status)


_development_service = GovernanceResilienceCapabilityDevelopmentService()


def get_governance_resilience_capability_development_service() -> GovernanceResilienceCapabilityDevelopmentService:
    return _development_service

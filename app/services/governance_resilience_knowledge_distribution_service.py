"""Phase 83: Knowledge Distribution Campaign Service.

Manages targeted dissemination campaigns for resilience knowledge, enforcing the
distribution gate (only approved/published knowledge can be distributed) and
generating recipient delivery tracking records.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_knowledge_repository import (
    GovernanceResilienceKnowledgeRepository,
    get_governance_resilience_knowledge_repository,
)
from app.schemas.governance_resilience_knowledge import KnowledgeLifecycleState
from app.schemas.governance_resilience_knowledge_distribution import (
    ApproveDistributionCampaignRequest,
    CampaignStatus,
    CreateDistributionCampaignRequest,
    DispatchDistributionCampaignRequest,
    KnowledgeDistributionCampaignRecord,
)
from app.schemas.governance_resilience_knowledge_tracking import (
    AcknowledgementStatus,
    KnowledgeAcknowledgementRecord,
)


class GovernanceResilienceKnowledgeDistributionService:
    """Service managing knowledge campaign lifecycle, distribution gate, and dispatching."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    def create_campaign(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateDistributionCampaignRequest,
    ) -> KnowledgeDistributionCampaignRecord:
        knowledge = self.repository.get_knowledge(request.knowledge_id, tenant_id)
        if not knowledge:
            raise AppException(
                code=ErrorCode.RESILIENCE_KNOWLEDGE_NOT_FOUND,
                message=f"Knowledge record '{request.knowledge_id}' not found.",
                status_code=404,
            )

        # Distribution Gate: Knowledge must be APPROVED_FOR_PUBLICATION or PUBLISHED
        if knowledge.current_state not in [
            KnowledgeLifecycleState.APPROVED_FOR_PUBLICATION,
            KnowledgeLifecycleState.PUBLISHED,
        ]:
            raise AppException(
                code=ErrorCode.UNPUBLISHED_KNOWLEDGE_DISTRIBUTION_DENIED,
                message=(
                    f"Cannot create distribution campaign for knowledge in state '{knowledge.current_state}'. "
                    "Only APPROVED_FOR_PUBLICATION or PUBLISHED knowledge may be distributed."
                ),
                status_code=400,
            )

        campaign_id = f"cmp-{uuid.uuid4().hex[:10]}"
        campaign = KnowledgeDistributionCampaignRecord(
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            knowledge_id=knowledge.knowledge_id,
            knowledge_version=knowledge.version,
            title=request.title,
            description=request.description,
            target_audiences=request.target_audiences,
            acknowledgement_required=request.acknowledgement_required,
            due_date=request.due_date,
            status=CampaignStatus.DRAFT,
            created_by=user_id,
        )
        return self.repository.save_campaign(campaign)

    def get_campaign(self, tenant_id: str, campaign_id: str) -> KnowledgeDistributionCampaignRecord:
        campaign = self.repository.get_campaign(campaign_id, tenant_id)
        if not campaign:
            raise AppException(
                code=ErrorCode.DISTRIBUTION_CAMPAIGN_NOT_FOUND,
                message=f"Distribution campaign '{campaign_id}' not found.",
                status_code=404,
            )
        return campaign

    def approve_campaign(
        self,
        tenant_id: str,
        campaign_id: str,
        approver_id: str,
        request: ApproveDistributionCampaignRequest,
    ) -> KnowledgeDistributionCampaignRecord:
        campaign = self.get_campaign(tenant_id, campaign_id)
        if campaign.status != CampaignStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_DISTRIBUTION_CAMPAIGN_STATE,
                message=f"Campaign in state '{campaign.status}' cannot be approved. Must be DRAFT.",
                status_code=400,
            )
        campaign.status = CampaignStatus.APPROVED
        campaign.approved_by = approver_id
        campaign.updated_at = datetime.utcnow()
        return self.repository.save_campaign(campaign)

    def dispatch_campaign(
        self,
        tenant_id: str,
        campaign_id: str,
        dispatcher_id: str,
        request: DispatchDistributionCampaignRequest,
    ) -> KnowledgeDistributionCampaignRecord:
        campaign = self.get_campaign(tenant_id, campaign_id)
        if campaign.status != CampaignStatus.APPROVED:
            raise AppException(
                code=ErrorCode.INVALID_DISTRIBUTION_CAMPAIGN_STATE,
                message=f"Campaign in state '{campaign.status}' cannot be dispatched. Must be APPROVED.",
                status_code=400,
            )

        campaign.status = CampaignStatus.DISPATCHED
        campaign.dispatched_at = datetime.utcnow()
        campaign.dispatch_notes = request.dispatch_notes
        campaign.updated_at = datetime.utcnow()
        saved_campaign = self.repository.save_campaign(campaign)

        # Seed acknowledgements for target recipients
        recipients = request.recipient_user_ids or ["default_target_user"]
        for uid in recipients:
            ack_id = f"ack-{uuid.uuid4().hex[:10]}"
            ack = KnowledgeAcknowledgementRecord(
                acknowledgement_id=ack_id,
                tenant_id=tenant_id,
                campaign_id=campaign_id,
                knowledge_id=campaign.knowledge_id,
                user_id=uid,
                status=AcknowledgementStatus.DELIVERED,
                delivered_at=datetime.utcnow(),
            )
            self.repository.save_acknowledgement(ack)

        return saved_campaign

    def complete_campaign(
        self,
        tenant_id: str,
        campaign_id: str,
        user_id: str,
    ) -> KnowledgeDistributionCampaignRecord:
        campaign = self.get_campaign(tenant_id, campaign_id)
        if campaign.status != CampaignStatus.DISPATCHED:
            raise AppException(
                code=ErrorCode.INVALID_DISTRIBUTION_CAMPAIGN_STATE,
                message=f"Campaign in state '{campaign.status}' cannot be marked complete. Must be DISPATCHED.",
                status_code=400,
            )
        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = datetime.utcnow()
        campaign.updated_at = datetime.utcnow()
        return self.repository.save_campaign(campaign)

    def list_campaigns(
        self,
        tenant_id: str,
        knowledge_id: Optional[str] = None,
        status: Optional[CampaignStatus] = None,
    ) -> List[KnowledgeDistributionCampaignRecord]:
        return self.repository.list_campaigns(tenant_id=tenant_id, knowledge_id=knowledge_id, status=status)


_distribution_service = GovernanceResilienceKnowledgeDistributionService()


def get_governance_resilience_knowledge_distribution_service() -> GovernanceResilienceKnowledgeDistributionService:
    return _distribution_service

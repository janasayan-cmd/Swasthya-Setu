"""Phase 83: Resilience Knowledge Domain Service.

Coordinates authoring, validation, versioning, review, publication, withdrawal,
and superseding of clinical safety resilience knowledge assets.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_knowledge_repository import (
    GovernanceResilienceKnowledgeRepository,
    get_governance_resilience_knowledge_repository,
)
from app.schemas.governance_resilience_knowledge import (
    ApproveForPublicationRequest,
    CreateResilienceKnowledgeRequest,
    KnowledgeCategory,
    KnowledgeLifecycleState,
    PublishResilienceKnowledgeRequest,
    ResilienceKnowledgeRecord,
    ReviewResilienceKnowledgeRequest,
    SubmitForReviewRequest,
    SupersedeResilienceKnowledgeRequest,
    UpdateResilienceKnowledgeRequest,
    WithdrawResilienceKnowledgeRequest,
)


class GovernanceResilienceKnowledgeService:
    """Service managing resilience knowledge lifecycle, separation of duties, and versioning."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    def create_knowledge(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateResilienceKnowledgeRequest,
    ) -> ResilienceKnowledgeRecord:
        knowledge_id = f"rkm-{uuid.uuid4().hex[:10]}"
        record = ResilienceKnowledgeRecord(
            knowledge_id=knowledge_id,
            tenant_id=tenant_id,
            title=request.title,
            category=request.category,
            summary=request.summary,
            content=request.content,
            source_phase=request.source_phase,
            source_reference_id=request.source_reference_id,
            tags=request.tags,
            confidentiality_level=request.confidentiality_level,
            owner_id=author_id,
            author_id=author_id,
            current_state=KnowledgeLifecycleState.DRAFT,
            version=1,
            review_due_date=request.review_due_date,
        )
        return self.repository.save_knowledge(record)

    def get_knowledge(self, tenant_id: str, knowledge_id: str) -> ResilienceKnowledgeRecord:
        record = self.repository.get_knowledge(knowledge_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.RESILIENCE_KNOWLEDGE_NOT_FOUND,
                message=f"Resilience knowledge record '{knowledge_id}' not found.",
                status_code=404,
            )
        return record

    def update_knowledge(
        self,
        tenant_id: str,
        knowledge_id: str,
        user_id: str,
        request: UpdateResilienceKnowledgeRequest,
    ) -> ResilienceKnowledgeRecord:
        record = self.get_knowledge(tenant_id, knowledge_id)

        if record.current_state in [
            KnowledgeLifecycleState.ARCHIVED,
            KnowledgeLifecycleState.WITHDRAWN,
            KnowledgeLifecycleState.SUPERSEDED,
        ]:
            raise AppException(
                code=ErrorCode.INVALID_RESILIENCE_KNOWLEDGE_STATE,
                message=f"Cannot update knowledge record in terminal state '{record.current_state}'.",
                status_code=400,
            )

        if request.material_change:
            # Material change increments version and resets state to DRAFT if published or validated
            record.version += 1
            if record.current_state in [
                KnowledgeLifecycleState.PUBLISHED,
                KnowledgeLifecycleState.VALIDATED,
                KnowledgeLifecycleState.APPROVED_FOR_PUBLICATION,
            ]:
                record.current_state = KnowledgeLifecycleState.DRAFT

        if request.title is not None:
            record.title = request.title
        if request.category is not None:
            record.category = request.category
        if request.summary is not None:
            record.summary = request.summary
        if request.content is not None:
            record.content = request.content
        if request.tags is not None:
            record.tags = request.tags
        if request.confidentiality_level is not None:
            record.confidentiality_level = request.confidentiality_level
        if request.review_due_date is not None:
            record.review_due_date = request.review_due_date

        record.updated_at = datetime.utcnow()
        return self.repository.save_knowledge(record)

    def submit_for_review(
        self,
        tenant_id: str,
        knowledge_id: str,
        user_id: str,
        request: SubmitForReviewRequest,
    ) -> ResilienceKnowledgeRecord:
        record = self.get_knowledge(tenant_id, knowledge_id)
        if record.current_state not in [
            KnowledgeLifecycleState.DRAFT,
            KnowledgeLifecycleState.CHANGES_REQUESTED,
        ]:
            raise AppException(
                code=ErrorCode.INVALID_RESILIENCE_KNOWLEDGE_STATE,
                message=f"Knowledge record in '{record.current_state}' cannot be submitted for review.",
                status_code=400,
            )
        record.current_state = KnowledgeLifecycleState.SUBMITTED_FOR_REVIEW
        record.updated_at = datetime.utcnow()
        return self.repository.save_knowledge(record)

    def review_knowledge(
        self,
        tenant_id: str,
        knowledge_id: str,
        reviewer_id: str,
        request: ReviewResilienceKnowledgeRequest,
    ) -> ResilienceKnowledgeRecord:
        record = self.get_knowledge(tenant_id, knowledge_id)

        # Separation of duties: Reviewer cannot be author or owner
        if reviewer_id in [record.author_id, record.owner_id]:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Author or owner cannot independently validate their own resilience knowledge record.",
                status_code=400,
            )

        if record.current_state not in [
            KnowledgeLifecycleState.SUBMITTED_FOR_REVIEW,
            KnowledgeLifecycleState.UNDER_REVIEW,
        ]:
            raise AppException(
                code=ErrorCode.INVALID_RESILIENCE_KNOWLEDGE_STATE,
                message=f"Knowledge in state '{record.current_state}' cannot be reviewed.",
                status_code=400,
            )

        outcome_norm = request.outcome.upper()
        if outcome_norm == "VALIDATE":
            record.current_state = KnowledgeLifecycleState.VALIDATED
            record.validated_by = reviewer_id
        elif outcome_norm == "REQUEST_CHANGES":
            record.current_state = KnowledgeLifecycleState.CHANGES_REQUESTED
        elif outcome_norm == "REJECT":
            record.current_state = KnowledgeLifecycleState.DRAFT
        else:
            raise AppException(
                code=ErrorCode.INVALID_RESILIENCE_KNOWLEDGE_STATE,
                message=f"Invalid review outcome '{request.outcome}'. Must be VALIDATE, REQUEST_CHANGES, or REJECT.",
                status_code=400,
            )

        record.updated_at = datetime.utcnow()
        return self.repository.save_knowledge(record)

    def approve_for_publication(
        self,
        tenant_id: str,
        knowledge_id: str,
        approver_id: str,
        request: ApproveForPublicationRequest,
    ) -> ResilienceKnowledgeRecord:
        record = self.get_knowledge(tenant_id, knowledge_id)

        # Separation of duties: Approver cannot be author or owner
        if approver_id in [record.author_id, record.owner_id]:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Author or owner cannot approve publication of their own resilience knowledge record.",
                status_code=400,
            )

        if record.current_state != KnowledgeLifecycleState.VALIDATED:
            raise AppException(
                code=ErrorCode.INVALID_RESILIENCE_KNOWLEDGE_STATE,
                message=f"Knowledge must be in VALIDATED state before publication approval. Current: '{record.current_state}'.",
                status_code=400,
            )

        record.current_state = KnowledgeLifecycleState.APPROVED_FOR_PUBLICATION
        record.approved_by = approver_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_knowledge(record)

    def publish_knowledge(
        self,
        tenant_id: str,
        knowledge_id: str,
        user_id: str,
        request: PublishResilienceKnowledgeRequest,
    ) -> ResilienceKnowledgeRecord:
        record = self.get_knowledge(tenant_id, knowledge_id)

        if record.current_state != KnowledgeLifecycleState.APPROVED_FOR_PUBLICATION:
            raise AppException(
                code=ErrorCode.INVALID_RESILIENCE_KNOWLEDGE_STATE,
                message=f"Knowledge must be in APPROVED_FOR_PUBLICATION state to publish. Current: '{record.current_state}'.",
                status_code=400,
            )

        record.current_state = KnowledgeLifecycleState.PUBLISHED
        record.published_at = datetime.utcnow()
        record.updated_at = datetime.utcnow()
        return self.repository.save_knowledge(record)

    def withdraw_knowledge(
        self,
        tenant_id: str,
        knowledge_id: str,
        user_id: str,
        request: WithdrawResilienceKnowledgeRequest,
    ) -> ResilienceKnowledgeRecord:
        record = self.get_knowledge(tenant_id, knowledge_id)

        if record.current_state in [
            KnowledgeLifecycleState.WITHDRAWN,
            KnowledgeLifecycleState.ARCHIVED,
        ]:
            raise AppException(
                code=ErrorCode.INVALID_RESILIENCE_KNOWLEDGE_STATE,
                message=f"Knowledge is already in terminal state '{record.current_state}'.",
                status_code=400,
            )

        record.current_state = KnowledgeLifecycleState.WITHDRAWN
        record.withdrawn_reason = request.reason
        record.updated_at = datetime.utcnow()
        return self.repository.save_knowledge(record)

    def supersede_knowledge(
        self,
        tenant_id: str,
        knowledge_id: str,
        user_id: str,
        request: SupersedeResilienceKnowledgeRequest,
    ) -> ResilienceKnowledgeRecord:
        record = self.get_knowledge(tenant_id, knowledge_id)

        # Verify replacement exists
        replacement = self.repository.get_knowledge(request.new_knowledge_id, tenant_id)
        if not replacement:
            raise AppException(
                code=ErrorCode.RESILIENCE_KNOWLEDGE_NOT_FOUND,
                message=f"Replacement knowledge record '{request.new_knowledge_id}' not found.",
                status_code=404,
            )

        record.current_state = KnowledgeLifecycleState.SUPERSEDED
        record.superseded_by_id = request.new_knowledge_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_knowledge(record)

    def list_knowledge(
        self,
        tenant_id: str,
        category: Optional[KnowledgeCategory] = None,
        state: Optional[KnowledgeLifecycleState] = None,
        owner_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ResilienceKnowledgeRecord]:
        return self.repository.list_knowledge(
            tenant_id=tenant_id,
            category=category,
            state=state,
            owner_id=owner_id,
            query=query,
            limit=limit,
            offset=offset,
        )


_knowledge_service = GovernanceResilienceKnowledgeService()


def get_governance_resilience_knowledge_service() -> GovernanceResilienceKnowledgeService:
    return _knowledge_service

"""Phase 84: Capability Framework Domain Service.

Manages authoring, versioning, independent review, approval, publication, and
superseding of organizational resilience capability frameworks.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_capability_framework import (
    ApproveFrameworkRequest,
    CreateFrameworkRequest,
    FrameworkLifecycleState,
    PublishFrameworkRequest,
    ResilienceCapabilityFrameworkRecord,
    SubmitFrameworkRequest,
    UpdateFrameworkRequest,
)


class GovernanceResilienceCapabilityFrameworkService:
    """Service managing capability frameworks, version control, and publication governance."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def create_framework(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateFrameworkRequest,
    ) -> ResilienceCapabilityFrameworkRecord:
        framework_id = f"cfw-{uuid.uuid4().hex[:10]}"
        record = ResilienceCapabilityFrameworkRecord(
            framework_id=framework_id,
            tenant_id=tenant_id,
            framework_name=request.framework_name,
            description=request.description,
            version=1,
            lifecycle_state=FrameworkLifecycleState.DRAFT,
            capabilities=request.capabilities,
            created_by=user_id,
            review_date=request.review_date,
        )
        return self.repository.save_framework(record)

    def get_framework(self, tenant_id: str, framework_id: str) -> ResilienceCapabilityFrameworkRecord:
        record = self.repository.get_framework(framework_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPABILITY_FRAMEWORK_NOT_FOUND,
                message=f"Capability framework '{framework_id}' not found.",
                status_code=404,
            )
        return record

    def update_framework(
        self,
        tenant_id: str,
        framework_id: str,
        user_id: str,
        request: UpdateFrameworkRequest,
    ) -> ResilienceCapabilityFrameworkRecord:
        record = self.get_framework(tenant_id, framework_id)

        if record.lifecycle_state in [
            FrameworkLifecycleState.PUBLISHED,
            FrameworkLifecycleState.SUPERSEDED,
            FrameworkLifecycleState.ARCHIVED,
        ]:
            # For published frameworks, updating increments version and resets to DRAFT
            record.version += 1
            record.lifecycle_state = FrameworkLifecycleState.DRAFT

        if request.framework_name is not None:
            record.framework_name = request.framework_name
        if request.description is not None:
            record.description = request.description
        if request.capabilities is not None:
            record.capabilities = request.capabilities
        if request.review_date is not None:
            record.review_date = request.review_date

        record.updated_at = datetime.utcnow()
        return self.repository.save_framework(record)

    def submit_framework(
        self,
        tenant_id: str,
        framework_id: str,
        user_id: str,
        request: SubmitFrameworkRequest,
    ) -> ResilienceCapabilityFrameworkRecord:
        record = self.get_framework(tenant_id, framework_id)

        if record.lifecycle_state != FrameworkLifecycleState.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_FRAMEWORK_STATE,
                message=f"Framework in state '{record.lifecycle_state}' cannot be submitted. Must be DRAFT.",
                status_code=400,
            )

        record.lifecycle_state = FrameworkLifecycleState.SUBMITTED
        record.submitted_by = user_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_framework(record)

    def approve_framework(
        self,
        tenant_id: str,
        framework_id: str,
        approver_id: str,
        request: ApproveFrameworkRequest,
    ) -> ResilienceCapabilityFrameworkRecord:
        record = self.get_framework(tenant_id, framework_id)

        # Separation of duties: Creator cannot approve own framework
        if approver_id == record.created_by:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Framework creator cannot independently approve their own capability framework.",
                status_code=400,
            )

        if record.lifecycle_state != FrameworkLifecycleState.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_FRAMEWORK_STATE,
                message=f"Framework must be in SUBMITTED state before approval. Current: '{record.lifecycle_state}'.",
                status_code=400,
            )

        record.lifecycle_state = FrameworkLifecycleState.APPROVED
        record.approved_by = approver_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_framework(record)

    def publish_framework(
        self,
        tenant_id: str,
        framework_id: str,
        user_id: str,
        request: PublishFrameworkRequest,
    ) -> ResilienceCapabilityFrameworkRecord:
        record = self.get_framework(tenant_id, framework_id)

        if record.lifecycle_state != FrameworkLifecycleState.APPROVED:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_FRAMEWORK_STATE,
                message=f"Framework must be in APPROVED state before publication. Current: '{record.lifecycle_state}'.",
                status_code=400,
            )

        record.lifecycle_state = FrameworkLifecycleState.PUBLISHED
        record.published_at = datetime.utcnow()
        record.effective_date = request.effective_date or datetime.utcnow()
        record.updated_at = datetime.utcnow()
        return self.repository.save_framework(record)

    def list_frameworks(
        self,
        tenant_id: str,
        state: Optional[FrameworkLifecycleState] = None,
    ) -> List[ResilienceCapabilityFrameworkRecord]:
        return self.repository.list_frameworks(tenant_id=tenant_id, state=state)

    def get_framework_versions(
        self, tenant_id: str, framework_id: str
    ) -> List[ResilienceCapabilityFrameworkRecord]:
        self.get_framework(tenant_id, framework_id)
        return self.repository.get_framework_versions(framework_id, tenant_id)


_framework_service = GovernanceResilienceCapabilityFrameworkService()


def get_governance_resilience_capability_framework_service() -> GovernanceResilienceCapabilityFrameworkService:
    return _framework_service

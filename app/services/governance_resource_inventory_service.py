"""Phase 86: Critical Resource Inventory Service.

Manages the lifecycle of critical resources supporting governance operations.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_resource_common import (
    ResourceCategory,
    ResourceCriticality,
    ResourceLifecycleStatus,
)
from app.schemas.governance_resource_inventory import (
    CriticalResourceRecord,
    CreateResourceRequest,
    UpdateResourceRequest,
)


class GovernanceResourceInventoryService:

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def create_resource(
        self, tenant_id: str, user_id: str, request: CreateResourceRequest
    ) -> CriticalResourceRecord:
        now = datetime.utcnow()
        next_review = now + timedelta(days=request.review_cycle_days)
        record = CriticalResourceRecord(
            resource_id=f"res-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            resource_name=request.resource_name,
            category=request.category,
            description=request.description,
            owning_organization=request.owning_organization,
            responsible_department=request.responsible_department,
            resource_owner_ref=request.resource_owner_ref,
            criticality=request.criticality,
            associated_governance_capability=request.associated_governance_capability,
            availability_requirement_hours=request.availability_requirement_hours,
            recovery_requirement_ref=request.recovery_requirement_ref,
            dependency_refs=request.dependency_refs,
            alternative_resource_refs=request.alternative_resource_refs,
            external_provider_ref=request.external_provider_ref,
            source_system_ref=request.source_system_ref,
            verification_status="UNVERIFIED",
            last_verified_at=None,
            review_cycle_days=request.review_cycle_days,
            next_review_due=next_review,
            lifecycle_status=ResourceLifecycleStatus.ACTIVE,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_resource(record)

    def get_resource(self, tenant_id: str, resource_id: str) -> CriticalResourceRecord:
        record = self.repo.get_resource(resource_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Critical resource '{resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_resources(
        self,
        tenant_id: str,
        category: Optional[ResourceCategory] = None,
        criticality: Optional[ResourceCriticality] = None,
        lifecycle_status: Optional[ResourceLifecycleStatus] = None,
    ) -> List[CriticalResourceRecord]:
        return self.repo.list_resources(tenant_id, category, criticality, lifecycle_status)

    def update_resource(
        self, tenant_id: str, resource_id: str, request: UpdateResourceRequest
    ) -> CriticalResourceRecord:
        record = self.get_resource(tenant_id, resource_id)
        if record.lifecycle_status == ResourceLifecycleStatus.RETIRED:
            raise AppException(
                code=ErrorCode.INVALID_RESOURCE_STATE,
                message="Cannot update a retired resource.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        record.updated_at = datetime.utcnow()
        return self.repo.save_resource(record)


_resource_inventory_service: Optional[GovernanceResourceInventoryService] = None


def get_governance_resource_inventory_service() -> GovernanceResourceInventoryService:
    global _resource_inventory_service
    if _resource_inventory_service is None:
        _resource_inventory_service = GovernanceResourceInventoryService(
            get_governance_resource_dependency_repository()
        )
    return _resource_inventory_service

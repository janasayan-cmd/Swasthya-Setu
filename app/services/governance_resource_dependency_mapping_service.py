"""Phase 86: Capability-to-Resource Dependency Mapping Service.

Manages dependency mappings, approval lifecycle, and separation of duties.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_resource_common import DependencyMappingStatus
from app.schemas.governance_resource_dependency_mapping import (
    ApproveDependencyMappingRequest,
    CapabilityResourceDependencyRecord,
    CreateDependencyMappingRequest,
    UpdateDependencyMappingRequest,
)


class GovernanceResourceDependencyMappingService:

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def create_mapping(
        self, tenant_id: str, user_id: str, request: CreateDependencyMappingRequest
    ) -> CapabilityResourceDependencyRecord:
        # Verify resource exists
        resource = self.repo.get_resource(request.resource_id, tenant_id)
        if not resource:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource '{request.resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        now = datetime.utcnow()
        record = CapabilityResourceDependencyRecord(
            dependency_id=f"dep-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            governance_capability_ref=request.governance_capability_ref,
            responsibility_ref=request.responsibility_ref,
            resource_id=request.resource_id,
            resource_criticality=request.resource_criticality,
            dependency_type=request.dependency_type,
            minimum_availability_pct=request.minimum_availability_pct,
            required_operating_capacity=request.required_operating_capacity,
            organizational_scope=request.organizational_scope,
            dependency_owner=request.dependency_owner,
            evidence_refs=request.evidence_refs,
            status=DependencyMappingStatus.DRAFT,
            effective_start=request.effective_start,
            effective_end=request.effective_end,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_dependency_mapping(record)

    def get_mapping(self, tenant_id: str, dependency_id: str) -> CapabilityResourceDependencyRecord:
        record = self.repo.get_dependency_mapping(dependency_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPABILITY_DEPENDENCY_NOT_FOUND,
                message=f"Dependency mapping '{dependency_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_mappings(
        self,
        tenant_id: str,
        resource_id: Optional[str] = None,
        capability_ref: Optional[str] = None,
        mapping_status: Optional[DependencyMappingStatus] = None,
    ) -> List[CapabilityResourceDependencyRecord]:
        return self.repo.list_dependency_mappings(tenant_id, resource_id, capability_ref, mapping_status)

    def update_mapping(
        self, tenant_id: str, dependency_id: str, user_id: str, request: UpdateDependencyMappingRequest
    ) -> CapabilityResourceDependencyRecord:
        record = self.get_mapping(tenant_id, dependency_id)
        if record.status not in (DependencyMappingStatus.DRAFT, DependencyMappingStatus.SUBMITTED):
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_DEPENDENCY_STATE,
                message=f"Cannot update mapping in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        record.updated_at = datetime.utcnow()
        return self.repo.save_dependency_mapping(record)

    def submit_mapping(self, tenant_id: str, dependency_id: str, user_id: str) -> CapabilityResourceDependencyRecord:
        record = self.get_mapping(tenant_id, dependency_id)
        if record.status != DependencyMappingStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_DEPENDENCY_STATE,
                message="Only DRAFT mappings can be submitted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        record.status = DependencyMappingStatus.SUBMITTED
        record.updated_at = datetime.utcnow()
        return self.repo.save_dependency_mapping(record)

    def approve_mapping(
        self, tenant_id: str, dependency_id: str, approver_id: str, request: ApproveDependencyMappingRequest
    ) -> CapabilityResourceDependencyRecord:
        record = self.get_mapping(tenant_id, dependency_id)
        if record.created_by == approver_id:
            raise AppException(
                code=ErrorCode.RESOURCE_DEPENDENCY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties: Proposer cannot approve their own dependency mapping.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if record.status != DependencyMappingStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_DEPENDENCY_STATE,
                message=f"Cannot approve dependency mapping in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        now = datetime.utcnow()
        record.status = DependencyMappingStatus.APPROVED
        record.approved_by = approver_id
        record.approved_at = now
        record.updated_at = now
        return self.repo.save_dependency_mapping(record)


_dependency_mapping_service: Optional[GovernanceResourceDependencyMappingService] = None


def get_governance_resource_dependency_mapping_service() -> GovernanceResourceDependencyMappingService:
    global _dependency_mapping_service
    if _dependency_mapping_service is None:
        _dependency_mapping_service = GovernanceResourceDependencyMappingService(
            get_governance_resource_dependency_repository()
        )
    return _dependency_mapping_service

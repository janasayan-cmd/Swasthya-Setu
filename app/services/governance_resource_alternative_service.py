"""Phase 86: Alternative Resource and Fallback Readiness Assessment Service.

Manages alternative resource mappings and assesses fallback arrangement readiness.
A proposed alternative is NEVER treated as operationally equivalent without evidence.
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
from app.schemas.governance_resource_common import FallbackReadinessOutcome
from app.schemas.governance_resource_alternative import (
    AlternativeResourceRecord,
    AssessFallbackReadinessRequest,
    CreateAlternativeResourceRequest,
)


class GovernanceResourceAlternativeService:

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def create_alternative(
        self, tenant_id: str, resource_id: str, user_id: str, request: CreateAlternativeResourceRequest
    ) -> AlternativeResourceRecord:
        primary = self.repo.get_resource(resource_id, tenant_id)
        if not primary:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Primary resource '{resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if request.alternative_resource_id == resource_id:
            raise AppException(
                code=ErrorCode.INVALID_ALTERNATIVE_RESOURCE_STATE,
                message="A resource cannot be its own alternative.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        alternative_resource = self.repo.get_resource(request.alternative_resource_id, tenant_id)
        if not alternative_resource:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Alternative resource '{request.alternative_resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        now = datetime.utcnow()
        record = AlternativeResourceRecord(
            alternative_id=f"alt-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            primary_resource_id=resource_id,
            alternative_resource_id=request.alternative_resource_id,
            substitution_conditions=request.substitution_conditions,
            dependency_compatibility=request.dependency_compatibility,
            required_configuration_ref=request.required_configuration_ref,
            access_prerequisites=request.access_prerequisites,
            organizational_scope=request.organizational_scope,
            capacity_constraints=request.capacity_constraints,
            known_limitations=request.known_limitations,
            expiry_date=request.expiry_date,
            fallback_readiness=FallbackReadinessOutcome.NOT_ASSESSED,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_alternative(record)

    def get_alternative(self, tenant_id: str, alternative_id: str) -> AlternativeResourceRecord:
        record = self.repo.get_alternative(alternative_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.ALTERNATIVE_RESOURCE_NOT_FOUND,
                message=f"Alternative resource record '{alternative_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_alternatives_for_resource(
        self, tenant_id: str, resource_id: str
    ) -> List[AlternativeResourceRecord]:
        return self.repo.list_alternatives_for_resource(resource_id, tenant_id)

    def assess_fallback_readiness(
        self,
        tenant_id: str,
        alternative_id: str,
        assessor_id: str,
        request: AssessFallbackReadinessRequest,
    ) -> AlternativeResourceRecord:
        record = self.get_alternative(tenant_id, alternative_id)
        now = datetime.utcnow()
        record.fallback_readiness = request.fallback_readiness
        record.readiness_notes = request.readiness_notes
        record.verification_evidence_ref = request.verification_evidence_ref
        if request.last_successful_validation:
            record.last_successful_validation = request.last_successful_validation
        if request.limitations_identified:
            record.known_limitations = request.limitations_identified
        record.readiness_assessed_by = assessor_id
        record.readiness_assessed_at = now
        record.updated_at = now
        return self.repo.save_alternative(record)


_alternative_service: Optional[GovernanceResourceAlternativeService] = None


def get_governance_resource_alternative_service() -> GovernanceResourceAlternativeService:
    global _alternative_service
    if _alternative_service is None:
        _alternative_service = GovernanceResourceAlternativeService(
            get_governance_resource_dependency_repository()
        )
    return _alternative_service

"""Phase 85: Critical Governance Role and Responsibility Service.

Manages the inventory of critical governance roles, assigned responsibilities,
criticality tiers, and periodic governance reviews.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_role_coverage_repository import (
    GovernanceRoleCoverageRepository,
    get_governance_role_coverage_repository,
)
from app.schemas.governance_role_coverage_common import (
    CriticalityTier,
    CoverageScope,
)
from app.schemas.governance_role_responsibility import (
    CreateCriticalResponsibilityRequest,
    CriticalGovernanceResponsibilityRecord,
    ReviewCriticalResponsibilityRequest,
    UpdateCriticalResponsibilityRequest,
)


class GovernanceRoleResponsibilityService:
    """Service for managing critical governance responsibilities."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def create_responsibility(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateCriticalResponsibilityRequest,
    ) -> CriticalGovernanceResponsibilityRecord:
        now = datetime.utcnow()
        next_review = now + timedelta(days=request.review_cycle_days)
        record = CriticalGovernanceResponsibilityRecord(
            responsibility_id=f"cresp-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            role_title=request.role_title,
            responsibility_name=request.responsibility_name,
            description=request.description,
            criticality_tier=request.criticality_tier,
            coverage_scope=request.coverage_scope,
            max_acceptable_outage_hours=request.max_acceptable_outage_hours,
            primary_owner_id=request.primary_owner_id,
            primary_owner_name=request.primary_owner_name,
            required_capability_framework_id=request.required_capability_framework_id,
            required_capability_ids=request.required_capability_ids,
            status="ACTIVE",
            review_cycle_days=request.review_cycle_days,
            last_reviewed_at=now,
            next_review_due=next_review,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_responsibility(record)

    def get_responsibility(
        self, tenant_id: str, responsibility_id: str
    ) -> CriticalGovernanceResponsibilityRecord:
        record = self.repository.get_responsibility(responsibility_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CRITICAL_RESPONSIBILITY_NOT_FOUND,
                message=f"Critical governance responsibility '{responsibility_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_responsibilities(
        self,
        tenant_id: str,
        criticality_tier: Optional[CriticalityTier] = None,
        scope: Optional[CoverageScope] = None,
    ) -> List[CriticalGovernanceResponsibilityRecord]:
        return self.repository.list_responsibilities(tenant_id, criticality_tier, scope)

    def update_responsibility(
        self,
        tenant_id: str,
        responsibility_id: str,
        request: UpdateCriticalResponsibilityRequest,
    ) -> CriticalGovernanceResponsibilityRecord:
        record = self.get_responsibility(tenant_id, responsibility_id)
        if request.role_title is not None:
            record.role_title = request.role_title
        if request.responsibility_name is not None:
            record.responsibility_name = request.responsibility_name
        if request.description is not None:
            record.description = request.description
        if request.criticality_tier is not None:
            record.criticality_tier = request.criticality_tier
        if request.coverage_scope is not None:
            record.coverage_scope = request.coverage_scope
        if request.max_acceptable_outage_hours is not None:
            record.max_acceptable_outage_hours = request.max_acceptable_outage_hours
        if request.primary_owner_id is not None:
            record.primary_owner_id = request.primary_owner_id
        if request.primary_owner_name is not None:
            record.primary_owner_name = request.primary_owner_name
        if request.required_capability_framework_id is not None:
            record.required_capability_framework_id = request.required_capability_framework_id
        if request.required_capability_ids is not None:
            record.required_capability_ids = request.required_capability_ids
        if request.review_cycle_days is not None:
            record.review_cycle_days = request.review_cycle_days
        if request.status is not None:
            record.status = request.status
        record.updated_at = datetime.utcnow()
        return self.repository.save_responsibility(record)

    def review_responsibility(
        self,
        tenant_id: str,
        responsibility_id: str,
        reviewer_id: str,
        request: ReviewCriticalResponsibilityRequest,
    ) -> CriticalGovernanceResponsibilityRecord:
        record = self.get_responsibility(tenant_id, responsibility_id)
        now = datetime.utcnow()
        days = request.next_review_cycle_days or record.review_cycle_days
        record.last_reviewed_at = now
        record.next_review_due = now + timedelta(days=days)
        record.updated_at = now
        return self.repository.save_responsibility(record)


_responsibility_service: Optional[GovernanceRoleResponsibilityService] = None


def get_governance_role_responsibility_service() -> GovernanceRoleResponsibilityService:
    global _responsibility_service
    if _responsibility_service is None:
        _responsibility_service = GovernanceRoleResponsibilityService(
            get_governance_role_coverage_repository()
        )
    return _responsibility_service

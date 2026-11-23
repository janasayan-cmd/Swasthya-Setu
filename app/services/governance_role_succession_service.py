"""Phase 85: Governance Succession Readiness Service.

Manages succession readiness plans, pipeline pipelines, candidate readiness tiers,
and separation of duties for critical governance roles.
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
    SuccessionPlanStatus,
)
from app.schemas.governance_role_succession import (
    ApproveSuccessionPlanRequest,
    CreateSuccessionPlanRequest,
    ReviewSuccessionPlanRequest,
    SuccessionPlanRecord,
    UpdateSuccessionPlanRequest,
)


class GovernanceRoleSuccessionService:
    """Service for managing governance succession readiness plans."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def create_succession_plan(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateSuccessionPlanRequest,
    ) -> SuccessionPlanRecord:
        resp = self.repository.get_responsibility(request.responsibility_id, tenant_id)
        if not resp:
            raise AppException(
                code=ErrorCode.CRITICAL_RESPONSIBILITY_NOT_FOUND,
                message=f"Critical responsibility '{request.responsibility_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.utcnow()
        next_review = now + timedelta(days=request.review_cycle_days)
        record = SuccessionPlanRecord(
            succession_plan_id=f"succ-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            responsibility_id=request.responsibility_id,
            role_title=resp.role_title,
            status=SuccessionPlanStatus.DRAFT,
            candidates=request.candidates,
            review_cycle_days=request.review_cycle_days,
            last_reviewed_at=now,
            next_review_due=next_review,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_succession_plan(record)

    def get_succession_plan(
        self, tenant_id: str, succession_plan_id: str
    ) -> SuccessionPlanRecord:
        record = self.repository.get_succession_plan(succession_plan_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.SUCCESSION_PLAN_NOT_FOUND,
                message=f"Succession plan '{succession_plan_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_succession_plans(
        self,
        tenant_id: str,
        plan_status: Optional[SuccessionPlanStatus] = None,
    ) -> List[SuccessionPlanRecord]:
        return self.repository.list_succession_plans(tenant_id, plan_status)

    def update_succession_plan(
        self,
        tenant_id: str,
        succession_plan_id: str,
        request: UpdateSuccessionPlanRequest,
    ) -> SuccessionPlanRecord:
        record = self.get_succession_plan(tenant_id, succession_plan_id)
        if record.status not in (SuccessionPlanStatus.DRAFT, SuccessionPlanStatus.UNDER_REVIEW):
            raise AppException(
                code=ErrorCode.INVALID_SUCCESSION_PLAN_STATE,
                message=f"Cannot update succession plan in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if request.candidates is not None:
            record.candidates = request.candidates
        if request.review_cycle_days is not None:
            record.review_cycle_days = request.review_cycle_days
        record.updated_at = datetime.utcnow()
        return self.repository.save_succession_plan(record)

    def approve_succession_plan(
        self,
        tenant_id: str,
        succession_plan_id: str,
        approver_id: str,
        request: ApproveSuccessionPlanRequest,
    ) -> SuccessionPlanRecord:
        record = self.get_succession_plan(tenant_id, succession_plan_id)

        # Separation of duties: Creator cannot approve their own succession plan
        if record.created_by == approver_id:
            raise AppException(
                code=ErrorCode.ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Creator cannot approve their own succession plan.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Separation of duties: Nominated candidate cannot approve their own succession plan
        for c in record.candidates:
            if c.user_id == approver_id:
                raise AppException(
                    code=ErrorCode.ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION,
                    message="Separation of duties violation: Nominated candidate cannot approve their own succession plan.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        if not record.candidates:
            raise AppException(
                code=ErrorCode.INVALID_SUCCESSION_PLAN_STATE,
                message="Cannot approve succession plan without any nominated candidates.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        record.status = SuccessionPlanStatus.APPROVED
        record.approved_by = approver_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_succession_plan(record)

    def review_succession_plan(
        self,
        tenant_id: str,
        succession_plan_id: str,
        user_id: str,
        request: ReviewSuccessionPlanRequest,
    ) -> SuccessionPlanRecord:
        record = self.get_succession_plan(tenant_id, succession_plan_id)
        now = datetime.utcnow()
        days = request.next_cycle_days or record.review_cycle_days
        record.last_reviewed_at = now
        record.next_review_due = now + timedelta(days=days)
        record.updated_at = now
        return self.repository.save_succession_plan(record)


_succession_service: Optional[GovernanceRoleSuccessionService] = None


def get_governance_role_succession_service() -> GovernanceRoleSuccessionService:
    global _succession_service
    if _succession_service is None:
        _succession_service = GovernanceRoleSuccessionService(
            get_governance_role_coverage_repository()
        )
    return _succession_service

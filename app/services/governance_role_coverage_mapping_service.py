"""Phase 85: Role-Coverage Mapping and Arrangement Service.

Manages coverage arrangements, designated backups, approval lifecycles,
and strict separation-of-duties enforcement.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_role_coverage_repository import (
    GovernanceRoleCoverageRepository,
    get_governance_role_coverage_repository,
)
from app.schemas.governance_role_coverage_common import (
    CoverageArrangementStatus,
)
from app.schemas.governance_role_coverage_mapping import (
    ApproveCoverageArrangementRequest,
    CloseCoverageArrangementRequest,
    CreateCoverageArrangementRequest,
    RoleCoverageArrangementRecord,
    SubmitCoverageArrangementRequest,
    SuspendCoverageArrangementRequest,
    UpdateCoverageArrangementRequest,
)


class GovernanceRoleCoverageMappingService:
    """Service for managing role-coverage arrangements and designated backups."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def create_coverage(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateCoverageArrangementRequest,
    ) -> RoleCoverageArrangementRecord:
        # Check if responsibility exists
        responsibility = self.repository.get_responsibility(
            request.responsibility_id, tenant_id
        )
        if not responsibility:
            raise AppException(
                code=ErrorCode.CRITICAL_RESPONSIBILITY_NOT_FOUND,
                message=f"Critical responsibility '{request.responsibility_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.utcnow()
        record = RoleCoverageArrangementRecord(
            coverage_id=f"cov-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            responsibility_id=request.responsibility_id,
            status=CoverageArrangementStatus.DRAFT,
            designated_backups=request.designated_backups,
            effective_start_date=request.effective_start_date,
            effective_end_date=request.effective_end_date,
            activation_condition=request.activation_condition,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_coverage(record)

    def get_coverage(
        self, tenant_id: str, coverage_id: str
    ) -> RoleCoverageArrangementRecord:
        record = self.repository.get_coverage(coverage_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.ROLE_COVERAGE_NOT_FOUND,
                message=f"Role-coverage arrangement '{coverage_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def get_coverage_by_responsibility(
        self, tenant_id: str, responsibility_id: str
    ) -> Optional[RoleCoverageArrangementRecord]:
        return self.repository.get_coverage_by_responsibility(responsibility_id, tenant_id)

    def list_coverages(
        self,
        tenant_id: str,
        coverage_status: Optional[CoverageArrangementStatus] = None,
    ) -> List[RoleCoverageArrangementRecord]:
        return self.repository.list_coverages(tenant_id, coverage_status)

    def update_coverage(
        self,
        tenant_id: str,
        coverage_id: str,
        user_id: str,
        request: UpdateCoverageArrangementRequest,
    ) -> RoleCoverageArrangementRecord:
        record = self.get_coverage(tenant_id, coverage_id)
        if record.status not in (
            CoverageArrangementStatus.DRAFT,
            CoverageArrangementStatus.UNDER_REVIEW,
            CoverageArrangementStatus.EVIDENCE_PENDING,
        ):
            raise AppException(
                code=ErrorCode.INVALID_ROLE_COVERAGE_STATE,
                message=f"Cannot update coverage arrangement in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if request.designated_backups is not None:
            record.designated_backups = request.designated_backups
        if request.effective_start_date is not None:
            record.effective_start_date = request.effective_start_date
        if request.effective_end_date is not None:
            record.effective_end_date = request.effective_end_date
        if request.activation_condition is not None:
            record.activation_condition = request.activation_condition
        record.updated_at = datetime.utcnow()
        return self.repository.save_coverage(record)

    def submit_coverage(
        self,
        tenant_id: str,
        coverage_id: str,
        user_id: str,
        request: SubmitCoverageArrangementRequest,
    ) -> RoleCoverageArrangementRecord:
        record = self.get_coverage(tenant_id, coverage_id)
        if record.status != CoverageArrangementStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_ROLE_COVERAGE_STATE,
                message=f"Only DRAFT coverage arrangements can be submitted for review. Current: '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not record.designated_backups:
            raise AppException(
                code=ErrorCode.INVALID_ROLE_COVERAGE_STATE,
                message="Cannot submit coverage arrangement without at least one designated backup.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        record.status = CoverageArrangementStatus.UNDER_REVIEW
        record.reviewed_by = user_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_coverage(record)

    def approve_coverage(
        self,
        tenant_id: str,
        coverage_id: str,
        approver_id: str,
        request: ApproveCoverageArrangementRequest,
    ) -> RoleCoverageArrangementRecord:
        record = self.get_coverage(tenant_id, coverage_id)

        # Separation of duties: Proposer cannot approve their own arrangement
        if record.created_by == approver_id:
            raise AppException(
                code=ErrorCode.ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Proposer cannot approve their own coverage arrangement.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Separation of duties: Designated backup cannot approve their own appointment
        for backup in record.designated_backups:
            if backup.backup_user_id == approver_id:
                raise AppException(
                    code=ErrorCode.ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION,
                    message="Separation of duties violation: Designated backup cannot approve their own appointment.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        if record.status not in (
            CoverageArrangementStatus.UNDER_REVIEW,
            CoverageArrangementStatus.EVIDENCE_PENDING,
            CoverageArrangementStatus.AUTHORIZATION_PENDING,
        ):
            raise AppException(
                code=ErrorCode.INVALID_ROLE_COVERAGE_STATE,
                message=f"Cannot approve coverage arrangement in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate verified backup criteria
        has_verified_backup = any(
            b.capability_verified and b.authorization_verified and b.is_available
            for b in record.designated_backups
        )
        if not has_verified_backup:
            raise AppException(
                code=ErrorCode.UNVERIFIED_BACKUP_COVERAGE_DENIED,
                message="Cannot approve coverage arrangement without at least one designated backup with verified capability and authorization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.utcnow()
        record.status = CoverageArrangementStatus.ACTIVE
        record.approved_by = approver_id
        record.approved_at = now
        record.activation_notes = request.approval_notes
        record.updated_at = now
        return self.repository.save_coverage(record)

    def suspend_coverage(
        self,
        tenant_id: str,
        coverage_id: str,
        user_id: str,
        request: SuspendCoverageArrangementRequest,
    ) -> RoleCoverageArrangementRecord:
        record = self.get_coverage(tenant_id, coverage_id)
        if record.status not in (CoverageArrangementStatus.ACTIVE, CoverageArrangementStatus.APPROVED):
            raise AppException(
                code=ErrorCode.INVALID_ROLE_COVERAGE_STATE,
                message=f"Cannot suspend coverage arrangement in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        record.status = CoverageArrangementStatus.SUSPENDED
        record.activation_notes = request.reason
        record.updated_at = datetime.utcnow()
        return self.repository.save_coverage(record)

    def close_coverage(
        self,
        tenant_id: str,
        coverage_id: str,
        user_id: str,
        request: CloseCoverageArrangementRequest,
    ) -> RoleCoverageArrangementRecord:
        record = self.get_coverage(tenant_id, coverage_id)
        record.status = CoverageArrangementStatus.CLOSED
        record.activation_notes = request.closure_reason
        record.updated_at = datetime.utcnow()
        return self.repository.save_coverage(record)


_coverage_mapping_service: Optional[GovernanceRoleCoverageMappingService] = None


def get_governance_role_coverage_mapping_service() -> GovernanceRoleCoverageMappingService:
    global _coverage_mapping_service
    if _coverage_mapping_service is None:
        _coverage_mapping_service = GovernanceRoleCoverageMappingService(
            get_governance_role_coverage_repository()
        )
    return _coverage_mapping_service

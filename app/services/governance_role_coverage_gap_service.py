"""Phase 85: Role-Coverage Gap Management and Escalation Service.

Tracks identified coverage gaps, assigns remediation owners, coordinates
authoritative escalations to Phases 54/63/67/72, and verifies evidence-backed resolution.
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
    CoverageGapCategory,
    CoverageGapStatus,
)
from app.schemas.governance_role_coverage_gap import (
    AssignCoverageGapRequest,
    CreateCoverageGapRequest,
    EscalateCoverageGapRequest,
    ResolveCoverageGapRequest,
    RoleCoverageGapRecord,
)


class GovernanceRoleCoverageGapService:
    """Service for managing coverage gaps and authoritative escalations."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def create_gap(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateCoverageGapRequest,
    ) -> RoleCoverageGapRecord:
        resp = self.repository.get_responsibility(request.responsibility_id, tenant_id)
        if not resp:
            raise AppException(
                code=ErrorCode.CRITICAL_RESPONSIBILITY_NOT_FOUND,
                message=f"Critical responsibility '{request.responsibility_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.utcnow()
        gap_status = CoverageGapStatus.ASSIGNED if request.assigned_to else CoverageGapStatus.IDENTIFIED
        record = RoleCoverageGapRecord(
            gap_id=f"gap-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            responsibility_id=request.responsibility_id,
            category=request.category,
            severity=request.severity,
            status=gap_status,
            title=request.title,
            description=request.description,
            identified_at=now,
            assigned_to=request.assigned_to,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_coverage_gap(record)

    def get_gap(self, tenant_id: str, gap_id: str) -> RoleCoverageGapRecord:
        record = self.repository.get_coverage_gap(gap_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.COVERAGE_GAP_NOT_FOUND,
                message=f"Role-coverage gap '{gap_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_gaps(
        self,
        tenant_id: str,
        responsibility_id: Optional[str] = None,
        gap_status: Optional[CoverageGapStatus] = None,
        category: Optional[CoverageGapCategory] = None,
    ) -> List[RoleCoverageGapRecord]:
        return self.repository.list_coverage_gaps(
            tenant_id, responsibility_id, gap_status, category
        )

    def assign_gap(
        self,
        tenant_id: str,
        gap_id: str,
        user_id: str,
        request: AssignCoverageGapRequest,
    ) -> RoleCoverageGapRecord:
        record = self.get_gap(tenant_id, gap_id)
        record.assigned_to = request.assigned_to
        record.status = CoverageGapStatus.ASSIGNED
        if request.notes:
            record.remediation_notes = request.notes
        record.updated_at = datetime.utcnow()
        return self.repository.save_coverage_gap(record)

    def escalate_gap(
        self,
        tenant_id: str,
        gap_id: str,
        user_id: str,
        request: EscalateCoverageGapRequest,
    ) -> RoleCoverageGapRecord:
        record = self.get_gap(tenant_id, gap_id)
        record.status = CoverageGapStatus.ESCALATED
        record.escalated_to_phase = request.escalated_to_phase
        record.escalation_reference_id = request.escalation_reference_id
        if request.escalation_notes:
            record.remediation_notes = request.escalation_notes
        record.updated_at = datetime.utcnow()
        return self.repository.save_coverage_gap(record)

    def resolve_gap(
        self,
        tenant_id: str,
        gap_id: str,
        verifier_id: str,
        request: ResolveCoverageGapRequest,
    ) -> RoleCoverageGapRecord:
        record = self.get_gap(tenant_id, gap_id)

        # Verification check: Must reference newly verified coverage or approved succession plan
        if not request.verified_coverage_id and not request.verified_succession_plan_id:
            raise AppException(
                code=ErrorCode.INVALID_COVERAGE_GAP_STATE,
                message="Cannot resolve coverage gap without linking a verified coverage arrangement or approved succession plan.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.utcnow()
        record.status = CoverageGapStatus.VERIFIED_RESOLVED
        record.remediation_notes = request.remediation_notes
        record.resolved_at = now
        record.resolution_verified_by = verifier_id
        record.updated_at = now
        return self.repository.save_coverage_gap(record)


_coverage_gap_service: Optional[GovernanceRoleCoverageGapService] = None


def get_governance_role_coverage_gap_service() -> GovernanceRoleCoverageGapService:
    global _coverage_gap_service
    if _coverage_gap_service is None:
        _coverage_gap_service = GovernanceRoleCoverageGapService(
            get_governance_role_coverage_repository()
        )
    return _coverage_gap_service

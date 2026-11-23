"""Phase 86: Resource Dependency Gap Management Service.

Tracks resource gaps, remediates assignments, coordinates escalations to Phases 54/63/67/72,
and verifies resolution with evidence.
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
from app.schemas.governance_resource_common import ResourceGapCategory, ResourceGapStatus
from app.schemas.governance_resource_gap import (
    AssignResourceGapRequest,
    CreateResourceGapRequest,
    EscalateResourceGapRequest,
    ResolveResourceGapRequest,
    ResourceDependencyGapRecord,
)


class GovernanceResourceGapService:

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def create_gap(
        self, tenant_id: str, user_id: str, request: CreateResourceGapRequest
    ) -> ResourceDependencyGapRecord:
        now = datetime.utcnow()
        initial_status = ResourceGapStatus.ASSIGNED if request.assigned_to else ResourceGapStatus.IDENTIFIED
        record = ResourceDependencyGapRecord(
            gap_id=f"rgap-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            governance_capability_ref=request.governance_capability_ref,
            resource_id=request.resource_id,
            dependency_id=request.dependency_id,
            category=request.category,
            severity=request.severity,
            status=initial_status,
            title=request.title,
            description=request.description,
            identified_at=now,
            assigned_to=request.assigned_to,
            remediation_proposal=request.remediation_proposal,
            target_resolution_date=request.target_resolution_date,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_resource_gap(record)

    def get_gap(self, tenant_id: str, gap_id: str) -> ResourceDependencyGapRecord:
        record = self.repo.get_resource_gap(gap_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.RESOURCE_GAP_NOT_FOUND,
                message=f"Resource dependency gap '{gap_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_gaps(
        self,
        tenant_id: str,
        gap_status: Optional[ResourceGapStatus] = None,
        category: Optional[ResourceGapCategory] = None,
        resource_id: Optional[str] = None,
    ) -> List[ResourceDependencyGapRecord]:
        return self.repo.list_resource_gaps(tenant_id, gap_status, category, resource_id)

    def assign_gap(
        self, tenant_id: str, gap_id: str, user_id: str, request: AssignResourceGapRequest
    ) -> ResourceDependencyGapRecord:
        record = self.get_gap(tenant_id, gap_id)
        record.assigned_to = request.assigned_to
        if request.remediation_proposal:
            record.remediation_proposal = request.remediation_proposal
        if request.target_resolution_date:
            record.target_resolution_date = request.target_resolution_date
        record.status = ResourceGapStatus.ASSIGNED
        record.updated_at = datetime.utcnow()
        return self.repo.save_resource_gap(record)

    def escalate_gap(
        self, tenant_id: str, gap_id: str, user_id: str, request: EscalateResourceGapRequest
    ) -> ResourceDependencyGapRecord:
        record = self.get_gap(tenant_id, gap_id)
        record.escalated_to_phase = request.escalated_to_phase
        record.escalation_reference_id = request.escalation_reference_id
        if request.escalation_notes:
            record.remediation_proposal = request.escalation_notes
        record.status = ResourceGapStatus.ESCALATED
        record.updated_at = datetime.utcnow()
        return self.repo.save_resource_gap(record)

    def resolve_gap(
        self, tenant_id: str, gap_id: str, verifier_id: str, request: ResolveResourceGapRequest
    ) -> ResourceDependencyGapRecord:
        record = self.get_gap(tenant_id, gap_id)
        if not request.resolution_evidence_ref:
            raise AppException(
                code=ErrorCode.INVALID_RESOURCE_GAP_STATE,
                message="Cannot resolve resource gap without linking resolution evidence.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        now = datetime.utcnow()
        record.status = ResourceGapStatus.VERIFIED_RESOLVED
        record.remediation_proposal = request.resolution_notes
        record.resolution_evidence_ref = request.resolution_evidence_ref
        record.resolved_at = now
        record.resolution_verified_by = verifier_id
        record.updated_at = now
        return self.repo.save_resource_gap(record)


_gap_service: Optional[GovernanceResourceGapService] = None


def get_governance_resource_gap_service() -> GovernanceResourceGapService:
    global _gap_service
    if _gap_service is None:
        _gap_service = GovernanceResourceGapService(
            get_governance_resource_dependency_repository()
        )
    return _gap_service

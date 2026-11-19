"""Phase 70: Audit Programme & Lifecycle Management Service.

Coordinates:
- Establishment and governance approval of audit programmes
- Clinical safety audit instantiation under programmes
- Audit state machine transitions: SCHEDULED, IN_PROGRESS, PAUSED, CANCELLED, etc.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_programme import (
    ApproveAuditProgrammeRequest,
    AuditProgrammeRecord,
    AuditProgrammeStatus,
    CreateAuditProgrammeRequest,
    UpdateAuditProgrammeRequest,
)
from app.schemas.audit_scope_planning import (
    AuditLifecycleStatus,
    AuditScopeStatus,
    ClinicalSafetyAuditRecord,
    CreateAuditRequest,
    ScheduleAuditRequest,
    UpdateAuditRequest,
)
from app.schemas.user import AuthenticatedUserContext


class AuditProgrammeService:
    """Service managing audit programmes and individual audit lifecycle states."""

    def __init__(self, repository: Optional[GovernanceAuditRepository] = None) -> None:
        self.repository = repository or get_governance_audit_repository()

    # -------------------------------------------------------------------------
    # Audit Programmes
    # -------------------------------------------------------------------------

    def create_programme(
        self, user: AuthenticatedUserContext, payload: CreateAuditProgrammeRequest
    ) -> AuditProgrammeRecord:
        """Establish a new clinical safety governance audit programme."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create audit programmes.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = AuditProgrammeRecord(
            name=payload.name,
            description=payload.description,
            objectives=payload.objectives,
            category=payload.category,
            priority=payload.priority,
            status=AuditProgrammeStatus.ACTIVE,  # Active for audit scheduling
            organization_id=user.organization_id,
            facility_id=payload.facility_id or user.facility_id,
            responsible_owner_id=user.user_id,
            responsible_owner_role=user.role.value,
            planned_start_date=payload.planned_start_date or now,
            planned_end_date=payload.planned_end_date,
            related_framework_ids=payload.related_framework_ids or [],
            created_by=user.user_id,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_programme(record)

    def get_programme(
        self, user: AuthenticatedUserContext, programme_id: str
    ) -> AuditProgrammeRecord:
        """Retrieve audit programme ensuring tenant boundary enforcement."""
        prog = self.repository.get_programme(programme_id)
        if not prog:
            raise AppException(
                code=ErrorCode.AUDIT_PROGRAMME_NOT_FOUND,
                message=f"Audit programme {programme_id} not found.",
                status_code=404,
            )
        if prog.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access audit programme across tenant boundaries.",
                status_code=403,
            )
        return prog

    def list_programmes(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditProgrammeRecord]:
        """List audit programmes within tenant scope."""
        return self.repository.list_programmes(
            organization_id=user.organization_id,
            facility_id=facility_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    def approve_programme(
        self,
        user: AuthenticatedUserContext,
        programme_id: str,
        payload: ApproveAuditProgrammeRequest,
    ) -> AuditProgrammeRecord:
        """Formally approve an audit programme (Admin or Doctor role)."""
        prog = self.get_programme(user, programme_id)
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can approve audit programmes.",
                status_code=403,
            )

        prog.status = AuditProgrammeStatus.APPROVED
        prog.approved_by = user.user_id
        prog.approved_at = datetime.now(timezone.utc)
        prog.approval_rationale = payload.approval_rationale
        return self.repository.save_programme(prog)

    # -------------------------------------------------------------------------
    # Individual Safety Audits
    # -------------------------------------------------------------------------

    def create_audit(
        self, user: AuthenticatedUserContext, payload: CreateAuditRequest
    ) -> ClinicalSafetyAuditRecord:
        """Create a new safety audit under an approved programme."""
        prog = self.get_programme(user, payload.programme_id)

        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create audits.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = ClinicalSafetyAuditRecord(
            programme_id=prog.programme_id,
            title=payload.title,
            description=payload.description,
            category=payload.category or prog.category,
            priority=payload.priority or prog.priority,
            lifecycle_status=AuditLifecycleStatus.DRAFT,
            organization_id=user.organization_id,
            facility_id=payload.facility_id or prog.facility_id,
            lead_auditor_id=payload.lead_auditor_id,
            planned_start_date=payload.planned_start_date,
            planned_end_date=payload.planned_end_date,
            created_by=user.user_id,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_audit(record)

    def get_audit(
        self, user: AuthenticatedUserContext, audit_id: str
    ) -> ClinicalSafetyAuditRecord:
        """Retrieve audit record ensuring tenant boundary isolation."""
        audit = self.repository.get_audit(audit_id)
        if not audit:
            raise AppException(
                code=ErrorCode.AUDIT_NOT_FOUND,
                message=f"Clinical safety audit {audit_id} not found.",
                status_code=404,
            )
        if audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access audit across tenant boundaries.",
                status_code=403,
            )
        return audit

    def list_audits(
        self,
        user: AuthenticatedUserContext,
        programme_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ClinicalSafetyAuditRecord]:
        """List audits within tenant scope."""
        return self.repository.list_audits(
            organization_id=user.organization_id,
            programme_id=programme_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    def schedule_audit(
        self, user: AuthenticatedUserContext, audit_id: str, payload: ScheduleAuditRequest
    ) -> ClinicalSafetyAuditRecord:
        """Schedule or initiate an approved audit."""
        audit = self.get_audit(user, audit_id)

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only governance leads or administrators can schedule audits.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        audit.planned_start_date = payload.scheduled_start_date
        audit.planned_end_date = payload.scheduled_end_date

        if payload.start_immediately:
            audit.lifecycle_status = AuditLifecycleStatus.IN_PROGRESS
            audit.actual_start_date = now
            # Freeze scope if defined
            scope = self.repository.get_scope_for_audit(audit_id)
            if scope:
                scope.is_frozen = True
                scope.frozen_at = now
                scope.frozen_by = user.user_id
                scope.status = AuditScopeStatus.FROZEN
                self.repository.save_scope(scope)
        else:
            audit.lifecycle_status = AuditLifecycleStatus.SCHEDULED

        return self.repository.save_audit(audit)

    def pause_audit(
        self, user: AuthenticatedUserContext, audit_id: str, reason: str
    ) -> ClinicalSafetyAuditRecord:
        """Pause an in-progress audit with documented operational reason."""
        audit = self.get_audit(user, audit_id)
        if audit.lifecycle_status != AuditLifecycleStatus.IN_PROGRESS:
            raise AppException(
                code=ErrorCode.INVALID_AUDIT_STATE,
                message=f"Audit cannot be paused from status {audit.lifecycle_status.value}.",
                status_code=400,
            )

        audit.lifecycle_status = AuditLifecycleStatus.PAUSED
        audit.paused_reason = reason
        return self.repository.save_audit(audit)

    def resume_audit(
        self, user: AuthenticatedUserContext, audit_id: str
    ) -> ClinicalSafetyAuditRecord:
        """Resume a paused audit."""
        audit = self.get_audit(user, audit_id)
        if audit.lifecycle_status != AuditLifecycleStatus.PAUSED:
            raise AppException(
                code=ErrorCode.INVALID_AUDIT_STATE,
                message=f"Audit cannot be resumed from status {audit.lifecycle_status.value}.",
                status_code=400,
            )

        audit.lifecycle_status = AuditLifecycleStatus.IN_PROGRESS
        return self.repository.save_audit(audit)

    def cancel_audit(
        self, user: AuthenticatedUserContext, audit_id: str, reason: str
    ) -> ClinicalSafetyAuditRecord:
        """Cancel an audit while strictly preserving full audit history."""
        audit = self.get_audit(user, audit_id)
        if audit.lifecycle_status == AuditLifecycleStatus.CLOSED:
            raise AppException(
                code=ErrorCode.INVALID_AUDIT_STATE,
                message="Closed audits cannot be cancelled.",
                status_code=400,
            )

        audit.lifecycle_status = AuditLifecycleStatus.CANCELLED
        audit.cancellation_reason = reason
        return self.repository.save_audit(audit)


# Global singleton
_global_programme_service = AuditProgrammeService()


def get_audit_programme_service() -> AuditProgrammeService:
    """Dependency provider for audit programme service."""
    return _global_programme_service

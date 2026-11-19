"""Phase 70: Auditor Assignment & Independence Service.

Coordinates:
- Auditor assignment to clinical safety audits
- Independence assessment and conflict-of-interest declarations
- Mitigation evaluation and independent approval
- Separation-of-duties enforcement: self-review of independence is forbidden
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.auditor_assignment import (
    AssignAuditorRequest,
    AuditorAssignmentRecord,
    AuditorRole,
    IndependenceReviewRequest,
    IndependenceStatus,
)
from app.schemas.user import AuthenticatedUserContext


class AuditorIndependenceService:
    """Service governing auditor assignment and independent review."""

    def __init__(self, repository: Optional[GovernanceAuditRepository] = None) -> None:
        self.repository = repository or get_governance_audit_repository()

    def assign_auditor(
        self, user: AuthenticatedUserContext, audit_id: str, payload: AssignAuditorRequest
    ) -> AuditorAssignmentRecord:
        """Assign an auditor to an audit and record declared conflicts."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot assign auditors.",
                status_code=403,
            )

        audit = self.repository.get_audit(audit_id)
        if not audit:
            raise AppException(
                code=ErrorCode.AUDIT_NOT_FOUND,
                message=f"Audit {audit_id} not found.",
                status_code=404,
            )
        if audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot assign auditor across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        conflicts = payload.declared_conflicts or []
        init_status = (
            IndependenceStatus.CONFLICT_IDENTIFIED
            if len(conflicts) > 0
            else IndependenceStatus.PENDING_REVIEW
        )

        record = AuditorAssignmentRecord(
            audit_id=audit_id,
            auditor_id=payload.auditor_id,
            auditor_name=payload.auditor_name,
            auditor_role=payload.auditor_role or AuditorRole.SUPPORTING_AUDITOR,
            independence_status=init_status,
            declared_conflicts=conflicts,
            conflict_mitigation=payload.conflict_mitigation,
            assigned_by=user.user_id,
            assigned_at=now,
            is_active=True,
            created_at=now,
            metadata=payload.metadata or {},
        )

        saved = self.repository.save_assignment(record)

        # If assigned as lead auditor, update audit lead_auditor_id
        if record.auditor_role == AuditorRole.LEAD_AUDITOR:
            audit.lead_auditor_id = record.auditor_id
            self.repository.save_audit(audit)

        return saved

    def review_independence(
        self,
        user: AuthenticatedUserContext,
        assignment_id: str,
        payload: IndependenceReviewRequest,
    ) -> AuditorAssignmentRecord:
        """Review and confirm auditor independence or approve mitigations.
        
        Enforces separation of duties: auditors cannot review their own independence.
        """
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can review auditor independence.",
                status_code=403,
            )

        assignment = self.repository.get_assignment(assignment_id)
        if not assignment:
            raise AppException(
                code=ErrorCode.AUDITOR_ASSIGNMENT_NOT_FOUND,
                message=f"Auditor assignment {assignment_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(assignment.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot review independence across tenant boundaries.",
                status_code=403,
            )

        # Enforce separation of duties: cannot review one's own independence
        if user.user_id == assignment.auditor_id:
            raise AppException(
                code=ErrorCode.AUDITOR_INDEPENDENCE_CONFLICT,
                message="Auditors cannot review or verify their own independence.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        assignment.independence_status = payload.independence_status
        assignment.independence_reviewed_by = user.user_id
        assignment.independence_reviewed_at = now
        assignment.independence_review_rationale = payload.review_rationale
        if payload.conflict_mitigation:
            assignment.conflict_mitigation = payload.conflict_mitigation

        return self.repository.save_assignment(assignment)

    def list_assignments(
        self, user: AuthenticatedUserContext, audit_id: str
    ) -> List[AuditorAssignmentRecord]:
        """List active auditor assignments for an audit within tenant scope."""
        audit = self.repository.get_audit(audit_id)
        if not audit:
            raise AppException(
                code=ErrorCode.AUDIT_NOT_FOUND,
                message=f"Audit {audit_id} not found.",
                status_code=404,
            )
        if audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot list assignments across tenant boundaries.",
                status_code=403,
            )

        return self.repository.list_assignments_for_audit(audit_id)

    def get_assignment(
        self, user: AuthenticatedUserContext, assignment_id: str
    ) -> AuditorAssignmentRecord:
        """Get an auditor assignment ensuring tenant boundary isolation."""
        assignment = self.repository.get_assignment(assignment_id)
        if not assignment:
            raise AppException(
                code=ErrorCode.AUDITOR_ASSIGNMENT_NOT_FOUND,
                message=f"Auditor assignment {assignment_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(assignment.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access assignment across tenant boundaries.",
                status_code=403,
            )
        return assignment


# Global singleton
_global_independence_service = AuditorIndependenceService()


def get_auditor_independence_service() -> AuditorIndependenceService:
    """Dependency provider for auditor independence service."""
    return _global_independence_service

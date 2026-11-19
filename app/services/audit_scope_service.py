"""Phase 70: Audit Scope Management Service.

Coordinates:
- Definition and formal approval of audit scopes
- Scope freezing upon audit initiation
- Controlled amendment workflow preventing silent scope overwrites
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_scope_planning import (
    AmendAuditScopeRequest,
    ApproveAuditScopeRequest,
    AuditScopeRecord,
    AuditScopeStatus,
    DefineAuditScopeRequest,
)
from app.schemas.user import AuthenticatedUserContext


class AuditScopeService:
    """Service managing audit scope definitions, approvals, freezing, and amendments."""

    def __init__(self, repository: Optional[GovernanceAuditRepository] = None) -> None:
        self.repository = repository or get_governance_audit_repository()

    def define_scope(
        self, user: AuthenticatedUserContext, audit_id: str, payload: DefineAuditScopeRequest
    ) -> AuditScopeRecord:
        """Establish or update a draft audit scope before approval."""
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
                message="Cannot access audit across tenant boundaries.",
                status_code=403,
            )

        existing = self.repository.get_scope_for_audit(audit_id)
        if existing and existing.is_frozen:
            raise AppException(
                code=ErrorCode.SCOPE_FROZEN_MODIFICATION_FORBIDDEN,
                message="Audit scope is frozen. Use the formal amendment workflow to propose scope changes.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        scope = existing or AuditScopeRecord(audit_id=audit_id)
        scope.included_governance_processes = payload.included_governance_processes or []
        scope.included_safety_controls = payload.included_safety_controls or []
        scope.included_compliance_requirements = payload.included_compliance_requirements or []
        scope.included_workflow_phases = payload.included_workflow_phases or []
        scope.included_facilities = payload.included_facilities or []
        scope.evaluation_period_start = payload.evaluation_period_start
        scope.evaluation_period_end = payload.evaluation_period_end
        scope.scope_limitations = payload.scope_limitations or []
        scope.scope_exclusions = payload.scope_exclusions or []
        scope.status = AuditScopeStatus.DRAFT
        scope.updated_at = now
        scope.metadata = payload.metadata or {}

        saved = self.repository.save_scope(scope)
        audit.scope_id = saved.scope_id
        self.repository.save_audit(audit)
        return saved

    def get_scope(
        self, user: AuthenticatedUserContext, audit_id: str
    ) -> AuditScopeRecord:
        """Retrieve the current audit scope."""
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
                message="Cannot access audit across tenant boundaries.",
                status_code=403,
            )

        scope = self.repository.get_scope_for_audit(audit_id)
        if not scope:
            raise AppException(
                code=ErrorCode.AUDIT_SCOPE_NOT_FOUND,
                message=f"Audit scope not yet defined for audit {audit_id}.",
                status_code=404,
            )
        return scope

    def approve_scope(
        self, user: AuthenticatedUserContext, audit_id: str, payload: ApproveAuditScopeRequest
    ) -> AuditScopeRecord:
        """Approve an audit scope prior to audit execution."""
        scope = self.get_scope(user, audit_id)

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only governance leads or administrators can approve audit scopes.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        scope.status = AuditScopeStatus.APPROVED
        scope.approved_by = user.user_id
        scope.approved_at = now
        scope.metadata["approval_rationale"] = payload.approval_rationale
        return self.repository.save_scope(scope)

    def amend_scope(
        self, user: AuthenticatedUserContext, audit_id: str, payload: AmendAuditScopeRequest
    ) -> AuditScopeRecord:
        """Formally amend an approved or frozen scope with traceable change history."""
        scope = self.get_scope(user, audit_id)

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only governance leads or administrators can amend approved audit scopes.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        change_entry = {
            "version_before": scope.version,
            "version_after": scope.version + 1,
            "change_justification": payload.change_justification,
            "amended_by": user.user_id,
            "amended_at": now.isoformat(),
        }

        if payload.amended_processes is not None:
            scope.included_governance_processes = payload.amended_processes
        if payload.amended_requirements is not None:
            scope.included_compliance_requirements = payload.amended_requirements
        if payload.amended_controls is not None:
            scope.included_safety_controls = payload.amended_controls
        if payload.amended_exclusions is not None:
            scope.scope_exclusions = payload.amended_exclusions

        scope.version += 1
        scope.status = AuditScopeStatus.AMENDED
        scope.change_history.append(change_entry)
        scope.updated_at = now

        return self.repository.save_scope(scope)


# Global singleton
_global_scope_service = AuditScopeService()


def get_audit_scope_service() -> AuditScopeService:
    """Dependency provider for audit scope service."""
    return _global_scope_service

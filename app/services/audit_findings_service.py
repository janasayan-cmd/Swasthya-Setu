"""Phase 70: Audit Findings & Auditee Response Service.

Coordinates:
- Recording audit observations and findings (CONTROL_GAP, PROCESS_DEVIATION, etc.)
- Confirmation of findings by lead auditor / governance authority
- Dispute handling and auditee response submissions
- Linking confirmed findings to authoritative Phase 54 corrective action orchestration
  and Phase 55 effectiveness evaluation
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_finding_response import (
    AuditeeResponseRecord,
    AuditeeResponseType,
    AuditFindingCategory,
    AuditFindingRecord,
    AuditFindingSeverity,
    AuditFindingStatus,
    ConfirmAuditFindingRequest,
    CreateAuditFindingRequest,
    DisputeAuditFindingRequest,
    LinkCorrectiveActionRequest,
    ReviewAuditeeResponseRequest,
    SubmitAuditeeResponseRequest,
)
from app.schemas.audit_scope_planning import AuditLifecycleStatus
from app.schemas.user import AuthenticatedUserContext


class AuditFindingsService:
    """Service governing audit findings, disputes, auditee responses, and remediation links."""

    def __init__(self, repository: Optional[GovernanceAuditRepository] = None) -> None:
        self.repository = repository or get_governance_audit_repository()

    # -------------------------------------------------------------------------
    # Findings
    # -------------------------------------------------------------------------

    def create_finding(
        self,
        user: AuthenticatedUserContext,
        audit_id: str,
        payload: CreateAuditFindingRequest,
    ) -> AuditFindingRecord:
        """Record an audit finding or observation."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create audit findings.",
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
                message="Cannot record finding across tenant boundaries.",
                status_code=403,
            )
        if audit.lifecycle_status in {AuditLifecycleStatus.CLOSED, AuditLifecycleStatus.CANCELLED}:
            raise AppException(
                code=ErrorCode.INVALID_AUDIT_STATE,
                message="Cannot add findings to closed or cancelled audits.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        record = AuditFindingRecord(
            audit_id=audit_id,
            criterion_id=payload.criterion_id,
            test_id=payload.test_id,
            category=payload.category,
            severity=payload.severity,
            status=AuditFindingStatus.UNDER_REVIEW,
            finding_statement=payload.finding_statement,
            observed_condition=payload.observed_condition,
            expected_condition=payload.expected_condition,
            gap_description=payload.gap_description,
            potential_impact=payload.potential_impact,
            evidence_refs=payload.evidence_refs or [],
            responsible_owner_id=payload.responsible_owner_id,
            responsible_owner_role=payload.responsible_owner_role,
            created_by=user.user_id,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_finding(record)

    def get_finding(
        self, user: AuthenticatedUserContext, finding_id: str
    ) -> AuditFindingRecord:
        """Retrieve a finding ensuring tenant boundary isolation."""
        finding = self.repository.get_finding(finding_id)
        if not finding:
            raise AppException(
                code=ErrorCode.AUDIT_FINDING_NOT_FOUND,
                message=f"Audit finding {finding_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(finding.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access finding across tenant boundaries.",
                status_code=403,
            )
        return finding

    def confirm_finding(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: ConfirmAuditFindingRequest,
    ) -> AuditFindingRecord:
        """Formally confirm an audit finding (lead auditor or governance authority)."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can confirm audit findings.",
                status_code=403,
            )

        finding = self.get_finding(user, finding_id)
        now = datetime.now(timezone.utc)
        finding.is_confirmed = True
        finding.confirmed_by = user.user_id
        finding.confirmed_at = now
        finding.status = AuditFindingStatus.CONFIRMED
        finding.metadata["confirmation_rationale"] = payload.confirmation_rationale
        return self.repository.save_finding(finding)

    def dispute_finding(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: DisputeAuditFindingRequest,
    ) -> AuditFindingRecord:
        """Auditee or responsible owner disputes an audit finding."""
        finding = self.get_finding(user, finding_id)
        finding.is_disputed = True
        finding.dispute_rationale = payload.dispute_rationale
        finding.status = AuditFindingStatus.DISPUTED
        if payload.supporting_evidence_refs:
            finding.evidence_refs.extend(payload.supporting_evidence_refs)
        return self.repository.save_finding(finding)

    def list_findings(
        self,
        user: AuthenticatedUserContext,
        audit_id: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        is_confirmed: Optional[bool] = None,
        is_closed: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditFindingRecord]:
        """List findings within tenant scope."""
        if audit_id:
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
                    message="Cannot list findings across tenant boundaries.",
                    status_code=403,
                )

        return self.repository.list_findings_for_audit(
            audit_id=audit_id,
            category=category,
            severity=severity,
            is_confirmed=is_confirmed,
            is_closed=is_closed,
            limit=limit,
            offset=offset,
        )

    # -------------------------------------------------------------------------
    # Auditee Responses
    # -------------------------------------------------------------------------

    def submit_auditee_response(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: SubmitAuditeeResponseRequest,
    ) -> AuditeeResponseRecord:
        """Submit an auditee response to a finding."""
        finding = self.get_finding(user, finding_id)
        now = datetime.now(timezone.utc)

        response = AuditeeResponseRecord(
            finding_id=finding_id,
            auditee_id=user.user_id,
            auditee_role=user.role.value,
            response_type=payload.response_type,
            response_statement=payload.response_statement,
            explanation=payload.explanation,
            supporting_evidence_refs=payload.supporting_evidence_refs or [],
            proposed_corrective_action=payload.proposed_corrective_action,
            proposed_completion_date=payload.proposed_completion_date,
            submitted_at=now,
            created_at=now,
            metadata=payload.metadata or {},
        )

        saved = self.repository.save_response(response)

        # Update finding status based on response type
        if payload.response_type == AuditeeResponseType.ACCEPTED:
            finding.status = AuditFindingStatus.ACTION_REQUIRED
        elif payload.response_type == AuditeeResponseType.DISPUTED:
            finding.status = AuditFindingStatus.DISPUTED
            finding.is_disputed = True
            finding.dispute_rationale = payload.explanation or payload.response_statement
        self.repository.save_finding(finding)

        return saved

    def review_auditee_response(
        self,
        user: AuthenticatedUserContext,
        response_id: str,
        payload: ReviewAuditeeResponseRequest,
    ) -> AuditeeResponseRecord:
        """Auditor evaluates auditee response and proposed action plan."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only auditor or governance roles can review auditee responses.",
                status_code=403,
            )

        resp = self.repository.get_response(response_id)
        if not resp:
            raise AppException(
                code=ErrorCode.AUDITEE_RESPONSE_NOT_FOUND,
                message=f"Auditee response {response_id} not found.",
                status_code=404,
            )

        # Enforce separation of duties: auditee cannot review their own response
        if user.user_id == resp.auditee_id:
            raise AppException(
                code=ErrorCode.AUDITOR_INDEPENDENCE_CONFLICT,
                message="Auditees cannot review their own response.",
                status_code=400,
            )

        finding = self.get_finding(user, resp.finding_id)

        now = datetime.now(timezone.utc)
        resp.auditor_review_decision = payload.decision.upper()
        resp.auditor_review_comments = payload.review_comments
        resp.reviewed_by = user.user_id
        resp.reviewed_at = now

        if resp.auditor_review_decision == "ACCEPTED":
            finding.status = AuditFindingStatus.ACTION_REQUIRED
            self.repository.save_finding(finding)

        return self.repository.save_response(resp)

    def list_responses(
        self, user: AuthenticatedUserContext, finding_id: str
    ) -> List[AuditeeResponseRecord]:
        """List responses for a finding within tenant scope."""
        self.get_finding(user, finding_id)
        return self.repository.list_responses_for_finding(finding_id)

    # -------------------------------------------------------------------------
    # Corrective Action Referral
    # -------------------------------------------------------------------------

    def link_corrective_action(
        self,
        user: AuthenticatedUserContext,
        finding_id: str,
        payload: LinkCorrectiveActionRequest,
    ) -> AuditFindingRecord:
        """Link an authoritative Phase 54 corrective action and Phase 55 evaluation.
        
        Important: Phase 70 does not duplicate or independently manage CAPA closures;
        it coordinates referral and follow-up tracking against authoritative Phase 54 records.
        """
        finding = self.get_finding(user, finding_id)

        if not payload.phase54_action_ref:
            raise AppException(
                code=ErrorCode.CORRECTIVE_ACTION_REFERRAL_FAILED,
                message="Valid Phase 54 corrective action reference is required for referral.",
                status_code=400,
            )

        finding.corrective_action_ref = payload.phase54_action_ref
        finding.phase55_eval_ref = payload.phase55_eval_ref
        finding.status = AuditFindingStatus.FOLLOW_UP_PENDING
        if payload.notes:
            finding.metadata["remediation_notes"] = payload.notes

        return self.repository.save_finding(finding)


# Global singleton
_global_findings_service = AuditFindingsService()


def get_audit_findings_service() -> AuditFindingsService:
    """Dependency provider for audit findings service."""
    return _global_findings_service

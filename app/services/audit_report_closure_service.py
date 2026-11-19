"""Phase 70: Audit Report, Review, Closure & Follow-Up Service.

Coordinates:
- Compilation and generation of independent clinical safety audit reports
- Peer/technical review workflows
- Independent governance approval with strict separation of duties (author cannot self-approve)
- Governed audit closure requiring an approved report
- Post-closure follow-up and controlled audit reopening
- Aggregated governance reports (summary, findings, overdue, follow-up status)
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_execution import AuditTestOutcome, EvidenceRequestStatus
from app.schemas.audit_finding_response import AuditFindingStatus
from app.schemas.audit_report_closure import (
    ApproveAuditReportRequest,
    AuditConclusion,
    AuditFindingsReportResponse,
    AuditFollowUpStatusResponse,
    AuditOverdueReportResponse,
    AuditReportRecord,
    AuditReportStatus,
    AuditSummaryReportResponse,
    CloseAuditRequest,
    GenerateAuditReportRequest,
    ReopenAuditRequest,
    ReviewAuditReportRequest,
)
from app.schemas.audit_scope_planning import (
    AuditLifecycleStatus,
    ClinicalSafetyAuditRecord,
)
from app.schemas.user import AuthenticatedUserContext


class AuditReportClosureService:
    """Service governing audit report generation, review, approval, and lifecycle closure."""

    def __init__(self, repository: Optional[GovernanceAuditRepository] = None) -> None:
        self.repository = repository or get_governance_audit_repository()

    # -------------------------------------------------------------------------
    # Report Generation & Review
    # -------------------------------------------------------------------------

    def generate_report(
        self,
        user: AuthenticatedUserContext,
        audit_id: str,
        payload: GenerateAuditReportRequest,
    ) -> AuditReportRecord:
        """Compile test results, findings, and auditor observations into a formal audit report."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot generate audit reports.",
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
                message="Cannot generate report across tenant boundaries.",
                status_code=403,
            )

        # Aggregate test metrics
        tests = self.repository.list_tests_for_audit(audit_id)
        tests_count = len(tests)
        passed_count = sum(1 for t in tests if t.outcome == AuditTestOutcome.PASSED)
        failed_count = sum(1 for t in tests if t.outcome == AuditTestOutcome.FAILED)
        inconclusive_count = sum(
            1 for t in tests if t.outcome in {AuditTestOutcome.INCONCLUSIVE, AuditTestOutcome.PARTIALLY_PASSED}
        )

        # Aggregate findings metrics
        findings = self.repository.list_findings_for_audit(audit_id=audit_id)
        findings_by_severity: Dict[str, int] = {}
        for f in findings:
            sev = f.severity.value
            findings_by_severity[sev] = findings_by_severity.get(sev, 0) + 1

        confirmed_ids = [f.finding_id for f in findings if f.is_confirmed]
        disputed_ids = [f.finding_id for f in findings if f.is_disputed]
        action_refs = [f.corrective_action_ref for f in findings if f.corrective_action_ref]

        # Auditor assignments summary
        assignments = self.repository.list_assignments_for_audit(audit_id)
        assignments_summary = [
            {"auditor_id": a.auditor_id, "role": a.auditor_role.value, "status": a.independence_status.value}
            for a in assignments
        ]

        # Scope summary
        scope = self.repository.get_scope_for_audit(audit_id)
        scope_summary_text = (
            f"Scope v{scope.version}: {len(scope.included_governance_processes)} processes, "
            f"{len(scope.included_safety_controls)} controls, {len(scope.included_compliance_requirements)} requirements."
            if scope
            else "Standard governed scope."
        )
        scope_limitations = scope.scope_limitations if scope else []

        now = datetime.now(timezone.utc)
        report = AuditReportRecord(
            audit_id=audit_id,
            version=1,
            status=AuditReportStatus.DRAFT,
            title=payload.title,
            executive_summary=payload.executive_summary,
            audit_period_start=audit.planned_start_date or audit.actual_start_date,
            audit_period_end=audit.planned_end_date,
            scope_summary=scope_summary_text,
            scope_limitations=scope_limitations,
            auditor_assignments_summary=assignments_summary,
            independence_status_summary="VERIFIED",
            tests_performed_count=tests_count,
            tests_passed_count=passed_count,
            tests_failed_count=failed_count,
            tests_inconclusive_count=inconclusive_count,
            findings_summary=findings_by_severity,
            confirmed_finding_ids=confirmed_ids,
            disputed_finding_ids=disputed_ids,
            corrective_action_refs=action_refs,
            audit_conclusion=payload.audit_conclusion,
            recommendations=payload.recommendations or [],
            created_by=user.user_id,
            created_at=now,
            metadata=payload.metadata or {},
        )

        saved = self.repository.save_report(report)

        # Progress audit lifecycle
        audit.lifecycle_status = AuditLifecycleStatus.REPORT_DRAFT
        self.repository.save_audit(audit)

        return saved

    def get_report(
        self, user: AuthenticatedUserContext, report_id: str
    ) -> AuditReportRecord:
        """Retrieve an audit report ensuring tenant isolation."""
        report = self.repository.get_report(report_id)
        if not report:
            raise AppException(
                code=ErrorCode.AUDIT_REPORT_NOT_FOUND,
                message=f"Audit report {report_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(report.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access report across tenant boundaries.",
                status_code=403,
            )
        return report

    def review_report(
        self,
        user: AuthenticatedUserContext,
        report_id: str,
        payload: ReviewAuditReportRequest,
    ) -> AuditReportRecord:
        """Technical or peer review of an audit report."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can review audit reports.",
                status_code=403,
            )

        report = self.get_report(user, report_id)
        now = datetime.now(timezone.utc)

        report.reviewed_by = user.user_id
        report.reviewed_at = now
        report.review_comments = payload.review_comments

        if payload.requires_revision:
            report.status = AuditReportStatus.DRAFT
        else:
            report.status = AuditReportStatus.PENDING_REVIEW

        return self.repository.save_report(report)

    def approve_report(
        self,
        user: AuthenticatedUserContext,
        report_id: str,
        payload: ApproveAuditReportRequest,
    ) -> AuditReportRecord:
        """Governance approval for an audit report.
        
        Enforces strict separation of duties: the author/creator of the report
        cannot approve their own report.
        """
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can approve audit reports.",
                status_code=403,
            )

        report = self.get_report(user, report_id)

        # Enforce separation of duties
        if user.user_id == report.created_by:
            raise AppException(
                code=ErrorCode.REPORT_SELF_APPROVAL_FORBIDDEN,
                message="Report author cannot approve their own audit report. Independent governance sign-off is required.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        report.status = AuditReportStatus.APPROVED
        report.approved_by = user.user_id
        report.approved_at = now
        report.approval_policy_ref = payload.approval_policy_ref
        if payload.approval_comments:
            report.metadata["approval_comments"] = payload.approval_comments

        saved = self.repository.save_report(report)

        # Update audit lifecycle status
        audit = self.repository.get_audit(report.audit_id)
        if audit:
            audit.lifecycle_status = AuditLifecycleStatus.REPORT_APPROVED
            self.repository.save_audit(audit)

        return saved

    # -------------------------------------------------------------------------
    # Audit Closure & Reopening
    # -------------------------------------------------------------------------

    def close_audit(
        self,
        user: AuthenticatedUserContext,
        audit_id: str,
        payload: CloseAuditRequest,
    ) -> ClinicalSafetyAuditRecord:
        """Formally close an audit. Requires an approved audit report."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can close audits.",
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
                message="Cannot close audit across tenant boundaries.",
                status_code=403,
            )

        # Verify an approved report exists
        reports = self.repository.list_reports_for_audit(audit_id)
        has_approved_report = any(r.status == AuditReportStatus.APPROVED for r in reports)
        if not has_approved_report:
            raise AppException(
                code=ErrorCode.AUDIT_CLOSURE_CONDITIONS_UNMET,
                message="Audit cannot be closed without an approved audit report.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        audit.actual_end_date = now
        audit.closure_rationale = payload.closure_rationale

        if payload.follow_up_required:
            audit.lifecycle_status = AuditLifecycleStatus.FOLLOW_UP_REQUIRED
        else:
            audit.lifecycle_status = AuditLifecycleStatus.CLOSED

        return self.repository.save_audit(audit)

    def reopen_audit(
        self,
        user: AuthenticatedUserContext,
        audit_id: str,
        payload: ReopenAuditRequest,
    ) -> ClinicalSafetyAuditRecord:
        """Controlled reopening of a closed or follow-up audit following new safety signals."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can reopen audits.",
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
                message="Cannot reopen audit across tenant boundaries.",
                status_code=403,
            )

        if audit.lifecycle_status not in {
            AuditLifecycleStatus.CLOSED,
            AuditLifecycleStatus.FOLLOW_UP_REQUIRED,
        }:
            raise AppException(
                code=ErrorCode.INVALID_AUDIT_STATE,
                message=f"Only closed or follow-up-required audits can be reopened; current state: {audit.lifecycle_status.value}.",
                status_code=400,
            )

        audit.lifecycle_status = AuditLifecycleStatus.IN_PROGRESS
        audit.metadata["reopened_at"] = datetime.now(timezone.utc).isoformat()
        audit.metadata["reopened_by"] = user.user_id
        audit.metadata["reopening_reason"] = payload.reopening_reason
        if payload.source_trigger_ref:
            audit.metadata["source_trigger_ref"] = payload.source_trigger_ref

        return self.repository.save_audit(audit)

    # -------------------------------------------------------------------------
    # Aggregated Management Reporting
    # -------------------------------------------------------------------------

    def generate_summary_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> AuditSummaryReportResponse:
        """High-level summary of audit programmes, audits, and completion rates."""
        programmes = self.repository.list_programmes(
            organization_id=user.organization_id, facility_id=facility_id
        )
        audits = self.repository.list_audits(
            organization_id=user.organization_id
        )
        if facility_id:
            audits = [a for a in audits if a.facility_id == facility_id]

        in_progress = sum(1 for a in audits if a.lifecycle_status == AuditLifecycleStatus.IN_PROGRESS)
        closed = sum(1 for a in audits if a.lifecycle_status == AuditLifecycleStatus.CLOSED)
        now = datetime.now(timezone.utc)
        overdue = sum(
            1
            for a in audits
            if a.planned_end_date
            and a.planned_end_date < now
            and a.lifecycle_status not in {AuditLifecycleStatus.CLOSED, AuditLifecycleStatus.CANCELLED}
        )

        return AuditSummaryReportResponse(
            organization_id=user.organization_id,
            facility_id=facility_id,
            total_programmes=len(programmes),
            total_audits=len(audits),
            audits_in_progress=in_progress,
            audits_closed=closed,
            audits_overdue=overdue,
            generated_at=now,
        )

    def generate_findings_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> AuditFindingsReportResponse:
        """Aggregated findings report across tenant audits."""
        findings = self.repository.list_findings_for_audit()
        # Filter findings belonging to user's tenant
        tenant_findings = []
        for f in findings:
            audit = self.repository.get_audit(f.audit_id)
            if (
                audit
                and audit.organization_id == user.organization_id
                and (facility_id is None or audit.facility_id == facility_id)
            ):
                tenant_findings.append(f)

        by_severity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        for f in tenant_findings:
            sev = f.severity.value
            cat = f.category.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_category[cat] = by_category.get(cat, 0) + 1

        now = datetime.now(timezone.utc)
        return AuditFindingsReportResponse(
            organization_id=user.organization_id,
            facility_id=facility_id,
            total_findings=len(tenant_findings),
            confirmed_findings=sum(1 for f in tenant_findings if f.is_confirmed),
            disputed_findings=sum(1 for f in tenant_findings if f.is_disputed),
            open_findings=sum(1 for f in tenant_findings if not f.is_closed),
            closed_findings=sum(1 for f in tenant_findings if f.is_closed),
            findings_by_severity=by_severity,
            findings_by_category=by_category,
            generated_at=now,
        )

    def generate_overdue_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> AuditOverdueReportResponse:
        """Report on overdue audits, evidence requests, and finding responses."""
        now = datetime.now(timezone.utc)
        audits = self.repository.list_audits(organization_id=user.organization_id)
        if facility_id:
            audits = [a for a in audits if a.facility_id == facility_id]

        overdue_audits = sum(
            1
            for a in audits
            if a.planned_end_date
            and a.planned_end_date < now
            and a.lifecycle_status not in {AuditLifecycleStatus.CLOSED, AuditLifecycleStatus.CANCELLED}
        )

        # Overdue evidence requests
        overdue_ev_count = 0
        for a in audits:
            reqs = self.repository.list_evidence_requests_for_audit(a.audit_id)
            for r in reqs:
                if (
                    r.due_date
                    and r.due_date < now
                    and r.status not in {EvidenceRequestStatus.ACCEPTED, EvidenceRequestStatus.CANCELLED}
                ):
                    overdue_ev_count += 1

        # Overdue finding responses (findings confirmed with no responses)
        overdue_responses_count = 0
        for a in audits:
            findings = self.repository.list_findings_for_audit(audit_id=a.audit_id, is_confirmed=True)
            for f in findings:
                resps = self.repository.list_responses_for_finding(f.finding_id)
                if not resps and not f.is_closed:
                    overdue_responses_count += 1

        return AuditOverdueReportResponse(
            organization_id=user.organization_id,
            facility_id=facility_id,
            overdue_audits_count=overdue_audits,
            overdue_evidence_requests_count=overdue_ev_count,
            overdue_finding_responses_count=overdue_responses_count,
            generated_at=now,
        )

    def generate_follow_up_status(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> AuditFollowUpStatusResponse:
        """Report on follow-up required audits and linked corrective action activity."""
        audits = self.repository.list_audits(organization_id=user.organization_id)
        if facility_id:
            audits = [a for a in audits if a.facility_id == facility_id]

        follow_up_audits = sum(
            1 for a in audits if a.lifecycle_status == AuditLifecycleStatus.FOLLOW_UP_REQUIRED
        )
        reopened = sum(
            1 for a in audits if "reopened_at" in a.metadata
        )

        active_capa_links = 0
        for a in audits:
            findings = self.repository.list_findings_for_audit(audit_id=a.audit_id)
            for f in findings:
                if f.corrective_action_ref and not f.is_closed:
                    active_capa_links += 1

        now = datetime.now(timezone.utc)
        return AuditFollowUpStatusResponse(
            organization_id=user.organization_id,
            facility_id=facility_id,
            audits_requiring_follow_up=follow_up_audits,
            active_corrective_action_links=active_capa_links,
            reopened_audits_count=reopened,
            generated_at=now,
        )


# Global singleton
_global_report_service = AuditReportClosureService()


def get_audit_report_closure_service() -> AuditReportClosureService:
    """Dependency provider for audit report closure service."""
    return _global_report_service

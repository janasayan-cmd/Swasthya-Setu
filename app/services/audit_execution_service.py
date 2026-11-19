"""Phase 70: Audit Execution Service.

Coordinates:
- Definition and tracking of audit criteria mapped to Phase 69 controls
- Evidence request lifecycle: request, auditee submission, and auditor review
- Audit test procedures, sampling, execution observations, and supervisory review
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_execution import (
    AuditCriterionRecord,
    AuditEvidenceRequestRecord,
    AuditTestOutcome,
    AuditTestRecord,
    CreateAuditCriterionRequest,
    CreateAuditTestRequest,
    CreateEvidenceRequest,
    EvidenceRequestStatus,
    ExecuteAuditTestRequest,
    ReviewAuditTestRequest,
    ReviewEvidenceRequest,
    SubmitEvidenceRequest,
)
from app.schemas.audit_scope_planning import AuditLifecycleStatus
from app.schemas.user import AuthenticatedUserContext


class AuditExecutionService:
    """Service governing audit criteria, evidence requests, and test executions."""

    def __init__(self, repository: Optional[GovernanceAuditRepository] = None) -> None:
        self.repository = repository or get_governance_audit_repository()

    # -------------------------------------------------------------------------
    # Criteria
    # -------------------------------------------------------------------------

    def create_criterion(
        self,
        user: AuthenticatedUserContext,
        audit_id: str,
        payload: CreateAuditCriterionRequest,
    ) -> AuditCriterionRecord:
        """Establish a verifiable audit criterion mapped to compliance requirements."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create audit criteria.",
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
                message="Cannot create criterion across tenant boundaries.",
                status_code=403,
            )
        if audit.lifecycle_status in {AuditLifecycleStatus.CLOSED, AuditLifecycleStatus.CANCELLED}:
            raise AppException(
                code=ErrorCode.INVALID_AUDIT_STATE,
                message="Cannot add criteria to a closed or cancelled audit.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        record = AuditCriterionRecord(
            audit_id=audit_id,
            criterion_code=payload.criterion_code,
            title=payload.title,
            description=payload.description,
            source_framework_id=payload.source_framework_id,
            source_requirement_id=payload.source_requirement_id,
            source_control_id=payload.source_control_id,
            expected_evidence_description=payload.expected_evidence_description,
            sampling_strategy=payload.sampling_strategy,
            is_active=True,
            created_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_criterion(record)

    def list_criteria(
        self, user: AuthenticatedUserContext, audit_id: str
    ) -> List[AuditCriterionRecord]:
        """List active criteria for an audit within tenant scope."""
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
                message="Cannot list criteria across tenant boundaries.",
                status_code=403,
            )
        return self.repository.list_criteria_for_audit(audit_id)

    # -------------------------------------------------------------------------
    # Evidence Requests
    # -------------------------------------------------------------------------

    def create_evidence_request(
        self,
        user: AuthenticatedUserContext,
        audit_id: str,
        payload: CreateEvidenceRequest,
    ) -> AuditEvidenceRequestRecord:
        """Issue an evidence request to an auditee."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create evidence requests.",
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
                message="Cannot create evidence request across tenant boundaries.",
                status_code=403,
            )
        if audit.lifecycle_status in {AuditLifecycleStatus.CLOSED, AuditLifecycleStatus.CANCELLED}:
            raise AppException(
                code=ErrorCode.INVALID_AUDIT_STATE,
                message="Cannot request evidence for closed or cancelled audits.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        record = AuditEvidenceRequestRecord(
            audit_id=audit_id,
            criterion_id=payload.criterion_id,
            description=payload.description,
            responsible_auditee_id=payload.responsible_auditee_id,
            responsible_auditee_role=payload.responsible_auditee_role,
            requested_by=user.user_id,
            requested_at=now,
            due_date=payload.due_date,
            status=EvidenceRequestStatus.REQUESTED,
            created_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_evidence_request(record)

    def submit_evidence(
        self,
        user: AuthenticatedUserContext,
        request_id: str,
        payload: SubmitEvidenceRequest,
    ) -> AuditEvidenceRequestRecord:
        """Submit requested evidence files or Phase 69 evidence references."""
        req = self.repository.get_evidence_request(request_id)
        if not req:
            raise AppException(
                code=ErrorCode.EVIDENCE_REQUEST_NOT_FOUND,
                message=f"Evidence request {request_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(req.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot submit evidence across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        req.submitted_evidence_refs = payload.submitted_evidence_refs
        req.auditee_notes = payload.auditee_notes
        req.submission_timestamp = now
        req.status = EvidenceRequestStatus.SUBMITTED
        return self.repository.save_evidence_request(req)

    def review_evidence(
        self,
        user: AuthenticatedUserContext,
        request_id: str,
        payload: ReviewEvidenceRequest,
    ) -> AuditEvidenceRequestRecord:
        """Auditor evaluates submitted evidence."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only auditor or governance roles can review submitted evidence.",
                status_code=403,
            )

        req = self.repository.get_evidence_request(request_id)
        if not req:
            raise AppException(
                code=ErrorCode.EVIDENCE_REQUEST_NOT_FOUND,
                message=f"Evidence request {request_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(req.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot review evidence across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        req.review_outcome = payload.review_outcome.upper()
        req.review_comments = payload.review_comments
        req.reviewed_by = user.user_id
        req.reviewed_at = now

        if req.review_outcome == "ACCEPTED":
            req.status = EvidenceRequestStatus.ACCEPTED
        elif req.review_outcome == "PARTIALLY_ACCEPTED":
            req.status = EvidenceRequestStatus.PARTIALLY_ACCEPTED
        else:
            req.status = EvidenceRequestStatus.REJECTED

        return self.repository.save_evidence_request(req)

    def list_evidence_requests(
        self, user: AuthenticatedUserContext, audit_id: str
    ) -> List[AuditEvidenceRequestRecord]:
        """List evidence requests for an audit within tenant scope."""
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
                message="Cannot list evidence requests across tenant boundaries.",
                status_code=403,
            )
        return self.repository.list_evidence_requests_for_audit(audit_id)

    # -------------------------------------------------------------------------
    # Audit Test Procedures
    # -------------------------------------------------------------------------

    def create_test(
        self,
        user: AuthenticatedUserContext,
        audit_id: str,
        payload: CreateAuditTestRequest,
    ) -> AuditTestRecord:
        """Establish an audit test procedure associated with a criterion."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create audit tests.",
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
                message="Cannot create test across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = AuditTestRecord(
            audit_id=audit_id,
            criterion_id=payload.criterion_id,
            test_procedure=payload.test_procedure,
            sampling_approach=payload.sampling_approach,
            sample_selection_reference=payload.sample_selection_reference,
            outcome=AuditTestOutcome.NOT_STARTED,
            created_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_test(record)

    def execute_test(
        self,
        user: AuthenticatedUserContext,
        test_id: str,
        payload: ExecuteAuditTestRequest,
    ) -> AuditTestRecord:
        """Execute an audit test and record observations and outcome."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot execute audit tests.",
                status_code=403,
            )

        test = self.repository.get_test(test_id)
        if not test:
            raise AppException(
                code=ErrorCode.AUDIT_TEST_NOT_FOUND,
                message=f"Audit test {test_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(test.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot execute test across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        test.outcome = payload.outcome
        test.observations = payload.observations
        test.evidence_refs = payload.evidence_refs or []
        test.auditor_notes = payload.auditor_notes
        test.executed_by = user.user_id
        test.executed_at = now
        return self.repository.save_test(test)

    def review_test(
        self,
        user: AuthenticatedUserContext,
        test_id: str,
        payload: ReviewAuditTestRequest,
    ) -> AuditTestRecord:
        """Lead auditor or peer reviews and validates a test execution."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can review audit tests.",
                status_code=403,
            )

        test = self.repository.get_test(test_id)
        if not test:
            raise AppException(
                code=ErrorCode.AUDIT_TEST_NOT_FOUND,
                message=f"Audit test {test_id} not found.",
                status_code=404,
            )

        audit = self.repository.get_audit(test.audit_id)
        if not audit or audit.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot review test across tenant boundaries.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        test.reviewed_by = user.user_id
        test.reviewed_at = now
        test.metadata["review_comments"] = payload.review_comments
        if payload.confirmed_outcome:
            test.outcome = payload.confirmed_outcome

        return self.repository.save_test(test)

    def list_tests(
        self, user: AuthenticatedUserContext, audit_id: str
    ) -> List[AuditTestRecord]:
        """List tests for an audit within tenant scope."""
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
                message="Cannot list tests across tenant boundaries.",
                status_code=403,
            )
        return self.repository.list_tests_for_audit(audit_id)


# Global singleton
_global_execution_service = AuditExecutionService()


def get_audit_execution_service() -> AuditExecutionService:
    """Dependency provider for audit execution service."""
    return _global_execution_service

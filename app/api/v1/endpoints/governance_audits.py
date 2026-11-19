"""Phase 70: Independent Clinical Safety Governance Audit REST API Endpoints.

Implements endpoints for:
- Clinical safety audit programmes (creation, approval, listing)
- Individual audit lifecycle management (creation, scheduling, pausing, resuming, cancelling, closing, reopening)
- Audit scope definition, approval, freeze, and formal amendment
- Auditor assignments, conflict declarations, and independence verification
- Audit criteria definition mapped to Phase 69 controls
- Audit evidence request lifecycle (request, submission, and review)
- Audit test execution, sampling, observations, and peer/technical review
- Findings management: draft observations, confirmation, disputes, auditee responses, and Phase 54/55 CAPA linkage
- Formal audit report generation, review, and governance approval with separation-of-duties enforcement
- Supervisory queues (review-required, overdue)
- Aggregated governance reports (summary, findings, overdue, follow-up status)

Base Path: /api/v1/governance-audits
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_execution import (
    AuditCriterionRecord,
    AuditEvidenceRequestRecord,
    AuditTestRecord,
    CreateAuditCriterionRequest,
    CreateAuditTestRequest,
    CreateEvidenceRequest,
    ExecuteAuditTestRequest,
    ReviewAuditTestRequest,
    ReviewEvidenceRequest,
    SubmitEvidenceRequest,
)
from app.schemas.audit_finding_response import (
    AuditeeResponseRecord,
    AuditFindingRecord,
    ConfirmAuditFindingRequest,
    CreateAuditFindingRequest,
    DisputeAuditFindingRequest,
    LinkCorrectiveActionRequest,
    ReviewAuditeeResponseRequest,
    SubmitAuditeeResponseRequest,
)
from app.schemas.audit_programme import (
    ApproveAuditProgrammeRequest,
    AuditProgrammeRecord,
    CreateAuditProgrammeRequest,
    UpdateAuditProgrammeRequest,
)
from app.schemas.audit_report_closure import (
    ApproveAuditReportRequest,
    AuditFindingsReportResponse,
    AuditFollowUpStatusResponse,
    AuditOverdueReportResponse,
    AuditReportRecord,
    AuditSummaryReportResponse,
    CloseAuditRequest,
    GenerateAuditReportRequest,
    ReopenAuditRequest,
    ReviewAuditReportRequest,
)
from app.schemas.audit_scope_planning import (
    AmendAuditScopeRequest,
    ApproveAuditScopeRequest,
    AuditScopeRecord,
    CancelAuditRequest,
    ClinicalSafetyAuditRecord,
    CreateAuditRequest,
    DefineAuditScopeRequest,
    PauseAuditRequest,
    ScheduleAuditRequest,
)
from app.schemas.auditor_assignment import (
    AssignAuditorRequest,
    AuditorAssignmentRecord,
    IndependenceReviewRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_execution_service import (
    AuditExecutionService,
    get_audit_execution_service,
)
from app.services.audit_findings_service import (
    AuditFindingsService,
    get_audit_findings_service,
)
from app.services.audit_programme_service import (
    AuditProgrammeService,
    get_audit_programme_service,
)
from app.services.audit_report_closure_service import (
    AuditReportClosureService,
    get_audit_report_closure_service,
)
from app.services.audit_scope_service import (
    AuditScopeService,
    get_audit_scope_service,
)
from app.services.auditor_independence_service import (
    AuditorIndependenceService,
    get_auditor_independence_service,
)

router = APIRouter(
    prefix="/governance-audits",
    tags=["Phase 70 - Independent Clinical Safety Governance Audits"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforce that patient role cannot access audit governance endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access clinical safety governance audit features.",
            status_code=403,
        )


# =============================================================================
# 1. SPECIALIZED QUEUES (Mounted before path parameters)
# =============================================================================

@router.get(
    "/queues/review-required",
    response_model=List[ClinicalSafetyAuditRecord],
    summary="Get audits requiring supervisory or governance review",
)
def get_review_required_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceAuditRepository = Depends(get_governance_audit_repository),
) -> List[ClinicalSafetyAuditRecord]:
    _ensure_not_patient(current_user)
    return repo.list_review_required_queue(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


@router.get(
    "/queues/overdue",
    response_model=List[ClinicalSafetyAuditRecord],
    summary="Get audits past planned end date that remain open",
)
def get_overdue_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceAuditRepository = Depends(get_governance_audit_repository),
) -> List[ClinicalSafetyAuditRecord]:
    _ensure_not_patient(current_user)
    return repo.list_overdue_queue(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


# =============================================================================
# 2. AGGREGATED REPORTING (Mounted before path parameters)
# =============================================================================

@router.get(
    "/reports/summary",
    response_model=AuditSummaryReportResponse,
    summary="Get high-level summary of audit programmes and status",
)
def get_audit_summary_report(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditSummaryReportResponse:
    _ensure_not_patient(current_user)
    return report_service.generate_summary_report(current_user, facility_id=facility_id)


@router.get(
    "/reports/findings",
    response_model=AuditFindingsReportResponse,
    summary="Get aggregated finding statistics by severity and status",
)
def get_audit_findings_report(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditFindingsReportResponse:
    _ensure_not_patient(current_user)
    return report_service.generate_findings_report(current_user, facility_id=facility_id)


@router.get(
    "/reports/overdue",
    response_model=AuditOverdueReportResponse,
    summary="Get overdue tracking report across audits, evidence, and responses",
)
def get_audit_overdue_report(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditOverdueReportResponse:
    _ensure_not_patient(current_user)
    return report_service.generate_overdue_report(current_user, facility_id=facility_id)


@router.get(
    "/reports/follow-up-status",
    response_model=AuditFollowUpStatusResponse,
    summary="Get follow-up and corrective action referral metrics",
)
def get_audit_follow_up_status_report(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditFollowUpStatusResponse:
    _ensure_not_patient(current_user)
    return report_service.generate_follow_up_status(current_user, facility_id=facility_id)


# =============================================================================
# 3. AUDIT PROGRAMMES
# =============================================================================

@router.post(
    "/programmes",
    response_model=AuditProgrammeRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new clinical safety governance audit programme",
)
def create_audit_programme(
    payload: CreateAuditProgrammeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> AuditProgrammeRecord:
    _ensure_not_patient(current_user)
    return programme_service.create_programme(current_user, payload)


@router.get(
    "/programmes",
    response_model=List[AuditProgrammeRecord],
    summary="List audit programmes within tenant scope",
)
def list_audit_programmes(
    facility_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> List[AuditProgrammeRecord]:
    _ensure_not_patient(current_user)
    return programme_service.list_programmes(
        current_user, facility_id=facility_id, status=status_filter, limit=limit, offset=offset
    )


@router.get(
    "/programmes/{programme_id}",
    response_model=AuditProgrammeRecord,
    summary="Get audit programme details",
)
def get_audit_programme(
    programme_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> AuditProgrammeRecord:
    _ensure_not_patient(current_user)
    return programme_service.get_programme(current_user, programme_id)


@router.post(
    "/programmes/{programme_id}/approve",
    response_model=AuditProgrammeRecord,
    summary="Formally approve an audit programme",
)
def approve_audit_programme(
    programme_id: str,
    payload: ApproveAuditProgrammeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> AuditProgrammeRecord:
    _ensure_not_patient(current_user)
    return programme_service.approve_programme(current_user, programme_id, payload)


# =============================================================================
# 4. CLINICAL SAFETY AUDITS LIFECYCLE
# =============================================================================

@router.post(
    "/audits",
    response_model=ClinicalSafetyAuditRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a new clinical safety audit under a programme",
)
def create_clinical_safety_audit(
    payload: CreateAuditRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return programme_service.create_audit(current_user, payload)


@router.get(
    "/audits",
    response_model=List[ClinicalSafetyAuditRecord],
    summary="List clinical safety audits within tenant scope",
)
def list_clinical_safety_audits(
    programme_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> List[ClinicalSafetyAuditRecord]:
    _ensure_not_patient(current_user)
    return programme_service.list_audits(
        current_user, programme_id=programme_id, status=status_filter, limit=limit, offset=offset
    )


@router.get(
    "/audits/{audit_id}",
    response_model=ClinicalSafetyAuditRecord,
    summary="Get clinical safety audit details",
)
def get_clinical_safety_audit(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return programme_service.get_audit(current_user, audit_id)


@router.post(
    "/audits/{audit_id}/schedule",
    response_model=ClinicalSafetyAuditRecord,
    summary="Schedule or initiate execution for an audit",
)
def schedule_clinical_safety_audit(
    audit_id: str,
    payload: ScheduleAuditRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return programme_service.schedule_audit(current_user, audit_id, payload)


@router.post(
    "/audits/{audit_id}/pause",
    response_model=ClinicalSafetyAuditRecord,
    summary="Pause an in-progress audit with documented reason",
)
def pause_clinical_safety_audit(
    audit_id: str,
    payload: PauseAuditRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return programme_service.pause_audit(current_user, audit_id, payload.paused_reason)


@router.post(
    "/audits/{audit_id}/resume",
    response_model=ClinicalSafetyAuditRecord,
    summary="Resume a paused audit",
)
def resume_clinical_safety_audit(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return programme_service.resume_audit(current_user, audit_id)


@router.post(
    "/audits/{audit_id}/cancel",
    response_model=ClinicalSafetyAuditRecord,
    summary="Cancel an audit with documented reason",
)
def cancel_clinical_safety_audit(
    audit_id: str,
    payload: CancelAuditRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    programme_service: AuditProgrammeService = Depends(get_audit_programme_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return programme_service.cancel_audit(current_user, audit_id, payload.cancellation_reason)


@router.post(
    "/audits/{audit_id}/close",
    response_model=ClinicalSafetyAuditRecord,
    summary="Formally close an audit. Requires approved report.",
)
def close_clinical_safety_audit(
    audit_id: str,
    payload: CloseAuditRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return report_service.close_audit(current_user, audit_id, payload)


@router.post(
    "/audits/{audit_id}/reopen",
    response_model=ClinicalSafetyAuditRecord,
    summary="Controlled reopening of a closed audit upon new safety signals",
)
def reopen_clinical_safety_audit(
    audit_id: str,
    payload: ReopenAuditRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> ClinicalSafetyAuditRecord:
    _ensure_not_patient(current_user)
    return report_service.reopen_audit(current_user, audit_id, payload)


# =============================================================================
# 5. AUDIT SCOPE MANAGEMENT
# =============================================================================

@router.post(
    "/audits/{audit_id}/scope",
    response_model=AuditScopeRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Establish or update draft audit scope",
)
def define_audit_scope(
    audit_id: str,
    payload: DefineAuditScopeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    scope_service: AuditScopeService = Depends(get_audit_scope_service),
) -> AuditScopeRecord:
    _ensure_not_patient(current_user)
    return scope_service.define_scope(current_user, audit_id, payload)


@router.get(
    "/audits/{audit_id}/scope",
    response_model=AuditScopeRecord,
    summary="Get current audit scope",
)
def get_audit_scope(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    scope_service: AuditScopeService = Depends(get_audit_scope_service),
) -> AuditScopeRecord:
    _ensure_not_patient(current_user)
    return scope_service.get_scope(current_user, audit_id)


@router.post(
    "/audits/{audit_id}/scope/approve",
    response_model=AuditScopeRecord,
    summary="Approve audit scope prior to execution",
)
def approve_audit_scope(
    audit_id: str,
    payload: ApproveAuditScopeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    scope_service: AuditScopeService = Depends(get_audit_scope_service),
) -> AuditScopeRecord:
    _ensure_not_patient(current_user)
    return scope_service.approve_scope(current_user, audit_id, payload)


@router.post(
    "/audits/{audit_id}/scope/amend",
    response_model=AuditScopeRecord,
    summary="Formally amend an approved or frozen scope with versioning",
)
def amend_audit_scope(
    audit_id: str,
    payload: AmendAuditScopeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    scope_service: AuditScopeService = Depends(get_audit_scope_service),
) -> AuditScopeRecord:
    _ensure_not_patient(current_user)
    return scope_service.amend_scope(current_user, audit_id, payload)


# =============================================================================
# 6. AUDITOR ASSIGNMENT & INDEPENDENCE
# =============================================================================

@router.post(
    "/audits/{audit_id}/assignments",
    response_model=AuditorAssignmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an auditor and record conflict declarations",
)
def assign_auditor(
    audit_id: str,
    payload: AssignAuditorRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    independence_service: AuditorIndependenceService = Depends(get_auditor_independence_service),
) -> AuditorAssignmentRecord:
    _ensure_not_patient(current_user)
    return independence_service.assign_auditor(current_user, audit_id, payload)


@router.get(
    "/audits/{audit_id}/assignments",
    response_model=List[AuditorAssignmentRecord],
    summary="List active auditor assignments for an audit",
)
def list_auditor_assignments(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    independence_service: AuditorIndependenceService = Depends(get_auditor_independence_service),
) -> List[AuditorAssignmentRecord]:
    _ensure_not_patient(current_user)
    return independence_service.list_assignments(current_user, audit_id)


@router.post(
    "/assignments/{assignment_id}/independence-review",
    response_model=AuditorAssignmentRecord,
    summary="Review auditor independence or approve mitigations (self-review forbidden)",
)
def review_auditor_independence(
    assignment_id: str,
    payload: IndependenceReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    independence_service: AuditorIndependenceService = Depends(get_auditor_independence_service),
) -> AuditorAssignmentRecord:
    _ensure_not_patient(current_user)
    return independence_service.review_independence(current_user, assignment_id, payload)


# =============================================================================
# 7. AUDIT CRITERIA
# =============================================================================

@router.post(
    "/audits/{audit_id}/criteria",
    response_model=AuditCriterionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Establish an audit criterion mapped to compliance controls",
)
def create_audit_criterion(
    audit_id: str,
    payload: CreateAuditCriterionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> AuditCriterionRecord:
    _ensure_not_patient(current_user)
    return execution_service.create_criterion(current_user, audit_id, payload)


@router.get(
    "/audits/{audit_id}/criteria",
    response_model=List[AuditCriterionRecord],
    summary="List criteria established for an audit",
)
def list_audit_criteria(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> List[AuditCriterionRecord]:
    _ensure_not_patient(current_user)
    return execution_service.list_criteria(current_user, audit_id)


# =============================================================================
# 8. EVIDENCE REQUESTS
# =============================================================================

@router.post(
    "/audits/{audit_id}/evidence-requests",
    response_model=AuditEvidenceRequestRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Issue an evidence request to an auditee",
)
def create_evidence_request(
    audit_id: str,
    payload: CreateEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> AuditEvidenceRequestRecord:
    _ensure_not_patient(current_user)
    return execution_service.create_evidence_request(current_user, audit_id, payload)


@router.get(
    "/audits/{audit_id}/evidence-requests",
    response_model=List[AuditEvidenceRequestRecord],
    summary="List evidence requests for an audit",
)
def list_evidence_requests(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> List[AuditEvidenceRequestRecord]:
    _ensure_not_patient(current_user)
    return execution_service.list_evidence_requests(current_user, audit_id)


@router.post(
    "/evidence-requests/{request_id}/submit",
    response_model=AuditEvidenceRequestRecord,
    summary="Auditee submits requested evidence references",
)
def submit_audit_evidence(
    request_id: str,
    payload: SubmitEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> AuditEvidenceRequestRecord:
    _ensure_not_patient(current_user)
    return execution_service.submit_evidence(current_user, request_id, payload)


@router.post(
    "/evidence-requests/{request_id}/review",
    response_model=AuditEvidenceRequestRecord,
    summary="Auditor reviews and accepts/rejects submitted evidence",
)
def review_audit_evidence(
    request_id: str,
    payload: ReviewEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> AuditEvidenceRequestRecord:
    _ensure_not_patient(current_user)
    return execution_service.review_evidence(current_user, request_id, payload)


# =============================================================================
# 9. AUDIT TEST PROCEDURES & EXECUTION
# =============================================================================

@router.post(
    "/audits/{audit_id}/tests",
    response_model=AuditTestRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Establish an audit test procedure associated with a criterion",
)
def create_audit_test(
    audit_id: str,
    payload: CreateAuditTestRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> AuditTestRecord:
    _ensure_not_patient(current_user)
    return execution_service.create_test(current_user, audit_id, payload)


@router.get(
    "/audits/{audit_id}/tests",
    response_model=List[AuditTestRecord],
    summary="List tests configured for an audit",
)
def list_audit_tests(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> List[AuditTestRecord]:
    _ensure_not_patient(current_user)
    return execution_service.list_tests(current_user, audit_id)


@router.post(
    "/tests/{test_id}/execute",
    response_model=AuditTestRecord,
    summary="Record test observations and execution outcome",
)
def execute_audit_test(
    test_id: str,
    payload: ExecuteAuditTestRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> AuditTestRecord:
    _ensure_not_patient(current_user)
    return execution_service.execute_test(current_user, test_id, payload)


@router.post(
    "/tests/{test_id}/review",
    response_model=AuditTestRecord,
    summary="Peer or supervisory review of test execution",
)
def review_audit_test(
    test_id: str,
    payload: ReviewAuditTestRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_service: AuditExecutionService = Depends(get_audit_execution_service),
) -> AuditTestRecord:
    _ensure_not_patient(current_user)
    return execution_service.review_test(current_user, test_id, payload)


# =============================================================================
# 10. AUDIT FINDINGS, AUDITEE RESPONSES & CAPA LINKAGE
# =============================================================================

@router.post(
    "/audits/{audit_id}/findings",
    response_model=AuditFindingRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record an audit finding or observation",
)
def create_audit_finding(
    audit_id: str,
    payload: CreateAuditFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> AuditFindingRecord:
    _ensure_not_patient(current_user)
    return findings_service.create_finding(current_user, audit_id, payload)


@router.get(
    "/audits/{audit_id}/findings",
    response_model=List[AuditFindingRecord],
    summary="List findings for an audit",
)
def list_audit_findings(
    audit_id: str,
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_confirmed: Optional[bool] = Query(None),
    is_closed: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> List[AuditFindingRecord]:
    _ensure_not_patient(current_user)
    return findings_service.list_findings(
        current_user,
        audit_id=audit_id,
        category=category,
        severity=severity,
        is_confirmed=is_confirmed,
        is_closed=is_closed,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/findings/{finding_id}",
    response_model=AuditFindingRecord,
    summary="Get finding details",
)
def get_audit_finding(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> AuditFindingRecord:
    _ensure_not_patient(current_user)
    return findings_service.get_finding(current_user, finding_id)


@router.post(
    "/findings/{finding_id}/confirm",
    response_model=AuditFindingRecord,
    summary="Lead auditor or governance authority confirms a finding",
)
def confirm_audit_finding(
    finding_id: str,
    payload: ConfirmAuditFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> AuditFindingRecord:
    _ensure_not_patient(current_user)
    return findings_service.confirm_finding(current_user, finding_id, payload)


@router.post(
    "/findings/{finding_id}/dispute",
    response_model=AuditFindingRecord,
    summary="Auditee or responsible owner disputes an audit finding",
)
def dispute_audit_finding(
    finding_id: str,
    payload: DisputeAuditFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> AuditFindingRecord:
    _ensure_not_patient(current_user)
    return findings_service.dispute_finding(current_user, finding_id, payload)


@router.post(
    "/findings/{finding_id}/responses",
    response_model=AuditeeResponseRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Auditee submits a formal response or remediation plan",
)
def submit_auditee_response(
    finding_id: str,
    payload: SubmitAuditeeResponseRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> AuditeeResponseRecord:
    _ensure_not_patient(current_user)
    return findings_service.submit_auditee_response(current_user, finding_id, payload)


@router.get(
    "/findings/{finding_id}/responses",
    response_model=List[AuditeeResponseRecord],
    summary="List responses submitted for a finding",
)
def list_auditee_responses(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> List[AuditeeResponseRecord]:
    _ensure_not_patient(current_user)
    return findings_service.list_responses(current_user, finding_id)


@router.post(
    "/findings/responses/{response_id}/review",
    response_model=AuditeeResponseRecord,
    summary="Auditor reviews an auditee response (self-review forbidden)",
)
def review_auditee_response(
    response_id: str,
    payload: ReviewAuditeeResponseRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> AuditeeResponseRecord:
    _ensure_not_patient(current_user)
    return findings_service.review_auditee_response(current_user, response_id, payload)


@router.post(
    "/findings/{finding_id}/link-corrective-action",
    response_model=AuditFindingRecord,
    summary="Link an authoritative Phase 54 corrective action to a finding",
)
def link_corrective_action_to_finding(
    finding_id: str,
    payload: LinkCorrectiveActionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    findings_service: AuditFindingsService = Depends(get_audit_findings_service),
) -> AuditFindingRecord:
    _ensure_not_patient(current_user)
    return findings_service.link_corrective_action(current_user, finding_id, payload)


# =============================================================================
# 11. AUDIT REPORTS & GOVERNANCE APPROVAL
# =============================================================================

@router.post(
    "/audits/{audit_id}/reports",
    response_model=AuditReportRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Compile and generate a draft audit report",
)
def generate_audit_report(
    audit_id: str,
    payload: GenerateAuditReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditReportRecord:
    _ensure_not_patient(current_user)
    return report_service.generate_report(current_user, audit_id, payload)


@router.get(
    "/audits/{audit_id}/reports",
    response_model=List[AuditReportRecord],
    summary="List reports generated for an audit",
)
def list_audit_reports(
    audit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceAuditRepository = Depends(get_governance_audit_repository),
) -> List[AuditReportRecord]:
    _ensure_not_patient(current_user)
    audit = repo.get_audit(audit_id)
    if not audit:
        raise AppException(
            code=ErrorCode.AUDIT_NOT_FOUND,
            message=f"Audit {audit_id} not found.",
            status_code=404,
        )
    if audit.organization_id != current_user.organization_id:
        raise AppException(
            code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
            message="Cannot list reports across tenant boundaries.",
            status_code=403,
        )
    return repo.list_reports_for_audit(audit_id)


@router.get(
    "/reports/{report_id}",
    response_model=AuditReportRecord,
    summary="Get audit report details",
)
def get_audit_report(
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditReportRecord:
    _ensure_not_patient(current_user)
    return report_service.get_report(current_user, report_id)


@router.post(
    "/reports/{report_id}/review",
    response_model=AuditReportRecord,
    summary="Peer or technical review of an audit report",
)
def review_audit_report(
    report_id: str,
    payload: ReviewAuditReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditReportRecord:
    _ensure_not_patient(current_user)
    return report_service.review_report(current_user, report_id, payload)


@router.post(
    "/reports/{report_id}/approve",
    response_model=AuditReportRecord,
    summary="Governance approval for an audit report (author self-approval forbidden)",
)
def approve_audit_report(
    report_id: str,
    payload: ApproveAuditReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: AuditReportClosureService = Depends(get_audit_report_closure_service),
) -> AuditReportRecord:
    _ensure_not_patient(current_user)
    return report_service.approve_report(current_user, report_id, payload)

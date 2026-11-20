"""Phase 74: Governance Change Adoption, Operational Sustainability & Drift Monitoring REST API Endpoints.

Provides comprehensive HTTP APIs for:
- Registering approved governance changes for operational adoption monitoring
- Establishing and managing version-controlled operational baselines
- Defining and activating adoption monitoring plans across organizational scopes
- Submitting, verifying, and rejecting operational adoption evidence
- Defining and assessing adoption indicators backed by verified evidence
- Logging, reviewing, and disposing implementation drift signals
- Conducting multi-dimensional operational sustainability assessments
- Managing operational exceptions, approval provenance, and expiry tracking
- Reporting and routing unintended operational consequences (Phases 49, 54, 59, 63, 67, 72)
- Adoption-level escalations
- Summaries, executive analytics, and scheduled monitoring cycles

Base Path: /api/v1/governance-change-adoption
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_change_adoption_registration import (
    AdoptionLineageResponse,
    AdoptionRegistrationStatus,
    CreateAdoptionRegistrationRequest,
    GovernanceChangeAdoptionRecord,
    UpdateAdoptionRegistrationRequest,
)
from app.schemas.operational_adoption_baseline import (
    ApproveBaselineRequest,
    BaselineApprovalStatus,
    CreateBaselineRequest,
    OperationalAdoptionBaselineRecord,
    SubmitBaselineRequest,
    UpdateBaselineRequest,
)
from app.schemas.adoption_monitoring_plan import (
    ActivateMonitoringPlanRequest,
    AdoptionMonitoringPlanRecord,
    CreateMonitoringPlanRequest,
    MonitoringPlanStatus,
    UpdateMonitoringPlanRequest,
)
from app.schemas.adoption_evidence_indicators import (
    AdoptionEvidenceRecord,
    AdoptionIndicatorRecord,
    AssessIndicatorRequest,
    CreateAdoptionIndicatorRequest,
    EvidenceVerificationStatus,
    RejectAdoptionEvidenceRequest,
    SubmitAdoptionEvidenceRequest,
    VerifyAdoptionEvidenceRequest,
)
from app.schemas.drift_sustainability_consequences import (
    AdoptionEscalationRecord,
    AdoptionExceptionRecord,
    AdoptionExceptionStatus,
    ApproveSustainabilityAssessmentRequest,
    CreateAdoptionEscalationRequest,
    CreateAdoptionExceptionRequest,
    CreateSustainabilityAssessmentRequest,
    DisposeDriftSignalRequest,
    DriftSignalStatus,
    EscalateAdoptionExceptionRequest,
    ImplementationDriftSignalRecord,
    LogDriftSignalRequest,
    OperationalConsequenceRecord,
    ReportConsequenceRequest,
    ReviewAdoptionExceptionRequest,
    ReviewDriftSignalRequest,
    RouteConsequenceRequest,
    SubmitAdoptionExceptionRequest,
    SubmitSustainabilityAssessmentRequest,
    SustainabilityAssessmentRecord,
)
from app.schemas.adoption_reporting import (
    AdoptionSummaryResponse,
    BackgroundJobRunResult,
    MonitoringHistoryResponse,
    OperationalDriftReportResponse,
    OrganizationAdoptionReportResponse,
    SustainabilitySummaryResponse,
)
from app.services.governance_change_adoption_registration_service import (
    GovernanceChangeAdoptionRegistrationService,
)
from app.services.operational_adoption_baseline_service import (
    OperationalAdoptionBaselineService,
)
from app.services.adoption_monitoring_plan_service import (
    AdoptionMonitoringPlanService,
)
from app.services.adoption_evidence_service import (
    AdoptionEvidenceService,
)
from app.services.adoption_indicator_service import (
    AdoptionIndicatorService,
)
from app.services.implementation_drift_service import (
    ImplementationDriftService,
)
from app.services.sustainability_assessment_service import (
    SustainabilityAssessmentService,
)
from app.services.adoption_exception_consequence_service import (
    AdoptionExceptionConsequenceService,
)
from app.services.adoption_monitoring_background_service import (
    AdoptionMonitoringBackgroundService,
)
from app.services.adoption_reporting_service import (
    AdoptionReportingService,
)

router = APIRouter(
    prefix="/governance-change-adoption",
    tags=["Phase 74 - Governance Change Adoption, Operational Sustainability & Drift Monitoring"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforce that patient role cannot access change adoption governance endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance change adoption monitoring features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


# =============================================================================
# A. Adoption Registration Endpoints
# =============================================================================


@router.post(
    "/registrations",
    response_model=GovernanceChangeAdoptionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register an approved governance change for adoption monitoring",
)
async def register_change_adoption(
    request: CreateAdoptionRegistrationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangeAdoptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangeAdoptionRegistrationService()
    return service.register_change_adoption(request, current_user)


@router.get(
    "/registrations",
    response_model=List[GovernanceChangeAdoptionRecord],
    summary="List adoption registrations",
)
async def list_registrations(
    status_filter: Optional[AdoptionRegistrationStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceChangeAdoptionRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceChangeAdoptionRegistrationService()
    return service.list_registrations(current_user, status_filter, skip, limit)


@router.get(
    "/registrations/{registration_id}",
    response_model=GovernanceChangeAdoptionRecord,
    summary="Get adoption registration details",
)
async def get_registration(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangeAdoptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangeAdoptionRegistrationService()
    return service.get_registration(registration_id, current_user)


@router.get(
    "/registrations/{registration_id}/lineage",
    response_model=AdoptionLineageResponse,
    summary="Get full decision-to-adoption governance lineage",
)
async def get_registration_lineage(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionLineageResponse:
    _ensure_not_patient(current_user)
    service = GovernanceChangeAdoptionRegistrationService()
    return service.get_registration_lineage(registration_id, current_user)


@router.patch(
    "/registrations/{registration_id}",
    response_model=GovernanceChangeAdoptionRecord,
    summary="Update adoption registration metadata or scope",
)
async def update_registration(
    registration_id: str,
    request: UpdateAdoptionRegistrationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangeAdoptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangeAdoptionRegistrationService()
    return service.update_registration(registration_id, request, current_user)


# =============================================================================
# B. Operational Baselines Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/baselines",
    response_model=OperationalAdoptionBaselineRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a version-controlled operational adoption baseline",
)
async def create_baseline(
    registration_id: str,
    request: CreateBaselineRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalAdoptionBaselineRecord:
    _ensure_not_patient(current_user)
    service = OperationalAdoptionBaselineService()
    return service.create_baseline(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/baselines",
    response_model=List[OperationalAdoptionBaselineRecord],
    summary="List operational baselines for registration",
)
async def list_baselines_for_registration(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[OperationalAdoptionBaselineRecord]:
    _ensure_not_patient(current_user)
    service = OperationalAdoptionBaselineService()
    return service.list_baselines_for_registration(registration_id, current_user)


@router.get(
    "/baselines/{baseline_id}",
    response_model=OperationalAdoptionBaselineRecord,
    summary="Get operational baseline by ID",
)
async def get_baseline(
    baseline_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalAdoptionBaselineRecord:
    _ensure_not_patient(current_user)
    service = OperationalAdoptionBaselineService()
    return service.get_baseline(baseline_id, current_user)


@router.post(
    "/baselines/{baseline_id}/submit",
    response_model=OperationalAdoptionBaselineRecord,
    summary="Submit baseline draft for approval",
)
async def submit_baseline(
    baseline_id: str,
    request: SubmitBaselineRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalAdoptionBaselineRecord:
    _ensure_not_patient(current_user)
    service = OperationalAdoptionBaselineService()
    return service.submit_baseline(baseline_id, request, current_user)


@router.post(
    "/baselines/{baseline_id}/approve",
    response_model=OperationalAdoptionBaselineRecord,
    summary="Approve operational baseline (Separation of duties enforced)",
)
async def approve_baseline(
    baseline_id: str,
    request: ApproveBaselineRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalAdoptionBaselineRecord:
    _ensure_not_patient(current_user)
    service = OperationalAdoptionBaselineService()
    return service.approve_baseline(baseline_id, request, current_user)


# =============================================================================
# C. Monitoring Plans Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/monitoring-plans",
    response_model=AdoptionMonitoringPlanRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create an adoption monitoring plan",
)
async def create_monitoring_plan(
    registration_id: str,
    request: CreateMonitoringPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionMonitoringPlanRecord:
    _ensure_not_patient(current_user)
    service = AdoptionMonitoringPlanService()
    return service.create_monitoring_plan(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/monitoring-plans",
    response_model=List[AdoptionMonitoringPlanRecord],
    summary="List monitoring plans for registration",
)
async def list_monitoring_plans(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[AdoptionMonitoringPlanRecord]:
    _ensure_not_patient(current_user)
    service = AdoptionMonitoringPlanService()
    return service.list_monitoring_plans_for_registration(registration_id, current_user)


@router.get(
    "/monitoring-plans/{plan_id}",
    response_model=AdoptionMonitoringPlanRecord,
    summary="Get monitoring plan by ID",
)
async def get_monitoring_plan(
    plan_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionMonitoringPlanRecord:
    _ensure_not_patient(current_user)
    service = AdoptionMonitoringPlanService()
    return service.get_monitoring_plan(plan_id, current_user)


@router.post(
    "/monitoring-plans/{plan_id}/activate",
    response_model=AdoptionMonitoringPlanRecord,
    summary="Activate a monitoring plan",
)
async def activate_monitoring_plan(
    plan_id: str,
    request: ActivateMonitoringPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionMonitoringPlanRecord:
    _ensure_not_patient(current_user)
    service = AdoptionMonitoringPlanService()
    return service.activate_monitoring_plan(plan_id, request, current_user)


# =============================================================================
# D. Evidence Management Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/evidence",
    response_model=AdoptionEvidenceRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit operational adoption evidence",
)
async def submit_evidence(
    registration_id: str,
    request: SubmitAdoptionEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionEvidenceRecord:
    _ensure_not_patient(current_user)
    service = AdoptionEvidenceService()
    return service.submit_evidence(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/evidence",
    response_model=List[AdoptionEvidenceRecord],
    summary="List evidence items for registration",
)
async def list_evidence(
    registration_id: str,
    status_filter: Optional[EvidenceVerificationStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[AdoptionEvidenceRecord]:
    _ensure_not_patient(current_user)
    service = AdoptionEvidenceService()
    return service.list_evidence_for_registration(registration_id, current_user, status_filter, skip, limit)


@router.get(
    "/evidence/{evidence_id}",
    response_model=AdoptionEvidenceRecord,
    summary="Get evidence item by ID",
)
async def get_evidence(
    evidence_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionEvidenceRecord:
    _ensure_not_patient(current_user)
    service = AdoptionEvidenceService()
    return service.get_evidence(evidence_id, current_user)


@router.post(
    "/evidence/{evidence_id}/verify",
    response_model=AdoptionEvidenceRecord,
    summary="Verify submitted evidence (Separation of duties enforced)",
)
async def verify_evidence(
    evidence_id: str,
    request: VerifyAdoptionEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionEvidenceRecord:
    _ensure_not_patient(current_user)
    service = AdoptionEvidenceService()
    return service.verify_evidence(evidence_id, request, current_user)


@router.post(
    "/evidence/{evidence_id}/reject",
    response_model=AdoptionEvidenceRecord,
    summary="Reject submitted evidence with reason",
)
async def reject_evidence(
    evidence_id: str,
    request: RejectAdoptionEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionEvidenceRecord:
    _ensure_not_patient(current_user)
    service = AdoptionEvidenceService()
    return service.reject_evidence(evidence_id, request, current_user)


# =============================================================================
# E. Adoption Indicators Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/indicators",
    response_model=AdoptionIndicatorRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Define an adoption indicator",
)
async def create_indicator(
    registration_id: str,
    request: CreateAdoptionIndicatorRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionIndicatorRecord:
    _ensure_not_patient(current_user)
    service = AdoptionIndicatorService()
    return service.create_indicator(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/indicators",
    response_model=List[AdoptionIndicatorRecord],
    summary="List adoption indicators for registration",
)
async def list_indicators(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[AdoptionIndicatorRecord]:
    _ensure_not_patient(current_user)
    service = AdoptionIndicatorService()
    return service.list_indicators_for_registration(registration_id, current_user)


@router.get(
    "/indicators/{indicator_id}",
    response_model=AdoptionIndicatorRecord,
    summary="Get adoption indicator by ID",
)
async def get_indicator(
    indicator_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionIndicatorRecord:
    _ensure_not_patient(current_user)
    service = AdoptionIndicatorService()
    return service.get_indicator(indicator_id, current_user)


@router.post(
    "/indicators/{indicator_id}/assess",
    response_model=AdoptionIndicatorRecord,
    summary="Assess indicator outcome against verified evidence",
)
async def assess_indicator(
    indicator_id: str,
    request: AssessIndicatorRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionIndicatorRecord:
    _ensure_not_patient(current_user)
    service = AdoptionIndicatorService()
    return service.assess_indicator(indicator_id, request, current_user)


# =============================================================================
# F. Drift Monitoring Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/drift-signals",
    response_model=ImplementationDriftSignalRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Log a potential implementation drift signal",
)
async def log_drift_signal(
    registration_id: str,
    request: LogDriftSignalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationDriftSignalRecord:
    _ensure_not_patient(current_user)
    service = ImplementationDriftService()
    return service.log_drift_signal(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/drift-signals",
    response_model=List[ImplementationDriftSignalRecord],
    summary="List drift signals for registration",
)
async def list_drift_signals(
    registration_id: str,
    status_filter: Optional[DriftSignalStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationDriftSignalRecord]:
    _ensure_not_patient(current_user)
    service = ImplementationDriftService()
    return service.list_drift_signals_for_registration(registration_id, current_user, status_filter)


@router.get(
    "/drift-signals/{signal_id}",
    response_model=ImplementationDriftSignalRecord,
    summary="Get drift signal by ID",
)
async def get_drift_signal(
    signal_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationDriftSignalRecord:
    _ensure_not_patient(current_user)
    service = ImplementationDriftService()
    return service.get_drift_signal(signal_id, current_user)


@router.post(
    "/drift-signals/{signal_id}/review",
    response_model=ImplementationDriftSignalRecord,
    summary="Record human review of a drift signal",
)
async def review_drift_signal(
    signal_id: str,
    request: ReviewDriftSignalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationDriftSignalRecord:
    _ensure_not_patient(current_user)
    service = ImplementationDriftService()
    return service.review_drift_signal(signal_id, request, current_user)


@router.post(
    "/drift-signals/{signal_id}/disposition",
    response_model=ImplementationDriftSignalRecord,
    summary="Record formal disposition of a drift signal",
)
async def dispose_drift_signal(
    signal_id: str,
    request: DisposeDriftSignalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationDriftSignalRecord:
    _ensure_not_patient(current_user)
    service = ImplementationDriftService()
    return service.dispose_drift_signal(signal_id, request, current_user)


# =============================================================================
# G. Sustainability Assessments Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/sustainability-assessments",
    response_model=SustainabilityAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create an operational sustainability assessment",
)
async def create_sustainability_assessment(
    registration_id: str,
    request: CreateSustainabilityAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SustainabilityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = SustainabilityAssessmentService()
    return service.create_assessment(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/sustainability-assessments",
    response_model=List[SustainabilityAssessmentRecord],
    summary="List sustainability assessments for registration",
)
async def list_sustainability_assessments(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SustainabilityAssessmentRecord]:
    _ensure_not_patient(current_user)
    service = SustainabilityAssessmentService()
    return service.list_assessments_for_registration(registration_id, current_user)


@router.get(
    "/sustainability-assessments/{assessment_id}",
    response_model=SustainabilityAssessmentRecord,
    summary="Get sustainability assessment by ID",
)
async def get_sustainability_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SustainabilityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = SustainabilityAssessmentService()
    return service.get_assessment(assessment_id, current_user)


@router.post(
    "/sustainability-assessments/{assessment_id}/submit",
    response_model=SustainabilityAssessmentRecord,
    summary="Submit sustainability assessment for approval",
)
async def submit_sustainability_assessment(
    assessment_id: str,
    request: SubmitSustainabilityAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SustainabilityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = SustainabilityAssessmentService()
    return service.submit_assessment(assessment_id, request, current_user)


@router.post(
    "/sustainability-assessments/{assessment_id}/approve",
    response_model=SustainabilityAssessmentRecord,
    summary="Approve sustainability assessment",
)
async def approve_sustainability_assessment(
    assessment_id: str,
    request: ApproveSustainabilityAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SustainabilityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = SustainabilityAssessmentService()
    return service.approve_assessment(assessment_id, request, current_user)


# =============================================================================
# H. Exceptions and Escalation Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/exceptions",
    response_model=AdoptionExceptionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create an operational adoption exception",
)
async def create_exception(
    registration_id: str,
    request: CreateAdoptionExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionExceptionRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.create_exception(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/exceptions",
    response_model=List[AdoptionExceptionRecord],
    summary="List adoption exceptions for registration",
)
async def list_exceptions(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[AdoptionExceptionRecord]:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.list_exceptions_for_registration(registration_id, current_user)


@router.get(
    "/exceptions/{exception_id}",
    response_model=AdoptionExceptionRecord,
    summary="Get adoption exception by ID",
)
async def get_exception(
    exception_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionExceptionRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.get_exception(exception_id, current_user)


@router.post(
    "/exceptions/{exception_id}/submit",
    response_model=AdoptionExceptionRecord,
    summary="Submit exception for review",
)
async def submit_exception(
    exception_id: str,
    request: SubmitAdoptionExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionExceptionRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.submit_exception(exception_id, request, current_user)


@router.post(
    "/exceptions/{exception_id}/review",
    response_model=AdoptionExceptionRecord,
    summary="Review adoption exception (approve or reject)",
)
async def review_exception(
    exception_id: str,
    request: ReviewAdoptionExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionExceptionRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.review_exception(exception_id, request, current_user)


@router.post(
    "/exceptions/{exception_id}/escalate",
    response_model=AdoptionExceptionRecord,
    summary="Escalate adoption exception to governance authority",
)
async def escalate_exception(
    exception_id: str,
    request: EscalateAdoptionExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionExceptionRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.escalate_exception(exception_id, request, current_user)


@router.post(
    "/registrations/{registration_id}/escalations",
    response_model=AdoptionEscalationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create adoption escalation",
)
async def create_escalation(
    registration_id: str,
    request: CreateAdoptionEscalationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionEscalationRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.create_escalation(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/escalations",
    response_model=List[AdoptionEscalationRecord],
    summary="List escalations for registration",
)
async def list_escalations(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[AdoptionEscalationRecord]:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.list_escalations_for_registration(registration_id, current_user)


# =============================================================================
# I. Operational Consequences Endpoints
# =============================================================================


@router.post(
    "/registrations/{registration_id}/operational-consequences",
    response_model=OperationalConsequenceRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Report unintended operational consequence",
)
async def report_consequence(
    registration_id: str,
    request: ReportConsequenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalConsequenceRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.report_consequence(registration_id, request, current_user)


@router.get(
    "/registrations/{registration_id}/operational-consequences",
    response_model=List[OperationalConsequenceRecord],
    summary="List unintended consequences for registration",
)
async def list_consequences(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[OperationalConsequenceRecord]:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.list_consequences_for_registration(registration_id, current_user)


@router.get(
    "/operational-consequences/{consequence_id}",
    response_model=OperationalConsequenceRecord,
    summary="Get operational consequence by ID",
)
async def get_consequence(
    consequence_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalConsequenceRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.get_consequence(consequence_id, current_user)


@router.post(
    "/operational-consequences/{consequence_id}/route",
    response_model=OperationalConsequenceRecord,
    summary="Route unintended consequence to authoritative workflow (Phases 49, 54, 59, 63, 67, 72)",
)
async def route_consequence(
    consequence_id: str,
    request: RouteConsequenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalConsequenceRecord:
    _ensure_not_patient(current_user)
    service = AdoptionExceptionConsequenceService()
    return service.route_consequence(consequence_id, request, current_user)


# =============================================================================
# J. Reporting & Analytics & Background Scan Endpoints
# =============================================================================


@router.get(
    "/registrations/{registration_id}/adoption-summary",
    response_model=AdoptionSummaryResponse,
    summary="Get adoption summary for an initiative",
)
async def get_adoption_summary(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AdoptionSummaryResponse:
    _ensure_not_patient(current_user)
    service = AdoptionReportingService()
    return service.get_adoption_summary(registration_id, current_user)


@router.get(
    "/registrations/{registration_id}/sustainability-summary",
    response_model=SustainabilitySummaryResponse,
    summary="Get sustainability summary for an initiative",
)
async def get_sustainability_summary(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SustainabilitySummaryResponse:
    _ensure_not_patient(current_user)
    service = AdoptionReportingService()
    return service.get_sustainability_summary(registration_id, current_user)


@router.get(
    "/registrations/{registration_id}/monitoring-history",
    response_model=MonitoringHistoryResponse,
    summary="Get historical timeline of monitoring actions",
)
async def get_monitoring_history(
    registration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> MonitoringHistoryResponse:
    _ensure_not_patient(current_user)
    service = AdoptionReportingService()
    return service.get_monitoring_history(registration_id, current_user)


@router.get(
    "/reports/organization-adoption",
    response_model=OrganizationAdoptionReportResponse,
    summary="Get cross-initiative adoption report across facilities and departments",
)
async def get_organization_adoption_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OrganizationAdoptionReportResponse:
    _ensure_not_patient(current_user)
    service = AdoptionReportingService()
    return service.get_organization_adoption_report(current_user)


@router.get(
    "/reports/operational-drift",
    response_model=OperationalDriftReportResponse,
    summary="Get system-wide operational drift summary report",
)
async def get_operational_drift_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OperationalDriftReportResponse:
    _ensure_not_patient(current_user)
    service = AdoptionReportingService()
    return service.get_operational_drift_report(current_user)


@router.post(
    "/jobs/run-monitoring-cycle",
    response_model=BackgroundJobRunResult,
    summary="Run an asynchronous / scheduled monitoring cycle (milestones, stale evidence, drift)",
)
async def run_monitoring_cycle(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BackgroundJobRunResult:
    _ensure_not_patient(current_user)
    service = AdoptionMonitoringBackgroundService()
    return service.run_scheduled_monitoring_cycle(tenant_id=current_user.tenant_id)

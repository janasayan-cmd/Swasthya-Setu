"""Phase 77: Clinical Safety Governance Strategic Assurance REST API Endpoints.

Base Route: /api/v1/governance-strategic-assurance

Provides endpoints for:
- Clinical safety governance maturity framework management and lifecycle
- Organizational maturity assessment scoping, evidence-backed evaluation, and aggregation
- Assurance evidence collection, freshness tracking, and positive verification
- Systemic governance gap identification, human confirmation, and remediation routing
- Governance capability improvement plans, milestones, and authoritative handoffs
- Independent assessment reviews, conflict of interest checks, and separation of duties
- Strategic management review packages for Phase 72 referral
- Assurance reporting (maturity radar, coverage, longitudinal trends) and routine scan jobs
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

from app.schemas.governance_maturity_framework import (
    ActivateFrameworkRequest,
    AddCriterionRequest,
    AddDimensionRequest,
    ApproveFrameworkRequest,
    CreateFrameworkRequest,
    FrameworkStatus,
    GovernanceMaturityFrameworkRecord,
)
from app.schemas.governance_maturity_assessment import (
    AggregateMaturityRequest,
    AggregateMaturityResponse,
    AssessmentStatus,
    CreateAssessmentRequest,
    EvaluateDimensionRequest,
    GovernanceMaturityAssessmentRecord,
    SubmitAssessmentRequest,
)
from app.schemas.governance_assurance_evidence import (
    GovernanceAssuranceEvidenceRecord,
    RejectAssuranceEvidenceRequest,
    SubmitAssuranceEvidenceRequest,
    VerifyAssuranceEvidenceRequest,
)
from app.schemas.governance_systemic_gaps import (
    ConfirmGapRequest,
    GapStatus,
    IdentifyGapRequest,
    RouteGapRequest,
    SystemicGovernanceGapRecord,
)
from app.schemas.governance_improvement_plan import (
    CreateImprovementPlanRequest,
    GovernanceImprovementPlanRecord,
    ImprovementPlanStatus,
    RouteImprovementActionRequest,
    UpdateMilestoneRequest,
)
from app.schemas.governance_assurance_review import (
    AssignReviewerRequest,
    AssuranceReviewRecord,
    PrepareReviewPackageRequest,
    ReferToPhase72Request,
    StrategicManagementReviewPackageRecord,
    SubmitReviewDecisionRequest,
)
from app.schemas.governance_assurance_reporting import (
    AssuranceRoutineScanJobResult,
    CoverageAnalysisResponse,
    LongitudinalTrendReportResponse,
    MaturityReportResponse,
)

from app.services.governance_maturity_framework_service import (
    GovernanceMaturityFrameworkService,
)
from app.services.governance_maturity_assessment_service import (
    GovernanceMaturityAssessmentService,
)
from app.services.governance_assurance_evidence_service import (
    GovernanceAssuranceEvidenceService,
)
from app.services.governance_systemic_gaps_service import (
    GovernanceSystemicGapsService,
)
from app.services.governance_improvement_plan_service import (
    GovernanceImprovementPlanService,
)
from app.services.governance_assurance_review_service import (
    GovernanceAssuranceReviewService,
)
from app.services.governance_strategic_assurance_reporting_service import (
    GovernanceStrategicAssuranceReportingService,
)
from app.services.governance_assurance_background_service import (
    GovernanceAssuranceBackgroundService,
)

router = APIRouter(
    prefix="/governance-strategic-assurance",
    tags=["Phase 77 - Clinical Safety Governance Strategic Assurance"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforces that patient role cannot access governance strategic assurance endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance strategic assurance features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


# =============================================================================
# Framework Lifecycle Endpoints
# =============================================================================

@router.post(
    "/frameworks",
    response_model=GovernanceMaturityFrameworkRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new maturity framework definition in DRAFT status",
)
def create_framework(
    request: CreateFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityFrameworkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.create_framework(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/frameworks",
    response_model=List[GovernanceMaturityFrameworkRecord],
    summary="List maturity framework definitions for current tenant",
)
def list_frameworks(
    status_filter: Optional[FrameworkStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceMaturityFrameworkRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.list_frameworks(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/frameworks/{framework_id}",
    response_model=GovernanceMaturityFrameworkRecord,
    summary="Get maturity framework by ID",
)
def get_framework(
    framework_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityFrameworkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.get_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
    )


@router.post(
    "/frameworks/{framework_id}/dimensions",
    response_model=GovernanceMaturityFrameworkRecord,
    summary="Add or update a dimension in a draft framework",
)
def add_dimension(
    framework_id: str,
    request: AddDimensionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityFrameworkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.add_dimension(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        request=request,
    )


@router.post(
    "/frameworks/{framework_id}/criteria",
    response_model=GovernanceMaturityFrameworkRecord,
    summary="Add a criterion to a dimension in a draft framework",
)
def add_criterion(
    framework_id: str,
    request: AddCriterionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityFrameworkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.add_criterion(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        request=request,
    )


@router.post(
    "/frameworks/{framework_id}/submit",
    response_model=GovernanceMaturityFrameworkRecord,
    summary="Submit a draft framework for review and approval",
)
def submit_framework(
    framework_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityFrameworkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.submit_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
    )


@router.post(
    "/frameworks/{framework_id}/approve",
    response_model=GovernanceMaturityFrameworkRecord,
    summary="Approve a submitted framework with separation of duties enforcement",
)
def approve_framework(
    framework_id: str,
    request: ApproveFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityFrameworkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.approve_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        approver_id=current_user.user_id,
        notes=request.approver_notes,
    )


@router.post(
    "/frameworks/{framework_id}/activate",
    response_model=GovernanceMaturityFrameworkRecord,
    summary="Activate an approved framework (supersedes currently active framework)",
)
def activate_framework(
    framework_id: str,
    request: ActivateFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityFrameworkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityFrameworkService()
    return service.activate_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        notes=request.activation_notes,
    )


# =============================================================================
# Assessment Endpoints
# =============================================================================

@router.post(
    "/assessments",
    response_model=GovernanceMaturityAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a new organizational governance maturity assessment",
)
def create_assessment(
    request: CreateAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityAssessmentService()
    return service.create_assessment(
        tenant_id=current_user.tenant_id,
        assessor_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/assessments",
    response_model=List[GovernanceMaturityAssessmentRecord],
    summary="List maturity assessments for current tenant",
)
def list_assessments(
    scope_id: Optional[str] = Query(None),
    scope_type: Optional[str] = Query(None),
    status_filter: Optional[AssessmentStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceMaturityAssessmentRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityAssessmentService()
    return service.list_assessments(
        tenant_id=current_user.tenant_id,
        scope_id=scope_id,
        scope_type=scope_type,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=GovernanceMaturityAssessmentRecord,
    summary="Get assessment by ID",
)
def get_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityAssessmentService()
    return service.get_assessment(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
    )


@router.post(
    "/assessments/{assessment_id}/evaluate-dimension",
    response_model=GovernanceMaturityAssessmentRecord,
    summary="Evaluate criteria and determine achieved level for a maturity dimension",
)
def evaluate_dimension(
    assessment_id: str,
    request: EvaluateDimensionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityAssessmentService()
    return service.evaluate_dimension(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        request=request,
    )


@router.post(
    "/assessments/{assessment_id}/submit",
    response_model=GovernanceMaturityAssessmentRecord,
    summary="Submit an assessment for independent review and approval",
)
def submit_assessment(
    assessment_id: str,
    request: SubmitAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceMaturityAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityAssessmentService()
    return service.submit_assessment(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        request=request,
    )


@router.post(
    "/assessments/aggregate",
    response_model=AggregateMaturityResponse,
    summary="Aggregate maturity across multiple assessed organizational scopes",
)
def aggregate_maturity(
    request: AggregateMaturityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AggregateMaturityResponse:
    _ensure_not_patient(current_user)
    service = GovernanceMaturityAssessmentService()
    return service.aggregate_maturity(
        tenant_id=current_user.tenant_id,
        request=request,
    )


# =============================================================================
# Evidence Intake & Verification Endpoints
# =============================================================================

@router.post(
    "/assessments/{assessment_id}/evidence",
    response_model=GovernanceAssuranceEvidenceRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit assurance evidence for an assessment criterion",
)
def submit_evidence(
    assessment_id: str,
    request: SubmitAssuranceEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceAssuranceEvidenceRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceEvidenceService()
    return service.submit_evidence(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        collected_by=current_user.user_id,
        request=request,
    )


@router.get(
    "/assessments/{assessment_id}/evidence",
    response_model=List[GovernanceAssuranceEvidenceRecord],
    summary="List evidence submitted for an assessment",
)
def list_evidence(
    assessment_id: str,
    dimension: Optional[str] = Query(None),
    criterion_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceAssuranceEvidenceRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceEvidenceService()
    return service.list_evidence_for_assessment(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        dimension=dimension,
        criterion_id=criterion_id,
    )


@router.get(
    "/evidence/{evidence_id}",
    response_model=GovernanceAssuranceEvidenceRecord,
    summary="Get evidence item by ID",
)
def get_evidence(
    evidence_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceAssuranceEvidenceRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceEvidenceService()
    return service.get_evidence(
        tenant_id=current_user.tenant_id,
        evidence_id=evidence_id,
    )


@router.post(
    "/evidence/{evidence_id}/verify",
    response_model=GovernanceAssuranceEvidenceRecord,
    summary="Verify submitted assurance evidence",
)
def verify_evidence(
    evidence_id: str,
    request: VerifyAssuranceEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceAssuranceEvidenceRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceEvidenceService()
    return service.verify_evidence(
        tenant_id=current_user.tenant_id,
        evidence_id=evidence_id,
        verifier_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/evidence/{evidence_id}/reject",
    response_model=GovernanceAssuranceEvidenceRecord,
    summary="Reject submitted assurance evidence",
)
def reject_evidence(
    evidence_id: str,
    request: RejectAssuranceEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceAssuranceEvidenceRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceEvidenceService()
    return service.reject_evidence(
        tenant_id=current_user.tenant_id,
        evidence_id=evidence_id,
        verifier_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# Systemic Gaps Endpoints
# =============================================================================

@router.post(
    "/systemic-gaps",
    response_model=SystemicGovernanceGapRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Identify a potential systemic governance gap",
)
def identify_gap(
    request: IdentifyGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SystemicGovernanceGapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceSystemicGapsService()
    return service.identify_gap(
        tenant_id=current_user.tenant_id,
        identified_by=current_user.user_id,
        request=request,
    )


@router.get(
    "/systemic-gaps",
    response_model=List[SystemicGovernanceGapRecord],
    summary="List identified systemic governance gaps",
)
def list_gaps(
    status_filter: Optional[GapStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SystemicGovernanceGapRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceSystemicGapsService()
    return service.list_gaps(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/systemic-gaps/{gap_id}",
    response_model=SystemicGovernanceGapRecord,
    summary="Get systemic governance gap by ID",
)
def get_gap(
    gap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SystemicGovernanceGapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceSystemicGapsService()
    return service.get_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
    )


@router.post(
    "/systemic-gaps/{gap_id}/confirm",
    response_model=SystemicGovernanceGapRecord,
    summary="Human-confirm a potential systemic governance gap",
)
def confirm_gap(
    gap_id: str,
    request: ConfirmGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SystemicGovernanceGapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceSystemicGapsService()
    return service.confirm_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        confirmer_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/systemic-gaps/{gap_id}/route",
    response_model=SystemicGovernanceGapRecord,
    summary="Route confirmed gap to an improvement plan",
)
def route_gap(
    gap_id: str,
    request: RouteGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> SystemicGovernanceGapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceSystemicGapsService()
    return service.route_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        request=request,
    )


# =============================================================================
# Improvement Plans Endpoints
# =============================================================================

@router.post(
    "/improvement-plans",
    response_model=GovernanceImprovementPlanRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a strategic governance capability improvement plan",
)
def create_improvement_plan(
    request: CreateImprovementPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceImprovementPlanRecord:
    _ensure_not_patient(current_user)
    service = GovernanceImprovementPlanService()
    return service.create_plan(
        tenant_id=current_user.tenant_id,
        creator_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/improvement-plans",
    response_model=List[GovernanceImprovementPlanRecord],
    summary="List governance improvement plans",
)
def list_improvement_plans(
    status_filter: Optional[ImprovementPlanStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceImprovementPlanRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceImprovementPlanService()
    return service.list_plans(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/improvement-plans/{plan_id}",
    response_model=GovernanceImprovementPlanRecord,
    summary="Get governance improvement plan by ID",
)
def get_improvement_plan(
    plan_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceImprovementPlanRecord:
    _ensure_not_patient(current_user)
    service = GovernanceImprovementPlanService()
    return service.get_plan(
        tenant_id=current_user.tenant_id,
        plan_id=plan_id,
    )


@router.post(
    "/improvement-plans/{plan_id}/milestones/{milestone_id}",
    response_model=GovernanceImprovementPlanRecord,
    summary="Update progress on an improvement plan milestone",
)
def update_milestone(
    plan_id: str,
    milestone_id: str,
    request: UpdateMilestoneRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceImprovementPlanRecord:
    _ensure_not_patient(current_user)
    service = GovernanceImprovementPlanService()
    return service.update_milestone(
        tenant_id=current_user.tenant_id,
        plan_id=plan_id,
        milestone_id=milestone_id,
        request=request,
    )


@router.post(
    "/improvement-plans/{plan_id}/route-action",
    response_model=GovernanceImprovementPlanRecord,
    summary="Route improvement action to an external authoritative workflow",
)
def route_improvement_action(
    plan_id: str,
    request: RouteImprovementActionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceImprovementPlanRecord:
    _ensure_not_patient(current_user)
    service = GovernanceImprovementPlanService()
    return service.route_action(
        tenant_id=current_user.tenant_id,
        plan_id=plan_id,
        routed_by=current_user.user_id,
        request=request,
    )


# =============================================================================
# Independent Reviews & Phase 72 Dossier Endpoints
# =============================================================================

@router.post(
    "/assessments/{assessment_id}/assign-reviewer",
    response_model=AssuranceReviewRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an independent reviewer with conflict of interest check",
)
def assign_reviewer(
    assessment_id: str,
    request: AssignReviewerRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AssuranceReviewRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceReviewService()
    return service.assign_reviewer(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        assigned_by=current_user.user_id,
        request=request,
    )


@router.post(
    "/reviews/{review_id}/decision",
    response_model=AssuranceReviewRecord,
    summary="Submit review decision by assigned reviewer",
)
def submit_review_decision(
    review_id: str,
    request: SubmitReviewDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AssuranceReviewRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceReviewService()
    return service.submit_review_decision(
        tenant_id=current_user.tenant_id,
        review_id=review_id,
        reviewer_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/review-packages",
    response_model=StrategicManagementReviewPackageRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Prepare a strategic management review package for Phase 72 referral",
)
def prepare_review_package(
    request: PrepareReviewPackageRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicManagementReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceReviewService()
    return service.prepare_review_package(
        tenant_id=current_user.tenant_id,
        prepared_by=current_user.user_id,
        request=request,
    )


@router.get(
    "/review-packages",
    response_model=List[StrategicManagementReviewPackageRecord],
    summary="List prepared strategic review packages",
)
def list_review_packages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicManagementReviewPackageRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceReviewService()
    return service.list_packages(
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/review-packages/{package_id}",
    response_model=StrategicManagementReviewPackageRecord,
    summary="Get strategic review package by ID",
)
def get_review_package(
    package_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicManagementReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceReviewService()
    return service.get_package(
        tenant_id=current_user.tenant_id,
        package_id=package_id,
    )


@router.post(
    "/review-packages/{package_id}/refer-phase-72",
    response_model=StrategicManagementReviewPackageRecord,
    summary="Refer prepared package to Phase 72 Management Review",
)
def refer_to_phase72(
    package_id: str,
    request: ReferToPhase72Request,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicManagementReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceReviewService()
    return service.refer_to_phase72(
        tenant_id=current_user.tenant_id,
        package_id=package_id,
        request=request,
    )


# =============================================================================
# Reporting & Background Scanning Endpoints
# =============================================================================

@router.get(
    "/reports/maturity/{assessment_id}",
    response_model=MaturityReportResponse,
    summary="Get maturity radar report for an assessment",
)
def get_maturity_report(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> MaturityReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategicAssuranceReportingService()
    return service.get_maturity_report(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
    )


@router.get(
    "/reports/coverage",
    response_model=CoverageAnalysisResponse,
    summary="Get assurance coverage analysis across organizational scopes",
)
def get_coverage_analysis(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CoverageAnalysisResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategicAssuranceReportingService()
    return service.get_coverage_analysis(
        tenant_id=current_user.tenant_id,
    )


@router.get(
    "/reports/longitudinal-trend/{scope_id}",
    response_model=LongitudinalTrendReportResponse,
    summary="Get longitudinal trend report preserving framework comparability",
)
def get_longitudinal_trend(
    scope_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> LongitudinalTrendReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategicAssuranceReportingService()
    return service.get_longitudinal_trend(
        tenant_id=current_user.tenant_id,
        scope_id=scope_id,
    )


@router.post(
    "/maintenance/routine-scan",
    response_model=AssuranceRoutineScanJobResult,
    summary="Execute idempotent routine background scan",
)
def run_routine_scan(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AssuranceRoutineScanJobResult:
    _ensure_not_patient(current_user)
    service = GovernanceAssuranceBackgroundService()
    return service.run_assurance_routine_scan(
        tenant_id=current_user.tenant_id,
    )

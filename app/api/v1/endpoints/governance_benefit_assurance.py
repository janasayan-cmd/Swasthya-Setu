"""Phase 76: Governance Portfolio Performance Assurance & Benefit Realization REST API Endpoints.

Base Route: /api/v1/governance-benefit-assurance

Provides endpoints for:
- Benefit registration & lineage tracking
- Baseline and target versioning & approval workflows
- Performance indicator configuration and reproducible assessment
- Measurement intake and verification
- Benefit realization evaluations & portfolio aggregations
- Attribution analysis & unintended consequences/trade-offs management
- Longitudinal sustainability monitoring & independent verifications
- Exception management & management review packages
- Executive and operational reporting & background routine scans
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

from app.schemas.governance_benefit_register import (
    BenefitLineageResponse,
    GovernanceBenefitRecord,
    RegisterBenefitRequest,
)
from app.schemas.governance_benefit_baseline_target import (
    ApproveBaselineRequest,
    ApproveTargetRequest,
    BenefitBaselineRecord,
    BenefitTargetRecord,
    CreateBaselineRequest,
    CreateTargetRequest,
    SubmitBaselineRequest,
    SubmitTargetRequest,
)
from app.schemas.governance_benefit_indicator_measurement import (
    AssessIndicatorRequest,
    BenefitIndicatorRecord,
    BenefitMeasurementRecord,
    CreateIndicatorRequest,
    CreateMeasurementRequest,
    IndicatorAssessmentResult,
    RejectMeasurementRequest,
    ValidateMeasurementRequest,
)
from app.schemas.governance_benefit_assessment import (
    ApproveRealizationAssessmentRequest,
    BenefitRealizationAssessmentRecord,
    CreatePortfolioBenefitAssessmentRequest,
    CreateRealizationAssessmentRequest,
    PortfolioBenefitAssessmentRecord,
    PortfolioBenefitSummaryResponse,
    SubmitRealizationAssessmentRequest,
)
from app.schemas.governance_benefit_attribution_consequences import (
    BenefitAttributionRecord,
    CreateAttributionAssessmentRequest,
    CreateConsequenceRequest,
    ReviewConsequenceRequest,
    RouteConsequenceRequest,
    UnintendedConsequenceRecord,
)
from app.schemas.governance_benefit_sustainability_verification import (
    AssignVerifierRequest,
    BenefitSustainabilityRecord,
    BenefitVerificationRecord,
    CompleteVerificationRequest,
    CreateSustainabilityAssessmentRequest,
    CreateVerificationRequest,
)
from app.schemas.governance_benefit_exceptions_reviews import (
    BenefitExceptionRecord,
    BenefitReviewPackageRecord,
    CreateBenefitExceptionRequest,
    CreateBenefitReviewRequest,
    EscalateBenefitExceptionRequest,
    ReferBenefitReviewRequest,
    ReviewBenefitExceptionRequest,
    SubmitBenefitExceptionRequest,
    SubmitBenefitReviewRequest,
)
from app.schemas.governance_benefit_reporting import (
    BenefitAssuranceJobRunResult,
    BenefitRealizationReportResponse,
    BenefitSustainabilityReportResponse,
    BenefitVerificationReportResponse,
    DelayedBenefitsReportResponse,
    PortfolioBenefitPerformanceReportResponse,
    UnrealizedBenefitsReportResponse,
)

from app.services.governance_benefit_register_service import (
    GovernanceBenefitRegisterService,
)
from app.services.governance_benefit_baseline_target_service import (
    GovernanceBenefitBaselineTargetService,
)
from app.services.governance_benefit_indicator_measurement_service import (
    GovernanceBenefitIndicatorMeasurementService,
)
from app.services.governance_benefit_assessment_service import (
    GovernanceBenefitAssessmentService,
)
from app.services.governance_benefit_attribution_consequences_service import (
    GovernanceBenefitAttributionConsequencesService,
)
from app.services.governance_benefit_sustainability_verification_service import (
    GovernanceBenefitSustainabilityVerificationService,
)
from app.services.governance_benefit_exceptions_reviews_service import (
    GovernanceBenefitExceptionsReviewsService,
)
from app.services.governance_benefit_background_service import (
    GovernanceBenefitBackgroundService,
)
from app.services.governance_benefit_reporting_service import (
    GovernanceBenefitReportingService,
)

router = APIRouter(
    prefix="/governance-benefit-assurance",
    tags=["Phase 76 - Governance Portfolio Benefit Assurance & Strategic Outcome Review"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforces that patient role cannot access governance benefit assurance endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance benefit assurance features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


# =============================================================================
# A. Benefit Registration Endpoints
# =============================================================================


@router.post(
    "/benefits",
    response_model=GovernanceBenefitRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register an expected governance change benefit",
)
async def register_benefit(
    request: RegisterBenefitRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceBenefitRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitRegisterService()
    return service.register_benefit(request, current_user)


@router.get(
    "/benefits",
    response_model=List[GovernanceBenefitRecord],
    summary="List registered governance benefits",
)
async def list_benefits(
    portfolio_id: Optional[str] = Query(None),
    implementation_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceBenefitRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitRegisterService()
    return service.list_benefits(current_user, portfolio_id, implementation_id, category, skip, limit)


@router.get(
    "/benefits/{benefit_id}",
    response_model=GovernanceBenefitRecord,
    summary="Get benefit details by ID",
)
async def get_benefit(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceBenefitRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitRegisterService()
    return service.get_benefit(benefit_id, current_user)


@router.get(
    "/benefits/{benefit_id}/lineage",
    response_model=BenefitLineageResponse,
    summary="Get full decision-to-benefit governance lineage",
)
async def get_benefit_lineage(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitLineageResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitRegisterService()
    return service.get_benefit_lineage(benefit_id, current_user)


# =============================================================================
# B. Baseline & Target Management Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/baselines",
    response_model=BenefitBaselineRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a versioned benefit baseline",
)
async def create_baseline(
    benefit_id: str,
    request: CreateBaselineRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitBaselineRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.create_baseline(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/baselines",
    response_model=List[BenefitBaselineRecord],
    summary="List baselines for a benefit",
)
async def list_baselines(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitBaselineRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.list_baselines(benefit_id, current_user)


@router.post(
    "/baselines/{baseline_id}/submit",
    response_model=BenefitBaselineRecord,
    summary="Submit baseline for governance approval",
)
async def submit_baseline(
    baseline_id: str,
    request: SubmitBaselineRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitBaselineRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.submit_baseline(baseline_id, request, current_user)


@router.post(
    "/baselines/{baseline_id}/approve",
    response_model=BenefitBaselineRecord,
    summary="Approve baseline (Separation of duties enforced)",
)
async def approve_baseline(
    baseline_id: str,
    request: ApproveBaselineRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitBaselineRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.approve_baseline(baseline_id, request, current_user)


@router.post(
    "/benefits/{benefit_id}/targets",
    response_model=BenefitTargetRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a versioned benefit target",
)
async def create_target(
    benefit_id: str,
    request: CreateTargetRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitTargetRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.create_target(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/targets",
    response_model=List[BenefitTargetRecord],
    summary="List targets for a benefit",
)
async def list_targets(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitTargetRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.list_targets(benefit_id, current_user)


@router.post(
    "/targets/{target_id}/submit",
    response_model=BenefitTargetRecord,
    summary="Submit target for governance approval",
)
async def submit_target(
    target_id: str,
    request: SubmitTargetRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitTargetRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.submit_target(target_id, request, current_user)


@router.post(
    "/targets/{target_id}/approve",
    response_model=BenefitTargetRecord,
    summary="Approve target (Separation of duties enforced)",
)
async def approve_target(
    target_id: str,
    request: ApproveTargetRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitTargetRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBaselineTargetService()
    return service.approve_target(target_id, request, current_user)


# =============================================================================
# C. Indicator Management Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/indicators",
    response_model=BenefitIndicatorRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Configure a performance indicator for a benefit",
)
async def create_indicator(
    benefit_id: str,
    request: CreateIndicatorRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitIndicatorRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.create_indicator(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/indicators",
    response_model=List[BenefitIndicatorRecord],
    summary="List indicators for a benefit",
)
async def list_indicators(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitIndicatorRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.list_indicators(benefit_id, current_user)


@router.get(
    "/indicators/{indicator_id}",
    response_model=BenefitIndicatorRecord,
    summary="Get indicator details by ID",
)
async def get_indicator(
    indicator_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitIndicatorRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.get_indicator(indicator_id, current_user)


@router.post(
    "/indicators/{indicator_id}/assess",
    response_model=IndicatorAssessmentResult,
    summary="Assess indicator result reproducibly without missing value assumption",
)
async def assess_indicator(
    indicator_id: str,
    request: AssessIndicatorRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> IndicatorAssessmentResult:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.assess_indicator(indicator_id, request, current_user)


# =============================================================================
# D. Measurement Intake Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/measurements",
    response_model=BenefitMeasurementRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an observed measurement",
)
async def create_measurement(
    benefit_id: str,
    request: CreateMeasurementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitMeasurementRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.create_measurement(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/measurements",
    response_model=List[BenefitMeasurementRecord],
    summary="List measurements for a benefit",
)
async def list_measurements(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitMeasurementRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.list_measurements(benefit_id, current_user)


@router.get(
    "/measurements/{measurement_id}",
    response_model=BenefitMeasurementRecord,
    summary="Get measurement by ID",
)
async def get_measurement(
    measurement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitMeasurementRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.get_measurement(measurement_id, current_user)


@router.post(
    "/measurements/{measurement_id}/validate",
    response_model=BenefitMeasurementRecord,
    summary="Validate measurement (Separation of duties enforced)",
)
async def validate_measurement(
    measurement_id: str,
    request: ValidateMeasurementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitMeasurementRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.validate_measurement(measurement_id, request, current_user)


@router.post(
    "/measurements/{measurement_id}/reject",
    response_model=BenefitMeasurementRecord,
    summary="Reject invalid measurement with stated reason",
)
async def reject_measurement(
    measurement_id: str,
    request: RejectMeasurementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitMeasurementRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitIndicatorMeasurementService()
    return service.reject_measurement(measurement_id, request, current_user)


# =============================================================================
# E. Realization Assessment Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/assessments",
    response_model=BenefitRealizationAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Perform benefit realization assessment",
)
async def create_assessment(
    benefit_id: str,
    request: CreateRealizationAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitRealizationAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.create_assessment(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/assessments",
    response_model=List[BenefitRealizationAssessmentRecord],
    summary="List realization assessments for a benefit",
)
async def list_assessments(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitRealizationAssessmentRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.list_assessments(benefit_id, current_user)


@router.get(
    "/assessments/{assessment_id}",
    response_model=BenefitRealizationAssessmentRecord,
    summary="Get realization assessment by ID",
)
async def get_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitRealizationAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.get_assessment(assessment_id, current_user)


@router.post(
    "/assessments/{assessment_id}/submit",
    response_model=BenefitRealizationAssessmentRecord,
    summary="Submit realization assessment for approval",
)
async def submit_assessment(
    assessment_id: str,
    request: SubmitRealizationAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitRealizationAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.submit_assessment(assessment_id, request, current_user)


@router.post(
    "/assessments/{assessment_id}/approve",
    response_model=BenefitRealizationAssessmentRecord,
    summary="Approve realization assessment (Separation of duties enforced)",
)
async def approve_assessment(
    assessment_id: str,
    request: ApproveRealizationAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitRealizationAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.approve_assessment(assessment_id, request, current_user)


# =============================================================================
# F. Portfolio Benefit Analysis Endpoints
# =============================================================================


@router.get(
    "/portfolios/{portfolio_id}/benefits",
    response_model=List[GovernanceBenefitRecord],
    summary="List benefits associated with a Phase 75 portfolio",
)
async def list_portfolio_benefits(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceBenefitRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitRegisterService()
    return service.list_benefits(current_user, portfolio_id=portfolio_id)


@router.get(
    "/portfolios/{portfolio_id}/benefit-summary",
    response_model=PortfolioBenefitSummaryResponse,
    summary="Consolidated portfolio benefit realization overview",
)
async def get_portfolio_benefit_summary(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioBenefitSummaryResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.get_portfolio_benefit_summary(portfolio_id, current_user)


@router.post(
    "/portfolios/{portfolio_id}/benefit-assessments",
    response_model=PortfolioBenefitAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Perform portfolio-level cumulative benefit assessment",
)
async def create_portfolio_benefit_assessment(
    portfolio_id: str,
    request: CreatePortfolioBenefitAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioBenefitAssessmentRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.create_portfolio_benefit_assessment(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/benefit-assessments",
    response_model=List[PortfolioBenefitAssessmentRecord],
    summary="List portfolio-level benefit assessments",
)
async def list_portfolio_benefit_assessments(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[PortfolioBenefitAssessmentRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAssessmentService()
    return service.list_portfolio_assessments(portfolio_id, current_user)


# =============================================================================
# G. Attribution Analysis Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/attribution-assessments",
    response_model=BenefitAttributionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record transparent benefit attribution assessment",
)
async def create_attribution_assessment(
    benefit_id: str,
    request: CreateAttributionAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitAttributionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAttributionConsequencesService()
    return service.create_attribution_assessment(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/attribution-assessments",
    response_model=List[BenefitAttributionRecord],
    summary="List attribution assessments for a benefit",
)
async def list_attribution_assessments(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitAttributionRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAttributionConsequencesService()
    return service.list_attributions(benefit_id, current_user)


@router.get(
    "/attribution-assessments/{assessment_id}",
    response_model=BenefitAttributionRecord,
    summary="Get attribution assessment by ID",
)
async def get_attribution_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitAttributionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAttributionConsequencesService()
    return service.get_attribution(assessment_id, current_user)


# =============================================================================
# H. Consequence & Trade-off Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/consequences",
    response_model=UnintendedConsequenceRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Log unintended consequence or operational trade-off",
)
async def create_consequence(
    benefit_id: str,
    request: CreateConsequenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> UnintendedConsequenceRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAttributionConsequencesService()
    return service.create_consequence(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/consequences",
    response_model=List[UnintendedConsequenceRecord],
    summary="List consequences and trade-offs for a benefit",
)
async def list_consequences(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[UnintendedConsequenceRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAttributionConsequencesService()
    return service.list_consequences(benefit_id, current_user)


@router.post(
    "/consequences/{consequence_id}/review",
    response_model=UnintendedConsequenceRecord,
    summary="Record human review of unintended consequence",
)
async def review_consequence(
    consequence_id: str,
    request: ReviewConsequenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> UnintendedConsequenceRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAttributionConsequencesService()
    return service.review_consequence(consequence_id, request, current_user)


@router.post(
    "/consequences/{consequence_id}/route",
    response_model=UnintendedConsequenceRecord,
    summary="Route consequence to authoritative workflow (Phases 49, 54, 63, 74)",
)
async def route_consequence(
    consequence_id: str,
    request: RouteConsequenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> UnintendedConsequenceRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitAttributionConsequencesService()
    return service.route_consequence(consequence_id, request, current_user)


# =============================================================================
# I. Sustainability Monitoring Endpoints
# =============================================================================


@router.get(
    "/benefits/{benefit_id}/performance-history",
    response_model=List[Dict[str, Any]],
    summary="Retrieve longitudinal performance measurement history",
)
async def get_performance_history(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.get_performance_history(benefit_id, current_user)


@router.get(
    "/benefits/{benefit_id}/sustainability",
    response_model=Dict[str, Any],
    summary="Get latest longitudinal benefit sustainability summary",
)
async def get_sustainability_summary(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.get_sustainability_summary(benefit_id, current_user)


@router.post(
    "/benefits/{benefit_id}/sustainability-assessments",
    response_model=BenefitSustainabilityRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record longitudinal benefit sustainability evaluation",
)
async def create_sustainability_assessment(
    benefit_id: str,
    request: CreateSustainabilityAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitSustainabilityRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.create_sustainability_assessment(benefit_id, request, current_user)


# =============================================================================
# J. Independent Verification Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/verification-requests",
    response_model=BenefitVerificationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Request independent verification of benefit realization",
)
async def create_verification_request(
    benefit_id: str,
    request: CreateVerificationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitVerificationRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.create_verification_request(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/verification-requests",
    response_model=List[BenefitVerificationRecord],
    summary="List independent verification requests for a benefit",
)
async def list_verification_requests(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitVerificationRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.list_verifications(benefit_id, current_user)


@router.get(
    "/verification-requests/{verification_id}",
    response_model=BenefitVerificationRecord,
    summary="Get verification request details by ID",
)
async def get_verification_request(
    verification_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitVerificationRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.get_verification(verification_id, current_user)


@router.post(
    "/verification-requests/{verification_id}/assign",
    response_model=BenefitVerificationRecord,
    summary="Assign independent verifier with conflict-of-interest check",
)
async def assign_verifier(
    verification_id: str,
    request: AssignVerifierRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitVerificationRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.assign_verifier(verification_id, request, current_user)


@router.post(
    "/verification-requests/{verification_id}/complete",
    response_model=BenefitVerificationRecord,
    summary="Complete verification and record verified findings",
)
async def complete_verification(
    verification_id: str,
    request: CompleteVerificationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitVerificationRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitSustainabilityVerificationService()
    return service.complete_verification(verification_id, request, current_user)


# =============================================================================
# K. Exception Management Endpoints
# =============================================================================


@router.post(
    "/benefits/{benefit_id}/exceptions",
    response_model=BenefitExceptionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Log benefit measurement or realization exception",
)
async def create_exception(
    benefit_id: str,
    request: CreateBenefitExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.create_exception(benefit_id, request, current_user)


@router.get(
    "/benefits/{benefit_id}/exceptions",
    response_model=List[BenefitExceptionRecord],
    summary="List exceptions for a benefit",
)
async def list_exceptions(
    benefit_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitExceptionRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.list_exceptions(benefit_id, current_user)


@router.post(
    "/exceptions/{exception_id}/submit",
    response_model=BenefitExceptionRecord,
    summary="Submit exception for governance review",
)
async def submit_exception(
    exception_id: str,
    request: SubmitBenefitExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.submit_exception(exception_id, request, current_user)


@router.post(
    "/exceptions/{exception_id}/review",
    response_model=BenefitExceptionRecord,
    summary="Review exception with explicit authorization reference",
)
async def review_exception(
    exception_id: str,
    request: ReviewBenefitExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.review_exception(exception_id, request, current_user)


@router.post(
    "/exceptions/{exception_id}/escalate",
    response_model=BenefitExceptionRecord,
    summary="Escalate unresolved exception to Phase 67 governance escalation",
)
async def escalate_exception(
    exception_id: str,
    request: EscalateBenefitExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.escalate_exception(exception_id, request, current_user)


# =============================================================================
# L. Management Review Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/benefit-reviews",
    response_model=BenefitReviewPackageRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Draft benefit realization management review package",
)
async def create_benefit_review(
    portfolio_id: str,
    request: CreateBenefitReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.create_review(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/benefit-reviews",
    response_model=List[BenefitReviewPackageRecord],
    summary="List benefit reviews for portfolio",
)
async def list_benefit_reviews(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[BenefitReviewPackageRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.list_reviews(portfolio_id, current_user)


@router.get(
    "/benefit-reviews/{review_id}",
    response_model=BenefitReviewPackageRecord,
    summary="Get benefit review package by ID",
)
async def get_benefit_review(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.get_review(review_id, current_user)


@router.post(
    "/benefit-reviews/{review_id}/submit",
    response_model=BenefitReviewPackageRecord,
    summary="Submit benefit review package for sign-off",
)
async def submit_benefit_review(
    review_id: str,
    request: SubmitBenefitReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.submit_review(review_id, request, current_user)


@router.post(
    "/benefit-reviews/{review_id}/refer-to-management",
    response_model=BenefitReviewPackageRecord,
    summary="Refer benefit review findings to Phase 72 Management Review",
)
async def refer_benefit_review_to_management(
    review_id: str,
    request: ReferBenefitReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitExceptionsReviewsService()
    return service.refer_to_management(review_id, request, current_user)


# =============================================================================
# M. Reporting & Background Job Endpoints
# =============================================================================


@router.get(
    "/reports/benefit-realization",
    response_model=BenefitRealizationReportResponse,
    summary="System-wide benefit realization summary report",
)
async def get_benefit_realization_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitRealizationReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitReportingService()
    return service.get_benefit_realization_report(current_user)


@router.get(
    "/reports/delayed-benefits",
    response_model=DelayedBenefitsReportResponse,
    summary="Report of benefits past expected realization date",
)
async def get_delayed_benefits_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DelayedBenefitsReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitReportingService()
    return service.get_delayed_benefits_report(current_user)


@router.get(
    "/reports/unrealized-benefits",
    response_model=UnrealizedBenefitsReportResponse,
    summary="Report of benefits that failed to realize planned outcomes",
)
async def get_unrealized_benefits_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> UnrealizedBenefitsReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitReportingService()
    return service.get_unrealized_benefits_report(current_user)


@router.get(
    "/reports/benefit-sustainability",
    response_model=BenefitSustainabilityReportResponse,
    summary="Report tracking multi-period benefit sustainability trends",
)
async def get_benefit_sustainability_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitSustainabilityReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitReportingService()
    return service.get_benefit_sustainability_report(current_user)


@router.get(
    "/reports/portfolio-benefit-performance",
    response_model=PortfolioBenefitPerformanceReportResponse,
    summary="Executive overview of benefit performance across portfolios",
)
async def get_portfolio_benefit_performance_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioBenefitPerformanceReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitReportingService()
    return service.get_portfolio_benefit_performance_report(current_user)


@router.get(
    "/reports/benefit-verification",
    response_model=BenefitVerificationReportResponse,
    summary="Summary of independent verification status across benefits",
)
async def get_benefit_verification_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitVerificationReportResponse:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitReportingService()
    return service.get_benefit_verification_report(current_user)


@router.post(
    "/jobs/run-benefit-assurance-cycle",
    response_model=BenefitAssuranceJobRunResult,
    summary="Trigger asynchronous / scheduled benefit assurance routine scan",
)
async def run_benefit_assurance_cycle(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> BenefitAssuranceJobRunResult:
    _ensure_not_patient(current_user)
    service = GovernanceBenefitBackgroundService()
    return service.run_benefit_assurance_cycle(tenant_id=current_user.tenant_id or current_user.organization_id or "default_tenant")

"""Phase 75: Governance Change Portfolio Oversight REST API Endpoints.

Provides comprehensive HTTP APIs for:
- Registering and organizing multiple approved governance changes into portfolios
- Portfolio scoping, lifecycle transitions, and separation of duties enforcement
- Initiative registration referencing Phase 72 decisions, Phase 73 implementations, and Phase 74 adoptions
- Cross-initiative dependency management and circular dependency detection
- Conflict detection, human review, and formal disposition
- Scheduling coordination and advisory sequencing recommendations
- Cumulative operational impact assessments across concurrent changes
- Resource dependency visibility without unsupported capacity claims
- Cross-initiative issues coordination and routing to authoritative workflows
- Portfolio review packages and referrals to Phase 72 Management Review
- Consolidated portfolio reporting and background coordination scans

Base Path: /api/v1/governance-change-portfolios
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_change_portfolio import (
    ApprovePortfolioRequest,
    ArchivePortfolioRequest,
    CreatePortfolioRequest,
    GovernanceChangePortfolioRecord,
    PortfolioStatus,
    SubmitPortfolioRequest,
    SuspendPortfolioRequest,
    UpdatePortfolioRequest,
)
from app.schemas.portfolio_initiative import (
    InitiativeLineageResponse,
    PortfolioInitiativeRecord,
    RegisterInitiativeRequest,
    RemoveInitiativeRequest,
)
from app.schemas.portfolio_dependencies_conflicts import (
    ConfirmDependencyRequest,
    CreateDependencyRequest,
    CrossInitiativeDependencyRecord,
    DependencyGraphResponse,
    DisposeConflictRequest,
    PortfolioConflictRecord,
    DisputeDependencyRequest,
    ResolveDependencyRequest,
    ReviewConflictRequest,
)
from app.schemas.portfolio_scheduling_impact import (
    CreateImpactAssessmentRequest,
    CreateResourceDependencyRequest,
    CreateScheduleAssessmentRequest,
    CumulativeImpactAssessmentRecord,
    ResourceDependencyRecord,
    ScheduleAssessmentRecord,
)
from app.schemas.portfolio_issues_reviews import (
    ApprovePortfolioReviewRequest,
    CreatePortfolioIssueRequest,
    CreatePortfolioReviewRequest,
    EscalatePortfolioIssueRequest,
    PortfolioIssueRecord,
    PortfolioReviewRecord,
    ReferPortfolioReviewRequest,
    RoutePortfolioIssueRequest,
    SubmitPortfolioReviewRequest,
)
from app.schemas.portfolio_reporting import (
    CrossInitiativeConflictReportResponse,
    CumulativeImpactReportResponse,
    PortfolioAdoptionSummaryResponse,
    PortfolioBackgroundJobRunResult,
    PortfolioDependencySummaryResponse,
    PortfolioExecutiveOverviewResponse,
    PortfolioImpactSummaryResponse,
    PortfolioOverviewResponse,
    PortfolioProgressResponse,
)
from app.services.governance_change_portfolio_service import (
    GovernanceChangePortfolioService,
)
from app.services.portfolio_initiative_service import (
    PortfolioInitiativeService,
)
from app.services.portfolio_dependency_service import (
    PortfolioDependencyService,
)
from app.services.portfolio_conflict_service import (
    PortfolioConflictService,
)
from app.services.portfolio_scheduling_impact_service import (
    PortfolioSchedulingImpactService,
)
from app.services.portfolio_issues_reviews_service import (
    PortfolioIssuesReviewsService,
)
from app.services.portfolio_coordination_background_service import (
    PortfolioCoordinationBackgroundService,
)
from app.services.portfolio_reporting_service import (
    PortfolioReportingService,
)

router = APIRouter(
    prefix="/governance-change-portfolios",
    tags=["Phase 75 - Governance Change Portfolio Oversight & Cumulative Impact Coordination"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforces that patient role cannot access governance portfolio coordination endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance change portfolio features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


# =============================================================================
# A. Portfolio Management Endpoints
# =============================================================================


@router.post(
    "/portfolios",
    response_model=GovernanceChangePortfolioRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new governance change portfolio",
)
async def create_portfolio(
    request: CreatePortfolioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.create_portfolio(request, current_user)


@router.get(
    "/portfolios",
    response_model=List[GovernanceChangePortfolioRecord],
    summary="List governance change portfolios",
)
async def list_portfolios(
    status_filter: Optional[PortfolioStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceChangePortfolioRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.list_portfolios(current_user, status_filter, skip, limit)


@router.get(
    "/portfolios/{portfolio_id}",
    response_model=GovernanceChangePortfolioRecord,
    summary="Get portfolio details by ID",
)
async def get_portfolio(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.get_portfolio(portfolio_id, current_user)


@router.patch(
    "/portfolios/{portfolio_id}",
    response_model=GovernanceChangePortfolioRecord,
    summary="Update portfolio metadata and scopes",
)
async def update_portfolio(
    portfolio_id: str,
    request: UpdatePortfolioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.update_portfolio(portfolio_id, request, current_user)


@router.post(
    "/portfolios/{portfolio_id}/submit",
    response_model=GovernanceChangePortfolioRecord,
    summary="Submit portfolio draft for governance review",
)
async def submit_portfolio(
    portfolio_id: str,
    request: SubmitPortfolioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.submit_portfolio(portfolio_id, request, current_user)


@router.post(
    "/portfolios/{portfolio_id}/approve",
    response_model=GovernanceChangePortfolioRecord,
    summary="Approve portfolio (Separation of duties enforced)",
)
async def approve_portfolio(
    portfolio_id: str,
    request: ApprovePortfolioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.approve_portfolio(portfolio_id, request, current_user)


@router.post(
    "/portfolios/{portfolio_id}/activate",
    response_model=GovernanceChangePortfolioRecord,
    summary="Activate approved portfolio for operational coordination",
)
async def activate_portfolio(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.activate_portfolio(portfolio_id, current_user)


@router.post(
    "/portfolios/{portfolio_id}/suspend",
    response_model=GovernanceChangePortfolioRecord,
    summary="Suspend portfolio to ON_HOLD",
)
async def suspend_portfolio(
    portfolio_id: str,
    request: SuspendPortfolioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.suspend_portfolio(portfolio_id, request, current_user)


@router.post(
    "/portfolios/{portfolio_id}/archive",
    response_model=GovernanceChangePortfolioRecord,
    summary="Archive completed or cancelled portfolio",
)
async def archive_portfolio(
    portfolio_id: str,
    request: ArchivePortfolioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceChangePortfolioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceChangePortfolioService()
    return service.archive_portfolio(portfolio_id, request, current_user)


# =============================================================================
# B. Initiative Management Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/initiatives",
    response_model=PortfolioInitiativeRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register an authorized initiative into a portfolio",
)
async def register_initiative(
    portfolio_id: str,
    request: RegisterInitiativeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioInitiativeRecord:
    _ensure_not_patient(current_user)
    service = PortfolioInitiativeService()
    return service.register_initiative(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/initiatives",
    response_model=List[PortfolioInitiativeRecord],
    summary="List initiatives in a portfolio",
)
async def list_initiatives_for_portfolio(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[PortfolioInitiativeRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioInitiativeService()
    return service.list_initiatives_for_portfolio(portfolio_id, current_user)


@router.get(
    "/initiatives/{initiative_id}",
    response_model=PortfolioInitiativeRecord,
    summary="Get portfolio initiative by ID",
)
async def get_initiative(
    initiative_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioInitiativeRecord:
    _ensure_not_patient(current_user)
    service = PortfolioInitiativeService()
    return service.get_initiative(initiative_id, current_user)


@router.get(
    "/initiatives/{initiative_id}/lineage",
    response_model=InitiativeLineageResponse,
    summary="Get full decision-to-portfolio governance lineage",
)
async def get_initiative_lineage(
    initiative_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> InitiativeLineageResponse:
    _ensure_not_patient(current_user)
    service = PortfolioInitiativeService()
    return service.get_initiative_lineage(initiative_id, current_user)


@router.post(
    "/initiatives/{initiative_id}/remove",
    response_model=PortfolioInitiativeRecord,
    summary="Remove initiative from portfolio coordination",
)
async def remove_initiative(
    initiative_id: str,
    request: RemoveInitiativeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioInitiativeRecord:
    _ensure_not_patient(current_user)
    service = PortfolioInitiativeService()
    return service.remove_initiative(initiative_id, request, current_user)


# =============================================================================
# C. Dependency Management Endpoints
# =============================================================================


@router.post(
    "/initiatives/{initiative_id}/dependencies",
    response_model=CrossInitiativeDependencyRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Declare a cross-initiative dependency",
)
async def create_dependency(
    initiative_id: str,
    request: CreateDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossInitiativeDependencyRecord:
    _ensure_not_patient(current_user)
    service = PortfolioDependencyService()
    return service.create_dependency(initiative_id, request, current_user)


@router.get(
    "/initiatives/{initiative_id}/dependencies",
    response_model=List[CrossInitiativeDependencyRecord],
    summary="List dependencies involving an initiative",
)
async def list_dependencies_for_initiative(
    initiative_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[CrossInitiativeDependencyRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioDependencyService()
    return service.list_dependencies_for_initiative(initiative_id, current_user)


@router.get(
    "/dependencies/{dependency_id}",
    response_model=CrossInitiativeDependencyRecord,
    summary="Get dependency details by ID",
)
async def get_dependency(
    dependency_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossInitiativeDependencyRecord:
    _ensure_not_patient(current_user)
    service = PortfolioDependencyService()
    return service.get_dependency(dependency_id, current_user)


@router.post(
    "/dependencies/{dependency_id}/confirm",
    response_model=CrossInitiativeDependencyRecord,
    summary="Confirm a proposed dependency",
)
async def confirm_dependency(
    dependency_id: str,
    request: ConfirmDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossInitiativeDependencyRecord:
    _ensure_not_patient(current_user)
    service = PortfolioDependencyService()
    return service.confirm_dependency(dependency_id, request, current_user)


@router.post(
    "/dependencies/{dependency_id}/resolve",
    response_model=CrossInitiativeDependencyRecord,
    summary="Mark dependency satisfied upon verified evidence",
)
async def resolve_dependency(
    dependency_id: str,
    request: ResolveDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossInitiativeDependencyRecord:
    _ensure_not_patient(current_user)
    service = PortfolioDependencyService()
    return service.resolve_dependency(dependency_id, request, current_user)


@router.post(
    "/dependencies/{dependency_id}/dispute",
    response_model=CrossInitiativeDependencyRecord,
    summary="Dispute a dependency with stated reason",
)
async def dispute_dependency(
    dependency_id: str,
    request: DisputeDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossInitiativeDependencyRecord:
    _ensure_not_patient(current_user)
    service = PortfolioDependencyService()
    return service.dispute_dependency(dependency_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/dependency-graph",
    response_model=DependencyGraphResponse,
    summary="Get full dependency graph and circular cycle detection",
)
async def get_dependency_graph(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DependencyGraphResponse:
    _ensure_not_patient(current_user)
    service = PortfolioDependencyService()
    return service.get_dependency_graph(portfolio_id, current_user)


# =============================================================================
# D. Conflict Management Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/conflicts/scan",
    response_model=List[PortfolioConflictRecord],
    summary="Scan for potential cross-initiative conflicts",
)
async def scan_conflicts(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[PortfolioConflictRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioConflictService()
    return service.scan_and_detect_conflicts(portfolio_id, current_user)


@router.get(
    "/portfolios/{portfolio_id}/conflicts",
    response_model=List[PortfolioConflictRecord],
    summary="List conflicts detected in a portfolio",
)
async def list_conflicts(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[PortfolioConflictRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioConflictService()
    return service.list_conflicts_for_portfolio(portfolio_id, current_user)


@router.get(
    "/conflicts/{conflict_id}",
    response_model=PortfolioConflictRecord,
    summary="Get conflict by ID",
)
async def get_conflict(
    conflict_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioConflictRecord:
    _ensure_not_patient(current_user)
    service = PortfolioConflictService()
    return service.get_conflict(conflict_id, current_user)


@router.post(
    "/conflicts/{conflict_id}/review",
    response_model=PortfolioConflictRecord,
    summary="Record human review of potential conflict",
)
async def review_conflict(
    conflict_id: str,
    request: ReviewConflictRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioConflictRecord:
    _ensure_not_patient(current_user)
    service = PortfolioConflictService()
    return service.review_conflict(conflict_id, request, current_user)


@router.post(
    "/conflicts/{conflict_id}/disposition",
    response_model=PortfolioConflictRecord,
    summary="Record formal disposition of evaluated conflict",
)
async def dispose_conflict(
    conflict_id: str,
    request: DisposeConflictRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioConflictRecord:
    _ensure_not_patient(current_user)
    service = PortfolioConflictService()
    return service.dispose_conflict(conflict_id, request, current_user)


# =============================================================================
# E. Scheduling Coordination Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/schedule-assessments",
    response_model=ScheduleAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Conduct schedule assessment and generate advisory recommendations",
)
async def create_schedule_assessment(
    portfolio_id: str,
    request: CreateScheduleAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ScheduleAssessmentRecord:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.assess_schedule(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/schedule-assessments",
    response_model=List[ScheduleAssessmentRecord],
    summary="List schedule assessments for portfolio",
)
async def list_schedule_assessments(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ScheduleAssessmentRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.list_schedule_assessments(portfolio_id, current_user)


@router.get(
    "/schedule-assessments/{assessment_id}",
    response_model=ScheduleAssessmentRecord,
    summary="Get schedule assessment by ID",
)
async def get_schedule_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ScheduleAssessmentRecord:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.get_schedule_assessment(assessment_id, current_user)


# =============================================================================
# F. Cumulative Impact Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/impact-assessments",
    response_model=CumulativeImpactAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Perform cumulative operational impact assessment",
)
async def create_impact_assessment(
    portfolio_id: str,
    request: CreateImpactAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CumulativeImpactAssessmentRecord:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.assess_cumulative_impact(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/impact-assessments",
    response_model=List[CumulativeImpactAssessmentRecord],
    summary="List cumulative impact assessments for portfolio",
)
async def list_impact_assessments(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[CumulativeImpactAssessmentRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.list_impact_assessments(portfolio_id, current_user)


@router.get(
    "/impact-assessments/{assessment_id}",
    response_model=CumulativeImpactAssessmentRecord,
    summary="Get impact assessment by ID",
)
async def get_impact_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CumulativeImpactAssessmentRecord:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.get_impact_assessment(assessment_id, current_user)


# =============================================================================
# G. Resource Coordination Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/resource-dependencies",
    response_model=ResourceDependencyRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register shared resource dependency",
)
async def create_resource_dependency(
    portfolio_id: str,
    request: CreateResourceDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ResourceDependencyRecord:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.create_resource_dependency(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/resource-dependencies",
    response_model=List[ResourceDependencyRecord],
    summary="List resource dependencies for portfolio",
)
async def list_resource_dependencies(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ResourceDependencyRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.list_resource_dependencies(portfolio_id, current_user)


@router.get(
    "/resource-dependencies/{resource_dependency_id}",
    response_model=ResourceDependencyRecord,
    summary="Get resource dependency by ID",
)
async def get_resource_dependency(
    resource_dependency_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ResourceDependencyRecord:
    _ensure_not_patient(current_user)
    service = PortfolioSchedulingImpactService()
    return service.get_resource_dependency(resource_dependency_id, current_user)


# =============================================================================
# H. Issue Coordination Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/issues",
    response_model=PortfolioIssueRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Log a cross-initiative issue",
)
async def create_issue(
    portfolio_id: str,
    request: CreatePortfolioIssueRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioIssueRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.create_issue(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/issues",
    response_model=List[PortfolioIssueRecord],
    summary="List issues for portfolio",
)
async def list_issues(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[PortfolioIssueRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.list_issues(portfolio_id, current_user)


@router.get(
    "/issues/{issue_id}",
    response_model=PortfolioIssueRecord,
    summary="Get issue details by ID",
)
async def get_issue(
    issue_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioIssueRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.get_issue(issue_id, current_user)


@router.post(
    "/issues/{issue_id}/route",
    response_model=PortfolioIssueRecord,
    summary="Route issue to authoritative workflow (Phases 49, 54, 63, 67, 72, 74)",
)
async def route_issue(
    issue_id: str,
    request: RoutePortfolioIssueRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioIssueRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.route_issue(issue_id, request, current_user)


@router.post(
    "/issues/{issue_id}/escalate",
    response_model=PortfolioIssueRecord,
    summary="Escalate issue to governance leadership",
)
async def escalate_issue(
    issue_id: str,
    request: EscalatePortfolioIssueRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioIssueRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.escalate_issue(issue_id, request, current_user)


# =============================================================================
# I. Portfolio Review Endpoints
# =============================================================================


@router.post(
    "/portfolios/{portfolio_id}/reviews",
    response_model=PortfolioReviewRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Draft portfolio review package snapshot",
)
async def create_review(
    portfolio_id: str,
    request: CreatePortfolioReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioReviewRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.create_review(portfolio_id, request, current_user)


@router.get(
    "/portfolios/{portfolio_id}/reviews",
    response_model=List[PortfolioReviewRecord],
    summary="List reviews for portfolio",
)
async def list_reviews(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[PortfolioReviewRecord]:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.list_reviews(portfolio_id, current_user)


@router.get(
    "/reviews/{review_id}",
    response_model=PortfolioReviewRecord,
    summary="Get review by ID",
)
async def get_review(
    review_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioReviewRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.get_review(review_id, current_user)


@router.post(
    "/reviews/{review_id}/submit",
    response_model=PortfolioReviewRecord,
    summary="Submit review package for sign-off",
)
async def submit_review(
    review_id: str,
    request: SubmitPortfolioReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioReviewRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.submit_review(review_id, request, current_user)


@router.post(
    "/reviews/{review_id}/approve",
    response_model=PortfolioReviewRecord,
    summary="Approve portfolio review package",
)
async def approve_review(
    review_id: str,
    request: ApprovePortfolioReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioReviewRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.approve_review(review_id, request, current_user)


@router.post(
    "/reviews/{review_id}/refer-to-management",
    response_model=PortfolioReviewRecord,
    summary="Refer portfolio review findings to Phase 72 Management Review",
)
async def refer_to_management(
    review_id: str,
    request: ReferPortfolioReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioReviewRecord:
    _ensure_not_patient(current_user)
    service = PortfolioIssuesReviewsService()
    return service.refer_to_management(review_id, request, current_user)


# =============================================================================
# J. Reporting Endpoints
# =============================================================================


@router.get(
    "/portfolios/{portfolio_id}/overview",
    response_model=PortfolioOverviewResponse,
    summary="Get single portfolio overview metrics",
)
async def get_portfolio_overview(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioOverviewResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_portfolio_overview(portfolio_id, current_user)


@router.get(
    "/portfolios/{portfolio_id}/implementation-progress",
    response_model=PortfolioProgressResponse,
    summary="Consolidate implementation progress from Phase 73",
)
async def get_portfolio_progress(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioProgressResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_portfolio_progress(portfolio_id, current_user)


@router.get(
    "/portfolios/{portfolio_id}/adoption-summary",
    response_model=PortfolioAdoptionSummaryResponse,
    summary="Consolidate adoption monitoring coverage from Phase 74",
)
async def get_portfolio_adoption_summary(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioAdoptionSummaryResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_portfolio_adoption_summary(portfolio_id, current_user)


@router.get(
    "/portfolios/{portfolio_id}/dependency-summary",
    response_model=PortfolioDependencySummaryResponse,
    summary="Get portfolio dependency metrics and circular status",
)
async def get_portfolio_dependency_summary(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioDependencySummaryResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_portfolio_dependency_summary(portfolio_id, current_user)


@router.get(
    "/portfolios/{portfolio_id}/impact-summary",
    response_model=PortfolioImpactSummaryResponse,
    summary="Get latest cumulative operational impact summary",
)
async def get_portfolio_impact_summary(
    portfolio_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioImpactSummaryResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_portfolio_impact_summary(portfolio_id, current_user)


@router.get(
    "/reports/portfolio-overview",
    response_model=PortfolioExecutiveOverviewResponse,
    summary="Executive overview across all portfolios",
)
async def get_portfolio_executive_overview(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioExecutiveOverviewResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_portfolio_executive_overview(current_user)


@router.get(
    "/reports/cross-initiative-conflicts",
    response_model=CrossInitiativeConflictReportResponse,
    summary="Executive report of cross-initiative conflicts",
)
async def get_cross_initiative_conflict_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossInitiativeConflictReportResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_cross_initiative_conflict_report(current_user)


@router.get(
    "/reports/cumulative-operational-impact",
    response_model=CumulativeImpactReportResponse,
    summary="System-wide cumulative operational impact report",
)
async def get_cumulative_impact_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CumulativeImpactReportResponse:
    _ensure_not_patient(current_user)
    service = PortfolioReportingService()
    return service.get_cumulative_impact_report(current_user)


@router.post(
    "/jobs/run-coordination-cycle",
    response_model=PortfolioBackgroundJobRunResult,
    summary="Trigger asynchronous / scheduled coordination cycle",
)
async def run_coordination_cycle(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioBackgroundJobRunResult:
    _ensure_not_patient(current_user)
    service = PortfolioCoordinationBackgroundService()
    return service.run_coordination_cycle(tenant_id=current_user.tenant_id or current_user.organization_id)

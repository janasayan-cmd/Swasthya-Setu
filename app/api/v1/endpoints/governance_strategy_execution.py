"""Phase 79: Clinical Safety Governance Strategy Execution REST API Endpoints.

Base Route: /api/v1/governance-strategy-execution

Provides endpoints for:
- Strategic execution monitoring and upstream source reconciliation
- Cross-roadmap dependencies, cycle detection, and sequencing conflict validation
- Strategic alignment analysis and explainable findings
- Strategic assumption registration and validation tracking
- Strategic change signal detection and escalation routing to Phase 63
- Strategic adaptation proposals, separation of duties, and downstream follow-through
- Advisory scenario analysis and comparative simulations
- Strategic execution exceptions, authoritative escalation, and resolution
- Executive review package generation and Phase 72 referral
- Background scheduled routine maintenance scan
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Schemas
from app.schemas.governance_strategy_execution_monitoring import (
    CreateExecutionMonitoringRequest,
    MonitoredWorkflowType,
    MonitoringHealthStatus,
    ReconcileExecutionMonitoringRequest,
    StrategicExecutionMonitoringRecord,
)
from app.schemas.governance_cross_roadmap_dependency import (
    CreateCrossRoadmapDependencyRequest,
    CrossDependencyStatus,
    CrossRoadmapDependencyRecord,
    CrossRoadmapValidationResult,
    ReviewCrossRoadmapDependencyRequest,
)
from app.schemas.governance_strategy_alignment import (
    AlignmentFindingCategory,
    AlignmentFindingStatus,
    CreateAlignmentFindingRequest,
    ReviewAlignmentFindingRequest,
    StrategicAlignmentFindingRecord,
)
from app.schemas.governance_strategy_assumption import (
    AssumptionCategory,
    AssumptionStatus,
    CreateAssumptionRequest,
    StrategicAssumptionRecord,
    ValidateAssumptionRequest,
)
from app.schemas.governance_strategy_signals import (
    CreateSignalRequest,
    ReviewSignalRequest,
    SignalCategory,
    SignalDisposition,
    SignalSeverity,
    StrategicChangeSignalRecord,
)
from app.schemas.governance_strategy_adaptation import (
    AdaptationFollowThroughRecord,
    AdaptationProposalStatus,
    AdaptationProposalType,
    CreateAdaptationProposalRequest,
    LinkAuthoritativeDecisionRequest,
    ReviewAdaptationProposalRequest,
    StrategicAdaptationProposalRecord,
    SubmitAdaptationProposalRequest,
)
from app.schemas.governance_strategy_scenarios import (
    CreateScenarioRequest,
    ExecuteScenarioRequest,
    ScenarioComparisonResponse,
    ScenarioType,
    StrategicScenarioRecord,
)
from app.schemas.governance_strategy_execution_exceptions import (
    CreateExecutionExceptionRequest,
    EscalateExecutionExceptionRequest,
    ExecutionExceptionCategory,
    ExecutionExceptionStatus,
    ResolveExecutionExceptionRequest,
    StrategicExecutionExceptionRecord,
)
from app.schemas.governance_strategy_review_packages import (
    ExecutionRoutineScanJobResult,
    GenerateReviewPackageRequest,
    ReferReviewPackageToPhase72Request,
    StrategicReviewPackageRecord,
)

# Services
from app.services.governance_strategy_execution_monitoring_service import (
    GovernanceStrategyExecutionMonitoringService,
)
from app.services.governance_cross_roadmap_dependency_service import (
    GovernanceCrossRoadmapDependencyService,
)
from app.services.governance_strategy_alignment_service import (
    GovernanceStrategyAlignmentService,
)
from app.services.governance_strategy_assumption_service import (
    GovernanceStrategyAssumptionService,
)
from app.services.governance_strategy_signals_service import (
    GovernanceStrategySignalsService,
)
from app.services.governance_strategy_adaptation_service import (
    GovernanceStrategyAdaptationService,
)
from app.services.governance_strategy_scenarios_service import (
    GovernanceStrategyScenariosService,
)
from app.services.governance_strategy_execution_exceptions_service import (
    GovernanceStrategyExecutionExceptionsService,
)
from app.services.governance_strategy_review_packages_service import (
    GovernanceStrategyReviewPackagesService,
)
from app.services.governance_strategy_execution_background_service import (
    GovernanceStrategyExecutionBackgroundService,
)


def _ensure_not_patient(user: AuthenticatedUserContext = Depends(get_current_user)) -> AuthenticatedUserContext:
    """Enforces that patient role cannot access strategic execution monitoring endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance strategy execution features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return user


router = APIRouter(
    prefix="/governance-strategy-execution",
    tags=["Phase 79 - Strategic Execution Monitoring & Long-Term Strategy Adaptation"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# A. Strategic Execution Monitoring Endpoints
# =============================================================================

@router.post(
    "/monitoring",
    response_model=StrategicExecutionMonitoringRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create or initialize strategic execution monitoring record",
)
def create_monitoring_record(
    request: CreateExecutionMonitoringRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicExecutionMonitoringRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionMonitoringService()
    return service.create_monitoring_record(tenant_id=current_user.tenant_id, request=request)


@router.post(
    "/monitoring/{monitoring_id}/reconcile",
    response_model=StrategicExecutionMonitoringRecord,
    status_code=status.HTTP_200_OK,
    summary="Reconcile and update execution health status for monitored item",
)
def reconcile_monitoring_record(
    monitoring_id: str,
    request: ReconcileExecutionMonitoringRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicExecutionMonitoringRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionMonitoringService()
    return service.reconcile_monitoring_record(
        tenant_id=current_user.tenant_id,
        monitoring_id=monitoring_id,
        request=request,
    )


@router.get(
    "/monitoring/{monitoring_id}",
    response_model=StrategicExecutionMonitoringRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic execution monitoring record by ID",
)
def get_monitoring_record(
    monitoring_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicExecutionMonitoringRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionMonitoringService()
    return service.get_monitoring_record(tenant_id=current_user.tenant_id, monitoring_id=monitoring_id)


@router.get(
    "/monitoring",
    response_model=List[StrategicExecutionMonitoringRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic execution monitoring records",
)
def list_monitoring_records(
    roadmap_id: Optional[str] = Query(None),
    monitored_item_type: Optional[MonitoredWorkflowType] = Query(None),
    health_status: Optional[MonitoringHealthStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicExecutionMonitoringRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionMonitoringService()
    return service.list_monitoring_records(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        monitored_item_type=monitored_item_type,
        health_status=health_status,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# B. Cross-Roadmap Dependencies Endpoints
# =============================================================================

@router.post(
    "/cross-dependencies",
    response_model=CrossRoadmapDependencyRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create an inter-roadmap dependency with cycle detection",
)
def create_cross_dependency(
    request: CreateCrossRoadmapDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossRoadmapDependencyRecord:
    _ensure_not_patient(current_user)
    service = GovernanceCrossRoadmapDependencyService()
    return service.create_cross_dependency(
        tenant_id=current_user.tenant_id,
        request=request,
    )


@router.post(
    "/cross-dependencies/{dependency_id}/review",
    response_model=CrossRoadmapDependencyRecord,
    status_code=status.HTTP_200_OK,
    summary="Review and disposition a cross-roadmap dependency",
)
def review_cross_dependency(
    dependency_id: str,
    request: ReviewCrossRoadmapDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossRoadmapDependencyRecord:
    _ensure_not_patient(current_user)
    service = GovernanceCrossRoadmapDependencyService()
    return service.review_cross_dependency(
        tenant_id=current_user.tenant_id,
        reviewer_id=current_user.user_id,
        dependency_id=dependency_id,
        request=request,
    )


@router.get(
    "/cross-dependencies/{dependency_id}",
    response_model=CrossRoadmapDependencyRecord,
    status_code=status.HTTP_200_OK,
    summary="Get cross-roadmap dependency by ID",
)
def get_cross_dependency(
    dependency_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossRoadmapDependencyRecord:
    _ensure_not_patient(current_user)
    service = GovernanceCrossRoadmapDependencyService()
    return service.get_cross_dependency(
        tenant_id=current_user.tenant_id,
        dependency_id=dependency_id,
    )


@router.get(
    "/cross-dependencies",
    response_model=List[CrossRoadmapDependencyRecord],
    status_code=status.HTTP_200_OK,
    summary="List cross-roadmap dependencies",
)
def list_cross_dependencies(
    roadmap_id: Optional[str] = Query(None),
    status_filter: Optional[CrossDependencyStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[CrossRoadmapDependencyRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceCrossRoadmapDependencyService()
    return service.list_cross_dependencies(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/cross-dependencies/validate",
    response_model=CrossRoadmapValidationResult,
    status_code=status.HTTP_200_OK,
    summary="Validate cross-roadmap dependencies for circular cycles and conflicts",
)
def validate_cross_dependencies(
    roadmap_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CrossRoadmapValidationResult:
    _ensure_not_patient(current_user)
    service = GovernanceCrossRoadmapDependencyService()
    return service.validate_cross_dependencies(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


# =============================================================================
# C. Strategic Alignment Findings Endpoints
# =============================================================================

@router.post(
    "/alignment-findings",
    response_model=StrategicAlignmentFindingRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record a strategic alignment finding",
)
def record_alignment_finding(
    request: CreateAlignmentFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAlignmentFindingRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAlignmentService()
    return service.record_alignment_finding(
        tenant_id=current_user.tenant_id,
        request=request,
    )


@router.post(
    "/alignment-findings/{finding_id}/review",
    response_model=StrategicAlignmentFindingRecord,
    status_code=status.HTTP_200_OK,
    summary="Review and disposition a strategic alignment finding",
)
def review_alignment_finding(
    finding_id: str,
    request: ReviewAlignmentFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAlignmentFindingRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAlignmentService()
    return service.review_alignment_finding(
        tenant_id=current_user.tenant_id,
        reviewer_id=current_user.user_id,
        finding_id=finding_id,
        request=request,
    )


@router.get(
    "/alignment-findings/{finding_id}",
    response_model=StrategicAlignmentFindingRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic alignment finding by ID",
)
def get_alignment_finding(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAlignmentFindingRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAlignmentService()
    return service.get_alignment_finding(
        tenant_id=current_user.tenant_id,
        finding_id=finding_id,
    )


@router.get(
    "/alignment-findings",
    response_model=List[StrategicAlignmentFindingRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic alignment findings",
)
def list_alignment_findings(
    roadmap_id: Optional[str] = Query(None),
    category: Optional[AlignmentFindingCategory] = Query(None),
    status_filter: Optional[AlignmentFindingStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicAlignmentFindingRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAlignmentService()
    return service.list_alignment_findings(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        category=category,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# D. Strategic Planning Assumptions Endpoints
# =============================================================================

@router.post(
    "/assumptions",
    response_model=StrategicAssumptionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a strategic planning assumption",
)
def register_assumption(
    request: CreateAssumptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAssumptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAssumptionService()
    return service.register_assumption(
        tenant_id=current_user.tenant_id,
        request=request,
    )


@router.post(
    "/assumptions/{assumption_id}/validate",
    response_model=StrategicAssumptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Validate or update status of a strategic assumption",
)
def validate_assumption(
    assumption_id: str,
    request: ValidateAssumptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAssumptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAssumptionService()
    return service.validate_assumption(
        tenant_id=current_user.tenant_id,
        assumption_id=assumption_id,
        request=request,
    )


@router.get(
    "/assumptions/{assumption_id}",
    response_model=StrategicAssumptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic assumption by ID",
)
def get_assumption(
    assumption_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAssumptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAssumptionService()
    return service.get_assumption(
        tenant_id=current_user.tenant_id,
        assumption_id=assumption_id,
    )


@router.get(
    "/assumptions",
    response_model=List[StrategicAssumptionRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic planning assumptions",
)
def list_assumptions(
    roadmap_id: Optional[str] = Query(None),
    category: Optional[AssumptionCategory] = Query(None),
    status_filter: Optional[AssumptionStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicAssumptionRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAssumptionService()
    return service.list_assumptions(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        category=category,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# E. Strategic Change Signals Endpoints
# =============================================================================

@router.post(
    "/signals",
    response_model=StrategicChangeSignalRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record a detected strategic change signal",
)
def record_signal(
    request: CreateSignalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicChangeSignalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategySignalsService()
    return service.record_signal(
        tenant_id=current_user.tenant_id,
        request=request,
    )


@router.post(
    "/signals/{signal_id}/review",
    response_model=StrategicChangeSignalRecord,
    status_code=status.HTTP_200_OK,
    summary="Review and disposition a strategic change signal",
)
def review_signal(
    signal_id: str,
    request: ReviewSignalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicChangeSignalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategySignalsService()
    return service.review_signal(
        tenant_id=current_user.tenant_id,
        reviewer_id=current_user.user_id,
        signal_id=signal_id,
        request=request,
    )


@router.post(
    "/signals/{signal_id}/escalate-phase-63",
    response_model=StrategicChangeSignalRecord,
    status_code=status.HTTP_200_OK,
    summary="Escalate strategic change signal to Phase 63 clinical risk governance",
)
def escalate_signal_to_phase_63(
    signal_id: str,
    risk_rationale: str = Query(..., description="Clinical risk escalation rationale"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicChangeSignalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategySignalsService()
    return service.escalate_signal_to_phase_63(
        tenant_id=current_user.tenant_id,
        reviewer_id=current_user.user_id,
        signal_id=signal_id,
        risk_rationale=risk_rationale,
    )


@router.get(
    "/signals/{signal_id}",
    response_model=StrategicChangeSignalRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic change signal by ID",
)
def get_signal(
    signal_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicChangeSignalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategySignalsService()
    return service.get_signal(
        tenant_id=current_user.tenant_id,
        signal_id=signal_id,
    )


@router.get(
    "/signals",
    response_model=List[StrategicChangeSignalRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic change signals",
)
def list_signals(
    roadmap_id: Optional[str] = Query(None),
    category: Optional[SignalCategory] = Query(None),
    severity: Optional[SignalSeverity] = Query(None),
    disposition: Optional[SignalDisposition] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicChangeSignalRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategySignalsService()
    return service.list_signals(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        category=category,
        severity=severity,
        disposition=disposition,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# F. Strategic Adaptation Proposals & Follow-Through Endpoints
# =============================================================================

@router.post(
    "/adaptation-proposals",
    response_model=StrategicAdaptationProposalRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a strategic adaptation proposal in DRAFT status",
)
def create_adaptation_proposal(
    request: CreateAdaptationProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAdaptationProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.create_adaptation_proposal(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/adaptation-proposals/{proposal_id}/submit",
    response_model=StrategicAdaptationProposalRecord,
    status_code=status.HTTP_200_OK,
    summary="Submit adaptation proposal for strategic review",
)
def submit_adaptation_proposal(
    proposal_id: str,
    request: SubmitAdaptationProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAdaptationProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.submit_adaptation_proposal(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        proposal_id=proposal_id,
        request=request,
    )


@router.post(
    "/adaptation-proposals/{proposal_id}/review",
    response_model=StrategicAdaptationProposalRecord,
    status_code=status.HTTP_200_OK,
    summary="Review adaptation proposal (enforces separation of duties)",
)
def review_adaptation_proposal(
    proposal_id: str,
    request: ReviewAdaptationProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAdaptationProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.review_adaptation_proposal(
        tenant_id=current_user.tenant_id,
        reviewer_id=current_user.user_id,
        proposal_id=proposal_id,
        request=request,
    )


@router.post(
    "/adaptation-proposals/{proposal_id}/link-decision",
    response_model=StrategicAdaptationProposalRecord,
    status_code=status.HTTP_200_OK,
    summary="Link Phase 72/78 authoritative decision references to adaptation proposal",
)
def link_authoritative_decision(
    proposal_id: str,
    request: LinkAuthoritativeDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAdaptationProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.link_authoritative_decision(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
        request=request,
    )


@router.get(
    "/adaptation-proposals/{proposal_id}",
    response_model=StrategicAdaptationProposalRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic adaptation proposal by ID",
)
def get_adaptation_proposal(
    proposal_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicAdaptationProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.get_adaptation_proposal(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
    )


@router.get(
    "/adaptation-proposals",
    response_model=List[StrategicAdaptationProposalRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic adaptation proposals",
)
def list_adaptation_proposals(
    roadmap_id: Optional[str] = Query(None),
    status_filter: Optional[AdaptationProposalStatus] = Query(None, alias="status"),
    proposal_type: Optional[AdaptationProposalType] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicAdaptationProposalRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.list_adaptation_proposals(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        status=status_filter,
        proposal_type=proposal_type,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/adaptation-proposals/{proposal_id}/follow-through",
    response_model=Optional[AdaptationFollowThroughRecord],
    status_code=status.HTTP_200_OK,
    summary="Get follow-through tracking record for an adaptation proposal",
)
def get_adaptation_followthrough(
    proposal_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> Optional[AdaptationFollowThroughRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.get_followthrough_by_proposal(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
    )


@router.get(
    "/adaptation-follow-through",
    response_model=List[AdaptationFollowThroughRecord],
    status_code=status.HTTP_200_OK,
    summary="List all adaptation follow-through records",
)
def list_adaptation_followthroughs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[AdaptationFollowThroughRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyAdaptationService()
    return service.list_adaptation_followthroughs(
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# G. Strategic Scenarios Endpoints
# =============================================================================

@router.post(
    "/scenarios",
    response_model=StrategicScenarioRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create an advisory strategic what-if scenario",
)
def create_scenario(
    request: CreateScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicScenarioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyScenariosService()
    return service.create_scenario(
        tenant_id=current_user.tenant_id,
        creator_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/scenarios/{scenario_id}/execute",
    response_model=StrategicScenarioRecord,
    status_code=status.HTTP_200_OK,
    summary="Execute simulated impact projections for a strategic scenario",
)
def execute_scenario(
    scenario_id: str,
    request: ExecuteScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicScenarioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyScenariosService()
    return service.execute_scenario(
        tenant_id=current_user.tenant_id,
        scenario_id=scenario_id,
        request=request,
    )


@router.post(
    "/scenarios/compare",
    response_model=ScenarioComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare projected impacts across multiple strategic scenarios",
)
def compare_scenarios(
    scenario_ids: List[str] = Query(..., description="List of scenario IDs to compare"),
    baseline_roadmap_id: str = Query(..., description="Baseline roadmap ID"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ScenarioComparisonResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyScenariosService()
    return service.compare_scenarios(
        tenant_id=current_user.tenant_id,
        scenario_ids=scenario_ids,
        baseline_roadmap_id=baseline_roadmap_id,
    )


@router.get(
    "/scenarios/{scenario_id}",
    response_model=StrategicScenarioRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic scenario by ID",
)
def get_scenario(
    scenario_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicScenarioRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyScenariosService()
    return service.get_scenario(
        tenant_id=current_user.tenant_id,
        scenario_id=scenario_id,
    )


@router.get(
    "/scenarios",
    response_model=List[StrategicScenarioRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic scenarios",
)
def list_scenarios(
    roadmap_id: Optional[str] = Query(None),
    scenario_type: Optional[ScenarioType] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicScenarioRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyScenariosService()
    return service.list_scenarios(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        scenario_type=scenario_type,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# H. Strategic Execution Exceptions Endpoints
# =============================================================================

@router.post(
    "/exceptions",
    response_model=StrategicExecutionExceptionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Log a strategic execution exception",
)
def create_exception(
    request: CreateExecutionExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicExecutionExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionExceptionsService()
    return service.create_exception(
        tenant_id=current_user.tenant_id,
        request=request,
    )


@router.post(
    "/exceptions/{exception_id}/escalate",
    response_model=StrategicExecutionExceptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Escalate strategic execution exception to authoritative workflow",
)
def escalate_exception(
    exception_id: str,
    request: EscalateExecutionExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicExecutionExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionExceptionsService()
    return service.escalate_exception(
        tenant_id=current_user.tenant_id,
        exception_id=exception_id,
        request=request,
    )


@router.post(
    "/exceptions/{exception_id}/resolve",
    response_model=StrategicExecutionExceptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Resolve a strategic execution exception with verification evidence",
)
def resolve_exception(
    exception_id: str,
    request: ResolveExecutionExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicExecutionExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionExceptionsService()
    return service.resolve_exception(
        tenant_id=current_user.tenant_id,
        exception_id=exception_id,
        request=request,
    )


@router.get(
    "/exceptions/{exception_id}",
    response_model=StrategicExecutionExceptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic execution exception by ID",
)
def get_exception(
    exception_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicExecutionExceptionRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionExceptionsService()
    return service.get_exception(
        tenant_id=current_user.tenant_id,
        exception_id=exception_id,
    )


@router.get(
    "/exceptions",
    response_model=List[StrategicExecutionExceptionRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic execution exceptions",
)
def list_exceptions(
    roadmap_id: Optional[str] = Query(None),
    category: Optional[ExecutionExceptionCategory] = Query(None),
    status_filter: Optional[ExecutionExceptionStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicExecutionExceptionRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionExceptionsService()
    return service.list_exceptions(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        category=category,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# I. Strategic Review Packages & Routine Scan Endpoints
# =============================================================================

@router.post(
    "/review-packages",
    response_model=StrategicReviewPackageRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a consolidated executive strategic review package",
)
def generate_review_package(
    request: GenerateReviewPackageRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReviewPackagesService()
    return service.generate_review_package(
        tenant_id=current_user.tenant_id,
        preparer_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/review-packages/{package_id}/refer-phase-72",
    response_model=StrategicReviewPackageRecord,
    status_code=status.HTTP_200_OK,
    summary="Formally refer strategic review package to Phase 72 Management Review",
)
def refer_review_package_to_phase_72(
    package_id: str,
    request: ReferReviewPackageToPhase72Request,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReviewPackagesService()
    return service.refer_to_phase_72(
        tenant_id=current_user.tenant_id,
        referrer_id=current_user.user_id,
        package_id=package_id,
        request=request,
    )


@router.get(
    "/review-packages/{package_id}",
    response_model=StrategicReviewPackageRecord,
    status_code=status.HTTP_200_OK,
    summary="Get strategic review package by ID",
)
def get_review_package(
    package_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategicReviewPackageRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReviewPackagesService()
    return service.get_review_package(
        tenant_id=current_user.tenant_id,
        package_id=package_id,
    )


@router.get(
    "/review-packages",
    response_model=List[StrategicReviewPackageRecord],
    status_code=status.HTTP_200_OK,
    summary="List strategic review packages",
)
def list_review_packages(
    roadmap_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[StrategicReviewPackageRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReviewPackagesService()
    return service.list_review_packages(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/maintenance/routine-scan",
    response_model=ExecutionRoutineScanJobResult,
    status_code=status.HTTP_200_OK,
    summary="Execute idempotent background strategic execution maintenance scan",
)
def run_routine_scan(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ExecutionRoutineScanJobResult:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyExecutionBackgroundService()
    return service.run_routine_scan(tenant_id=current_user.tenant_id)

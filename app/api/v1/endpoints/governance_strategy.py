"""Phase 78: Clinical Safety Governance Strategy REST API Endpoints.

Base Route: /api/v1/governance-strategy

Provides endpoints for:
- Strategic objectives and lifecycle management
- Traceable strategic priority identification and human review
- Multi-year version-controlled roadmaps and controlled revisions
- Capability development target operating states
- Strategic milestones, typed dependencies, cycle detection, and verified completion
- Resource and investment proposals
- Strategy-to-portfolio and milestone-to-implementation coordination
- Strategic risks, delays, conflicts, and issue escalation
- Strategic reporting and scheduled maintenance scans
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

from app.schemas.governance_strategy_objective import (
    ApproveObjectiveRequest,
    CreateObjectiveRequest,
    GovernanceStrategyObjectiveRecord,
    ObjectiveCategory,
    ObjectiveStatus,
    RetireObjectiveRequest,
    SubmitObjectiveRequest,
    UpdateObjectiveRequest,
)
from app.schemas.governance_strategy_priority import (
    GovernanceStrategyPriorityRecord,
    PriorityReviewOutcome,
    ProposePriorityRequest,
    ReviewPriorityRequest,
)
from app.schemas.governance_strategy_roadmap import (
    ApproveRoadmapRequest,
    CreateRoadmapRequest,
    GovernanceStrategyRoadmapRecord,
    ReviseRoadmapRequest,
    RoadmapStatus,
    SubmitRoadmapRequest,
    UpdateRoadmapRequest,
)
from app.schemas.governance_strategy_capability_target import (
    CapabilityDomainEnum,
    CreateCapabilityTargetRequest,
    GovernanceCapabilityTargetRecord,
    UpdateCapabilityTargetRequest,
)
from app.schemas.governance_strategy_milestone import (
    AddDependencyRequest,
    CreateMilestoneRequest,
    DependencyValidationResult,
    GovernanceStrategyMilestoneRecord,
    MilestoneStatus,
    SubmitMilestoneCompletionRequest,
    UpdateMilestoneRequest,
    VerifyMilestoneCompletionRequest,
)
from app.schemas.governance_strategy_resource import (
    CreateResourceProposalRequest,
    GovernanceResourceProposalRecord,
    InvestmentReviewStatus,
    RecordApprovalReferenceRequest,
    ReviewResourceProposalRequest,
)
from app.schemas.governance_strategy_coordination import (
    CreateStrategyIssueRequest,
    EscalateStrategyIssueRequest,
    GovernanceStrategyIssueRecord,
    ImplementationLinkRecord,
    LinkImplementationRequest,
    LinkPortfolioRequest,
    PortfolioLinkRecord,
    ResolveStrategyIssueRequest,
    StrategyIssueStatus,
)
from app.schemas.governance_strategy_reporting import (
    MilestoneScheduleResponse,
    ObjectiveRegisterResponse,
    PortfolioStrategyAlignmentResponse,
    StrategyIssueSummaryResponse,
    StrategyRoadmapOverviewResponse,
    StrategyRoutineScanJobResult,
)

from app.services.governance_strategy_objective_service import (
    GovernanceStrategyObjectiveService,
)
from app.services.governance_strategy_priority_service import (
    GovernanceStrategyPriorityService,
)
from app.services.governance_strategy_roadmap_service import (
    GovernanceStrategyRoadmapService,
)
from app.services.governance_strategy_capability_target_service import (
    GovernanceStrategyCapabilityTargetService,
)
from app.services.governance_strategy_milestone_service import (
    GovernanceStrategyMilestoneService,
)
from app.services.governance_strategy_resource_service import (
    GovernanceStrategyResourceService,
)
from app.services.governance_strategy_coordination_service import (
    GovernanceStrategyCoordinationService,
)
from app.services.governance_strategy_reporting_service import (
    GovernanceStrategyReportingService,
)
from app.services.governance_strategy_background_service import (
    GovernanceStrategyBackgroundService,
)

router = APIRouter(
    prefix="/governance-strategy",
    tags=["Phase 78 - Clinical Safety Governance Strategy & Multi-Year Roadmap"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforces that patient role cannot access governance strategy endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance strategy features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


# =============================================================================
# A. Strategic Objectives Endpoints
# =============================================================================

@router.post(
    "/objectives",
    response_model=GovernanceStrategyObjectiveRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new strategic governance objective in DRAFT status",
)
def create_objective(
    request: CreateObjectiveRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyObjectiveRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.create_objective(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/objectives",
    response_model=List[GovernanceStrategyObjectiveRecord],
    summary="List strategic objectives for current tenant",
)
def list_objectives(
    category: Optional[ObjectiveCategory] = Query(None),
    status_filter: Optional[ObjectiveStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceStrategyObjectiveRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.list_objectives(
        tenant_id=current_user.tenant_id,
        category=category,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/objectives/{objective_id}",
    response_model=GovernanceStrategyObjectiveRecord,
    summary="Get strategic objective by ID",
)
def get_objective(
    objective_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyObjectiveRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.get_objective(
        tenant_id=current_user.tenant_id,
        objective_id=objective_id,
    )


@router.put(
    "/objectives/{objective_id}",
    response_model=GovernanceStrategyObjectiveRecord,
    summary="Update a draft strategic objective",
)
def update_objective(
    objective_id: str,
    request: UpdateObjectiveRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyObjectiveRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.update_objective(
        tenant_id=current_user.tenant_id,
        objective_id=objective_id,
        request=request,
    )


@router.post(
    "/objectives/{objective_id}/submit",
    response_model=GovernanceStrategyObjectiveRecord,
    summary="Submit a draft objective for governance review",
)
def submit_objective(
    objective_id: str,
    request: SubmitObjectiveRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyObjectiveRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.submit_objective(
        tenant_id=current_user.tenant_id,
        objective_id=objective_id,
        request=request,
    )


@router.post(
    "/objectives/{objective_id}/approve",
    response_model=GovernanceStrategyObjectiveRecord,
    summary="Approve a submitted objective with separation of duties enforcement",
)
def approve_objective(
    objective_id: str,
    request: ApproveObjectiveRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyObjectiveRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.approve_objective(
        tenant_id=current_user.tenant_id,
        objective_id=objective_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/objectives/{objective_id}/activate",
    response_model=GovernanceStrategyObjectiveRecord,
    summary="Activate an approved strategic objective",
)
def activate_objective(
    objective_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyObjectiveRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.activate_objective(
        tenant_id=current_user.tenant_id,
        objective_id=objective_id,
    )


@router.post(
    "/objectives/{objective_id}/retire",
    response_model=GovernanceStrategyObjectiveRecord,
    summary="Retire or supersede an objective",
)
def retire_objective(
    objective_id: str,
    request: RetireObjectiveRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyObjectiveRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyObjectiveService()
    return service.retire_objective(
        tenant_id=current_user.tenant_id,
        objective_id=objective_id,
        request=request,
    )


# =============================================================================
# B. Strategic Priorities Endpoints
# =============================================================================

@router.post(
    "/priorities",
    response_model=GovernanceStrategyPriorityRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Propose an evidence-linked strategic priority",
)
def propose_priority(
    request: ProposePriorityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyPriorityRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyPriorityService()
    return service.propose_priority(
        tenant_id=current_user.tenant_id,
        proposer_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/priorities",
    response_model=List[GovernanceStrategyPriorityRecord],
    summary="List proposed strategic priorities",
)
def list_priorities(
    status_filter: Optional[PriorityReviewOutcome] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceStrategyPriorityRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyPriorityService()
    return service.list_priorities(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/priorities/{priority_id}",
    response_model=GovernanceStrategyPriorityRecord,
    summary="Get strategic priority by ID",
)
def get_priority(
    priority_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyPriorityRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyPriorityService()
    return service.get_priority(
        tenant_id=current_user.tenant_id,
        priority_id=priority_id,
    )


@router.post(
    "/priorities/{priority_id}/review",
    response_model=GovernanceStrategyPriorityRecord,
    summary="Review and record outcome for a proposed strategic priority",
)
def review_priority(
    priority_id: str,
    request: ReviewPriorityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyPriorityRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyPriorityService()
    return service.review_priority(
        tenant_id=current_user.tenant_id,
        priority_id=priority_id,
        reviewer_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# C. Strategic Roadmaps Endpoints
# =============================================================================

@router.post(
    "/roadmaps",
    response_model=GovernanceStrategyRoadmapRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new strategic roadmap in DRAFT status",
)
def create_roadmap(
    request: CreateRoadmapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyRoadmapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.create_roadmap(
        tenant_id=current_user.tenant_id,
        owner_id=request.owner_id or current_user.user_id,
        request=request,
    )


@router.get(
    "/roadmaps",
    response_model=List[GovernanceStrategyRoadmapRecord],
    summary="List strategic roadmaps for current tenant",
)
def list_roadmaps(
    status_filter: Optional[RoadmapStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceStrategyRoadmapRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.list_roadmaps(
        tenant_id=current_user.tenant_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/roadmaps/{roadmap_id}",
    response_model=GovernanceStrategyRoadmapRecord,
    summary="Get strategic roadmap by ID",
)
def get_roadmap(
    roadmap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyRoadmapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.get_roadmap(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.put(
    "/roadmaps/{roadmap_id}",
    response_model=GovernanceStrategyRoadmapRecord,
    summary="Update a draft strategic roadmap",
)
def update_roadmap(
    roadmap_id: str,
    request: UpdateRoadmapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyRoadmapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.update_roadmap(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        request=request,
    )


@router.post(
    "/roadmaps/{roadmap_id}/submit",
    response_model=GovernanceStrategyRoadmapRecord,
    summary="Submit a draft roadmap for governance approval",
)
def submit_roadmap(
    roadmap_id: str,
    request: SubmitRoadmapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyRoadmapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.submit_roadmap(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        request=request,
    )


@router.post(
    "/roadmaps/{roadmap_id}/approve",
    response_model=GovernanceStrategyRoadmapRecord,
    summary="Approve a submitted roadmap with separation of duties enforcement",
)
def approve_roadmap(
    roadmap_id: str,
    request: ApproveRoadmapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyRoadmapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.approve_roadmap(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/roadmaps/{roadmap_id}/activate",
    response_model=GovernanceStrategyRoadmapRecord,
    summary="Activate an approved roadmap",
)
def activate_roadmap(
    roadmap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyRoadmapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.activate_roadmap(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.post(
    "/roadmaps/{roadmap_id}/revise",
    response_model=GovernanceStrategyRoadmapRecord,
    summary="Formally revise an approved roadmap, incrementing version and preserving history",
)
def revise_roadmap(
    roadmap_id: str,
    request: ReviseRoadmapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyRoadmapRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyRoadmapService()
    return service.revise_roadmap(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        reviser_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# D. Capability Targets Endpoints
# =============================================================================

@router.post(
    "/capability-targets",
    response_model=GovernanceCapabilityTargetRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a capability development target operating state proposal",
)
def create_capability_target(
    request: CreateCapabilityTargetRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceCapabilityTargetRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCapabilityTargetService()
    return service.create_target(
        tenant_id=current_user.tenant_id,
        request=request,
    )


@router.get(
    "/capability-targets",
    response_model=List[GovernanceCapabilityTargetRecord],
    summary="List capability development targets",
)
def list_capability_targets(
    domain: Optional[CapabilityDomainEnum] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceCapabilityTargetRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCapabilityTargetService()
    return service.list_targets(
        tenant_id=current_user.tenant_id,
        domain=domain,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/capability-targets/{target_id}",
    response_model=GovernanceCapabilityTargetRecord,
    summary="Get capability development target by ID",
)
def get_capability_target(
    target_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceCapabilityTargetRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCapabilityTargetService()
    return service.get_target(
        tenant_id=current_user.tenant_id,
        target_id=target_id,
    )


@router.put(
    "/capability-targets/{target_id}",
    response_model=GovernanceCapabilityTargetRecord,
    summary="Update a capability development target proposal",
)
def update_capability_target(
    target_id: str,
    request: UpdateCapabilityTargetRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceCapabilityTargetRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCapabilityTargetService()
    return service.update_target(
        tenant_id=current_user.tenant_id,
        target_id=target_id,
        request=request,
    )


# =============================================================================
# E. Milestones & Dependencies Endpoints
# =============================================================================

@router.post(
    "/milestones",
    response_model=GovernanceStrategyMilestoneRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a strategic milestone in a roadmap",
)
def create_milestone(
    request: CreateMilestoneRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyMilestoneRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.create_milestone(
        tenant_id=current_user.tenant_id,
        request=request,
    )


@router.get(
    "/milestones",
    response_model=List[GovernanceStrategyMilestoneRecord],
    summary="List strategic roadmap milestones",
)
def list_milestones(
    roadmap_id: Optional[str] = Query(None),
    status_filter: Optional[MilestoneStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceStrategyMilestoneRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.list_milestones(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/milestones/{milestone_id}",
    response_model=GovernanceStrategyMilestoneRecord,
    summary="Get strategic milestone by ID",
)
def get_milestone(
    milestone_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyMilestoneRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.get_milestone(
        tenant_id=current_user.tenant_id,
        milestone_id=milestone_id,
    )


@router.put(
    "/milestones/{milestone_id}",
    response_model=GovernanceStrategyMilestoneRecord,
    summary="Update a strategic milestone",
)
def update_milestone(
    milestone_id: str,
    request: UpdateMilestoneRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyMilestoneRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.update_milestone(
        tenant_id=current_user.tenant_id,
        milestone_id=milestone_id,
        request=request,
    )


@router.post(
    "/milestones/{milestone_id}/dependencies",
    response_model=GovernanceStrategyMilestoneRecord,
    summary="Add a typed dependency to a milestone with cycle detection",
)
def add_dependency(
    milestone_id: str,
    request: AddDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyMilestoneRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.add_dependency(
        tenant_id=current_user.tenant_id,
        milestone_id=milestone_id,
        request=request,
    )


@router.get(
    "/roadmaps/{roadmap_id}/validate-dependencies",
    response_model=DependencyValidationResult,
    summary="Validate dependency graph integrity, cycles, and sequencing conflicts",
)
def validate_dependencies(
    roadmap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DependencyValidationResult:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.validate_dependencies(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.post(
    "/milestones/{milestone_id}/submit-completion",
    response_model=GovernanceStrategyMilestoneRecord,
    summary="Submit milestone completion with required evidence reference",
)
def submit_milestone_completion(
    milestone_id: str,
    request: SubmitMilestoneCompletionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyMilestoneRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.submit_completion(
        tenant_id=current_user.tenant_id,
        milestone_id=milestone_id,
        request=request,
    )


@router.post(
    "/milestones/{milestone_id}/verify-completion",
    response_model=GovernanceStrategyMilestoneRecord,
    summary="Verify milestone completion with separation of duties enforcement",
)
def verify_milestone_completion(
    milestone_id: str,
    request: VerifyMilestoneCompletionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyMilestoneRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyMilestoneService()
    return service.verify_completion(
        tenant_id=current_user.tenant_id,
        milestone_id=milestone_id,
        verifier_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# F. Resource & Investment Proposals Endpoints
# =============================================================================

@router.post(
    "/resource-proposals",
    response_model=GovernanceResourceProposalRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a strategic resource and investment proposal",
)
def create_resource_proposal(
    request: CreateResourceProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceResourceProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyResourceService()
    return service.create_proposal(
        tenant_id=current_user.tenant_id,
        proposer_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/resource-proposals",
    response_model=List[GovernanceResourceProposalRecord],
    summary="List strategic resource proposals",
)
def list_resource_proposals(
    roadmap_id: Optional[str] = Query(None),
    status_filter: Optional[InvestmentReviewStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceResourceProposalRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyResourceService()
    return service.list_proposals(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/resource-proposals/{proposal_id}",
    response_model=GovernanceResourceProposalRecord,
    summary="Get strategic resource proposal by ID",
)
def get_resource_proposal(
    proposal_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceResourceProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyResourceService()
    return service.get_proposal(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
    )


@router.post(
    "/resource-proposals/{proposal_id}/review",
    response_model=GovernanceResourceProposalRecord,
    summary="Record governance review of a resource proposal with separation of duties",
)
def review_resource_proposal(
    proposal_id: str,
    request: ReviewResourceProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceResourceProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyResourceService()
    return service.review_proposal(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
        reviewer_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/resource-proposals/{proposal_id}/approval-reference",
    response_model=GovernanceResourceProposalRecord,
    summary="Record external financial or executive management governance approval reference",
)
def record_approval_reference(
    proposal_id: str,
    request: RecordApprovalReferenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceResourceProposalRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyResourceService()
    return service.record_approval(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
        request=request,
    )


# =============================================================================
# G. Portfolio Coordination & Strategic Issues Endpoints
# =============================================================================

@router.post(
    "/roadmaps/{roadmap_id}/link-portfolio",
    response_model=PortfolioLinkRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Link an approved strategic objective to an existing Phase 75 portfolio",
)
def link_portfolio(
    roadmap_id: str,
    request: LinkPortfolioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioLinkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.link_portfolio(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        request=request,
    )


@router.post(
    "/roadmaps/{roadmap_id}/link-implementation",
    response_model=ImplementationLinkRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Link a milestone to an existing Phase 73 implementation record",
)
def link_implementation(
    roadmap_id: str,
    request: LinkImplementationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationLinkRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.link_implementation(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        request=request,
    )


@router.get(
    "/roadmaps/{roadmap_id}/portfolio-links",
    response_model=List[PortfolioLinkRecord],
    summary="List portfolio links for a roadmap",
)
def list_portfolio_links(
    roadmap_id: str,
    objective_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[PortfolioLinkRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.list_portfolio_links(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        objective_id=objective_id,
    )


@router.get(
    "/roadmaps/{roadmap_id}/implementation-links",
    response_model=List[ImplementationLinkRecord],
    summary="List implementation links for a roadmap",
)
def list_implementation_links(
    roadmap_id: str,
    milestone_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationLinkRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.list_implementation_links(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        milestone_id=milestone_id,
    )


@router.post(
    "/issues",
    response_model=GovernanceStrategyIssueRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record an identified strategic delivery conflict, delay, or risk",
)
def create_issue(
    request: CreateStrategyIssueRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyIssueRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.create_issue(
        tenant_id=current_user.tenant_id,
        detector_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/issues",
    response_model=List[GovernanceStrategyIssueRecord],
    summary="List strategic delivery issues",
)
def list_issues(
    roadmap_id: Optional[str] = Query(None),
    status_filter: Optional[StrategyIssueStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceStrategyIssueRecord]:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.list_issues(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/issues/{issue_id}",
    response_model=GovernanceStrategyIssueRecord,
    summary="Get strategic issue by ID",
)
def get_issue(
    issue_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyIssueRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.get_issue(
        tenant_id=current_user.tenant_id,
        issue_id=issue_id,
    )


@router.post(
    "/issues/{issue_id}/escalate",
    response_model=GovernanceStrategyIssueRecord,
    summary="Escalate strategic issue to an authoritative workflow (Phase 63, 67, 49, 54, 72)",
)
def escalate_issue(
    issue_id: str,
    request: EscalateStrategyIssueRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyIssueRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.escalate_issue(
        tenant_id=current_user.tenant_id,
        issue_id=issue_id,
        request=request,
    )


@router.post(
    "/issues/{issue_id}/resolve",
    response_model=GovernanceStrategyIssueRecord,
    summary="Resolve a strategic delivery issue",
)
def resolve_issue(
    issue_id: str,
    request: ResolveStrategyIssueRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceStrategyIssueRecord:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyCoordinationService()
    return service.resolve_issue(
        tenant_id=current_user.tenant_id,
        issue_id=issue_id,
        request=request,
    )


# =============================================================================
# H. Reports & Scheduled Background Processing Endpoints
# =============================================================================

@router.get(
    "/reports/roadmaps/{roadmap_id}/overview",
    response_model=StrategyRoadmapOverviewResponse,
    summary="Get strategic roadmap overview report",
)
def get_roadmap_overview(
    roadmap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategyRoadmapOverviewResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReportingService()
    return service.get_roadmap_overview(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.get(
    "/reports/roadmaps/{roadmap_id}/milestones",
    response_model=MilestoneScheduleResponse,
    summary="Get milestone schedule report",
)
def get_milestone_schedule(
    roadmap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> MilestoneScheduleResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReportingService()
    return service.get_milestone_schedule(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.get(
    "/reports/objectives",
    response_model=ObjectiveRegisterResponse,
    summary="Get strategic objectives register report",
)
def get_objective_register(
    roadmap_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ObjectiveRegisterResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReportingService()
    return service.get_objective_register(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.get(
    "/reports/roadmaps/{roadmap_id}/portfolio-alignment",
    response_model=PortfolioStrategyAlignmentResponse,
    summary="Get portfolio-to-strategy alignment analysis report",
)
def get_portfolio_alignment(
    roadmap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> PortfolioStrategyAlignmentResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReportingService()
    return service.get_portfolio_alignment(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.get(
    "/reports/roadmaps/{roadmap_id}/issues",
    response_model=StrategyIssueSummaryResponse,
    summary="Get strategic issue and delivery risk summary report",
)
def get_issue_summary(
    roadmap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategyIssueSummaryResponse:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyReportingService()
    return service.get_issue_summary(
        tenant_id=current_user.tenant_id,
        roadmap_id=roadmap_id,
    )


@router.post(
    "/maintenance/routine-scan",
    response_model=StrategyRoutineScanJobResult,
    summary="Execute idempotent background scheduled strategic maintenance scan",
)
def run_routine_scan(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> StrategyRoutineScanJobResult:
    _ensure_not_patient(current_user)
    service = GovernanceStrategyBackgroundService()
    return service.run_strategy_routine_scan(
        tenant_id=current_user.tenant_id,
    )

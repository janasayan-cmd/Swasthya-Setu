"""Phase 73: Clinical Safety Governance Decision Implementation REST API Endpoints.

Provides comprehensive HTTP APIs for:
- Approved management decision intake and eligibility verification
- Centralized decision implementation initiative registration
- Structured plan creation, versioning, and approvals
- Ownership assignment, acceptance tracking, and separation of duties enforcement
- Prerequisites and dependency tracking with circular dependency detection
- Milestone lifecycle, evidence indexing, and independent verification
- Destination workflow coordination (Phases 49, 54, 55, 63, 67, 69, 70)
- Outcome and intended-result reconciliation against approved decisions
- Implementation exceptions and decision change-impact coordination
- Controlled closure readiness checks, closure, reopening, and executive reporting

Base Path: /api/v1/governance-decision-implementation
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.decision_implementation_intake import (
    DecisionIntakeRecord,
    DecisionIntakeRequest,
)
from app.schemas.decision_implementation_register import (
    ApproveImplementationRequest,
    CreateImplementationRequest,
    DecisionImplementationRecord,
    SubmitImplementationRequest,
    UpdateImplementationRequest,
)
from app.schemas.decision_implementation_planning import (
    ApprovePlanRequest,
    CreatePlanRequest,
    ImplementationPlanRecord,
    SubmitPlanRequest,
    UpdatePlanRequest,
)
from app.schemas.decision_implementation_ownership_dependencies import (
    AcceptAssignmentRequest,
    CreateAssignmentRequest,
    CreateDependencyRequest,
    ImplementationAssignmentRecord,
    ImplementationDependencyRecord,
    ReconcileDependencyRequest,
    UpdateAssignmentRequest,
    WaiveDependencyRequest,
)
from app.schemas.decision_implementation_milestones_evidence import (
    CreateMilestoneRequest,
    ImplementationEvidenceRecord,
    ImplementationMilestoneRecord,
    ImplementationVerificationRecord,
    ReviewEvidenceRequest,
    SubmitEvidenceRequest,
    SubmitMilestoneRequest,
    UpdateMilestoneRequest,
    VerifyMilestoneRequest,
)
from app.schemas.decision_implementation_handoffs_outcomes import (
    AssessOutcomeRequest,
    CreateHandoffRequest,
    DecisionChangeImpactRecord,
    ImplementationExceptionRecord,
    OutcomeAssessmentRecord,
    ReconcileHandoffRequest,
    ReferExceptionRequest,
    ReviewChangeImpactRequest,
    WorkflowHandoffRecord,
)
from app.schemas.decision_implementation_closure_reports import (
    CloseImplementationRequest,
    GenerateImplementationReportRequest,
    ImplementationClosureCheckResponse,
    ImplementationOverviewResponse,
    ImplementationReportRecord,
    ReopenImplementationRequest,
)
from app.services.decision_implementation_intake_service import (
    DecisionIntakeService,
)
from app.services.decision_implementation_register_service import (
    DecisionImplementationRegisterService,
)
from app.services.decision_implementation_planning_service import (
    ImplementationPlanningService,
)
from app.services.decision_implementation_ownership_service import (
    ImplementationOwnershipService,
)
from app.services.decision_implementation_dependency_service import (
    ImplementationDependencyService,
)
from app.services.decision_implementation_milestone_service import (
    ImplementationMilestoneService,
)
from app.services.decision_implementation_coordination_service import (
    DecisionImplementationCoordinationService,
)
from app.services.decision_implementation_closure_service import (
    DecisionImplementationClosureService,
)

router = APIRouter(
    prefix="/governance-decision-implementation",
    tags=["Phase 73 - Clinical Safety Governance Decision Implementation & Outcome Assurance"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforce that patient role cannot access decision implementation governance endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access clinical safety governance decision implementation features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _get_services():
    return (
        DecisionIntakeService(),
        DecisionImplementationRegisterService(),
        ImplementationPlanningService(),
        ImplementationOwnershipService(),
        ImplementationDependencyService(),
        ImplementationMilestoneService(),
        DecisionImplementationCoordinationService(),
        DecisionImplementationClosureService(),
    )


# =============================================================================
# 1. MANAGEMENT OVERSIGHT REPORTING (Placed before parameterized routes)
# =============================================================================

@router.get(
    "/reports/overview",
    response_model=ImplementationOverviewResponse,
    summary="Get aggregated management oversight metrics on decision implementations",
)
def get_reports_overview(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationOverviewResponse:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, _, closure_svc = _get_services()
    return closure_svc.get_overview(current_user.organization_id)


@router.get(
    "/reports/overdue",
    response_model=List[ImplementationMilestoneRecord],
    summary="List overdue implementation milestones across initiatives",
)
def get_overdue_milestones(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationMilestoneRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, _, milestone_svc, _, _ = _get_services()
    return milestone_svc.list_milestones(is_overdue=True)


@router.get(
    "/reports/outcomes",
    response_model=List[OutcomeAssessmentRecord],
    summary="List all outcome assessments across implementations",
)
def get_outcomes_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[OutcomeAssessmentRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    outcomes = list(coord_svc.repository._outcomes.values())
    return outcomes


@router.post(
    "/reports/generate",
    response_model=ImplementationReportRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a formal oversight report",
)
def generate_report(
    request: GenerateImplementationReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationReportRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, _, closure_svc = _get_services()
    return closure_svc.generate_report(
        request=request,
        generator_id=str(current_user.user_id),
        organization_id=current_user.organization_id,
    )


@router.get(
    "/reports/{report_id}",
    response_model=ImplementationReportRecord,
    summary="Get a generated oversight report by ID",
)
def get_report(
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationReportRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, _, closure_svc = _get_services()
    return closure_svc.get_report(report_id)


# =============================================================================
# 2. DECISION INTAKE
# =============================================================================

@router.post(
    "/decisions/intake",
    response_model=DecisionIntakeRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an approved management decision from Phase 72",
)
def ingest_decision(
    request: DecisionIntakeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionIntakeRecord:
    _ensure_not_patient(current_user)
    intake_svc, _, _, _, _, _, _, _ = _get_services()
    return intake_svc.ingest_decision(
        request=request,
        ingested_by=str(current_user.user_id),
        organization_id=current_user.organization_id,
    )


@router.get(
    "/decisions",
    response_model=List[DecisionIntakeRecord],
    summary="List ingested decision records",
)
def list_intakes(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[DecisionIntakeRecord]:
    _ensure_not_patient(current_user)
    intake_svc, _, _, _, _, _, _, _ = _get_services()
    return intake_svc.list_intakes(
        organization_id=current_user.organization_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/decisions/{decision_id}/implementation-status",
    response_model=Dict[str, Any],
    summary="Check implementation status for a given decision ID",
)
def get_decision_implementation_status(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, _ = _get_services()
    imp = reg_svc.repository.get_implementation_by_decision(decision_id)
    if not imp:
        return {"decision_id": decision_id, "is_implemented": False, "status": "NOT_REGISTERED"}
    return {
        "decision_id": decision_id,
        "implementation_id": imp.implementation_id,
        "is_implemented": imp.status.value in ["VERIFIED", "RECONCILED", "CLOSED"],
        "status": imp.status.value,
        "responsible_owner_id": imp.responsible_owner_id,
        "target_completion_date": imp.target_completion_date.isoformat(),
    }


# =============================================================================
# 3. IMPLEMENTATION REGISTER
# =============================================================================

@router.post(
    "/implementations",
    response_model=DecisionImplementationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new decision implementation initiative",
)
def create_implementation(
    request: CreateImplementationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionImplementationRecord:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, _ = _get_services()
    return reg_svc.create_implementation(
        request=request,
        creator_id=str(current_user.user_id),
        organization_id=current_user.organization_id,
    )


@router.get(
    "/implementations",
    response_model=List[DecisionImplementationRecord],
    summary="List decision implementation initiatives",
)
def list_implementations(
    facility_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[DecisionImplementationRecord]:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, _ = _get_services()
    return reg_svc.list_implementations(
        organization_id=current_user.organization_id,
        facility_id=facility_id,
        status_filter=status_filter,
        category=category,
        priority=priority,
        owner_id=owner_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/implementations/{implementation_id}",
    response_model=DecisionImplementationRecord,
    summary="Get an implementation initiative by ID",
)
def get_implementation(
    implementation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionImplementationRecord:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, _ = _get_services()
    return reg_svc.get_implementation(implementation_id)


@router.patch(
    "/implementations/{implementation_id}",
    response_model=DecisionImplementationRecord,
    summary="Update implementation initiative details",
)
def update_implementation(
    implementation_id: str,
    request: UpdateImplementationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionImplementationRecord:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, _ = _get_services()
    return reg_svc.update_implementation(implementation_id, request)


@router.post(
    "/implementations/{implementation_id}/submit",
    response_model=DecisionImplementationRecord,
    summary="Submit implementation initiative for approval",
)
def submit_implementation(
    implementation_id: str,
    request: SubmitImplementationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionImplementationRecord:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, _ = _get_services()
    return reg_svc.submit_implementation(implementation_id, request)


@router.post(
    "/implementations/{implementation_id}/approve",
    response_model=DecisionImplementationRecord,
    summary="Formally approve an implementation initiative",
)
def approve_implementation(
    implementation_id: str,
    request: ApproveImplementationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionImplementationRecord:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, _ = _get_services()
    return reg_svc.approve_implementation(
        implementation_id, request, approver_id=str(current_user.user_id)
    )


# =============================================================================
# 4. IMPLEMENTATION PLANS
# =============================================================================

@router.post(
    "/implementations/{implementation_id}/plans",
    response_model=ImplementationPlanRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create or version a structured implementation plan",
)
def create_plan(
    implementation_id: str,
    request: CreatePlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationPlanRecord:
    _ensure_not_patient(current_user)
    _, _, plan_svc, _, _, _, _, _ = _get_services()
    return plan_svc.create_plan(
        implementation_id=implementation_id,
        request=request,
        creator_id=str(current_user.user_id),
    )


@router.get(
    "/implementations/{implementation_id}/plans",
    response_model=List[ImplementationPlanRecord],
    summary="List plans for an implementation",
)
def list_plans(
    implementation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationPlanRecord]:
    _ensure_not_patient(current_user)
    _, _, plan_svc, _, _, _, _, _ = _get_services()
    return plan_svc.list_plans(implementation_id)


@router.get(
    "/plans/{plan_id}",
    response_model=ImplementationPlanRecord,
    summary="Get plan by ID",
)
def get_plan(
    plan_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationPlanRecord:
    _ensure_not_patient(current_user)
    _, _, plan_svc, _, _, _, _, _ = _get_services()
    return plan_svc.get_plan(plan_id)


@router.patch(
    "/plans/{plan_id}",
    response_model=ImplementationPlanRecord,
    summary="Update a draft plan",
)
def update_plan(
    plan_id: str,
    request: UpdatePlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationPlanRecord:
    _ensure_not_patient(current_user)
    _, _, plan_svc, _, _, _, _, _ = _get_services()
    return plan_svc.update_plan(plan_id, request)


@router.post(
    "/plans/{plan_id}/submit",
    response_model=ImplementationPlanRecord,
    summary="Submit plan for approval",
)
def submit_plan(
    plan_id: str,
    request: SubmitPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationPlanRecord:
    _ensure_not_patient(current_user)
    _, _, plan_svc, _, _, _, _, _ = _get_services()
    return plan_svc.submit_plan(plan_id, request)


@router.post(
    "/plans/{plan_id}/approve",
    response_model=ImplementationPlanRecord,
    summary="Approve an implementation plan",
)
def approve_plan(
    plan_id: str,
    request: ApprovePlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationPlanRecord:
    _ensure_not_patient(current_user)
    _, _, plan_svc, _, _, _, _, _ = _get_services()
    return plan_svc.approve_plan(
        plan_id=plan_id, request=request, approver_id=str(current_user.user_id)
    )


# =============================================================================
# 5. OWNERSHIP ASSIGNMENTS & SEPARATION OF DUTIES
# =============================================================================

@router.post(
    "/implementations/{implementation_id}/assignments",
    response_model=ImplementationAssignmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an implementation role, enforcing separation of duties",
)
def create_assignment(
    implementation_id: str,
    request: CreateAssignmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationAssignmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, owner_svc, _, _, _, _ = _get_services()
    return owner_svc.create_assignment(
        implementation_id=implementation_id,
        request=request,
        assigned_by=str(current_user.user_id),
    )


@router.get(
    "/implementations/{implementation_id}/assignments",
    response_model=List[ImplementationAssignmentRecord],
    summary="List assignments for an implementation",
)
def list_assignments(
    implementation_id: str,
    user_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationAssignmentRecord]:
    _ensure_not_patient(current_user)
    _, _, _, owner_svc, _, _, _, _ = _get_services()
    return owner_svc.list_assignments(implementation_id, user_id=user_id, role=role)


@router.patch(
    "/assignments/{assignment_id}",
    response_model=ImplementationAssignmentRecord,
    summary="Update assignment details",
)
def update_assignment(
    assignment_id: str,
    request: UpdateAssignmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationAssignmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, owner_svc, _, _, _, _ = _get_services()
    return owner_svc.update_assignment(assignment_id, request)


@router.post(
    "/assignments/{assignment_id}/accept",
    response_model=ImplementationAssignmentRecord,
    summary="Accept, decline, or delegate an assigned role",
)
def accept_assignment(
    assignment_id: str,
    request: AcceptAssignmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationAssignmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, owner_svc, _, _, _, _ = _get_services()
    return owner_svc.accept_assignment(
        assignment_id=assignment_id,
        user_id=str(current_user.user_id),
        request=request,
    )


# =============================================================================
# 6. DEPENDENCIES & PREREQUISITES
# =============================================================================

@router.post(
    "/implementations/{implementation_id}/dependencies",
    response_model=ImplementationDependencyRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Link a prerequisite dependency, detecting circular dependencies",
)
def create_dependency(
    implementation_id: str,
    request: CreateDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationDependencyRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, dep_svc, _, _, _ = _get_services()
    return dep_svc.create_dependency(implementation_id=implementation_id, request=request)


@router.get(
    "/implementations/{implementation_id}/dependencies",
    response_model=List[ImplementationDependencyRecord],
    summary="List dependencies for an implementation",
)
def list_dependencies(
    implementation_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationDependencyRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, dep_svc, _, _, _ = _get_services()
    return dep_svc.list_dependencies(implementation_id, status_filter=status_filter)


@router.post(
    "/dependencies/{dependency_id}/reconcile",
    response_model=ImplementationDependencyRecord,
    summary="Reconcile dependency status against source workflow",
)
def reconcile_dependency(
    dependency_id: str,
    request: ReconcileDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationDependencyRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, dep_svc, _, _, _ = _get_services()
    return dep_svc.reconcile_dependency(dependency_id=dependency_id, request=request)


@router.post(
    "/dependencies/{dependency_id}/waive",
    response_model=ImplementationDependencyRecord,
    summary="Authorize a formal governance waiver on a dependency",
)
def waive_dependency(
    dependency_id: str,
    request: WaiveDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationDependencyRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, dep_svc, _, _, _ = _get_services()
    role_str = str(current_user.role.value if hasattr(current_user.role, "value") else current_user.role)
    return dep_svc.waive_dependency(
        dependency_id=dependency_id,
        request=request,
        authorizer_id=str(current_user.user_id),
        authorizer_role=role_str,
    )


# =============================================================================
# 7. MILESTONES & INDEPENDENT VERIFICATION
# =============================================================================

@router.post(
    "/implementations/{implementation_id}/milestones",
    response_model=ImplementationMilestoneRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add an implementation milestone",
)
def create_milestone(
    implementation_id: str,
    request: CreateMilestoneRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationMilestoneRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    return ms_svc.create_milestone(implementation_id=implementation_id, request=request)


@router.get(
    "/implementations/{implementation_id}/milestones",
    response_model=List[ImplementationMilestoneRecord],
    summary="List milestones for an implementation",
)
def list_milestones(
    implementation_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    is_overdue: Optional[bool] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationMilestoneRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    return ms_svc.list_milestones(
        implementation_id=implementation_id,
        status_filter=status_filter,
        is_overdue=is_overdue,
    )


@router.get(
    "/milestones/{milestone_id}",
    response_model=ImplementationMilestoneRecord,
    summary="Get milestone by ID",
)
def get_milestone(
    milestone_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationMilestoneRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    return ms_svc.get_milestone(milestone_id)


@router.patch(
    "/milestones/{milestone_id}",
    response_model=ImplementationMilestoneRecord,
    summary="Update milestone parameters",
)
def update_milestone(
    milestone_id: str,
    request: UpdateMilestoneRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationMilestoneRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    return ms_svc.update_milestone(milestone_id, request)


@router.post(
    "/milestones/{milestone_id}/submit",
    response_model=ImplementationMilestoneRecord,
    summary="Submit milestone completion for review (does NOT auto-verify)",
)
def submit_milestone(
    milestone_id: str,
    request: SubmitMilestoneRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationMilestoneRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    return ms_svc.submit_milestone(
        milestone_id=milestone_id,
        request=request,
        submitter_id=str(current_user.user_id),
    )


@router.post(
    "/milestones/{milestone_id}/verify",
    response_model=ImplementationVerificationRecord,
    summary="Independently verify milestone implementation, enforcing separation of duties",
)
def verify_milestone(
    milestone_id: str,
    request: VerifyMilestoneRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationVerificationRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    role_str = str(current_user.role.value if hasattr(current_user.role, "value") else current_user.role)
    return ms_svc.verify_milestone(
        milestone_id=milestone_id,
        request=request,
        verifier_id=str(current_user.user_id),
        verifier_role=role_str,
    )


# =============================================================================
# 8. EVIDENCE REFERENCES & REVIEW
# =============================================================================

@router.post(
    "/milestones/{milestone_id}/evidence",
    response_model=ImplementationEvidenceRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Attach evidence reference to a milestone",
)
def attach_milestone_evidence(
    milestone_id: str,
    request: SubmitEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationEvidenceRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    milestone = ms_svc.get_milestone(milestone_id)
    request.milestone_id = milestone_id
    return ms_svc.attach_evidence(
        implementation_id=milestone.implementation_id,
        request=request,
        submitter_id=str(current_user.user_id),
    )


@router.get(
    "/milestones/{milestone_id}/evidence",
    response_model=List[ImplementationEvidenceRecord],
    summary="List evidence attached to a milestone",
)
def list_milestone_evidence(
    milestone_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationEvidenceRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    milestone = ms_svc.get_milestone(milestone_id)
    return ms_svc.list_evidence(
        implementation_id=milestone.implementation_id, milestone_id=milestone_id
    )


@router.post(
    "/evidence/{evidence_id}/review",
    response_model=ImplementationEvidenceRecord,
    summary="Review evidence or flag contradictory evidence",
)
def review_evidence(
    evidence_id: str,
    request: ReviewEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationEvidenceRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, ms_svc, _, _ = _get_services()
    return ms_svc.review_evidence(
        evidence_id=evidence_id,
        request=request,
        reviewer_id=str(current_user.user_id),
    )


# =============================================================================
# 9. DESTINATION WORKFLOW DELEGATION HANDOFFS
# =============================================================================

@router.post(
    "/implementations/{implementation_id}/handoffs",
    response_model=WorkflowHandoffRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch implementation action to authoritative destination workflow",
)
def create_handoff(
    implementation_id: str,
    request: CreateHandoffRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> WorkflowHandoffRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.create_handoff(implementation_id=implementation_id, request=request)


@router.get(
    "/implementations/{implementation_id}/handoffs",
    response_model=List[WorkflowHandoffRecord],
    summary="List destination workflow handoffs for an implementation",
)
def list_handoffs(
    implementation_id: str,
    destination_workflow: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[WorkflowHandoffRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.list_handoffs(
        implementation_id=implementation_id,
        destination_workflow=destination_workflow,
        status_filter=status_filter,
    )


@router.post(
    "/handoffs/{handoff_id}/reconcile",
    response_model=WorkflowHandoffRecord,
    summary="Reconcile status from destination workflow",
)
def reconcile_handoff(
    handoff_id: str,
    request: ReconcileHandoffRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> WorkflowHandoffRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.reconcile_handoff(handoff_id=handoff_id, request=request)


@router.get(
    "/handoffs/{handoff_id}",
    response_model=WorkflowHandoffRecord,
    summary="Get handoff record by ID",
)
def get_handoff(
    handoff_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> WorkflowHandoffRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.get_handoff(handoff_id)


# =============================================================================
# 10. OUTCOME RECONCILIATION
# =============================================================================

@router.post(
    "/implementations/{implementation_id}/outcome-assessment",
    response_model=OutcomeAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Reconcile and assess outcome against original decision",
)
def assess_outcome(
    implementation_id: str,
    request: AssessOutcomeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OutcomeAssessmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.assess_outcome(
        implementation_id=implementation_id,
        request=request,
        assessor_id=str(current_user.user_id),
    )


@router.get(
    "/implementations/{implementation_id}/outcome-assessment",
    response_model=OutcomeAssessmentRecord,
    summary="Get outcome assessment for an implementation",
)
def get_outcome(
    implementation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OutcomeAssessmentRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.get_outcome(implementation_id)


# =============================================================================
# 11. EXCEPTIONS & DECISION CHANGE IMPACT
# =============================================================================

@router.get(
    "/implementations/{implementation_id}/exceptions",
    response_model=List[ImplementationExceptionRecord],
    summary="List exceptions logged for an implementation",
)
def list_exceptions(
    implementation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ImplementationExceptionRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.list_exceptions(implementation_id)


@router.post(
    "/implementations/{implementation_id}/exceptions/{exception_id}/refer",
    response_model=ImplementationExceptionRecord,
    summary="Refer an implementation exception to Phase 67 governance escalation",
)
def refer_exception(
    implementation_id: str,
    exception_id: str,
    request: ReferExceptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationExceptionRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.refer_exception(exception_id=exception_id, request=request)


@router.post(
    "/implementations/{implementation_id}/change-impact/review",
    response_model=DecisionChangeImpactRecord,
    summary="Assess and record authorized disposition when decision is amended or superseded",
)
def review_change_impact(
    implementation_id: str,
    request: ReviewChangeImpactRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionChangeImpactRecord:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.review_change_impact(
        implementation_id=implementation_id,
        request=request,
        reviewer_id=str(current_user.user_id),
    )


@router.get(
    "/implementations/{implementation_id}/change-impact",
    response_model=List[DecisionChangeImpactRecord],
    summary="List decision change impact assessments for an implementation",
)
def list_change_impacts(
    implementation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[DecisionChangeImpactRecord]:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, coord_svc, _ = _get_services()
    return coord_svc.list_impacts(implementation_id=implementation_id)


# =============================================================================
# 12. IMPLEMENTATION CLOSURE & REOPENING
# =============================================================================

@router.post(
    "/implementations/{implementation_id}/closure-check",
    response_model=ImplementationClosureCheckResponse,
    summary="Evaluate readiness and gating blockers for implementation closure",
)
def check_closure_readiness(
    implementation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ImplementationClosureCheckResponse:
    _ensure_not_patient(current_user)
    _, _, _, _, _, _, _, closure_svc = _get_services()
    return closure_svc.check_closure_readiness(implementation_id)


@router.post(
    "/implementations/{implementation_id}/close",
    response_model=DecisionImplementationRecord,
    summary="Close an implementation initiative after verifying all prerequisites",
)
def close_implementation(
    implementation_id: str,
    request: CloseImplementationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionImplementationRecord:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, closure_svc = _get_services()
    closure_svc.close_implementation(
        implementation_id=implementation_id,
        request=request,
        closer_id=str(current_user.user_id),
    )
    return reg_svc.get_implementation(implementation_id)


@router.post(
    "/implementations/{implementation_id}/reopen",
    response_model=DecisionImplementationRecord,
    summary="Reopen a closed implementation initiative",
)
def reopen_implementation(
    implementation_id: str,
    request: ReopenImplementationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionImplementationRecord:
    _ensure_not_patient(current_user)
    _, reg_svc, _, _, _, _, _, closure_svc = _get_services()
    closure_svc.reopen_implementation(
        implementation_id=implementation_id,
        request=request,
        reopener_id=str(current_user.user_id),
    )
    return reg_svc.get_implementation(implementation_id)

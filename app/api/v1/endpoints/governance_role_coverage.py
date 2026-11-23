"""Phase 85: Clinical Safety Governance Resilience Role-Coverage REST API Endpoints.

Base Route: /api/v1/governance-resilience-role-coverage

Provides endpoints for:
- Critical governance role and responsibility inventory
- Role-coverage mapping and designated backup coordination
- Backup competency and authorization verification
- Single-person dependency detection and personnel bottleneck analysis
- Coverage scenario stress testing and advisory evaluation
- Succession readiness plans and candidate pipelines
- Structured role transition and open governance item handovers
- Role-coverage gap tracking, remedial assignment, and authoritative escalation
- Executive and operational role-coverage reporting
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Common
from app.schemas.governance_role_coverage_common import (
    BackupVerificationStatus,
    CoverageArrangementStatus,
    CoverageGapCategory,
    CoverageGapStatus,
    CriticalityTier,
    CoverageScope,
    HandoverStatus,
    ScenarioType,
    SuccessionPlanStatus,
)

# Schemas
from app.schemas.governance_role_responsibility import (
    CreateCriticalResponsibilityRequest,
    CriticalGovernanceResponsibilityRecord,
    ReviewCriticalResponsibilityRequest,
    UpdateCriticalResponsibilityRequest,
)
from app.schemas.governance_role_coverage_mapping import (
    ApproveCoverageArrangementRequest,
    CloseCoverageArrangementRequest,
    CreateCoverageArrangementRequest,
    RoleCoverageArrangementRecord,
    SubmitCoverageArrangementRequest,
    SuspendCoverageArrangementRequest,
    UpdateCoverageArrangementRequest,
)
from app.schemas.governance_role_backup_verification import (
    BackupVerificationRecord,
    RecheckBackupVerificationRequest,
    VerifyBackupRequest,
)
from app.schemas.governance_role_dependency_analysis import (
    PersonnelConcentrationRecord,
    RunDependencyAnalysisRequest,
    SinglePersonDependencyRecord,
)
from app.schemas.governance_role_coverage_scenario import (
    CoverageScenarioEvaluationRecord,
    EvaluateCoverageScenarioRequest,
)
from app.schemas.governance_role_succession import (
    ApproveSuccessionPlanRequest,
    CreateSuccessionPlanRequest,
    ReviewSuccessionPlanRequest,
    SuccessionPlanRecord,
    UpdateSuccessionPlanRequest,
)
from app.schemas.governance_role_handover import (
    AcknowledgeHandoverRequest,
    CancelHandoverRequest,
    CompleteHandoverRequest,
    InitiateHandoverRequest,
    RoleHandoverRecord,
)
from app.schemas.governance_role_coverage_gap import (
    AssignCoverageGapRequest,
    CreateCoverageGapRequest,
    EscalateCoverageGapRequest,
    ResolveCoverageGapRequest,
    RoleCoverageGapRecord,
)
from app.schemas.governance_role_coverage_reporting import (
    BackupReadinessDeficienciesReport,
    ExpiringCoverageScheduleReport,
    RoleCoverageSummaryReport,
    SinglePersonDependencyReport,
)

# Services
from app.services.governance_role_responsibility_service import (
    get_governance_role_responsibility_service,
)
from app.services.governance_role_coverage_mapping_service import (
    get_governance_role_coverage_mapping_service,
)
from app.services.governance_role_backup_verification_service import (
    get_governance_role_backup_verification_service,
)
from app.services.governance_role_dependency_analysis_service import (
    get_governance_role_dependency_analysis_service,
)
from app.services.governance_role_coverage_scenario_service import (
    get_governance_role_coverage_scenario_service,
)
from app.services.governance_role_succession_service import (
    get_governance_role_succession_service,
)
from app.services.governance_role_handover_service import (
    get_governance_role_handover_service,
)
from app.services.governance_role_coverage_gap_service import (
    get_governance_role_coverage_gap_service,
)
from app.services.governance_role_coverage_reporting_service import (
    get_governance_role_coverage_reporting_service,
)


def _ensure_not_patient(current_user: AuthenticatedUserContext = Depends(get_current_user)) -> None:
    """Patients cannot access governance resilience role-coverage operations."""
    if current_user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patients are not permitted to access clinical safety governance resilience role-coverage operations.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


router = APIRouter(
    prefix="/governance-resilience-role-coverage",
    tags=["Clinical Safety Governance Resilience Role-Coverage & Succession"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# 1. Critical Governance Responsibilities
# =============================================================================

@router.post(
    "/responsibilities",
    response_model=CriticalGovernanceResponsibilityRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_critical_responsibility(
    request: CreateCriticalResponsibilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_responsibility_service()
    return service.create_responsibility(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/responsibilities",
    response_model=List[CriticalGovernanceResponsibilityRecord],
)
def list_critical_responsibilities(
    criticality_tier: Optional[CriticalityTier] = Query(None),
    scope: Optional[CoverageScope] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_responsibility_service()
    return service.list_responsibilities(
        tenant_id=current_user.tenant_id,
        criticality_tier=criticality_tier,
        scope=scope,
    )


@router.get(
    "/responsibilities/{responsibility_id}",
    response_model=CriticalGovernanceResponsibilityRecord,
)
def get_critical_responsibility(
    responsibility_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_responsibility_service()
    return service.get_responsibility(
        tenant_id=current_user.tenant_id,
        responsibility_id=responsibility_id,
    )


@router.put(
    "/responsibilities/{responsibility_id}",
    response_model=CriticalGovernanceResponsibilityRecord,
)
def update_critical_responsibility(
    responsibility_id: str,
    request: UpdateCriticalResponsibilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_responsibility_service()
    return service.update_responsibility(
        tenant_id=current_user.tenant_id,
        responsibility_id=responsibility_id,
        request=request,
    )


@router.post(
    "/responsibilities/{responsibility_id}/review",
    response_model=CriticalGovernanceResponsibilityRecord,
)
def review_critical_responsibility(
    responsibility_id: str,
    request: ReviewCriticalResponsibilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_responsibility_service()
    return service.review_responsibility(
        tenant_id=current_user.tenant_id,
        responsibility_id=responsibility_id,
        reviewer_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 2. Role-Coverage Arrangements
# =============================================================================

@router.post(
    "/coverages",
    response_model=RoleCoverageArrangementRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_coverage_arrangement(
    request: CreateCoverageArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.create_coverage(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/coverages",
    response_model=List[RoleCoverageArrangementRecord],
)
def list_coverage_arrangements(
    coverage_status: Optional[CoverageArrangementStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.list_coverages(
        tenant_id=current_user.tenant_id,
        coverage_status=coverage_status,
    )


@router.get(
    "/coverages/by-responsibility/{responsibility_id}",
    response_model=Optional[RoleCoverageArrangementRecord],
)
def get_coverage_by_responsibility(
    responsibility_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.get_coverage_by_responsibility(
        tenant_id=current_user.tenant_id,
        responsibility_id=responsibility_id,
    )


@router.get(
    "/coverages/{coverage_id}",
    response_model=RoleCoverageArrangementRecord,
)
def get_coverage_arrangement(
    coverage_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.get_coverage(
        tenant_id=current_user.tenant_id,
        coverage_id=coverage_id,
    )


@router.put(
    "/coverages/{coverage_id}",
    response_model=RoleCoverageArrangementRecord,
)
def update_coverage_arrangement(
    coverage_id: str,
    request: UpdateCoverageArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.update_coverage(
        tenant_id=current_user.tenant_id,
        coverage_id=coverage_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/coverages/{coverage_id}/submit",
    response_model=RoleCoverageArrangementRecord,
)
def submit_coverage_arrangement(
    coverage_id: str,
    request: SubmitCoverageArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.submit_coverage(
        tenant_id=current_user.tenant_id,
        coverage_id=coverage_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/coverages/{coverage_id}/approve",
    response_model=RoleCoverageArrangementRecord,
)
def approve_coverage_arrangement(
    coverage_id: str,
    request: ApproveCoverageArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.approve_coverage(
        tenant_id=current_user.tenant_id,
        coverage_id=coverage_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/coverages/{coverage_id}/suspend",
    response_model=RoleCoverageArrangementRecord,
)
def suspend_coverage_arrangement(
    coverage_id: str,
    request: SuspendCoverageArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.suspend_coverage(
        tenant_id=current_user.tenant_id,
        coverage_id=coverage_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/coverages/{coverage_id}/close",
    response_model=RoleCoverageArrangementRecord,
)
def close_coverage_arrangement(
    coverage_id: str,
    request: CloseCoverageArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_mapping_service()
    return service.close_coverage(
        tenant_id=current_user.tenant_id,
        coverage_id=coverage_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 3. Backup Verifications
# =============================================================================

@router.post(
    "/verifications",
    response_model=BackupVerificationRecord,
    status_code=status.HTTP_201_CREATED,
)
def verify_backup(
    request: VerifyBackupRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_backup_verification_service()
    return service.verify_backup(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/verifications",
    response_model=List[BackupVerificationRecord],
)
def list_backup_verifications(
    coverage_id: Optional[str] = Query(None),
    verification_status: Optional[BackupVerificationStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_backup_verification_service()
    return service.list_verifications(
        tenant_id=current_user.tenant_id,
        coverage_id=coverage_id,
        verification_status=verification_status,
    )


@router.get(
    "/verifications/{verification_id}",
    response_model=BackupVerificationRecord,
)
def get_backup_verification(
    verification_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_backup_verification_service()
    return service.get_verification(
        tenant_id=current_user.tenant_id,
        verification_id=verification_id,
    )


@router.post(
    "/verifications/{verification_id}/recheck",
    response_model=BackupVerificationRecord,
)
def recheck_backup_verification(
    verification_id: str,
    request: RecheckBackupVerificationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_backup_verification_service()
    return service.recheck_verification(
        tenant_id=current_user.tenant_id,
        verification_id=verification_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 4. Single-Person Dependency & Concentration Analysis
# =============================================================================

@router.post("/dependencies/analyze")
def run_dependency_analysis(
    request: RunDependencyAnalysisRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_dependency_analysis_service()
    single_person_deps, concentrations = service.run_dependency_analysis(
        tenant_id=current_user.tenant_id,
        request=request,
    )
    return {
        "single_person_dependencies": single_person_deps,
        "personnel_concentrations": concentrations,
    }


# =============================================================================
# 5. Coverage Scenarios & Stress Testing
# =============================================================================

@router.post(
    "/scenarios/evaluate",
    response_model=CoverageScenarioEvaluationRecord,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_coverage_scenario(
    request: EvaluateCoverageScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_scenario_service()
    return service.evaluate_scenario(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/scenarios",
    response_model=List[CoverageScenarioEvaluationRecord],
)
def list_coverage_scenarios(
    scenario_type: Optional[ScenarioType] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_scenario_service()
    return service.list_scenarios(
        tenant_id=current_user.tenant_id,
        scenario_type=scenario_type,
    )


@router.get(
    "/scenarios/{evaluation_id}",
    response_model=CoverageScenarioEvaluationRecord,
)
def get_coverage_scenario(
    evaluation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_scenario_service()
    return service.get_scenario(
        tenant_id=current_user.tenant_id,
        evaluation_id=evaluation_id,
    )


# =============================================================================
# 6. Succession Readiness Plans
# =============================================================================

@router.post(
    "/succession-plans",
    response_model=SuccessionPlanRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_succession_plan(
    request: CreateSuccessionPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_succession_service()
    return service.create_succession_plan(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/succession-plans",
    response_model=List[SuccessionPlanRecord],
)
def list_succession_plans(
    plan_status: Optional[SuccessionPlanStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_succession_service()
    return service.list_succession_plans(
        tenant_id=current_user.tenant_id,
        plan_status=plan_status,
    )


@router.get(
    "/succession-plans/{succession_plan_id}",
    response_model=SuccessionPlanRecord,
)
def get_succession_plan(
    succession_plan_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_succession_service()
    return service.get_succession_plan(
        tenant_id=current_user.tenant_id,
        succession_plan_id=succession_plan_id,
    )


@router.put(
    "/succession-plans/{succession_plan_id}",
    response_model=SuccessionPlanRecord,
)
def update_succession_plan(
    succession_plan_id: str,
    request: UpdateSuccessionPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_succession_service()
    return service.update_succession_plan(
        tenant_id=current_user.tenant_id,
        succession_plan_id=succession_plan_id,
        request=request,
    )


@router.post(
    "/succession-plans/{succession_plan_id}/approve",
    response_model=SuccessionPlanRecord,
)
def approve_succession_plan(
    succession_plan_id: str,
    request: ApproveSuccessionPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_succession_service()
    return service.approve_succession_plan(
        tenant_id=current_user.tenant_id,
        succession_plan_id=succession_plan_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/succession-plans/{succession_plan_id}/review",
    response_model=SuccessionPlanRecord,
)
def review_succession_plan(
    succession_plan_id: str,
    request: ReviewSuccessionPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_succession_service()
    return service.review_succession_plan(
        tenant_id=current_user.tenant_id,
        succession_plan_id=succession_plan_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 7. Role Handovers and Transitions
# =============================================================================

@router.post(
    "/handovers",
    response_model=RoleHandoverRecord,
    status_code=status.HTTP_201_CREATED,
)
def initiate_handover(
    request: InitiateHandoverRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_handover_service()
    return service.initiate_handover(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/handovers",
    response_model=List[RoleHandoverRecord],
)
def list_handovers(
    responsibility_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    handover_status: Optional[HandoverStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_handover_service()
    return service.list_handovers(
        tenant_id=current_user.tenant_id,
        responsibility_id=responsibility_id,
        user_id=user_id,
        handover_status=handover_status,
    )


@router.get(
    "/handovers/{handover_id}",
    response_model=RoleHandoverRecord,
)
def get_handover(
    handover_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_handover_service()
    return service.get_handover(
        tenant_id=current_user.tenant_id,
        handover_id=handover_id,
    )


@router.post(
    "/handovers/{handover_id}/acknowledge",
    response_model=RoleHandoverRecord,
)
def acknowledge_handover(
    handover_id: str,
    request: AcknowledgeHandoverRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_handover_service()
    return service.acknowledge_handover(
        tenant_id=current_user.tenant_id,
        handover_id=handover_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/handovers/{handover_id}/complete",
    response_model=RoleHandoverRecord,
)
def complete_handover(
    handover_id: str,
    request: CompleteHandoverRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_handover_service()
    return service.complete_handover(
        tenant_id=current_user.tenant_id,
        handover_id=handover_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/handovers/{handover_id}/cancel",
    response_model=RoleHandoverRecord,
)
def cancel_handover(
    handover_id: str,
    request: CancelHandoverRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_handover_service()
    return service.cancel_handover(
        tenant_id=current_user.tenant_id,
        handover_id=handover_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 8. Role-Coverage Gaps
# =============================================================================

@router.post(
    "/gaps",
    response_model=RoleCoverageGapRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_coverage_gap(
    request: CreateCoverageGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_gap_service()
    return service.create_gap(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get(
    "/gaps",
    response_model=List[RoleCoverageGapRecord],
)
def list_coverage_gaps(
    responsibility_id: Optional[str] = Query(None),
    gap_status: Optional[CoverageGapStatus] = Query(None, alias="status"),
    category: Optional[CoverageGapCategory] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_gap_service()
    return service.list_gaps(
        tenant_id=current_user.tenant_id,
        responsibility_id=responsibility_id,
        gap_status=gap_status,
        category=category,
    )


@router.get(
    "/gaps/{gap_id}",
    response_model=RoleCoverageGapRecord,
)
def get_coverage_gap(
    gap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_gap_service()
    return service.get_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
    )


@router.post(
    "/gaps/{gap_id}/assign",
    response_model=RoleCoverageGapRecord,
)
def assign_coverage_gap(
    gap_id: str,
    request: AssignCoverageGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_gap_service()
    return service.assign_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/gaps/{gap_id}/escalate",
    response_model=RoleCoverageGapRecord,
)
def escalate_coverage_gap(
    gap_id: str,
    request: EscalateCoverageGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_gap_service()
    return service.escalate_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/gaps/{gap_id}/resolve",
    response_model=RoleCoverageGapRecord,
)
def resolve_coverage_gap(
    gap_id: str,
    request: ResolveCoverageGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_gap_service()
    return service.resolve_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        verifier_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 9. Reports
# =============================================================================

@router.get(
    "/reports/summary",
    response_model=RoleCoverageSummaryReport,
)
def get_coverage_summary_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_reporting_service()
    return service.generate_summary_report(tenant_id=current_user.tenant_id)


@router.get(
    "/reports/dependencies",
    response_model=SinglePersonDependencyReport,
)
def get_dependency_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_reporting_service()
    return service.generate_dependency_report(tenant_id=current_user.tenant_id)


@router.get(
    "/reports/deficiencies",
    response_model=BackupReadinessDeficienciesReport,
)
def get_backup_deficiencies_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_reporting_service()
    return service.generate_backup_deficiencies_report(tenant_id=current_user.tenant_id)


@router.get(
    "/reports/expiring-schedule",
    response_model=ExpiringCoverageScheduleReport,
)
def get_expiring_schedule_report(
    days: int = Query(60, ge=1, le=365),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_role_coverage_reporting_service()
    return service.generate_expiring_schedule_report(
        tenant_id=current_user.tenant_id, days_threshold=days
    )

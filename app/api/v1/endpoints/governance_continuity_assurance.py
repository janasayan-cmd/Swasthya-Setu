"""Phase 81: Clinical Safety Governance Continuity Assurance REST API Endpoints.

Base Route: /api/v1/governance-continuity-assurance

Provides endpoints for:
- Continuity assurance frameworks and dimensions
- Controlled continuity plan validation
- Critical capability coverage assurance
- Continuity exercise assurance evaluations (12 exercise types)
- Scenario coverage and advisory stress validation
- Personnel and delegated-authority readiness assurance
- Critical dependency resilience and SPOF assurance
- Recovery performance evaluation against approved RTO/MTPD
- Decision and evidence reconciliation assurance
- Independent continuity validation programmes
- Continuity finding management and authoritative referrals
- Strategic resilience assurance reporting and scans
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Schemas
from app.schemas.governance_continuity_assurance_framework import (
    ApproveFrameworkRequest,
    ContinuityAssuranceFrameworkRecord,
    CreateContinuityAssuranceFrameworkRequest,
    FrameworkStatus,
    SubmitFrameworkRequest,
    UpdateContinuityAssuranceFrameworkRequest,
)
from app.schemas.governance_continuity_assurance_plan import (
    ContinuityPlanValidationRecord,
    CreatePlanValidationRequest,
    ReviewPlanValidationRequest,
)
from app.schemas.governance_continuity_assurance_coverage import (
    ContinuityCoverageAssessmentRecord,
    RunCoverageAssessmentRequest,
)
from app.schemas.governance_continuity_assurance_exercise import (
    ContinuityExerciseAssuranceRecord,
    CreateExerciseAssuranceEvaluationRequest,
)
from app.schemas.governance_continuity_assurance_scenario import (
    ContinuityScenarioAssessmentRecord,
    CreateScenarioAssessmentRequest,
    EvaluateScenarioRequest,
)
from app.schemas.governance_continuity_assurance_personnel import (
    AssessPersonnelReadinessRequest,
    PersonnelReadinessAssuranceRecord,
    VerifyDelegatedAuthorityRequest,
)
from app.schemas.governance_continuity_assurance_dependency import (
    AssessDependencyResilienceRequest,
    DependencyResilienceAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_recovery import (
    AssessRecoveryPerformanceRequest,
    RecoveryPerformanceAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_reconciliation import (
    AssessReconciliationIntegrityRequest,
    ReconciliationAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_programme import (
    AssignEvaluatorRequest,
    CreateValidationProgrammeRequest,
    IndependentValidationProgrammeRecord,
    ProgrammeStatus,
    RecordIndependenceDeclarationRequest,
    SubmitEvidenceRequest,
)
from app.schemas.governance_continuity_assurance_finding import (
    CloseFindingRequest,
    ContinuityAssuranceFindingRecord,
    CreateContinuityFindingRequest,
    FindingStatus,
    ReferFindingRequest,
)
from app.schemas.governance_continuity_assurance_reporting import (
    ContinuityAssuranceReportRecord,
    GenerateReportRequest,
    RoutineScanResult,
)

# Services
from app.services.governance_continuity_assurance_framework_service import (
    governance_continuity_assurance_framework_service,
)
from app.services.governance_continuity_assurance_plan_service import (
    governance_continuity_assurance_plan_service,
)
from app.services.governance_continuity_assurance_coverage_service import (
    governance_continuity_assurance_coverage_service,
)
from app.services.governance_continuity_assurance_exercise_service import (
    governance_continuity_assurance_exercise_service,
)
from app.services.governance_continuity_assurance_scenario_service import (
    governance_continuity_assurance_scenario_service,
)
from app.services.governance_continuity_assurance_personnel_service import (
    governance_continuity_assurance_personnel_service,
)
from app.services.governance_continuity_assurance_dependency_service import (
    governance_continuity_assurance_dependency_service,
)
from app.services.governance_continuity_assurance_recovery_service import (
    governance_continuity_assurance_recovery_service,
)
from app.services.governance_continuity_assurance_reconciliation_service import (
    governance_continuity_assurance_reconciliation_service,
)
from app.services.governance_continuity_assurance_programme_service import (
    governance_continuity_assurance_programme_service,
)
from app.services.governance_continuity_assurance_finding_service import (
    governance_continuity_assurance_finding_service,
)
from app.services.governance_continuity_assurance_reporting_service import (
    governance_continuity_assurance_reporting_service,
)


def _ensure_not_patient(current_user: AuthenticatedUserContext = Depends(get_current_user)) -> None:
    """Patients cannot access governance continuity assurance operations."""
    if current_user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patients are not permitted to access clinical safety governance continuity assurance operations.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


router = APIRouter(
    prefix="/governance-continuity-assurance",
    tags=["Clinical Safety Governance Continuity Assurance"],
    dependencies=[Depends(_ensure_not_patient)],
)


# ==========================================
# A. Assurance Frameworks
# ==========================================

@router.post("/frameworks", response_model=ContinuityAssuranceFrameworkRecord, status_code=status.HTTP_201_CREATED)
def create_framework(
    request: CreateContinuityAssuranceFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_framework_service.create_framework(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/frameworks/{framework_id}", response_model=ContinuityAssuranceFrameworkRecord)
def get_framework(
    framework_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_framework_service.get_framework(
        framework_id=framework_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/frameworks", response_model=List[ContinuityAssuranceFrameworkRecord])
def list_frameworks(
    status: Optional[FrameworkStatus] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_framework_service.list_frameworks(
        tenant_id=current_user.tenant_id,
        status=status,
    )


@router.patch("/frameworks/{framework_id}", response_model=ContinuityAssuranceFrameworkRecord)
def update_framework(
    framework_id: str,
    request: UpdateContinuityAssuranceFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_framework_service.update_framework(
        framework_id=framework_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/frameworks/{framework_id}/submit", response_model=ContinuityAssuranceFrameworkRecord)
def submit_framework(
    framework_id: str,
    request: SubmitFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_framework_service.submit_framework(
        framework_id=framework_id,
        actor_id=current_user.user_id,
        notes=request.submission_notes,
        tenant_id=current_user.tenant_id,
    )


@router.post("/frameworks/{framework_id}/approve", response_model=ContinuityAssuranceFrameworkRecord)
def approve_framework(
    framework_id: str,
    request: ApproveFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_framework_service.approve_framework(
        framework_id=framework_id,
        actor_id=current_user.user_id,
        notes=request.approval_notes,
        tenant_id=current_user.tenant_id,
    )


# ==========================================
# B. Continuity Plan Validation
# ==========================================

@router.post("/plan-validations", response_model=ContinuityPlanValidationRecord, status_code=status.HTTP_201_CREATED)
def create_plan_validation(
    request: CreatePlanValidationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_plan_service.create_validation_request(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/plan-validations/{validation_id}", response_model=ContinuityPlanValidationRecord)
def get_plan_validation(
    validation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_plan_service.get_plan_validation(
        validation_id=validation_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/plan-validations", response_model=List[ContinuityPlanValidationRecord])
def list_plan_validations(
    plan_id: Optional[str] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_plan_service.list_plan_validations(
        tenant_id=current_user.tenant_id,
        plan_id=plan_id,
    )


@router.post("/plan-validations/{validation_id}/review", response_model=ContinuityPlanValidationRecord)
def review_plan_validation(
    validation_id: str,
    request: ReviewPlanValidationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_plan_service.review_validation(
        validation_id=validation_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


# ==========================================
# C. Coverage Assurance
# ==========================================

@router.post("/coverage-assessments", response_model=ContinuityCoverageAssessmentRecord, status_code=status.HTTP_201_CREATED)
def run_coverage_assessment(
    request: RunCoverageAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_coverage_service.run_coverage_assessment(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/coverage-assessments/{assessment_id}", response_model=ContinuityCoverageAssessmentRecord)
def get_coverage_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_coverage_service.get_coverage_assessment(
        assessment_id=assessment_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/coverage-assessments", response_model=List[ContinuityCoverageAssessmentRecord])
def list_coverage_assessments(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_coverage_service.list_coverage_assessments(
        tenant_id=current_user.tenant_id,
    )


# ==========================================
# D. Exercise Assurance
# ==========================================

@router.post("/exercise-evaluations", response_model=ContinuityExerciseAssuranceRecord, status_code=status.HTTP_201_CREATED)
def create_exercise_evaluation(
    request: CreateExerciseAssuranceEvaluationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_exercise_service.create_evaluation(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/exercise-evaluations/{evaluation_id}", response_model=ContinuityExerciseAssuranceRecord)
def get_exercise_evaluation(
    evaluation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_exercise_service.get_evaluation(
        evaluation_id=evaluation_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/exercise-evaluations", response_model=List[ContinuityExerciseAssuranceRecord])
def list_exercise_evaluations(
    exercise_id: Optional[str] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_exercise_service.list_evaluations(
        tenant_id=current_user.tenant_id,
        exercise_id=exercise_id,
    )


# ==========================================
# E. Scenario Validation
# ==========================================

@router.post("/scenario-assessments", response_model=ContinuityScenarioAssessmentRecord, status_code=status.HTTP_201_CREATED)
def create_scenario_assessment(
    request: CreateScenarioAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_scenario_service.create_scenario_assessment(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/scenario-assessments/{scenario_id}/evaluate", response_model=ContinuityScenarioAssessmentRecord)
def evaluate_scenario(
    scenario_id: str,
    request: EvaluateScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_scenario_service.evaluate_scenario(
        scenario_id=scenario_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/scenario-assessments/{scenario_id}", response_model=ContinuityScenarioAssessmentRecord)
def get_scenario_assessment(
    scenario_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_scenario_service.get_scenario_assessment(
        scenario_id=scenario_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/scenario-assessments", response_model=List[ContinuityScenarioAssessmentRecord])
def list_scenario_assessments(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_scenario_service.list_scenario_assessments(
        tenant_id=current_user.tenant_id,
    )


# ==========================================
# F. Personnel Readiness
# ==========================================

@router.post("/personnel-readiness", response_model=PersonnelReadinessAssuranceRecord, status_code=status.HTTP_201_CREATED)
def assess_personnel_readiness(
    request: AssessPersonnelReadinessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_personnel_service.assess_readiness(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/personnel-readiness/{readiness_id}/verify-authority", response_model=PersonnelReadinessAssuranceRecord)
def verify_delegated_authority(
    readiness_id: str,
    request: VerifyDelegatedAuthorityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_personnel_service.verify_delegated_authority(
        readiness_id=readiness_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/personnel-readiness/{readiness_id}", response_model=PersonnelReadinessAssuranceRecord)
def get_personnel_readiness(
    readiness_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_personnel_service.get_personnel_readiness(
        readiness_id=readiness_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/personnel-readiness", response_model=List[PersonnelReadinessAssuranceRecord])
def list_personnel_readiness(
    role_key: Optional[str] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_personnel_service.list_personnel_readiness(
        tenant_id=current_user.tenant_id,
        role_key=role_key,
    )


# ==========================================
# G. Dependency Assurance
# ==========================================

@router.post("/dependency-assessments", response_model=DependencyResilienceAssuranceRecord, status_code=status.HTTP_201_CREATED)
def assess_dependency_resilience(
    request: AssessDependencyResilienceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_dependency_service.assess_dependency(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/dependency-assessments/{assessment_id}", response_model=DependencyResilienceAssuranceRecord)
def get_dependency_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_dependency_service.get_dependency_assessment(
        assessment_id=assessment_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/dependency-assessments", response_model=List[DependencyResilienceAssuranceRecord])
def list_dependency_assessments(
    dependency_id: Optional[str] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_dependency_service.list_dependency_assessments(
        tenant_id=current_user.tenant_id,
        dependency_id=dependency_id,
    )


# ==========================================
# H. Recovery Performance
# ==========================================

@router.post("/recovery-assessments", response_model=RecoveryPerformanceAssuranceRecord, status_code=status.HTTP_201_CREATED)
def assess_recovery_performance(
    request: AssessRecoveryPerformanceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_recovery_service.assess_recovery(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/recovery-assessments/{assessment_id}", response_model=RecoveryPerformanceAssuranceRecord)
def get_recovery_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_recovery_service.get_recovery_assessment(
        assessment_id=assessment_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/recovery-assessments", response_model=List[RecoveryPerformanceAssuranceRecord])
def list_recovery_assessments(
    recovery_id: Optional[str] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_recovery_service.list_recovery_assessments(
        tenant_id=current_user.tenant_id,
        recovery_id=recovery_id,
    )


# ==========================================
# I. Reconciliation Assurance
# ==========================================

@router.post("/reconciliation-assessments", response_model=ReconciliationAssuranceRecord, status_code=status.HTTP_201_CREATED)
def assess_reconciliation_integrity(
    request: AssessReconciliationIntegrityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_reconciliation_service.assess_reconciliation_integrity(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/reconciliation-assessments/{assurance_id}", response_model=ReconciliationAssuranceRecord)
def get_reconciliation_assessment(
    assurance_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_reconciliation_service.get_reconciliation_assessment(
        assurance_id=assurance_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/reconciliation-assessments", response_model=List[ReconciliationAssuranceRecord])
def list_reconciliation_assessments(
    activation_id: Optional[str] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_reconciliation_service.list_reconciliation_assessments(
        tenant_id=current_user.tenant_id,
        activation_id=activation_id,
    )


# ==========================================
# J. Independent Validation Programmes
# ==========================================

@router.post("/validation-programmes", response_model=IndependentValidationProgrammeRecord, status_code=status.HTTP_201_CREATED)
def create_validation_programme(
    request: CreateValidationProgrammeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_programme_service.create_programme(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/validation-programmes/{programme_id}/evaluators", response_model=IndependentValidationProgrammeRecord)
def assign_evaluator(
    programme_id: str,
    request: AssignEvaluatorRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_programme_service.assign_evaluator(
        programme_id=programme_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/validation-programmes/{programme_id}/independence-declarations", response_model=IndependentValidationProgrammeRecord)
def record_independence_declaration(
    programme_id: str,
    request: RecordIndependenceDeclarationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_programme_service.record_independence_declaration(
        programme_id=programme_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/validation-programmes/{programme_id}/evidence-requests", response_model=IndependentValidationProgrammeRecord)
def submit_evidence_request(
    programme_id: str,
    request: SubmitEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_programme_service.submit_evidence_request(
        programme_id=programme_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/validation-programmes/{programme_id}/approve", response_model=IndependentValidationProgrammeRecord)
def approve_programme_report(
    programme_id: str,
    management_response: str = Query(..., description="Formal management response to independent review findings"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_programme_service.approve_programme_report(
        programme_id=programme_id,
        management_response=management_response,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/validation-programmes/{programme_id}", response_model=IndependentValidationProgrammeRecord)
def get_validation_programme(
    programme_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_programme_service.get_programme(
        programme_id=programme_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/validation-programmes", response_model=List[IndependentValidationProgrammeRecord])
def list_validation_programmes(
    status: Optional[ProgrammeStatus] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_programme_service.list_programmes(
        tenant_id=current_user.tenant_id,
        status=status,
    )


# ==========================================
# K. Continuity Finding Management
# ==========================================

@router.post("/findings", response_model=ContinuityAssuranceFindingRecord, status_code=status.HTTP_201_CREATED)
def create_finding(
    request: CreateContinuityFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_finding_service.create_finding(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/findings/{finding_id}/refer", response_model=ContinuityAssuranceFindingRecord)
def refer_finding(
    finding_id: str,
    request: ReferFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_finding_service.refer_finding(
        finding_id=finding_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/findings/{finding_id}/close", response_model=ContinuityAssuranceFindingRecord)
def close_finding(
    finding_id: str,
    request: CloseFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_finding_service.close_finding(
        finding_id=finding_id,
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/findings/{finding_id}", response_model=ContinuityAssuranceFindingRecord)
def get_finding(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_finding_service.get_finding(
        finding_id=finding_id,
        tenant_id=current_user.tenant_id,
    )


@router.get("/findings", response_model=List[ContinuityAssuranceFindingRecord])
def list_findings(
    status: Optional[FindingStatus] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_finding_service.list_findings(
        tenant_id=current_user.tenant_id,
        status=status,
    )


# ==========================================
# L. Reporting & Routine Maintenance
# ==========================================

@router.post("/reports/generate", response_model=ContinuityAssuranceReportRecord)
def generate_report(
    request: GenerateReportRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_reporting_service.generate_report(
        req=request,
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/maintenance/scan", response_model=RoutineScanResult)
def run_routine_maintenance_scan(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    return governance_continuity_assurance_reporting_service.run_routine_scan(
        tenant_id=current_user.tenant_id,
    )

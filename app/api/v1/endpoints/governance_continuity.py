"""Phase 80: Clinical Safety Governance Strategic Resilience and Continuity REST API Endpoints.

Base Route: /api/v1/governance-continuity

Provides endpoints for:
- Critical governance capability inventory and classification
- Continuity requirements and recovery metrics (RTO, RPO, MTPD, MBCO)
- Governance dependency mapping and SPOF analysis
- Version-controlled continuity plans and controlled revisions
- Governance disruption classification and tracking
- Continuity activation coordination and acknowledgement
- Alternative operating arrangements and expiration monitoring
- Decision continuity, provenance preservation, and authoritative reconciliation
- Recovery monitoring, operational restoration, and independent verification
- Continuity exercises, execution, and weakness evaluations
- Continuity gap analysis and corrective action routing
- Resilience assurance reporting and routine maintenance scan
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Schemas
from app.schemas.governance_continuity_capability import (
    ApproveCapabilityRequest,
    CapabilityCriticalityTier,
    CapabilityInventoryStatus,
    ClinicalSafetyGovernanceCapabilityRecord,
    RegisterCapabilityRequest,
    SubmitCapabilityRequest,
    UpdateCapabilityRequest,
)
from app.schemas.governance_continuity_requirement import (
    ApproveContinuityRequirementRequest,
    ContinuityRequirementStatus,
    CreateContinuityRequirementRequest,
    GovernanceContinuityRequirementRecord,
    SubmitContinuityRequirementRequest,
)
from app.schemas.governance_continuity_dependency import (
    ContinuityDependencyType,
    CreateDependencyRequest,
    DependencyStatus,
    DependencyValidationResult,
    GovernanceContinuityDependencyRecord,
    ValidateDependencyRequest,
)
from app.schemas.governance_continuity_plan import (
    ApproveContinuityPlanRequest,
    ContinuityPlanStatus,
    CreateContinuityPlanRequest,
    GovernanceContinuityPlanRecord,
    ReviseContinuityPlanRequest,
    SubmitContinuityPlanRequest,
    UpdateContinuityPlanRequest,
)
from app.schemas.governance_continuity_disruption import (
    CloseDisruptionRequest,
    DisruptionCategory,
    DisruptionStatus,
    GovernanceDisruptionRecord,
    RegisterDisruptionRequest,
    UpdateDisruptionRequest,
)
from app.schemas.governance_continuity_activation import (
    AcknowledgeActivationRequest,
    AssessActivationRequest,
    AuthorizeActivationDecisionRequest,
    ContinuityActivationStatus,
    CreateActivationRequest,
    DeactivateActivationRequest,
    GovernanceContinuityActivationRecord,
)
from app.schemas.governance_continuity_arrangements import (
    AlternativeOperatingArrangementRecord,
    ArrangementVerificationStatus,
    CreateAlternativeArrangementRequest,
    DeactivateAlternativeArrangementRequest,
    UpdateAlternativeArrangementRequest,
)
from app.schemas.governance_continuity_reconciliation import (
    ReconciliationStatus,
    RecordTemporaryDecisionRequest,
    ReviewReconciliationConflictRequest,
    SubmitReconciliationRequest,
    TemporaryGovernanceDecisionRecord,
)
from app.schemas.governance_continuity_recovery import (
    CreateRecoveryRecordRequest,
    GovernanceRecoveryRecord,
    RecoveryStatus,
    UpdateRecoveryStatusRequest,
    VerifyRecoveryRestorationRequest,
)
from app.schemas.governance_continuity_exercises import (
    ContinuityExerciseRecord,
    ContinuityExerciseStatus,
    ContinuityExerciseType,
    CreateExerciseRequest,
    RecordExerciseExecutionRequest,
    SubmitExerciseEvaluationRequest,
)
from app.schemas.governance_continuity_gaps import (
    ContinuityGapCategory,
    ContinuityGapRecord,
    ContinuityGapSeverity,
    ContinuityGapStatus,
    CreateContinuityGapRequest,
    ReferGapToCorrectiveActionRequest,
    ReviewContinuityGapRequest,
)
from app.schemas.governance_continuity_reporting import (
    CapabilityInventorySummaryResponse,
    ContinuityPlanCoverageResponse,
    ContinuityRoutineScanJobResult,
    OrganizationalResilienceAssuranceResponse,
)

# Services
from app.services.governance_continuity_capability_service import (
    GovernanceContinuityCapabilityService,
)
from app.services.governance_continuity_requirement_service import (
    GovernanceContinuityRequirementService,
)
from app.services.governance_continuity_dependency_service import (
    GovernanceContinuityDependencyService,
)
from app.services.governance_continuity_plan_service import (
    GovernanceContinuityPlanService,
)
from app.services.governance_continuity_disruption_service import (
    GovernanceContinuityDisruptionService,
)
from app.services.governance_continuity_activation_service import (
    GovernanceContinuityActivationService,
)
from app.services.governance_continuity_arrangements_service import (
    GovernanceContinuityArrangementsService,
)
from app.services.governance_continuity_reconciliation_service import (
    GovernanceContinuityReconciliationService,
)
from app.services.governance_continuity_recovery_service import (
    GovernanceContinuityRecoveryService,
)
from app.services.governance_continuity_exercises_service import (
    GovernanceContinuityExercisesService,
)
from app.services.governance_continuity_gaps_service import (
    GovernanceContinuityGapsService,
)
from app.services.governance_continuity_reporting_service import (
    GovernanceContinuityReportingService,
)


def _ensure_not_patient(user: AuthenticatedUserContext = Depends(get_current_user)) -> AuthenticatedUserContext:
    """Enforces that patient role cannot access governance continuity and resilience features."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance continuity and resilience features.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return user


router = APIRouter(
    prefix="/governance-continuity",
    tags=["Phase 80 - Clinical Safety Governance Strategic Resilience & Continuity"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# A. Critical Governance Capability Inventory Endpoints
# =============================================================================

@router.post(
    "/capabilities",
    response_model=ClinicalSafetyGovernanceCapabilityRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a critical clinical safety governance capability",
)
def register_capability(
    request: RegisterCapabilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ClinicalSafetyGovernanceCapabilityRecord:
    service = GovernanceContinuityCapabilityService()
    return service.register_capability(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.put(
    "/capabilities/{capability_id}",
    response_model=ClinicalSafetyGovernanceCapabilityRecord,
    status_code=status.HTTP_200_OK,
    summary="Update draft governance capability information",
)
def update_capability(
    capability_id: str,
    request: UpdateCapabilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ClinicalSafetyGovernanceCapabilityRecord:
    service = GovernanceContinuityCapabilityService()
    return service.update_capability(
        tenant_id=current_user.tenant_id,
        capability_id=capability_id,
        request=request,
    )


@router.post(
    "/capabilities/{capability_id}/submit",
    response_model=ClinicalSafetyGovernanceCapabilityRecord,
    status_code=status.HTTP_200_OK,
    summary="Submit governance capability for formal classification approval",
)
def submit_capability(
    capability_id: str,
    request: SubmitCapabilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ClinicalSafetyGovernanceCapabilityRecord:
    service = GovernanceContinuityCapabilityService()
    return service.submit_capability(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        capability_id=capability_id,
        request=request,
    )


@router.post(
    "/capabilities/{capability_id}/approve",
    response_model=ClinicalSafetyGovernanceCapabilityRecord,
    status_code=status.HTTP_200_OK,
    summary="Approve governance capability classification (enforces separation of duties)",
)
def approve_capability(
    capability_id: str,
    request: ApproveCapabilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ClinicalSafetyGovernanceCapabilityRecord:
    service = GovernanceContinuityCapabilityService()
    return service.approve_capability(
        tenant_id=current_user.tenant_id,
        approver_id=current_user.user_id,
        capability_id=capability_id,
        request=request,
    )


@router.get(
    "/capabilities/{capability_id}",
    response_model=ClinicalSafetyGovernanceCapabilityRecord,
    status_code=status.HTTP_200_OK,
    summary="Get critical governance capability by ID",
)
def get_capability(
    capability_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ClinicalSafetyGovernanceCapabilityRecord:
    service = GovernanceContinuityCapabilityService()
    return service.get_capability(
        tenant_id=current_user.tenant_id,
        capability_id=capability_id,
    )


@router.get(
    "/capabilities",
    response_model=List[ClinicalSafetyGovernanceCapabilityRecord],
    status_code=status.HTTP_200_OK,
    summary="List critical governance capabilities",
)
def list_capabilities(
    criticality: Optional[CapabilityCriticalityTier] = Query(None),
    status_filter: Optional[CapabilityInventoryStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ClinicalSafetyGovernanceCapabilityRecord]:
    service = GovernanceContinuityCapabilityService()
    return service.list_capabilities(
        tenant_id=current_user.tenant_id,
        criticality=criticality,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# B. Governance Continuity Requirements Endpoints
# =============================================================================

@router.post(
    "/requirements",
    response_model=GovernanceContinuityRequirementRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create continuity requirements for a governance capability",
)
def create_requirement(
    request: CreateContinuityRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityRequirementRecord:
    service = GovernanceContinuityRequirementService()
    return service.create_requirement(tenant_id=current_user.tenant_id, request=request)


@router.post(
    "/requirements/{requirement_id}/submit",
    response_model=GovernanceContinuityRequirementRecord,
    status_code=status.HTTP_200_OK,
    summary="Submit continuity requirements for approval",
)
def submit_requirement(
    requirement_id: str,
    request: SubmitContinuityRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityRequirementRecord:
    service = GovernanceContinuityRequirementService()
    return service.submit_requirement(
        tenant_id=current_user.tenant_id,
        requirement_id=requirement_id,
        request=request,
    )


@router.post(
    "/requirements/{requirement_id}/approve",
    response_model=GovernanceContinuityRequirementRecord,
    status_code=status.HTTP_200_OK,
    summary="Approve governance continuity requirements",
)
def approve_requirement(
    requirement_id: str,
    request: ApproveContinuityRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityRequirementRecord:
    service = GovernanceContinuityRequirementService()
    return service.approve_requirement(
        tenant_id=current_user.tenant_id,
        approver_id=current_user.user_id,
        requirement_id=requirement_id,
        request=request,
    )


@router.get(
    "/requirements/{requirement_id}",
    response_model=GovernanceContinuityRequirementRecord,
    status_code=status.HTTP_200_OK,
    summary="Get governance continuity requirements by ID",
)
def get_requirement(
    requirement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityRequirementRecord:
    service = GovernanceContinuityRequirementService()
    return service.get_requirement(tenant_id=current_user.tenant_id, requirement_id=requirement_id)


@router.get(
    "/requirements",
    response_model=List[GovernanceContinuityRequirementRecord],
    status_code=status.HTTP_200_OK,
    summary="List governance continuity requirements",
)
def list_requirements(
    status_filter: Optional[ContinuityRequirementStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceContinuityRequirementRecord]:
    service = GovernanceContinuityRequirementService()
    return service.list_requirements(tenant_id=current_user.tenant_id, status=status_filter, skip=skip, limit=limit)


# =============================================================================
# C. Governance Dependency Mapping Endpoints
# =============================================================================

@router.post(
    "/dependencies",
    response_model=GovernanceContinuityDependencyRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Establish a critical governance dependency",
)
def create_dependency(
    request: CreateDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityDependencyRecord:
    service = GovernanceContinuityDependencyService()
    return service.create_dependency(tenant_id=current_user.tenant_id, request=request)


@router.post(
    "/dependencies/{dependency_id}/validate",
    response_model=GovernanceContinuityDependencyRecord,
    status_code=status.HTTP_200_OK,
    summary="Validate dependency and verify alternative arrangement",
)
def validate_dependency(
    dependency_id: str,
    request: ValidateDependencyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityDependencyRecord:
    service = GovernanceContinuityDependencyService()
    return service.validate_dependency(
        tenant_id=current_user.tenant_id,
        dependency_id=dependency_id,
        request=request,
    )


@router.get(
    "/dependencies/{dependency_id}",
    response_model=GovernanceContinuityDependencyRecord,
    status_code=status.HTTP_200_OK,
    summary="Get governance dependency by ID",
)
def get_dependency(
    dependency_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityDependencyRecord:
    service = GovernanceContinuityDependencyService()
    return service.get_dependency(tenant_id=current_user.tenant_id, dependency_id=dependency_id)


@router.get(
    "/dependencies",
    response_model=List[GovernanceContinuityDependencyRecord],
    status_code=status.HTTP_200_OK,
    summary="List governance dependencies",
)
def list_dependencies(
    capability_id: Optional[str] = Query(None),
    dependency_type: Optional[ContinuityDependencyType] = Query(None),
    status_filter: Optional[DependencyStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceContinuityDependencyRecord]:
    service = GovernanceContinuityDependencyService()
    return service.list_dependencies(
        tenant_id=current_user.tenant_id,
        capability_id=capability_id,
        dependency_type=dependency_type,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/dependencies/evaluate-spofs",
    response_model=DependencyValidationResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate dependencies for single points of failure and unvalidated alternatives",
)
def evaluate_dependencies_and_spofs(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> DependencyValidationResult:
    service = GovernanceContinuityDependencyService()
    return service.evaluate_dependencies_and_spofs(tenant_id=current_user.tenant_id)


# =============================================================================
# D. Governance Continuity Plan Management Endpoints
# =============================================================================

@router.post(
    "/plans",
    response_model=GovernanceContinuityPlanRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new governance continuity plan draft",
)
def create_plan(
    request: CreateContinuityPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityPlanRecord:
    service = GovernanceContinuityPlanService()
    return service.create_plan(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.put(
    "/plans/{plan_id}",
    response_model=GovernanceContinuityPlanRecord,
    status_code=status.HTTP_200_OK,
    summary="Update draft governance continuity plan",
)
def update_plan(
    plan_id: str,
    request: UpdateContinuityPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityPlanRecord:
    service = GovernanceContinuityPlanService()
    return service.update_plan(
        tenant_id=current_user.tenant_id,
        plan_id=plan_id,
        request=request,
    )


@router.post(
    "/plans/{plan_id}/submit",
    response_model=GovernanceContinuityPlanRecord,
    status_code=status.HTTP_200_OK,
    summary="Submit continuity plan for approval",
)
def submit_plan(
    plan_id: str,
    request: SubmitContinuityPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityPlanRecord:
    service = GovernanceContinuityPlanService()
    return service.submit_plan(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        plan_id=plan_id,
        request=request,
    )


@router.post(
    "/plans/{plan_id}/approve",
    response_model=GovernanceContinuityPlanRecord,
    status_code=status.HTTP_200_OK,
    summary="Approve governance continuity plan (enforces separation of duties)",
)
def approve_plan(
    plan_id: str,
    request: ApproveContinuityPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityPlanRecord:
    service = GovernanceContinuityPlanService()
    return service.approve_plan(
        tenant_id=current_user.tenant_id,
        approver_id=current_user.user_id,
        plan_id=plan_id,
        request=request,
    )


@router.post(
    "/plans/{plan_id}/revise",
    response_model=GovernanceContinuityPlanRecord,
    status_code=status.HTTP_200_OK,
    summary="Revise an approved continuity plan preserving baseline in version history",
)
def revise_plan(
    plan_id: str,
    request: ReviseContinuityPlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityPlanRecord:
    service = GovernanceContinuityPlanService()
    return service.revise_plan(
        tenant_id=current_user.tenant_id,
        reviser_id=current_user.user_id,
        plan_id=plan_id,
        request=request,
    )


@router.get(
    "/plans/{plan_id}",
    response_model=GovernanceContinuityPlanRecord,
    status_code=status.HTTP_200_OK,
    summary="Get governance continuity plan by ID",
)
def get_plan(
    plan_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityPlanRecord:
    service = GovernanceContinuityPlanService()
    return service.get_plan(tenant_id=current_user.tenant_id, plan_id=plan_id)


@router.get(
    "/plans",
    response_model=List[GovernanceContinuityPlanRecord],
    status_code=status.HTTP_200_OK,
    summary="List governance continuity plans",
)
def list_plans(
    status_filter: Optional[ContinuityPlanStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceContinuityPlanRecord]:
    service = GovernanceContinuityPlanService()
    return service.list_plans(tenant_id=current_user.tenant_id, status=status_filter, skip=skip, limit=limit)


# =============================================================================
# E. Governance Disruption Classification Endpoints
# =============================================================================

@router.post(
    "/disruptions",
    response_model=GovernanceDisruptionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a disruption affecting governance operations",
)
def register_disruption(
    request: RegisterDisruptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceDisruptionRecord:
    service = GovernanceContinuityDisruptionService()
    return service.register_disruption(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.put(
    "/disruptions/{disruption_id}",
    response_model=GovernanceDisruptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Update active disruption record",
)
def update_disruption(
    disruption_id: str,
    request: UpdateDisruptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceDisruptionRecord:
    service = GovernanceContinuityDisruptionService()
    return service.update_disruption(
        tenant_id=current_user.tenant_id,
        disruption_id=disruption_id,
        request=request,
    )


@router.post(
    "/disruptions/{disruption_id}/close",
    response_model=GovernanceDisruptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Close disruption with verified resolution evidence",
)
def close_disruption(
    disruption_id: str,
    request: CloseDisruptionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceDisruptionRecord:
    service = GovernanceContinuityDisruptionService()
    return service.close_disruption(
        tenant_id=current_user.tenant_id,
        closer_id=current_user.user_id,
        disruption_id=disruption_id,
        request=request,
    )


@router.get(
    "/disruptions/{disruption_id}",
    response_model=GovernanceDisruptionRecord,
    status_code=status.HTTP_200_OK,
    summary="Get governance disruption by ID",
)
def get_disruption(
    disruption_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceDisruptionRecord:
    service = GovernanceContinuityDisruptionService()
    return service.get_disruption(tenant_id=current_user.tenant_id, disruption_id=disruption_id)


@router.get(
    "/disruptions",
    response_model=List[GovernanceDisruptionRecord],
    status_code=status.HTTP_200_OK,
    summary="List governance disruptions",
)
def list_disruptions(
    category: Optional[DisruptionCategory] = Query(None),
    status_filter: Optional[DisruptionStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceDisruptionRecord]:
    service = GovernanceContinuityDisruptionService()
    return service.list_disruptions(
        tenant_id=current_user.tenant_id,
        category=category,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# F. Governance Continuity Activation Coordination Endpoints
# =============================================================================

@router.post(
    "/activations",
    response_model=GovernanceContinuityActivationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create continuity activation proposal for an active disruption",
)
def create_activation_request(
    request: CreateActivationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityActivationRecord:
    service = GovernanceContinuityActivationService()
    return service.create_activation_request(
        tenant_id=current_user.tenant_id,
        requestor_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/activations/{activation_id}/assess",
    response_model=GovernanceContinuityActivationRecord,
    status_code=status.HTTP_200_OK,
    summary="Record assessment for continuity activation",
)
def assess_activation(
    activation_id: str,
    request: AssessActivationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityActivationRecord:
    service = GovernanceContinuityActivationService()
    return service.assess_activation(
        tenant_id=current_user.tenant_id,
        assessor_id=current_user.user_id,
        activation_id=activation_id,
        request=request,
    )


@router.post(
    "/activations/{activation_id}/authorize",
    response_model=GovernanceContinuityActivationRecord,
    status_code=status.HTTP_200_OK,
    summary="Authorize continuity plan activation (enforces separation of duties)",
)
def authorize_activation_decision(
    activation_id: str,
    request: AuthorizeActivationDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityActivationRecord:
    service = GovernanceContinuityActivationService()
    return service.authorize_activation_decision(
        tenant_id=current_user.tenant_id,
        authorizer_id=current_user.user_id,
        activation_id=activation_id,
        request=request,
    )


@router.post(
    "/activations/{activation_id}/acknowledge",
    response_model=GovernanceContinuityActivationRecord,
    status_code=status.HTTP_200_OK,
    summary="Coordinator acknowledges continuity activation",
)
def acknowledge_activation(
    activation_id: str,
    request: AcknowledgeActivationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityActivationRecord:
    service = GovernanceContinuityActivationService()
    return service.acknowledge_activation(
        tenant_id=current_user.tenant_id,
        coordinator_id=current_user.user_id,
        activation_id=activation_id,
        request=request,
    )


@router.post(
    "/activations/{activation_id}/deactivate",
    response_model=GovernanceContinuityActivationRecord,
    status_code=status.HTTP_200_OK,
    summary="Deactivate continuity arrangements upon verified operational recovery",
)
def deactivate_activation(
    activation_id: str,
    request: DeactivateActivationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityActivationRecord:
    service = GovernanceContinuityActivationService()
    return service.deactivate_activation(
        tenant_id=current_user.tenant_id,
        deactivator_id=current_user.user_id,
        activation_id=activation_id,
        request=request,
    )


@router.get(
    "/activations/{activation_id}",
    response_model=GovernanceContinuityActivationRecord,
    status_code=status.HTTP_200_OK,
    summary="Get continuity activation by ID",
)
def get_activation(
    activation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceContinuityActivationRecord:
    service = GovernanceContinuityActivationService()
    return service.get_activation(tenant_id=current_user.tenant_id, activation_id=activation_id)


@router.get(
    "/activations",
    response_model=List[GovernanceContinuityActivationRecord],
    status_code=status.HTTP_200_OK,
    summary="List continuity activations",
)
def list_activations(
    disruption_id: Optional[str] = Query(None),
    status_filter: Optional[ContinuityActivationStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceContinuityActivationRecord]:
    service = GovernanceContinuityActivationService()
    return service.list_activations(
        tenant_id=current_user.tenant_id,
        disruption_id=disruption_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# G. Alternative Governance Operating Arrangements Endpoints
# =============================================================================

@router.post(
    "/arrangements",
    response_model=AlternativeOperatingArrangementRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Establish an authorized temporary alternative operating arrangement",
)
def create_alternative_arrangement(
    request: CreateAlternativeArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AlternativeOperatingArrangementRecord:
    service = GovernanceContinuityArrangementsService()
    return service.create_alternative_arrangement(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.put(
    "/arrangements/{arrangement_id}",
    response_model=AlternativeOperatingArrangementRecord,
    status_code=status.HTTP_200_OK,
    summary="Update alternative operating arrangement",
)
def update_arrangement(
    arrangement_id: str,
    request: UpdateAlternativeArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AlternativeOperatingArrangementRecord:
    service = GovernanceContinuityArrangementsService()
    return service.update_arrangement(
        tenant_id=current_user.tenant_id,
        arrangement_id=arrangement_id,
        request=request,
    )


@router.post(
    "/arrangements/{arrangement_id}/deactivate",
    response_model=AlternativeOperatingArrangementRecord,
    status_code=status.HTTP_200_OK,
    summary="Deactivate alternative operating arrangement",
)
def deactivate_arrangement(
    arrangement_id: str,
    request: DeactivateAlternativeArrangementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AlternativeOperatingArrangementRecord:
    service = GovernanceContinuityArrangementsService()
    return service.deactivate_arrangement(
        tenant_id=current_user.tenant_id,
        deactivator_id=current_user.user_id,
        arrangement_id=arrangement_id,
        request=request,
    )


@router.get(
    "/arrangements/{arrangement_id}",
    response_model=AlternativeOperatingArrangementRecord,
    status_code=status.HTTP_200_OK,
    summary="Get alternative operating arrangement by ID",
)
def get_arrangement(
    arrangement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AlternativeOperatingArrangementRecord:
    service = GovernanceContinuityArrangementsService()
    return service.get_arrangement(tenant_id=current_user.tenant_id, arrangement_id=arrangement_id)


@router.get(
    "/arrangements",
    response_model=List[AlternativeOperatingArrangementRecord],
    status_code=status.HTTP_200_OK,
    summary="List alternative operating arrangements",
)
def list_arrangements(
    activation_id: Optional[str] = Query(None),
    verification_status: Optional[ArrangementVerificationStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[AlternativeOperatingArrangementRecord]:
    service = GovernanceContinuityArrangementsService()
    return service.list_arrangements(
        tenant_id=current_user.tenant_id,
        activation_id=activation_id,
        verification_status=verification_status,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# H. Decision and Evidence Continuity & Reconciliation Endpoints
# =============================================================================

@router.post(
    "/temporary-decisions",
    response_model=TemporaryGovernanceDecisionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record a governance decision executed under continuity arrangements",
)
def record_temporary_decision(
    request: RecordTemporaryDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> TemporaryGovernanceDecisionRecord:
    service = GovernanceContinuityReconciliationService()
    return service.record_temporary_decision(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/temporary-decisions/{temporary_decision_id}/reconcile",
    response_model=TemporaryGovernanceDecisionRecord,
    status_code=status.HTTP_200_OK,
    summary="Reconcile temporary governance decision into authoritative system",
)
def submit_reconciliation(
    temporary_decision_id: str,
    request: SubmitReconciliationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> TemporaryGovernanceDecisionRecord:
    service = GovernanceContinuityReconciliationService()
    return service.submit_reconciliation(
        tenant_id=current_user.tenant_id,
        reconciler_id=current_user.user_id,
        temporary_decision_id=temporary_decision_id,
        request=request,
    )


@router.post(
    "/temporary-decisions/{temporary_decision_id}/resolve-conflict",
    response_model=TemporaryGovernanceDecisionRecord,
    status_code=status.HTTP_200_OK,
    summary="Review and resolve reconciliation conflict",
)
def review_reconciliation_conflict(
    temporary_decision_id: str,
    request: ReviewReconciliationConflictRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> TemporaryGovernanceDecisionRecord:
    service = GovernanceContinuityReconciliationService()
    return service.review_reconciliation_conflict(
        tenant_id=current_user.tenant_id,
        reviewer_id=current_user.user_id,
        temporary_decision_id=temporary_decision_id,
        request=request,
    )


@router.get(
    "/temporary-decisions/{temporary_decision_id}",
    response_model=TemporaryGovernanceDecisionRecord,
    status_code=status.HTTP_200_OK,
    summary="Get temporary governance decision by ID",
)
def get_temporary_decision(
    temporary_decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> TemporaryGovernanceDecisionRecord:
    service = GovernanceContinuityReconciliationService()
    return service.get_temporary_decision(
        tenant_id=current_user.tenant_id,
        temporary_decision_id=temporary_decision_id,
    )


@router.get(
    "/temporary-decisions",
    response_model=List[TemporaryGovernanceDecisionRecord],
    status_code=status.HTTP_200_OK,
    summary="List temporary governance decisions",
)
def list_temporary_decisions(
    activation_id: Optional[str] = Query(None),
    reconciliation_status: Optional[ReconciliationStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[TemporaryGovernanceDecisionRecord]:
    service = GovernanceContinuityReconciliationService()
    return service.list_temporary_decisions(
        tenant_id=current_user.tenant_id,
        activation_id=activation_id,
        reconciliation_status=reconciliation_status,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# I. Governance Recovery Coordination & Verification Endpoints
# =============================================================================

@router.post(
    "/recoveries",
    response_model=GovernanceRecoveryRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize recovery monitoring for an affected capability",
)
def create_recovery_record(
    request: CreateRecoveryRecordRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceRecoveryRecord:
    service = GovernanceContinuityRecoveryService()
    return service.create_recovery_record(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/recoveries/{recovery_id}/update-status",
    response_model=GovernanceRecoveryRecord,
    status_code=status.HTTP_200_OK,
    summary="Update capability recovery status and record progress milestone",
)
def update_recovery_status(
    recovery_id: str,
    request: UpdateRecoveryStatusRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceRecoveryRecord:
    service = GovernanceContinuityRecoveryService()
    return service.update_recovery_status(
        tenant_id=current_user.tenant_id,
        updater_id=current_user.user_id,
        recovery_id=recovery_id,
        request=request,
    )


@router.post(
    "/recoveries/{recovery_id}/verify",
    response_model=GovernanceRecoveryRecord,
    status_code=status.HTTP_200_OK,
    summary="Independently verify operational restoration (enforces separation of duties)",
)
def verify_recovery_restoration(
    recovery_id: str,
    request: VerifyRecoveryRestorationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceRecoveryRecord:
    service = GovernanceContinuityRecoveryService()
    return service.verify_recovery_restoration(
        tenant_id=current_user.tenant_id,
        verifier_id=current_user.user_id,
        recovery_id=recovery_id,
        request=request,
    )


@router.get(
    "/recoveries/{recovery_id}",
    response_model=GovernanceRecoveryRecord,
    status_code=status.HTTP_200_OK,
    summary="Get governance recovery record by ID",
)
def get_recovery_record(
    recovery_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> GovernanceRecoveryRecord:
    service = GovernanceContinuityRecoveryService()
    return service.get_recovery_record(tenant_id=current_user.tenant_id, recovery_id=recovery_id)


@router.get(
    "/recoveries",
    response_model=List[GovernanceRecoveryRecord],
    status_code=status.HTTP_200_OK,
    summary="List governance recovery records",
)
def list_recovery_records(
    disruption_id: Optional[str] = Query(None),
    recovery_status: Optional[RecoveryStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[GovernanceRecoveryRecord]:
    service = GovernanceContinuityRecoveryService()
    return service.list_recovery_records(
        tenant_id=current_user.tenant_id,
        disruption_id=disruption_id,
        recovery_status=recovery_status,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# J. Continuity Testing & Exercise Management Endpoints
# =============================================================================

@router.post(
    "/exercises",
    response_model=ContinuityExerciseRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a continuity exercise",
)
def create_exercise(
    request: CreateExerciseRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityExerciseRecord:
    service = GovernanceContinuityExercisesService()
    return service.create_exercise(
        tenant_id=current_user.tenant_id,
        author_id=current_user.user_id,
        request=request,
    )


@router.post(
    "/exercises/{exercise_id}/record-execution",
    response_model=ContinuityExerciseRecord,
    status_code=status.HTTP_200_OK,
    summary="Record completion and observations of a continuity exercise",
)
def record_exercise_execution(
    exercise_id: str,
    request: RecordExerciseExecutionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityExerciseRecord:
    service = GovernanceContinuityExercisesService()
    return service.record_exercise_execution(
        tenant_id=current_user.tenant_id,
        coordinator_id=current_user.user_id,
        exercise_id=exercise_id,
        request=request,
    )


@router.post(
    "/exercises/{exercise_id}/evaluate",
    response_model=ContinuityExerciseRecord,
    status_code=status.HTTP_200_OK,
    summary="Submit exercise evaluation and identified weaknesses",
)
def submit_exercise_evaluation(
    exercise_id: str,
    request: SubmitExerciseEvaluationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityExerciseRecord:
    service = GovernanceContinuityExercisesService()
    return service.submit_exercise_evaluation(
        tenant_id=current_user.tenant_id,
        evaluator_id=current_user.user_id,
        exercise_id=exercise_id,
        request=request,
    )


@router.get(
    "/exercises/{exercise_id}",
    response_model=ContinuityExerciseRecord,
    status_code=status.HTTP_200_OK,
    summary="Get continuity exercise by ID",
)
def get_exercise(
    exercise_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityExerciseRecord:
    service = GovernanceContinuityExercisesService()
    return service.get_exercise(tenant_id=current_user.tenant_id, exercise_id=exercise_id)


@router.get(
    "/exercises",
    response_model=List[ContinuityExerciseRecord],
    status_code=status.HTTP_200_OK,
    summary="List continuity exercises",
)
def list_exercises(
    exercise_type: Optional[ContinuityExerciseType] = Query(None),
    status_filter: Optional[ContinuityExerciseStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ContinuityExerciseRecord]:
    service = GovernanceContinuityExercisesService()
    return service.list_exercises(
        tenant_id=current_user.tenant_id,
        exercise_type=exercise_type,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# K. Continuity Gap and Resilience Weakness Endpoints
# =============================================================================

@router.post(
    "/gaps",
    response_model=ContinuityGapRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Log an identified continuity gap or resilience weakness",
)
def create_continuity_gap(
    request: CreateContinuityGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityGapRecord:
    service = GovernanceContinuityGapsService()
    return service.create_continuity_gap(tenant_id=current_user.tenant_id, request=request)


@router.post(
    "/gaps/{gap_id}/review",
    response_model=ContinuityGapRecord,
    status_code=status.HTTP_200_OK,
    summary="Review and disposition a continuity gap",
)
def review_continuity_gap(
    gap_id: str,
    request: ReviewContinuityGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityGapRecord:
    service = GovernanceContinuityGapsService()
    return service.review_continuity_gap(
        tenant_id=current_user.tenant_id,
        reviewer_id=current_user.user_id,
        gap_id=gap_id,
        request=request,
    )


@router.post(
    "/gaps/{gap_id}/refer-corrective-action",
    response_model=ContinuityGapRecord,
    status_code=status.HTTP_200_OK,
    summary="Route continuity gap finding to Phase 54 CAPA or Phase 63 Risk Governance",
)
def refer_gap_to_corrective_action(
    gap_id: str,
    request: ReferGapToCorrectiveActionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityGapRecord:
    service = GovernanceContinuityGapsService()
    return service.refer_gap_to_corrective_action(
        tenant_id=current_user.tenant_id,
        referrer_id=current_user.user_id,
        gap_id=gap_id,
        request=request,
    )


@router.get(
    "/gaps/{gap_id}",
    response_model=ContinuityGapRecord,
    status_code=status.HTTP_200_OK,
    summary="Get continuity gap by ID",
)
def get_gap(
    gap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityGapRecord:
    service = GovernanceContinuityGapsService()
    return service.get_gap(tenant_id=current_user.tenant_id, gap_id=gap_id)


@router.get(
    "/gaps",
    response_model=List[ContinuityGapRecord],
    status_code=status.HTTP_200_OK,
    summary="List continuity gaps",
)
def list_gaps(
    category: Optional[ContinuityGapCategory] = Query(None),
    severity: Optional[ContinuityGapSeverity] = Query(None),
    status_filter: Optional[ContinuityGapStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ContinuityGapRecord]:
    service = GovernanceContinuityGapsService()
    return service.list_gaps(
        tenant_id=current_user.tenant_id,
        category=category,
        severity=severity,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# L. Assurance Reporting & Scheduled Maintenance Scan Endpoints
# =============================================================================

@router.get(
    "/reports/capability-summary",
    response_model=CapabilityInventorySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get critical capability inventory summary report",
)
def get_capability_inventory_summary(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> CapabilityInventorySummaryResponse:
    service = GovernanceContinuityReportingService()
    return service.get_capability_inventory_summary(tenant_id=current_user.tenant_id)


@router.get(
    "/reports/plan-coverage",
    response_model=ContinuityPlanCoverageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get continuity plan coverage report across critical capabilities",
)
def get_continuity_plan_coverage(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityPlanCoverageResponse:
    service = GovernanceContinuityReportingService()
    return service.get_continuity_plan_coverage(tenant_id=current_user.tenant_id)


@router.get(
    "/reports/resilience-assurance",
    response_model=OrganizationalResilienceAssuranceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get organizational governance resilience assurance executive report",
)
def get_organizational_resilience_assurance(
    reporting_period: str = Query("Annual 2026", description="Reporting period"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> OrganizationalResilienceAssuranceResponse:
    service = GovernanceContinuityReportingService()
    return service.get_organizational_resilience_assurance(
        tenant_id=current_user.tenant_id,
        reporting_period=reporting_period,
    )


@router.post(
    "/maintenance/routine-scan",
    response_model=ContinuityRoutineScanJobResult,
    status_code=status.HTTP_200_OK,
    summary="Execute idempotent background routine continuity scan",
)
def run_routine_scan(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> ContinuityRoutineScanJobResult:
    service = GovernanceContinuityReportingService()
    return service.run_routine_scan(tenant_id=current_user.tenant_id)

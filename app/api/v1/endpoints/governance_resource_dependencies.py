"""Phase 86: Clinical Safety Governance Resilience Resource Dependency REST API Endpoints.

Base Route: /api/v1/governance-resilience-resource-dependencies

Provides endpoints for:
- Critical resource inventory management
- Capability-to-resource dependency mapping and approval
- Resource availability evidence ingestion and evaluation
- Alternative resource documentation and fallback readiness assessment
- Resource capacity requirements and shortfall tracking
- Dependency graph analysis and SPOF detection
- Resource dependency gap management and escalation
- Executive and operational reporting
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Common
from app.schemas.governance_resource_common import (
    DependencyMappingStatus,
    FallbackReadinessOutcome,
    ResourceAvailabilityStatus,
    ResourceCategory,
    ResourceCriticality,
    ResourceGapCategory,
    ResourceGapStatus,
    ResourceLifecycleStatus,
    SPOFSeverity,
)

# Schemas
from app.schemas.governance_resource_inventory import (
    CriticalResourceRecord,
    CreateResourceRequest,
    UpdateResourceRequest,
)
from app.schemas.governance_resource_dependency_mapping import (
    ApproveDependencyMappingRequest,
    CapabilityResourceDependencyRecord,
    CreateDependencyMappingRequest,
    UpdateDependencyMappingRequest,
)
from app.schemas.governance_resource_availability import (
    ResourceAvailabilityObservationRecord,
    ResourceAvailabilitySummary,
    SubmitAvailabilityObservationRequest,
)
from app.schemas.governance_resource_alternative import (
    AlternativeResourceRecord,
    AssessFallbackReadinessRequest,
    CreateAlternativeResourceRequest,
)
from app.schemas.governance_resource_capacity import (
    CapacityRequirementRecord,
    CreateCapacityRequirementRequest,
    EvaluateCapacityRequest,
)
from app.schemas.governance_resource_spof_analysis import (
    DependencyGraphAnalysisRecord,
    RunDependencyGraphAnalysisRequest,
)
from app.schemas.governance_resource_gap import (
    AssignResourceGapRequest,
    CreateResourceGapRequest,
    EscalateResourceGapRequest,
    ResolveResourceGapRequest,
    ResourceDependencyGapRecord,
)
from app.schemas.governance_resource_reporting import (
    DependencyConcentrationReport,
    FallbackReadinessReport,
    ResourceAvailabilityStatusReport,
    ResourceCoverageSummaryReport,
    ResourceGapsSummaryReport,
)

# Services
from app.services.governance_resource_inventory_service import get_governance_resource_inventory_service
from app.services.governance_resource_dependency_mapping_service import get_governance_resource_dependency_mapping_service
from app.services.governance_resource_availability_service import get_governance_resource_availability_service
from app.services.governance_resource_alternative_service import get_governance_resource_alternative_service
from app.services.governance_resource_capacity_service import get_governance_resource_capacity_service
from app.services.governance_resource_spof_analysis_service import get_governance_resource_spof_analysis_service
from app.services.governance_resource_gap_service import get_governance_resource_gap_service
from app.services.governance_resource_reporting_service import get_governance_resource_reporting_service


def _ensure_not_patient(current_user: AuthenticatedUserContext = Depends(get_current_user)) -> None:
    """Patients cannot access governance resilience resource dependency operations."""
    if current_user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patients are not permitted to access clinical safety governance resilience resource dependency operations.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


router = APIRouter(
    prefix="/governance-resilience-resource-dependencies",
    tags=["Clinical Safety Governance Resilience Resource Dependencies"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# 1. Critical Resource Inventory
# =============================================================================

@router.post("/resources", response_model=CriticalResourceRecord, status_code=status.HTTP_201_CREATED)
def create_resource(
    request: CreateResourceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_inventory_service()
    return svc.create_resource(current_user.tenant_id, current_user.user_id, request)


@router.get("/resources", response_model=List[CriticalResourceRecord])
def list_resources(
    category: Optional[ResourceCategory] = Query(None),
    criticality: Optional[ResourceCriticality] = Query(None),
    lifecycle_status: Optional[ResourceLifecycleStatus] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_inventory_service()
    return svc.list_resources(current_user.tenant_id, category, criticality, lifecycle_status)


@router.get("/resources/{resource_id}", response_model=CriticalResourceRecord)
def get_resource(
    resource_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_inventory_service()
    return svc.get_resource(current_user.tenant_id, resource_id)


@router.patch("/resources/{resource_id}", response_model=CriticalResourceRecord)
def update_resource(
    resource_id: str,
    request: UpdateResourceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_inventory_service()
    return svc.update_resource(current_user.tenant_id, resource_id, request)


# =============================================================================
# 2. Capability-to-Resource Dependency Mapping (static routes BEFORE parameterized)
# =============================================================================

@router.post("/dependencies", response_model=CapabilityResourceDependencyRecord, status_code=status.HTTP_201_CREATED)
def create_dependency_mapping(
    request: CreateDependencyMappingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_dependency_mapping_service()
    return svc.create_mapping(current_user.tenant_id, current_user.user_id, request)


@router.get("/dependencies", response_model=List[CapabilityResourceDependencyRecord])
def list_dependency_mappings(
    resource_id: Optional[str] = Query(None),
    capability_ref: Optional[str] = Query(None),
    mapping_status: Optional[DependencyMappingStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_dependency_mapping_service()
    return svc.list_mappings(current_user.tenant_id, resource_id, capability_ref, mapping_status)


@router.get("/dependencies/{dependency_id}", response_model=CapabilityResourceDependencyRecord)
def get_dependency_mapping(
    dependency_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_dependency_mapping_service()
    return svc.get_mapping(current_user.tenant_id, dependency_id)


@router.patch("/dependencies/{dependency_id}", response_model=CapabilityResourceDependencyRecord)
def update_dependency_mapping(
    dependency_id: str,
    request: UpdateDependencyMappingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_dependency_mapping_service()
    return svc.update_mapping(current_user.tenant_id, dependency_id, current_user.user_id, request)


@router.post("/dependencies/{dependency_id}/submit", response_model=CapabilityResourceDependencyRecord)
def submit_dependency_mapping(
    dependency_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_dependency_mapping_service()
    return svc.submit_mapping(current_user.tenant_id, dependency_id, current_user.user_id)


@router.post("/dependencies/{dependency_id}/approve", response_model=CapabilityResourceDependencyRecord)
def approve_dependency_mapping(
    dependency_id: str,
    request: ApproveDependencyMappingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_dependency_mapping_service()
    return svc.approve_mapping(current_user.tenant_id, dependency_id, current_user.user_id, request)


# =============================================================================
# 3. Resource Availability Evidence
# =============================================================================

@router.post(
    "/resources/{resource_id}/availability-observations",
    response_model=ResourceAvailabilityObservationRecord,
    status_code=status.HTTP_201_CREATED,
)
def submit_availability_observation(
    resource_id: str,
    request: SubmitAvailabilityObservationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_availability_service()
    return svc.submit_observation(current_user.tenant_id, resource_id, current_user.user_id, request)


@router.get(
    "/resources/{resource_id}/availability",
    response_model=ResourceAvailabilitySummary,
)
def get_resource_availability(
    resource_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_availability_service()
    return svc.get_resource_availability_summary(current_user.tenant_id, resource_id)


@router.get("/availability-observations", response_model=List[ResourceAvailabilityObservationRecord])
def list_availability_observations(
    resource_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_availability_service()
    return svc.list_observations(current_user.tenant_id, resource_id)


@router.get(
    "/availability-observations/{observation_id}",
    response_model=ResourceAvailabilityObservationRecord,
)
def get_availability_observation(
    observation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_availability_service()
    return svc.get_observation(current_user.tenant_id, observation_id)


# =============================================================================
# 4. Alternative Resources and Fallback Readiness (static before parameterized)
# =============================================================================

@router.post(
    "/resources/{resource_id}/alternatives",
    response_model=AlternativeResourceRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_alternative_resource(
    resource_id: str,
    request: CreateAlternativeResourceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_alternative_service()
    return svc.create_alternative(current_user.tenant_id, resource_id, current_user.user_id, request)


@router.get(
    "/resources/{resource_id}/alternatives",
    response_model=List[AlternativeResourceRecord],
)
def list_alternative_resources(
    resource_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_alternative_service()
    return svc.list_alternatives_for_resource(current_user.tenant_id, resource_id)


@router.get("/alternatives/{alternative_id}", response_model=AlternativeResourceRecord)
def get_alternative_resource(
    alternative_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_alternative_service()
    return svc.get_alternative(current_user.tenant_id, alternative_id)


@router.post("/alternatives/{alternative_id}/assess", response_model=AlternativeResourceRecord)
def assess_fallback_readiness(
    alternative_id: str,
    request: AssessFallbackReadinessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_alternative_service()
    return svc.assess_fallback_readiness(current_user.tenant_id, alternative_id, current_user.user_id, request)


# =============================================================================
# 5. Capacity Requirements
# =============================================================================

@router.post("/capacity-requirements", response_model=CapacityRequirementRecord, status_code=status.HTTP_201_CREATED)
def create_capacity_requirement(
    request: CreateCapacityRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_capacity_service()
    return svc.create_requirement(current_user.tenant_id, current_user.user_id, request)


@router.get("/capacity-requirements", response_model=List[CapacityRequirementRecord])
def list_capacity_requirements(
    resource_id: Optional[str] = Query(None),
    capability_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_capacity_service()
    return svc.list_requirements(current_user.tenant_id, resource_id, capability_ref)


@router.get("/capacity-requirements/{requirement_id}", response_model=CapacityRequirementRecord)
def get_capacity_requirement(
    requirement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_capacity_service()
    return svc.get_requirement(current_user.tenant_id, requirement_id)


@router.post("/capacity-requirements/{requirement_id}/evaluate", response_model=CapacityRequirementRecord)
def evaluate_capacity_requirement(
    requirement_id: str,
    request: EvaluateCapacityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_capacity_service()
    return svc.evaluate_capacity(current_user.tenant_id, requirement_id, current_user.user_id, request)


# =============================================================================
# 6. Dependency Graph Analysis (static routes BEFORE parameterized)
# =============================================================================

@router.post("/dependency-analysis/run", response_model=DependencyGraphAnalysisRecord, status_code=status.HTTP_201_CREATED)
def run_dependency_analysis(
    request: RunDependencyGraphAnalysisRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_spof_analysis_service()
    return svc.run_analysis(current_user.tenant_id, current_user.user_id, request)


@router.get("/dependency-analysis", response_model=List[DependencyGraphAnalysisRecord])
def list_dependency_analyses(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_spof_analysis_service()
    return svc.list_analyses(current_user.tenant_id)


@router.get("/dependency-analysis/{analysis_id}", response_model=DependencyGraphAnalysisRecord)
def get_dependency_analysis(
    analysis_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_spof_analysis_service()
    return svc.get_analysis(current_user.tenant_id, analysis_id)


# =============================================================================
# 7. Resource Dependency Gaps (static routes BEFORE parameterized)
# =============================================================================

@router.post("/gaps", response_model=ResourceDependencyGapRecord, status_code=status.HTTP_201_CREATED)
def create_resource_gap(
    request: CreateResourceGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_gap_service()
    return svc.create_gap(current_user.tenant_id, current_user.user_id, request)


@router.get("/gaps", response_model=List[ResourceDependencyGapRecord])
def list_resource_gaps(
    gap_status: Optional[ResourceGapStatus] = Query(None, alias="status"),
    category: Optional[ResourceGapCategory] = Query(None),
    resource_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_gap_service()
    return svc.list_gaps(current_user.tenant_id, gap_status, category, resource_id)


@router.get("/gaps/{gap_id}", response_model=ResourceDependencyGapRecord)
def get_resource_gap(
    gap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_gap_service()
    return svc.get_gap(current_user.tenant_id, gap_id)


@router.post("/gaps/{gap_id}/assign", response_model=ResourceDependencyGapRecord)
def assign_resource_gap(
    gap_id: str,
    request: AssignResourceGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_gap_service()
    return svc.assign_gap(current_user.tenant_id, gap_id, current_user.user_id, request)


@router.post("/gaps/{gap_id}/escalate", response_model=ResourceDependencyGapRecord)
def escalate_resource_gap(
    gap_id: str,
    request: EscalateResourceGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_gap_service()
    return svc.escalate_gap(current_user.tenant_id, gap_id, current_user.user_id, request)


@router.post("/gaps/{gap_id}/verify-resolution", response_model=ResourceDependencyGapRecord)
def resolve_resource_gap(
    gap_id: str,
    request: ResolveResourceGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_gap_service()
    return svc.resolve_gap(current_user.tenant_id, gap_id, current_user.user_id, request)


# =============================================================================
# 8. Reports (all static)
# =============================================================================

@router.get("/reports/resource-coverage", response_model=ResourceCoverageSummaryReport)
def get_resource_coverage_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_reporting_service()
    return svc.coverage_summary_report(current_user.tenant_id)


@router.get("/reports/dependency-concentration", response_model=DependencyConcentrationReport)
def get_concentration_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_reporting_service()
    return svc.concentration_report(current_user.tenant_id)


@router.get("/reports/fallback-readiness", response_model=FallbackReadinessReport)
def get_fallback_readiness_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_reporting_service()
    return svc.fallback_readiness_report(current_user.tenant_id)


@router.get("/reports/resource-availability", response_model=ResourceAvailabilityStatusReport)
def get_resource_availability_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_reporting_service()
    return svc.availability_status_report(current_user.tenant_id)


@router.get("/reports/resource-gaps", response_model=ResourceGapsSummaryReport)
def get_resource_gaps_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_resource_reporting_service()
    return svc.gaps_summary_report(current_user.tenant_id)

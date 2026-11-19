"""Phase 69: Governance Compliance & Regulatory Evidence REST API Endpoints.

Implements REST API endpoints for:
- Registering compliance frameworks and versioned requirements
- Approving and activating requirements with governance sign-offs
- Mapping requirements to authoritative workflow controls
- Indexing and reconciling supporting compliance evidence
- Executing deterministic policy-driven compliance assessments and reassessments
- Reviewing, resolving, and prioritizing compliance findings (gaps)
- Coordinating corrective action requests through Phase 54 and Phase 55
- Generating and exporting controlled regulatory evidence packages
- Queue monitoring: review-required, overdue, evidence-required, reassessment-required
- Aggregated compliance reporting: summary, gaps, control conformance, evidence completeness

Base Path: /api/v1/governance-compliance
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_compliance_repository import (
    GovernanceComplianceRepository,
    get_governance_compliance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.compliance_assessment import (
    ComplianceAssessmentRecord,
    ReassessRequest,
    TriggerAssessmentRequest,
)
from app.schemas.compliance_evidence import (
    ComplianceEvidenceRecord,
    ReconcileEvidenceRequest,
    RegisterEvidenceRequest,
)
from app.schemas.compliance_finding import (
    ComplianceFindingRecord,
    ResolveFindingRequest,
    ReviewFindingRequest,
)
from app.schemas.compliance_framework import (
    ActivateRequirementRequest,
    ApproveRequirementRequest,
    ComplianceFrameworkRecord,
    ComplianceRequirementRecord,
    CreateControlMappingRequest,
    CreateFrameworkRequest,
    CreateRequirementRequest,
    RequirementControlMappingRecord,
)
from app.schemas.compliance_package_report import (
    ComplianceCorrectiveActionRequestRecord,
    ComplianceGapReport,
    ComplianceSummaryReport,
    ControlConformanceReport,
    EvidenceCompletenessReport,
    EvidencePackageRecord,
    GenerateEvidencePackageRequest,
    SubmitCorrectiveActionRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.compliance_assessment_engine_service import (
    ComplianceAssessmentEngineService,
    get_compliance_assessment_engine_service,
)
from app.services.compliance_evidence_management_service import (
    ComplianceEvidenceManagementService,
    get_compliance_evidence_management_service,
)
from app.services.compliance_evidence_package_service import (
    ComplianceEvidencePackageService,
    get_compliance_evidence_package_service,
)
from app.services.compliance_framework_service import (
    ComplianceFrameworkService,
    get_compliance_framework_service,
)
from app.services.compliance_gap_coordination_service import (
    ComplianceGapCoordinationService,
    get_compliance_gap_coordination_service,
)
from app.services.governance_compliance_monitoring_service import (
    GovernanceComplianceMonitoringService,
    get_governance_compliance_monitoring_service,
)

router = APIRouter(
    prefix="/governance-compliance",
    tags=["Phase 69 - Governance Compliance & Regulatory Evidence"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforce that patient role cannot access compliance governance endpoints."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance compliance monitoring.",
            status_code=403,
        )


# ===========================================================================
# 1. Specialized Queue Endpoints (Declared first to avoid path collisions)
# ===========================================================================

@router.get(
    "/queues/review-required",
    response_model=List[ComplianceAssessmentRecord],
    status_code=status.HTTP_200_OK,
)
def get_review_required_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceComplianceRepository = Depends(get_governance_compliance_repository),
) -> List[ComplianceAssessmentRecord]:
    """Retrieve compliance assessments requiring human specialist review."""
    _ensure_not_patient(current_user)
    return repo.list_review_required_queue(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


@router.get(
    "/queues/overdue",
    response_model=List[ComplianceRequirementRecord],
    status_code=status.HTTP_200_OK,
)
def get_overdue_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceComplianceRepository = Depends(get_governance_compliance_repository),
) -> List[ComplianceRequirementRecord]:
    """Retrieve active requirements that are overdue for compliance assessment."""
    _ensure_not_patient(current_user)
    return repo.list_overdue_queue(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


@router.get(
    "/queues/evidence-required",
    response_model=List[ComplianceAssessmentRecord],
    status_code=status.HTTP_200_OK,
)
def get_evidence_required_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceComplianceRepository = Depends(get_governance_compliance_repository),
) -> List[ComplianceAssessmentRecord]:
    """Retrieve assessments stalled due to missing or inaccessible evidence."""
    _ensure_not_patient(current_user)
    return repo.list_evidence_required_queue(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


@router.get(
    "/queues/reassessment-required",
    response_model=List[ComplianceAssessmentRecord],
    status_code=status.HTTP_200_OK,
)
def get_reassessment_required_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceComplianceRepository = Depends(get_governance_compliance_repository),
) -> List[ComplianceAssessmentRecord]:
    """Retrieve assessments awaiting formal reassessment following corrective action."""
    _ensure_not_patient(current_user)
    return repo.list_reassessment_required_queue(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


# ===========================================================================
# 2. Aggregated Reporting Endpoints
# ===========================================================================

@router.get(
    "/reports/compliance-summary",
    response_model=ComplianceSummaryReport,
    status_code=status.HTTP_200_OK,
)
def get_compliance_summary(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceComplianceMonitoringService = Depends(
        get_governance_compliance_monitoring_service
    ),
) -> ComplianceSummaryReport:
    """Generate high-level compliance summary report for tenant."""
    _ensure_not_patient(current_user)
    return service.generate_summary_report(user=current_user, facility_id=facility_id)


@router.get(
    "/reports/compliance-gaps",
    response_model=ComplianceGapReport,
    status_code=status.HTTP_200_OK,
)
def get_compliance_gaps_report(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceComplianceMonitoringService = Depends(
        get_governance_compliance_monitoring_service
    ),
) -> ComplianceGapReport:
    """Generate categorized summary of identified compliance gaps."""
    _ensure_not_patient(current_user)
    return service.generate_gap_report(user=current_user, facility_id=facility_id)


@router.get(
    "/reports/control-conformance",
    response_model=ControlConformanceReport,
    status_code=status.HTTP_200_OK,
)
def get_control_conformance_report(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceComplianceMonitoringService = Depends(
        get_governance_compliance_monitoring_service
    ),
) -> ControlConformanceReport:
    """Generate report on control mapping coverage across requirements."""
    _ensure_not_patient(current_user)
    return service.generate_control_conformance_report(user=current_user, facility_id=facility_id)


@router.get(
    "/reports/evidence-completeness",
    response_model=EvidenceCompletenessReport,
    status_code=status.HTTP_200_OK,
)
def get_evidence_completeness_report(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceComplianceMonitoringService = Depends(
        get_governance_compliance_monitoring_service
    ),
) -> EvidenceCompletenessReport:
    """Generate diagnostic report on evidence item freshness and integrity."""
    _ensure_not_patient(current_user)
    return service.generate_evidence_completeness_report(user=current_user, facility_id=facility_id)


# ===========================================================================
# 3. Compliance Frameworks
# ===========================================================================

@router.post(
    "/frameworks",
    response_model=ComplianceFrameworkRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_framework(
    payload: CreateFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> ComplianceFrameworkRecord:
    """Register a new governance compliance framework."""
    _ensure_not_patient(current_user)
    return service.create_framework(user=current_user, payload=payload)


@router.get(
    "/frameworks",
    response_model=List[ComplianceFrameworkRecord],
    status_code=status.HTTP_200_OK,
)
def list_frameworks(
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    framework_type: Optional[str] = Query(None, description="Filter by framework type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> List[ComplianceFrameworkRecord]:
    """List registered compliance frameworks within tenant scope."""
    _ensure_not_patient(current_user)
    return service.list_frameworks(
        user=current_user,
        facility_id=facility_id,
        framework_type=framework_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/frameworks/{framework_id}",
    response_model=ComplianceFrameworkRecord,
    status_code=status.HTTP_200_OK,
)
def get_framework(
    framework_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> ComplianceFrameworkRecord:
    """Retrieve compliance framework details."""
    _ensure_not_patient(current_user)
    return service.get_framework(user=current_user, framework_id=framework_id)


# ===========================================================================
# 4. Compliance Requirements
# ===========================================================================

@router.post(
    "/requirements",
    response_model=ComplianceRequirementRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    payload: CreateRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> ComplianceRequirementRecord:
    """Register a new requirement under an approved framework."""
    _ensure_not_patient(current_user)
    return service.create_requirement(user=current_user, payload=payload)


@router.get(
    "/requirements",
    response_model=List[ComplianceRequirementRecord],
    status_code=status.HTTP_200_OK,
)
def list_requirements(
    framework_id: Optional[str] = Query(None, description="Filter by framework ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    lifecycle_status: Optional[str] = Query(None, description="Filter by lifecycle status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> List[ComplianceRequirementRecord]:
    """List compliance requirements within tenant scope."""
    _ensure_not_patient(current_user)
    return service.list_requirements(
        user=current_user,
        framework_id=framework_id,
        category=category,
        lifecycle_status=lifecycle_status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/requirements/{requirement_id}",
    response_model=ComplianceRequirementRecord,
    status_code=status.HTTP_200_OK,
)
def get_requirement(
    requirement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> ComplianceRequirementRecord:
    """Retrieve compliance requirement details."""
    _ensure_not_patient(current_user)
    return service.get_requirement(user=current_user, requirement_id=requirement_id)


@router.post(
    "/requirements/{requirement_id}/approve",
    response_model=ComplianceRequirementRecord,
    status_code=status.HTTP_200_OK,
)
def approve_requirement(
    requirement_id: str,
    payload: ApproveRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> ComplianceRequirementRecord:
    """Approve a draft requirement. Requires clinical governance or admin role."""
    _ensure_not_patient(current_user)
    return service.approve_requirement(
        user=current_user, requirement_id=requirement_id, payload=payload
    )


@router.post(
    "/requirements/{requirement_id}/activate",
    response_model=ComplianceRequirementRecord,
    status_code=status.HTTP_200_OK,
)
def activate_requirement(
    requirement_id: str,
    payload: ActivateRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> ComplianceRequirementRecord:
    """Activate an approved requirement for active monitoring."""
    _ensure_not_patient(current_user)
    return service.activate_requirement(
        user=current_user, requirement_id=requirement_id, payload=payload
    )


# ===========================================================================
# 5. Control Mappings
# ===========================================================================

@router.post(
    "/control-mappings",
    response_model=RequirementControlMappingRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_control_mapping(
    payload: CreateControlMappingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> RequirementControlMappingRecord:
    """Map a requirement to an authoritative workflow control."""
    _ensure_not_patient(current_user)
    return service.create_control_mapping(user=current_user, payload=payload)


@router.get(
    "/requirements/{requirement_id}/controls",
    response_model=List[RequirementControlMappingRecord],
    status_code=status.HTTP_200_OK,
)
def list_requirement_controls(
    requirement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceFrameworkService = Depends(get_compliance_framework_service),
) -> List[RequirementControlMappingRecord]:
    """List mapped controls for a requirement."""
    _ensure_not_patient(current_user)
    return service.list_control_mappings(user=current_user, requirement_id=requirement_id)


# ===========================================================================
# 6. Compliance Evidence Management
# ===========================================================================

@router.post(
    "/requirements/{requirement_id}/evidence",
    response_model=ComplianceEvidenceRecord,
    status_code=status.HTTP_201_CREATED,
)
def register_evidence(
    requirement_id: str,
    payload: RegisterEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceEvidenceManagementService = Depends(
        get_compliance_evidence_management_service
    ),
) -> ComplianceEvidenceRecord:
    """Index a supporting evidence reference against a requirement."""
    _ensure_not_patient(current_user)
    payload.requirement_id = requirement_id
    return service.register_evidence(user=current_user, payload=payload)


@router.get(
    "/requirements/{requirement_id}/evidence",
    response_model=List[ComplianceEvidenceRecord],
    status_code=status.HTTP_200_OK,
)
def list_requirement_evidence(
    requirement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceEvidenceManagementService = Depends(
        get_compliance_evidence_management_service
    ),
) -> List[ComplianceEvidenceRecord]:
    """List supporting evidence indexed for a requirement."""
    _ensure_not_patient(current_user)
    return service.list_evidence_for_requirement(
        user=current_user, requirement_id=requirement_id
    )


@router.post(
    "/requirements/{requirement_id}/evidence/reconcile",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def reconcile_requirement_evidence(
    requirement_id: str,
    payload: ReconcileEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceEvidenceManagementService = Depends(
        get_compliance_evidence_management_service
    ),
) -> Dict[str, Any]:
    """Reconcile and re-verify supporting evidence against source phases."""
    _ensure_not_patient(current_user)
    return service.reconcile_evidence(
        user=current_user, requirement_id=requirement_id, payload=payload
    )


# ===========================================================================
# 7. Compliance Assessments
# ===========================================================================

@router.post(
    "/assessments",
    response_model=ComplianceAssessmentRecord,
    status_code=status.HTTP_201_CREATED,
)
def trigger_assessment(
    payload: TriggerAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceAssessmentEngineService = Depends(
        get_compliance_assessment_engine_service
    ),
) -> ComplianceAssessmentRecord:
    """Trigger a deterministic policy-driven compliance assessment."""
    _ensure_not_patient(current_user)
    return service.evaluate_requirement(user=current_user, payload=payload)


@router.get(
    "/assessments",
    response_model=List[ComplianceAssessmentRecord],
    status_code=status.HTTP_200_OK,
)
def list_assessments(
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by compliance status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceComplianceRepository = Depends(get_governance_compliance_repository),
) -> List[ComplianceAssessmentRecord]:
    """List compliance assessment records within tenant scope."""
    _ensure_not_patient(current_user)
    return repo.list_assessments(
        organization_id=current_user.organization_id,
        facility_id=facility_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=ComplianceAssessmentRecord,
    status_code=status.HTTP_200_OK,
)
def get_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceComplianceRepository = Depends(get_governance_compliance_repository),
) -> ComplianceAssessmentRecord:
    """Retrieve compliance assessment details."""
    _ensure_not_patient(current_user)
    asm = repo.get_assessment(assessment_id)
    if not asm:
        raise AppException(
            code=ErrorCode.COMPLIANCE_ASSESSMENT_NOT_FOUND,
            message=f"Assessment {assessment_id} not found.",
            status_code=404,
        )
    if asm.organization_id != current_user.organization_id:
        raise AppException(
            code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
            message="Cannot access assessment across tenant boundaries.",
            status_code=403,
        )
    return asm


@router.post(
    "/assessments/{assessment_id}/reassess",
    response_model=ComplianceAssessmentRecord,
    status_code=status.HTTP_200_OK,
)
def reassess_assessment(
    assessment_id: str,
    payload: ReassessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceAssessmentEngineService = Depends(
        get_compliance_assessment_engine_service
    ),
) -> ComplianceAssessmentRecord:
    """Trigger reassessment of a previously evaluated requirement."""
    _ensure_not_patient(current_user)
    return service.reassess_requirement(
        user=current_user, assessment_id=assessment_id, payload=payload
    )


# ===========================================================================
# 8. Compliance Findings (Gaps) Management
# ===========================================================================

@router.get(
    "/findings",
    response_model=List[ComplianceFindingRecord],
    status_code=status.HTTP_200_OK,
)
def list_findings(
    assessment_id: Optional[str] = Query(None, description="Filter by assessment ID"),
    requirement_id: Optional[str] = Query(None, description="Filter by requirement ID"),
    gap_category: Optional[str] = Query(None, description="Filter by gap category"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    is_resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceComplianceRepository = Depends(get_governance_compliance_repository),
) -> List[ComplianceFindingRecord]:
    """List compliance findings across evaluated requirements."""
    _ensure_not_patient(current_user)
    return repo.list_findings(
        assessment_id=assessment_id,
        requirement_id=requirement_id,
        gap_category=gap_category,
        priority=priority,
        is_resolved=is_resolved,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/findings/{finding_id}",
    response_model=ComplianceFindingRecord,
    status_code=status.HTTP_200_OK,
)
def get_finding(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceGapCoordinationService = Depends(
        get_compliance_gap_coordination_service
    ),
) -> ComplianceFindingRecord:
    """Retrieve compliance finding details."""
    _ensure_not_patient(current_user)
    return service.get_finding(user=current_user, finding_id=finding_id)


@router.post(
    "/findings/{finding_id}/review",
    response_model=ComplianceFindingRecord,
    status_code=status.HTTP_200_OK,
)
def review_finding(
    finding_id: str,
    payload: ReviewFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceGapCoordinationService = Depends(
        get_compliance_gap_coordination_service
    ),
) -> ComplianceFindingRecord:
    """Record formal human governance review on a compliance finding."""
    _ensure_not_patient(current_user)
    return service.review_finding(
        user=current_user, finding_id=finding_id, payload=payload
    )


@router.post(
    "/findings/{finding_id}/resolve",
    response_model=ComplianceFindingRecord,
    status_code=status.HTTP_200_OK,
)
def resolve_finding(
    finding_id: str,
    payload: ResolveFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceGapCoordinationService = Depends(
        get_compliance_gap_coordination_service
    ),
) -> ComplianceFindingRecord:
    """Mark a compliance finding resolved with documented justification."""
    _ensure_not_patient(current_user)
    return service.resolve_finding(
        user=current_user, finding_id=finding_id, payload=payload
    )


@router.post(
    "/findings/{finding_id}/corrective-actions",
    response_model=ComplianceCorrectiveActionRequestRecord,
    status_code=status.HTTP_201_CREATED,
)
def submit_corrective_action(
    finding_id: str,
    payload: SubmitCorrectiveActionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceGapCoordinationService = Depends(
        get_compliance_gap_coordination_service
    ),
) -> ComplianceCorrectiveActionRequestRecord:
    """Initiate a Phase 54 corrective action for a compliance gap."""
    _ensure_not_patient(current_user)
    return service.submit_corrective_action(
        user=current_user, finding_id=finding_id, payload=payload
    )


@router.get(
    "/findings/{finding_id}/corrective-actions",
    response_model=List[ComplianceCorrectiveActionRequestRecord],
    status_code=status.HTTP_200_OK,
)
def list_corrective_actions(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceGapCoordinationService = Depends(
        get_compliance_gap_coordination_service
    ),
) -> List[ComplianceCorrectiveActionRequestRecord]:
    """List corrective actions requested for a finding."""
    _ensure_not_patient(current_user)
    return service.list_corrective_actions(user=current_user, finding_id=finding_id)


# ===========================================================================
# 9. Evidence Packages
# ===========================================================================

@router.post(
    "/evidence-packages",
    response_model=EvidencePackageRecord,
    status_code=status.HTTP_201_CREATED,
)
def generate_evidence_package(
    payload: GenerateEvidencePackageRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceEvidencePackageService = Depends(
        get_compliance_evidence_package_service
    ),
) -> EvidencePackageRecord:
    """Generate a controlled regulatory or governance evidence package."""
    _ensure_not_patient(current_user)
    return service.generate_package(user=current_user, payload=payload)


@router.get(
    "/evidence-packages",
    response_model=List[EvidencePackageRecord],
    status_code=status.HTTP_200_OK,
)
def list_evidence_packages(
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceEvidencePackageService = Depends(
        get_compliance_evidence_package_service
    ),
) -> List[EvidencePackageRecord]:
    """List generated evidence packages within tenant scope."""
    _ensure_not_patient(current_user)
    return service.list_packages(
        user=current_user, facility_id=facility_id, limit=limit, offset=offset
    )


@router.get(
    "/evidence-packages/{package_id}",
    response_model=EvidencePackageRecord,
    status_code=status.HTTP_200_OK,
)
def get_evidence_package(
    package_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceEvidencePackageService = Depends(
        get_compliance_evidence_package_service
    ),
) -> EvidencePackageRecord:
    """Retrieve an evidence package and log access audit."""
    _ensure_not_patient(current_user)
    return service.get_package(user=current_user, package_id=package_id)


@router.get(
    "/evidence-packages/{package_id}/status",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def get_evidence_package_status(
    package_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ComplianceEvidencePackageService = Depends(
        get_compliance_evidence_package_service
    ),
) -> Dict[str, Any]:
    """Retrieve status and integrity hash of an evidence package."""
    _ensure_not_patient(current_user)
    pkg = service.get_package(user=current_user, package_id=package_id)
    return {
        "package_id": pkg.package_id,
        "status": pkg.status.value,
        "integrity_hash": pkg.integrity_hash,
        "download_count": pkg.download_count,
        "last_accessed_at": pkg.last_accessed_at.isoformat() if pkg.last_accessed_at else None,
    }

"""Phase 84: Clinical Safety Governance Resilience Capability REST API Endpoints.

Base Route: /api/v1/governance-resilience-capability

Provides endpoints for:
- Versioned capability frameworks, review, approval, and publication
- Role-specific competency requirements and primary/backup criteria
- Capability assessment lifecycle, evidence submission, and independent verification
- Practical demonstration records (tabletops, exercises, simulations)
- Collective team readiness assessment without score averaging
- Delegated-authority emergency readiness assessment
- Capability gap identification, validation, and authoritative referral
- Multi-level operational readiness assessment and verification
- Continuous capability development remediation proposals
- Event-triggered and scheduled reassessments
- Executive analytics and management reporting
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Schemas
from app.schemas.governance_resilience_capability_framework import (
    ApproveFrameworkRequest,
    CreateFrameworkRequest,
    FrameworkLifecycleState,
    PublishFrameworkRequest,
    ResilienceCapabilityFrameworkRecord,
    SubmitFrameworkRequest,
    UpdateFrameworkRequest,
)
from app.schemas.governance_resilience_role_competency import (
    ApproveRoleRequirementRequest,
    CreateRoleRequirementRequest,
    RoleCapabilityRequirementRecord,
    RoleRequirementStatus,
    UpdateRoleRequirementRequest,
)
from app.schemas.governance_resilience_capability_assessment import (
    AssessmentLifecycleState,
    AssessmentOutcome,
    CapabilityAssessmentRecord,
    CreateAssessmentRequest,
    ReviewAssessmentRequest,
    ScheduleAssessmentRequest,
    SubmitAssessmentEvidenceRequest,
    VerifyAssessmentRequest,
)
from app.schemas.governance_resilience_capability_demonstration import (
    CapabilityDemonstrationRecord,
    DemonstrationOutcome,
    RecordDemonstrationRequest,
    ReviewDemonstrationRequest,
)
from app.schemas.governance_resilience_team_readiness import (
    AssessTeamReadinessRequest,
    TeamReadinessOutcome,
    TeamReadinessRecord,
)
from app.schemas.governance_resilience_delegated_authority_readiness import (
    AssessDelegatedAuthorityReadinessRequest,
    DelegatedAuthorityReadinessRecord,
    DelegatedAuthorityStatus,
)
from app.schemas.governance_resilience_capability_gap import (
    CapabilityGapCategory,
    CapabilityGapRecord,
    CapabilityGapSeverity,
    CapabilityGapStatus,
    DetectCapabilityGapRequest,
    DispositionCapabilityGapRequest,
    ValidateCapabilityGapRequest,
)
from app.schemas.governance_resilience_operational_readiness import (
    AssessOperationalReadinessRequest,
    OperationalReadinessOutcome,
    OperationalReadinessRecord,
    OperationalReadinessScope,
    VerifyOperationalReadinessRequest,
)
from app.schemas.governance_resilience_capability_development import (
    ApproveDevelopmentProposalRequest,
    CapabilityDevelopmentProposalRecord,
    CompleteDevelopmentProposalRequest,
    ProposalStatus,
    ProposeDevelopmentRequest,
    ReviewDevelopmentProposalRequest,
)
from app.schemas.governance_resilience_capability_reassessment import (
    CapabilityReassessmentRecord,
    CompleteReassessmentRequest,
    ReassessmentStatus,
    TriggerReassessmentRequest,
)
from app.schemas.governance_resilience_capability_reporting import (
    CapabilityCoverageReport,
    CapabilityGapsReport,
    DevelopmentProgressReport,
    OrganizationalReadinessReport,
    RoleReadinessReport,
    TeamReadinessReport,
)

# Services
from app.services.governance_resilience_capability_framework_service import (
    get_governance_resilience_capability_framework_service,
)
from app.services.governance_resilience_role_competency_service import (
    get_governance_resilience_role_competency_service,
)
from app.services.governance_resilience_capability_assessment_service import (
    get_governance_resilience_capability_assessment_service,
)
from app.services.governance_resilience_capability_demonstration_service import (
    get_governance_resilience_capability_demonstration_service,
)
from app.services.governance_resilience_team_readiness_service import (
    get_governance_resilience_team_readiness_service,
)
from app.services.governance_resilience_delegated_authority_readiness_service import (
    get_governance_resilience_delegated_authority_readiness_service,
)
from app.services.governance_resilience_capability_gap_service import (
    get_governance_resilience_capability_gap_service,
)
from app.services.governance_resilience_operational_readiness_service import (
    get_governance_resilience_operational_readiness_service,
)
from app.services.governance_resilience_capability_development_service import (
    get_governance_resilience_capability_development_service,
)
from app.services.governance_resilience_capability_reassessment_service import (
    get_governance_resilience_capability_reassessment_service,
)
from app.services.governance_resilience_capability_reporting_service import (
    get_governance_resilience_capability_reporting_service,
)


def _ensure_not_patient(current_user: AuthenticatedUserContext = Depends(get_current_user)) -> None:
    """Patients cannot access governance resilience capability assessment operations."""
    if current_user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patients are not permitted to access clinical safety governance resilience capability operations.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


router = APIRouter(
    prefix="/governance-resilience-capability",
    tags=["Clinical Safety Governance Resilience Capability Assessment"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# 1. Capability Frameworks
# =============================================================================

@router.post("/frameworks", response_model=ResilienceCapabilityFrameworkRecord, status_code=status.HTTP_201_CREATED)
def create_capability_framework(
    request: CreateFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.create_framework(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/frameworks", response_model=List[ResilienceCapabilityFrameworkRecord])
def list_capability_frameworks(
    state: Optional[FrameworkLifecycleState] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.list_frameworks(tenant_id=current_user.tenant_id, state=state)


@router.get("/frameworks/{framework_id}/versions", response_model=List[ResilienceCapabilityFrameworkRecord])
def get_framework_versions(
    framework_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.get_framework_versions(tenant_id=current_user.tenant_id, framework_id=framework_id)


@router.post("/frameworks/{framework_id}/submit", response_model=ResilienceCapabilityFrameworkRecord)
def submit_capability_framework(
    framework_id: str,
    request: SubmitFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.submit_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/frameworks/{framework_id}/approve", response_model=ResilienceCapabilityFrameworkRecord)
def approve_capability_framework(
    framework_id: str,
    request: ApproveFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.approve_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post("/frameworks/{framework_id}/publish", response_model=ResilienceCapabilityFrameworkRecord)
def publish_capability_framework(
    framework_id: str,
    request: PublishFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.publish_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/frameworks/{framework_id}", response_model=ResilienceCapabilityFrameworkRecord)
def get_capability_framework(
    framework_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.get_framework(tenant_id=current_user.tenant_id, framework_id=framework_id)


@router.patch("/frameworks/{framework_id}", response_model=ResilienceCapabilityFrameworkRecord)
def update_capability_framework(
    framework_id: str,
    request: UpdateFrameworkRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_framework_service()
    return service.update_framework(
        tenant_id=current_user.tenant_id,
        framework_id=framework_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 2. Role Competency Requirements
# =============================================================================

@router.post("/role-requirements", response_model=RoleCapabilityRequirementRecord, status_code=status.HTTP_201_CREATED)
def create_role_requirement(
    request: CreateRoleRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_role_competency_service()
    return service.create_role_requirement(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/role-requirements", response_model=List[RoleCapabilityRequirementRecord])
def list_role_requirements(
    role_name: Optional[str] = Query(None),
    framework_id: Optional[str] = Query(None),
    status_filter: Optional[RoleRequirementStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_role_competency_service()
    return service.list_role_requirements(
        tenant_id=current_user.tenant_id,
        role_name=role_name,
        framework_id=framework_id,
        status=status_filter,
    )


@router.get("/roles/{role_id}/capabilities", response_model=List[RoleCapabilityRequirementRecord])
def get_capabilities_for_role(
    role_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_role_competency_service()
    return service.list_role_requirements(tenant_id=current_user.tenant_id, role_name=role_id)


@router.post("/role-requirements/{requirement_id}/approve", response_model=RoleCapabilityRequirementRecord)
def approve_role_requirement(
    requirement_id: str,
    request: ApproveRoleRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_role_competency_service()
    return service.approve_role_requirement(
        tenant_id=current_user.tenant_id,
        requirement_id=requirement_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.get("/role-requirements/{requirement_id}", response_model=RoleCapabilityRequirementRecord)
def get_role_requirement(
    requirement_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_role_competency_service()
    return service.get_role_requirement(tenant_id=current_user.tenant_id, requirement_id=requirement_id)


@router.patch("/role-requirements/{requirement_id}", response_model=RoleCapabilityRequirementRecord)
def update_role_requirement(
    requirement_id: str,
    request: UpdateRoleRequirementRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_role_competency_service()
    return service.update_role_requirement(
        tenant_id=current_user.tenant_id,
        requirement_id=requirement_id,
        user_id=current_user.user_id,
        request=request,
    )


# =============================================================================
# 3. Practical Capability Demonstrations
# =============================================================================

@router.post("/demonstrations", response_model=CapabilityDemonstrationRecord, status_code=status.HTTP_201_CREATED)
def record_capability_demonstration(
    request: RecordDemonstrationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_demonstration_service()
    return service.record_demonstration(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/demonstrations", response_model=List[CapabilityDemonstrationRecord])
def list_capability_demonstrations(
    capability_id: Optional[str] = Query(None),
    participant_user_id: Optional[str] = Query(None),
    outcome: Optional[DemonstrationOutcome] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_demonstration_service()
    return service.list_demonstrations(
        tenant_id=current_user.tenant_id,
        capability_id=capability_id,
        participant_user_id=participant_user_id,
        outcome=outcome,
    )


@router.post("/demonstrations/{demonstration_id}/review", response_model=CapabilityDemonstrationRecord)
def review_capability_demonstration(
    demonstration_id: str,
    request: ReviewDemonstrationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_demonstration_service()
    return service.review_demonstration(
        tenant_id=current_user.tenant_id,
        demonstration_id=demonstration_id,
        reviewer_id=current_user.user_id,
        request=request,
    )


@router.get("/demonstrations/{demonstration_id}", response_model=CapabilityDemonstrationRecord)
def get_capability_demonstration(
    demonstration_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_demonstration_service()
    return service.get_demonstration(tenant_id=current_user.tenant_id, demonstration_id=demonstration_id)


# =============================================================================
# 4. Team Readiness Assessments
# =============================================================================

@router.post("/teams/{team_id}/assess-readiness", response_model=TeamReadinessRecord)
def assess_team_readiness_by_id(
    team_id: str,
    request: AssessTeamReadinessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_team_readiness_service()
    request.team_name = team_id
    return service.assess_team_readiness(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/teams/{team_id}/readiness", response_model=List[TeamReadinessRecord])
def get_team_readiness_history(
    team_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_team_readiness_service()
    all_teams = service.list_team_readiness(tenant_id=current_user.tenant_id)
    return [t for t in all_teams if t.team_name == team_id]


@router.get("/team-readiness", response_model=List[TeamReadinessRecord])
def list_team_readiness_records(
    department_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    outcome: Optional[TeamReadinessOutcome] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_team_readiness_service()
    return service.list_team_readiness(
        tenant_id=current_user.tenant_id,
        department_id=department_id,
        facility_id=facility_id,
        outcome=outcome,
    )


@router.get("/team-readiness/{team_assessment_id}", response_model=TeamReadinessRecord)
def get_team_readiness_assessment(
    team_assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_team_readiness_service()
    return service.get_team_readiness(tenant_id=current_user.tenant_id, team_assessment_id=team_assessment_id)


# =============================================================================
# 5. Delegated-Authority Readiness
# =============================================================================

@router.post("/delegated-authority-readiness/assess", response_model=DelegatedAuthorityReadinessRecord)
def assess_delegated_authority_readiness(
    request: AssessDelegatedAuthorityReadinessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_delegated_authority_readiness_service()
    return service.assess_delegated_readiness(
        tenant_id=current_user.tenant_id,
        assessor_id=current_user.user_id,
        request=request,
    )


@router.get("/delegated-authority-readiness", response_model=List[DelegatedAuthorityReadinessRecord])
def list_delegated_authority_readiness(
    delegate_user_id: Optional[str] = Query(None),
    status_filter: Optional[DelegatedAuthorityStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_delegated_authority_readiness_service()
    return service.list_delegated_readiness(
        tenant_id=current_user.tenant_id,
        delegate_user_id=delegate_user_id,
        status=status_filter,
    )


@router.get("/delegated-authority-readiness/{readiness_id}", response_model=DelegatedAuthorityReadinessRecord)
def get_delegated_authority_readiness_record(
    readiness_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_delegated_authority_readiness_service()
    return service.get_delegated_readiness(tenant_id=current_user.tenant_id, delegation_readiness_id=readiness_id)


# =============================================================================
# 6. Capability Gaps
# =============================================================================

@router.post("/capability-gaps", response_model=CapabilityGapRecord, status_code=status.HTTP_201_CREATED)
def detect_capability_gap(
    request: DetectCapabilityGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_gap_service()
    return service.detect_gap(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/capability-gaps", response_model=List[CapabilityGapRecord])
def list_capability_gaps(
    category: Optional[CapabilityGapCategory] = Query(None),
    severity: Optional[CapabilityGapSeverity] = Query(None),
    status_filter: Optional[CapabilityGapStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_gap_service()
    return service.list_gaps(
        tenant_id=current_user.tenant_id,
        category=category,
        severity=severity,
        status=status_filter,
    )


@router.post("/capability-gaps/{gap_id}/validate", response_model=CapabilityGapRecord)
def validate_capability_gap(
    gap_id: str,
    request: ValidateCapabilityGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_gap_service()
    return service.validate_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        validator_id=current_user.user_id,
        request=request,
    )


@router.post("/capability-gaps/{gap_id}/disposition", response_model=CapabilityGapRecord)
def disposition_capability_gap(
    gap_id: str,
    request: DispositionCapabilityGapRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_gap_service()
    return service.disposition_gap(
        tenant_id=current_user.tenant_id,
        gap_id=gap_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/capability-gaps/{gap_id}", response_model=CapabilityGapRecord)
def get_capability_gap(
    gap_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_gap_service()
    return service.get_gap(tenant_id=current_user.tenant_id, gap_id=gap_id)


# =============================================================================
# 7. Operational Readiness Verification
# =============================================================================

@router.post("/readiness/assess", response_model=OperationalReadinessRecord, status_code=status.HTTP_201_CREATED)
def assess_operational_readiness(
    request: AssessOperationalReadinessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_operational_readiness_service()
    return service.assess_readiness(
        tenant_id=current_user.tenant_id,
        assessor_id=current_user.user_id,
        request=request,
    )


@router.get("/readiness", response_model=List[OperationalReadinessRecord])
def list_operational_readiness(
    scope_type: Optional[OperationalReadinessScope] = Query(None),
    outcome: Optional[OperationalReadinessOutcome] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_operational_readiness_service()
    return service.list_readiness(
        tenant_id=current_user.tenant_id,
        scope_type=scope_type,
        outcome=outcome,
    )


@router.post("/readiness/{readiness_id}/verify", response_model=OperationalReadinessRecord)
def verify_operational_readiness(
    readiness_id: str,
    request: VerifyOperationalReadinessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_operational_readiness_service()
    return service.verify_readiness(
        tenant_id=current_user.tenant_id,
        readiness_id=readiness_id,
        verifier_id=current_user.user_id,
        request=request,
    )


@router.get("/readiness/{readiness_id}/history", response_model=List[OperationalReadinessRecord])
def get_operational_readiness_history(
    readiness_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_operational_readiness_service()
    return service.get_readiness_history(tenant_id=current_user.tenant_id, readiness_id=readiness_id)


@router.get("/readiness/{readiness_id}", response_model=OperationalReadinessRecord)
def get_operational_readiness(
    readiness_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_operational_readiness_service()
    return service.get_readiness(tenant_id=current_user.tenant_id, readiness_id=readiness_id)


# =============================================================================
# 8. Capability Development Proposals
# =============================================================================

@router.post("/development-proposals", response_model=CapabilityDevelopmentProposalRecord, status_code=status.HTTP_201_CREATED)
def propose_capability_development(
    request: ProposeDevelopmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_development_service()
    return service.propose_development(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/development-proposals", response_model=List[CapabilityDevelopmentProposalRecord])
def list_capability_development_proposals(
    status_filter: Optional[ProposalStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_development_service()
    return service.list_proposals(tenant_id=current_user.tenant_id, status=status_filter)


@router.post("/development-proposals/{proposal_id}/review", response_model=CapabilityDevelopmentProposalRecord)
def review_capability_development_proposal(
    proposal_id: str,
    request: ReviewDevelopmentProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_development_service()
    return service.review_proposal(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
        reviewer_id=current_user.user_id,
        request=request,
    )


@router.post("/development-proposals/{proposal_id}/approve", response_model=CapabilityDevelopmentProposalRecord)
def approve_capability_development_proposal(
    proposal_id: str,
    request: ApproveDevelopmentProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_development_service()
    return service.approve_proposal(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
        approver_id=current_user.user_id,
        request=request,
    )


@router.post("/development-proposals/{proposal_id}/complete", response_model=CapabilityDevelopmentProposalRecord)
def complete_capability_development_proposal(
    proposal_id: str,
    request: CompleteDevelopmentProposalRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_development_service()
    return service.complete_proposal(
        tenant_id=current_user.tenant_id,
        proposal_id=proposal_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/development-proposals/{proposal_id}", response_model=CapabilityDevelopmentProposalRecord)
def get_capability_development_proposal(
    proposal_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_development_service()
    return service.get_proposal(tenant_id=current_user.tenant_id, proposal_id=proposal_id)


# =============================================================================
# 9. Capability Reassessments
# =============================================================================

@router.post("/reassessments", response_model=CapabilityReassessmentRecord, status_code=status.HTTP_201_CREATED)
def trigger_capability_reassessment(
    request: TriggerReassessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reassessment_service()
    return service.trigger_reassessment(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/reassessments", response_model=List[CapabilityReassessmentRecord])
def list_capability_reassessments(
    status_filter: Optional[ReassessmentStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reassessment_service()
    return service.list_reassessments(tenant_id=current_user.tenant_id, status=status_filter)


@router.post("/reassessments/{reassessment_id}/complete", response_model=CapabilityReassessmentRecord)
def complete_capability_reassessment(
    reassessment_id: str,
    request: CompleteReassessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reassessment_service()
    return service.complete_reassessment(
        tenant_id=current_user.tenant_id,
        reassessment_id=reassessment_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/reassessments/{reassessment_id}", response_model=CapabilityReassessmentRecord)
def get_capability_reassessment(
    reassessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reassessment_service()
    return service.get_reassessment(tenant_id=current_user.tenant_id, reassessment_id=reassessment_id)


# =============================================================================
# 10. Management Reports
# =============================================================================

@router.get("/reports/capability-coverage", response_model=CapabilityCoverageReport)
def get_capability_coverage_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reporting_service()
    return service.get_capability_coverage_report(tenant_id=current_user.tenant_id)


@router.get("/reports/role-readiness", response_model=RoleReadinessReport)
def get_role_readiness_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reporting_service()
    return service.get_role_readiness_report(tenant_id=current_user.tenant_id)


@router.get("/reports/team-readiness", response_model=TeamReadinessReport)
def get_team_readiness_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reporting_service()
    return service.get_team_readiness_report(tenant_id=current_user.tenant_id)


@router.get("/reports/capability-gaps", response_model=CapabilityGapsReport)
def get_capability_gaps_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reporting_service()
    return service.get_capability_gaps_report(tenant_id=current_user.tenant_id)


@router.get("/reports/development-progress", response_model=DevelopmentProgressReport)
def get_development_progress_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reporting_service()
    return service.get_development_progress_report(tenant_id=current_user.tenant_id)


@router.get("/reports/organizational-readiness", response_model=OrganizationalReadinessReport)
def get_organizational_readiness_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_reporting_service()
    return service.get_organizational_readiness_report(tenant_id=current_user.tenant_id)


# =============================================================================
# 11. Individual Capability Assessments (Fixed + Dynamic paths)
# =============================================================================

@router.post("/assessments", response_model=CapabilityAssessmentRecord, status_code=status.HTTP_201_CREATED)
def create_capability_assessment(
    request: CreateAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.create_assessment(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.get("/assessments", response_model=List[CapabilityAssessmentRecord])
def list_capability_assessments(
    subject_user_id: Optional[str] = Query(None),
    applicable_role: Optional[str] = Query(None),
    lifecycle_state: Optional[AssessmentLifecycleState] = Query(None),
    outcome: Optional[AssessmentOutcome] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.list_assessments(
        tenant_id=current_user.tenant_id,
        subject_user_id=subject_user_id,
        applicable_role=applicable_role,
        lifecycle_state=lifecycle_state,
        outcome=outcome,
    )


@router.post("/assessments/{assessment_id}/schedule", response_model=CapabilityAssessmentRecord)
def schedule_capability_assessment(
    assessment_id: str,
    request: ScheduleAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.schedule_assessment(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/assessments/{assessment_id}/submit-evidence", response_model=CapabilityAssessmentRecord)
def submit_capability_assessment_evidence(
    assessment_id: str,
    request: SubmitAssessmentEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.submit_evidence(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        user_id=current_user.user_id,
        request=request,
    )


@router.post("/assessments/{assessment_id}/review", response_model=CapabilityAssessmentRecord)
def review_capability_assessment(
    assessment_id: str,
    request: ReviewAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.review_assessment(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        assessor_id=current_user.user_id,
        request=request,
    )


@router.post("/assessments/{assessment_id}/verify", response_model=CapabilityAssessmentRecord)
def verify_capability_assessment(
    assessment_id: str,
    request: VerifyAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.verify_assessment(
        tenant_id=current_user.tenant_id,
        assessment_id=assessment_id,
        verifier_id=current_user.user_id,
        request=request,
    )


@router.get("/assessments/{assessment_id}/history", response_model=List[CapabilityAssessmentRecord])
def get_capability_assessment_history(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.get_assessment_history(tenant_id=current_user.tenant_id, assessment_id=assessment_id)


@router.get("/assessments/{assessment_id}", response_model=CapabilityAssessmentRecord)
def get_capability_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    service = get_governance_resilience_capability_assessment_service()
    return service.get_assessment(tenant_id=current_user.tenant_id, assessment_id=assessment_id)

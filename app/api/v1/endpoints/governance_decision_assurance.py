"""Phase 68: Governance Decision Assurance REST API Endpoints.

Implements REST API endpoints for:
- Registering governance decisions across safety phases
- Triggering and managing comprehensive decision assurance evaluations
- Queue monitoring: review-required, authorization-unverifiable, policy-mismatch, decision-conflicts
- Reviewing and resolving assurance integrity findings
- Inspecting provenance, authorization, policy compliance, and evidence integrity
- Inspecting cross-workflow consistency evaluations
- Coordinating decision correction and revocation review requests
- Generating tenant-scoped decision assurance summary reports

Base Path: /api/v1/governance-decision-assurance
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_assurance_repository import (
    GovernanceDecisionAssuranceRepository,
    get_governance_decision_assurance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.decision_assurance import (
    DecisionAssuranceRecord,
    GovernanceDecisionRegisterRecord,
    RegisterDecisionRequest,
    TriggerDecisionAssuranceRequest,
)
from app.schemas.decision_assurance_finding import (
    AssuranceFindingRecord,
    ResolveAssuranceFindingRequest,
    ReviewAssuranceFindingRequest,
)
from app.schemas.decision_correction_coordination import (
    CorrectionRequestRecord,
    CrossWorkflowConsistencyCheckResult,
    DecisionAssuranceReportResponse,
    RespondCorrectionRequest,
    SubmitDecisionCorrectionRequest,
    SubmitRevocationReviewRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.decision_correction_coordination_service import (
    DecisionCorrectionCoordinationService,
    get_decision_correction_coordination_service,
)
from app.services.governance_decision_assurance_service import (
    GovernanceDecisionAssuranceService,
    get_governance_decision_assurance_service,
)

router = APIRouter(
    prefix="/governance-decision-assurance",
    tags=["Phase 68 - Governance Decision Assurance"],
)


def _ensure_not_patient(user: AuthenticatedUserContext) -> None:
    """Enforce that patient role cannot access governance decision assurance."""
    if user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patient role is not authorized to access governance decision assurance.",
            status_code=403,
        )


# ===========================================================================
# 1. Specialized Queue Endpoints (Declared first to avoid path collision)
# ===========================================================================

@router.get(
    "/queues/review-required",
    response_model=List[DecisionAssuranceRecord],
    status_code=status.HTTP_200_OK,
)
def get_review_required_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[DecisionAssuranceRecord]:
    """Retrieve decision assurance runs requiring human specialist or owner review."""
    _ensure_not_patient(current_user)
    return repo.list_review_required(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


@router.get(
    "/queues/authorization-unverifiable",
    response_model=List[DecisionAssuranceRecord],
    status_code=status.HTTP_200_OK,
)
def get_authorization_unverifiable_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[DecisionAssuranceRecord]:
    """Retrieve decision assurance runs where historical authorization could not be verified."""
    _ensure_not_patient(current_user)
    return repo.list_authorization_unverifiable(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


@router.get(
    "/queues/policy-mismatch",
    response_model=List[DecisionAssuranceRecord],
    status_code=status.HTTP_200_OK,
)
def get_policy_mismatch_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[DecisionAssuranceRecord]:
    """Retrieve decision assurance runs exhibiting policy version mismatches or invalid temporal windows."""
    _ensure_not_patient(current_user)
    return repo.list_policy_mismatch(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


@router.get(
    "/queues/decision-conflicts",
    response_model=List[DecisionAssuranceRecord],
    status_code=status.HTTP_200_OK,
)
def get_decision_conflicts_queue(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[DecisionAssuranceRecord]:
    """Retrieve decision assurance runs exhibiting cross-workflow conflicting outcomes."""
    _ensure_not_patient(current_user)
    return repo.list_decision_conflicts(
        organization_id=current_user.organization_id, facility_id=facility_id
    )


# ===========================================================================
# 2. Aggregated Reporting
# ===========================================================================

@router.get(
    "/reports/summary",
    response_model=DecisionAssuranceReportResponse,
    status_code=status.HTTP_200_OK,
)
def get_decision_assurance_summary(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
) -> DecisionAssuranceReportResponse:
    """Generate high-level aggregated assurance report across all registered decisions."""
    _ensure_not_patient(current_user)
    return service.generate_summary_report(user=current_user, facility_id=facility_id)


# ===========================================================================
# 3. Assurance Findings Management
# ===========================================================================

@router.get(
    "/findings",
    response_model=List[AssuranceFindingRecord],
    status_code=status.HTTP_200_OK,
)
def list_assurance_findings(
    category: Optional[str] = Query(None, description="Filter by finding category"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[AssuranceFindingRecord]:
    """List assurance integrity findings across evaluated decisions."""
    _ensure_not_patient(current_user)
    return repo.list_findings(
        category=category, severity=severity, limit=limit, offset=offset
    )


@router.get(
    "/findings/{finding_id}",
    response_model=AssuranceFindingRecord,
    status_code=status.HTTP_200_OK,
)
def get_assurance_finding(
    finding_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> AssuranceFindingRecord:
    """Retrieve details of a specific assurance integrity finding."""
    _ensure_not_patient(current_user)
    finding = repo.get_finding(finding_id)
    if not finding:
        raise AppException(
            code=ErrorCode.ASSURANCE_FINDING_NOT_FOUND,
            message=f"Assurance finding {finding_id} not found.",
            status_code=404,
        )
    return finding


@router.post(
    "/findings/{finding_id}/review",
    response_model=AssuranceFindingRecord,
    status_code=status.HTTP_200_OK,
)
def review_assurance_finding(
    finding_id: str,
    payload: ReviewAssuranceFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
) -> AssuranceFindingRecord:
    """Record a formal governance review on an assurance integrity finding."""
    _ensure_not_patient(current_user)
    return service.review_finding(
        user=current_user, finding_id=finding_id, payload=payload
    )


@router.post(
    "/findings/{finding_id}/resolve",
    response_model=AssuranceFindingRecord,
    status_code=status.HTTP_200_OK,
)
def resolve_assurance_finding(
    finding_id: str,
    payload: ResolveAssuranceFindingRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
) -> AssuranceFindingRecord:
    """Mark an assurance finding resolved with documented governance rationale."""
    _ensure_not_patient(current_user)
    return service.resolve_finding(
        user=current_user, finding_id=finding_id, payload=payload
    )


# ===========================================================================
# 4. Correction & Revocation Coordination
# ===========================================================================

@router.post(
    "/correction-requests/{request_id}/respond",
    response_model=CorrectionRequestRecord,
    status_code=status.HTTP_200_OK,
)
def respond_to_correction_request(
    request_id: str,
    payload: RespondCorrectionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: DecisionCorrectionCoordinationService = Depends(
        get_decision_correction_coordination_service
    ),
) -> CorrectionRequestRecord:
    """Authoritative decision owner responds to a decision correction or revocation request."""
    _ensure_not_patient(current_user)
    return service.respond_to_request(
        user=current_user, request_id=request_id, payload=payload
    )


# ===========================================================================
# 5. Governance Decision Register
# ===========================================================================

@router.post(
    "/decisions",
    response_model=GovernanceDecisionRegisterRecord,
    status_code=status.HTTP_201_CREATED,
)
def register_decision(
    payload: RegisterDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
) -> GovernanceDecisionRegisterRecord:
    """Register an authoritative clinical safety governance decision reference for assurance."""
    _ensure_not_patient(current_user)
    return service.register_decision(user=current_user, payload=payload)


@router.get(
    "/decisions",
    response_model=List[GovernanceDecisionRegisterRecord],
    status_code=status.HTTP_200_OK,
)
def list_decisions(
    facility_id: Optional[str] = Query(None, description="Optional facility filter"),
    source_phase: Optional[str] = Query(None, description="Optional source phase filter"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
) -> List[GovernanceDecisionRegisterRecord]:
    """List registered governance decisions within tenant scope."""
    _ensure_not_patient(current_user)
    return service.list_decisions(
        user=current_user,
        facility_id=facility_id,
        source_phase=source_phase,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/decisions/{decision_id}",
    response_model=GovernanceDecisionRegisterRecord,
    status_code=status.HTTP_200_OK,
)
def get_decision(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
) -> GovernanceDecisionRegisterRecord:
    """Retrieve registered decision details."""
    _ensure_not_patient(current_user)
    return service.get_decision(decision_id=decision_id, user=current_user)


# ===========================================================================
# 6. Verification & Assurance Run Execution
# ===========================================================================

@router.post(
    "/decisions/{decision_id}/verify",
    response_model=DecisionAssuranceRecord,
    status_code=status.HTTP_200_OK,
)
def verify_decision(
    decision_id: str,
    payload: TriggerDecisionAssuranceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
) -> DecisionAssuranceRecord:
    """Execute a comprehensive multi-dimensional decision assurance evaluation run."""
    _ensure_not_patient(current_user)
    return service.verify_decision(
        user=current_user, decision_id=decision_id, payload=payload
    )


@router.get(
    "/decisions/{decision_id}/assurance",
    response_model=DecisionAssuranceRecord,
    status_code=status.HTTP_200_OK,
)
def get_latest_assurance(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> DecisionAssuranceRecord:
    """Retrieve the latest assurance evaluation run for a registered decision."""
    _ensure_not_patient(current_user)
    # Check tenant access
    service.get_decision(decision_id, current_user)
    latest = repo.get_latest_assurance_for_decision(decision_id)
    if not latest:
        raise AppException(
            code=ErrorCode.DECISION_ASSURANCE_NOT_FOUND,
            message=f"No assurance evaluation found for decision {decision_id}.",
            status_code=404,
        )
    return latest


@router.get(
    "/decisions/{decision_id}/history",
    response_model=List[DecisionAssuranceRecord],
    status_code=status.HTTP_200_OK,
)
def get_assurance_history(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[DecisionAssuranceRecord]:
    """Retrieve historical assurance evaluation runs for a registered decision."""
    _ensure_not_patient(current_user)
    service.get_decision(decision_id, current_user)
    return repo.list_assurance_history_for_decision(decision_id)


# ===========================================================================
# 7. Verification Sub-aspects & Consistency
# ===========================================================================

@router.get(
    "/decisions/{decision_id}/provenance",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def get_decision_provenance(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> Dict[str, Any]:
    """Retrieve provenance verification details for a registered decision."""
    _ensure_not_patient(current_user)
    service.get_decision(decision_id, current_user)
    latest = repo.get_latest_assurance_for_decision(decision_id)
    return {
        "decision_id": decision_id,
        "provenance_verified": latest.provenance_verified if latest else False,
        "provenance_details": latest.provenance_details if latest else {},
    }


@router.get(
    "/decisions/{decision_id}/authorization",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def get_decision_authorization(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> Dict[str, Any]:
    """Retrieve authorization integrity and separation-of-duties details for a decision."""
    _ensure_not_patient(current_user)
    service.get_decision(decision_id, current_user)
    latest = repo.get_latest_assurance_for_decision(decision_id)
    return {
        "decision_id": decision_id,
        "authorization_status": latest.authorization_status.value if latest else "UNKNOWN",
        "separation_of_duties_status": latest.separation_of_duties_status.value if latest else "UNKNOWN",
        "authorization_details": latest.authorization_details if latest else {},
    }


@router.get(
    "/decisions/{decision_id}/policy-compliance",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def get_decision_policy_compliance(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> Dict[str, Any]:
    """Retrieve policy compliance and temporal applicability details for a decision."""
    _ensure_not_patient(current_user)
    service.get_decision(decision_id, current_user)
    latest = repo.get_latest_assurance_for_decision(decision_id)
    return {
        "decision_id": decision_id,
        "policy_compliance_verified": latest.policy_compliance_verified if latest else False,
        "policy_details": latest.policy_details if latest else {},
    }


@router.get(
    "/decisions/{decision_id}/evidence-integrity",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def get_decision_evidence_integrity(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> Dict[str, Any]:
    """Retrieve supporting evidence integrity status and details for a decision."""
    _ensure_not_patient(current_user)
    service.get_decision(decision_id, current_user)
    latest = repo.get_latest_assurance_for_decision(decision_id)
    return {
        "decision_id": decision_id,
        "evidence_assurance_status": latest.evidence_assurance_status.value if latest else "UNKNOWN",
        "evidence_details": latest.evidence_details if latest else {},
    }


@router.get(
    "/decisions/{decision_id}/consistency-checks",
    response_model=List[CrossWorkflowConsistencyCheckResult],
    status_code=status.HTTP_200_OK,
)
def get_decision_consistency_checks(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[CrossWorkflowConsistencyCheckResult]:
    """Retrieve cross-workflow consistency checks executed for a registered decision."""
    _ensure_not_patient(current_user)
    service.get_decision(decision_id, current_user)
    return repo.list_consistency_checks_for_decision(decision_id)


# ===========================================================================
# 8. Correction & Revocation Requests on Decisions
# ===========================================================================

@router.post(
    "/decisions/{decision_id}/correction-requests",
    response_model=CorrectionRequestRecord,
    status_code=status.HTTP_201_CREATED,
)
def submit_decision_correction_request(
    decision_id: str,
    payload: SubmitDecisionCorrectionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: DecisionCorrectionCoordinationService = Depends(
        get_decision_correction_coordination_service
    ),
) -> CorrectionRequestRecord:
    """Submit a formal decision correction request to the authoritative workflow owner."""
    _ensure_not_patient(current_user)
    return service.submit_correction_request(
        user=current_user, decision_id=decision_id, payload=payload
    )


@router.post(
    "/decisions/{decision_id}/revocation-review-requests",
    response_model=CorrectionRequestRecord,
    status_code=status.HTTP_201_CREATED,
)
def submit_decision_revocation_review_request(
    decision_id: str,
    payload: SubmitRevocationReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: DecisionCorrectionCoordinationService = Depends(
        get_decision_correction_coordination_service
    ),
) -> CorrectionRequestRecord:
    """Submit a formal decision revocation review request to the authoritative workflow owner."""
    _ensure_not_patient(current_user)
    return service.submit_revocation_review_request(
        user=current_user, decision_id=decision_id, payload=payload
    )


@router.get(
    "/decisions/{decision_id}/correction-requests",
    response_model=List[CorrectionRequestRecord],
    status_code=status.HTTP_200_OK,
)
def list_decision_correction_requests(
    decision_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GovernanceDecisionAssuranceService = Depends(
        get_governance_decision_assurance_service
    ),
    repo: GovernanceDecisionAssuranceRepository = Depends(
        get_governance_decision_assurance_repository
    ),
) -> List[CorrectionRequestRecord]:
    """List correction and revocation review requests for a decision."""
    _ensure_not_patient(current_user)
    service.get_decision(decision_id, current_user)
    return repo.list_corrections_for_decision(decision_id)

"""Phase 66: Clinical Safety Post-Closure Verification Endpoints.

Implements REST API endpoints for:
- Triggering post-closure verification
- Retrying failed/interrupted verification
- Listing verifications and integrity findings
- Reviewing and resolving integrity findings
- Managing post-closure monitoring status
- Submitting reassessment and reopening requests
- Retrieving comprehensive post-closure verification history

Base Path: /api/v1/safety-workflow-completions
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.schemas.safety_integrity_finding import (
    FindingCategory,
    FindingLifecycleState,
    IntegrityFindingRecord,
    ResolveFindingRequest,
    ReviewFindingRequest,
)
from app.schemas.safety_post_closure_monitoring import (
    PostClosureHistoryResponse,
    PostClosureMonitoringStatus,
    ReassessmentRecord,
    ReassessmentRequest,
    ReopeningCoordinationRecord,
    ReopeningCoordinationRequest,
)
from app.schemas.safety_post_closure_verification import (
    PostClosureVerificationRecord,
    TriggerPostClosureVerificationRequest,
    VerificationRetryRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_post_closure_verification_service import (
    SafetyPostClosureVerificationService,
    get_safety_post_closure_verification_service,
)

router = APIRouter(prefix="/safety-workflow-completions", tags=["Phase 66 - Post-Closure Verification"])


# ---------------------------------------------------------------------------
# Filtered Listing Endpoints (Declared first to avoid /{completion_id} collision)
# ---------------------------------------------------------------------------


@router.get(
    "/post-closure-verifications/pending",
    response_model=List[PostClosureVerificationRecord],
    summary="List active pending or scheduled post-closure verification runs",
)
def list_pending_verifications(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all pending or running verification executions for the tenant."""
    return service.list_pending_verifications(
        user=current_user,
        facility_id=facility_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/post-closure-verifications/failed",
    response_model=List[PostClosureVerificationRecord],
    summary="List failed or interrupted post-closure verification runs",
)
def list_failed_verifications(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all failed, conflicted, or dependency-interrupted verifications."""
    return service.list_failed_verifications(
        user=current_user,
        facility_id=facility_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/integrity-findings/review-required",
    response_model=List[IntegrityFindingRecord],
    summary="List post-closure integrity findings awaiting clinician review",
)
def list_review_required_findings(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve integrity findings requiring clinician or administrative review."""
    return service.list_review_required_findings(
        user=current_user,
        facility_id=facility_id,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Verification Executions (Per Completion)
# ---------------------------------------------------------------------------


@router.post(
    "/{completion_id}/post-closure-verifications",
    response_model=PostClosureVerificationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger post-closure integrity verification",
)
def trigger_post_closure_verification(
    completion_id: str,
    request: TriggerPostClosureVerificationRequest,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Execute authoritative post-closure verification against upstream and downstream states."""
    return service.trigger_verification(
        completion_id=completion_id,
        request=request,
        user=current_user,
    )


@router.get(
    "/{completion_id}/post-closure-verifications",
    response_model=List[PostClosureVerificationRecord],
    summary="List verification executions for a completion workflow",
)
def list_post_closure_verifications(
    completion_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve historical verification execution records for a completion workflow."""
    return service.list_verifications(
        completion_id=completion_id,
        user=current_user,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{completion_id}/post-closure-verifications/{verification_id}",
    response_model=PostClosureVerificationRecord,
    summary="Get details of a specific verification execution",
)
def get_post_closure_verification(
    completion_id: str,
    verification_id: str,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve details, evaluated checks, and limitations for a verification run."""
    return service.get_verification(
        completion_id=completion_id,
        verification_id=verification_id,
        user=current_user,
    )


@router.post(
    "/{completion_id}/post-closure-verifications/{verification_id}/retry",
    response_model=PostClosureVerificationRecord,
    summary="Retry a failed or interrupted post-closure verification",
)
def retry_post_closure_verification(
    completion_id: str,
    verification_id: str,
    request: VerificationRetryRequest,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retry an incomplete or failed verification execution."""
    return service.retry_verification(
        completion_id=completion_id,
        verification_id=verification_id,
        request=request,
        user=current_user,
    )


# ---------------------------------------------------------------------------
# Integrity Findings
# ---------------------------------------------------------------------------


@router.get(
    "/{completion_id}/integrity-findings",
    response_model=List[IntegrityFindingRecord],
    summary="List integrity findings for a completion workflow",
)
def list_integrity_findings(
    completion_id: str,
    verification_id: Optional[str] = Query(None),
    lifecycle_state: Optional[FindingLifecycleState] = Query(None),
    category: Optional[FindingCategory] = Query(None),
    is_material: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve all integrity findings generated during post-closure verifications."""
    return service.list_findings(
        completion_id=completion_id,
        user=current_user,
        verification_id=verification_id,
        lifecycle_state=lifecycle_state,
        category=category,
        is_material=is_material,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{completion_id}/integrity-findings/{finding_id}",
    response_model=IntegrityFindingRecord,
    summary="Get specific integrity finding details",
)
def get_integrity_finding(
    completion_id: str,
    finding_id: str,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve finding details, expected vs observed state, and audit references."""
    return service.get_finding(
        completion_id=completion_id,
        finding_id=finding_id,
        user=current_user,
    )


@router.post(
    "/{completion_id}/integrity-findings/{finding_id}/review",
    response_model=IntegrityFindingRecord,
    summary="Review an integrity finding",
)
def review_integrity_finding(
    completion_id: str,
    finding_id: str,
    request: ReviewFindingRequest,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Review an integrity finding and record confirmation, dismissal, or escalation."""
    return service.review_finding(
        completion_id=completion_id,
        finding_id=finding_id,
        request=request,
        user=current_user,
    )


@router.post(
    "/{completion_id}/integrity-findings/{finding_id}/resolve",
    response_model=IntegrityFindingRecord,
    summary="Resolve an integrity finding",
)
def resolve_integrity_finding(
    completion_id: str,
    finding_id: str,
    request: ResolveFindingRequest,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Resolve an integrity finding while preserving complete provenance and evidence."""
    return service.resolve_finding(
        completion_id=completion_id,
        finding_id=finding_id,
        request=request,
        user=current_user,
    )


# ---------------------------------------------------------------------------
# Monitoring Status, Reassessment & Reopening
# ---------------------------------------------------------------------------


@router.get(
    "/{completion_id}/monitoring-status",
    response_model=PostClosureMonitoringStatus,
    summary="Get post-closure monitoring operational status",
)
def get_monitoring_status(
    completion_id: str,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve current post-closure monitoring policy and evaluation schedules."""
    return service.get_monitoring_status(
        completion_id=completion_id,
        user=current_user,
    )


@router.post(
    "/{completion_id}/reassessment-requests",
    response_model=ReassessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a policy-controlled workflow reassessment request",
)
def request_reassessment(
    completion_id: str,
    request: ReassessmentRequest,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Submit a governed workflow reassessment request."""
    return service.request_reassessment(
        completion_id=completion_id,
        request=request,
        user=current_user,
    )


@router.post(
    "/{completion_id}/reopening-requests",
    response_model=ReopeningCoordinationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a governed workflow reopening coordination request",
)
def request_reopening(
    completion_id: str,
    request: ReopeningCoordinationRequest,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Submit a workflow reopening request and coordinate authorized reopening through Phase 65."""
    return service.request_reopening(
        completion_id=completion_id,
        request=request,
        user=current_user,
    )


@router.get(
    "/{completion_id}/post-closure-history",
    response_model=PostClosureHistoryResponse,
    summary="Get chronological post-closure history and preserved closure evidence",
)
def get_post_closure_history(
    completion_id: str,
    service: SafetyPostClosureVerificationService = Depends(get_safety_post_closure_verification_service),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    """Retrieve full audit history of verifications, findings, reassessments, and reopenings."""
    return service.get_post_closure_history(
        completion_id=completion_id,
        user=current_user,
    )

"""Phase 65: Clinical Safety Workflow Completion Endpoints.

Base Path: /api/v1/safety-workflow-completions
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.schemas.safety_completion_action import (
    AuthorizeCompletionRequest,
    CloseCompletionWorkflowRequest,
    CompletionAuthorizationRecord,
    CompletionClosureRecord,
    CompletionReopenRecord,
    ReassessCompletionWorkflowRequest,
    ReconcileCompletionWorkflowRequest,
    ReopenCompletionWorkflowRequest,
)
from app.schemas.safety_completion_history import (
    CompletionHistoryEntry,
    CompletionStatusResponse,
)
from app.schemas.safety_completion_readiness import (
    EvaluateReadinessRequest,
    ReadinessEvaluationRecord,
)
from app.schemas.safety_completion_review import (
    CompletionReviewRecord,
    SubmitCompletionReviewRequest,
)
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    CreateSafetyWorkflowCompletionRequest,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_workflow_completion_service import (
    SafetyWorkflowCompletionService,
    get_safety_workflow_completion_service,
)

router = APIRouter(prefix="/safety-workflow-completions", tags=["Phase 65 - Safety Workflow Completions"])


# ---------------------------------------------------------------------------
# Filtered Listing Endpoints (Declared before /{completion_id} to avoid conflicts)
# ---------------------------------------------------------------------------


@router.get(
    "/pending",
    response_model=List[SafetyWorkflowCompletionRecord],
    summary="List completion workflows with unresolved requirements or handoffs",
)
def list_pending_completions(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyWorkflowCompletionRecord]:
    return service.list_pending(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/blocked",
    response_model=List[SafetyWorkflowCompletionRecord],
    summary="List blocked completion workflows within caller's authorized scope",
)
def list_blocked_completions(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyWorkflowCompletionRecord]:
    return service.list_blocked(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/review-required",
    response_model=List[SafetyWorkflowCompletionRecord],
    summary="List completion workflows awaiting authorized human review",
)
def list_review_required_completions(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyWorkflowCompletionRecord]:
    return service.list_review_required(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/reopen-required",
    response_model=List[SafetyWorkflowCompletionRecord],
    summary="List workflows requiring reopening or reassessment",
)
def list_reopen_required_completions(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyWorkflowCompletionRecord]:
    return service.list_reopen_required(user, facility_id=facility_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# General Collection Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SafetyWorkflowCompletionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize a completion-coordination workflow from an authorized Phase 63 disposition",
)
def create_safety_workflow_completion(
    request: CreateSafetyWorkflowCompletionRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyWorkflowCompletionRecord:
    return service.create_completion(request, user)


@router.get(
    "",
    response_model=List[SafetyWorkflowCompletionRecord],
    summary="List authorized completion workflows with pagination and filters",
)
def list_safety_workflow_completions(
    facility_id: Optional[str] = Query(None),
    state: Optional[CompletionLifecycleState] = Query(None),
    readiness_state: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyWorkflowCompletionRecord]:
    return service.list_completions(
        user,
        facility_id=facility_id,
        state=state,
        readiness_state=readiness_state,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Item-Level Detail and Subresource Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{completion_id}",
    response_model=SafetyWorkflowCompletionRecord,
    summary="Retrieve authorized completion workflow details",
)
def get_completion_details(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyWorkflowCompletionRecord:
    return service.get_completion(completion_id, user)


@router.get(
    "/{completion_id}/status",
    response_model=CompletionStatusResponse,
    summary="Retrieve lifecycle status and completion metrics",
)
def get_completion_status(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> CompletionStatusResponse:
    return service.get_status(completion_id, user)


@router.get(
    "/{completion_id}/readiness",
    response_model=ReadinessEvaluationRecord,
    summary="Retrieve the latest readiness evaluation",
)
def get_completion_readiness(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReadinessEvaluationRecord:
    return service.get_readiness(completion_id, user)


@router.post(
    "/{completion_id}/evaluate",
    response_model=ReadinessEvaluationRecord,
    summary="Request an on-demand readiness evaluation",
)
def evaluate_completion_readiness(
    completion_id: str,
    request: EvaluateReadinessRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReadinessEvaluationRecord:
    return service.evaluate_readiness(completion_id, request, user)


@router.get(
    "/{completion_id}/requirements",
    response_model=List[Dict[str, Any]],
    summary="Retrieve the requirement register",
)
def get_completion_requirements(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return service.get_requirements(completion_id, user)


@router.get(
    "/{completion_id}/outcomes",
    response_model=List[Dict[str, Any]],
    summary="Retrieve authorized destination-outcome references",
)
def get_completion_outcomes(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return service.get_outcomes(completion_id, user)


@router.get(
    "/{completion_id}/follow-ups",
    response_model=List[Dict[str, Any]],
    summary="Retrieve outstanding and completed follow-up references",
)
def get_completion_follow_ups(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return service.get_follow_ups(completion_id, user)


@router.get(
    "/{completion_id}/package",
    response_model=Dict[str, Any],
    summary="Retrieve the 22-point authorized completion package",
)
def get_completion_package(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    return service.get_package(completion_id, user)


@router.get(
    "/{completion_id}/history",
    response_model=List[Dict[str, Any]],
    summary="Retrieve completion audit history",
)
def get_completion_history(
    completion_id: str,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return service.get_history(completion_id, user)


# ---------------------------------------------------------------------------
# Governance Actions: Review, Authorize, Close, Reconcile, Reopen, Reassess
# ---------------------------------------------------------------------------


@router.post(
    "/{completion_id}/review",
    response_model=CompletionReviewRecord,
    summary="Submit an authorized completion-review outcome",
)
def submit_completion_review(
    completion_id: str,
    request: SubmitCompletionReviewRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> CompletionReviewRecord:
    return service.submit_review(completion_id, request, user)


@router.post(
    "/{completion_id}/authorize",
    response_model=CompletionAuthorizationRecord,
    summary="Record completion authorization where required",
)
def authorize_completion(
    completion_id: str,
    request: AuthorizeCompletionRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> CompletionAuthorizationRecord:
    return service.authorize_completion(completion_id, request, user)


@router.post(
    "/{completion_id}/close",
    response_model=CompletionClosureRecord,
    summary="Request controlled workflow closure",
)
def close_completion_workflow(
    completion_id: str,
    request: CloseCompletionWorkflowRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> CompletionClosureRecord:
    return service.close_workflow(completion_id, request, user)


@router.post(
    "/{completion_id}/reconcile",
    response_model=SafetyWorkflowCompletionRecord,
    summary="Reconcile updated destination outcomes or follow-up references",
)
def reconcile_completion_workflow(
    completion_id: str,
    request: ReconcileCompletionWorkflowRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyWorkflowCompletionRecord:
    return service.reconcile_workflow(completion_id, request, user)


@router.post(
    "/{completion_id}/reopen",
    response_model=CompletionReopenRecord,
    summary="Request workflow reopening under configured policy",
)
def reopen_completion_workflow(
    completion_id: str,
    request: ReopenCompletionWorkflowRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> CompletionReopenRecord:
    return service.reopen_workflow(completion_id, request, user)


@router.post(
    "/{completion_id}/reassess",
    response_model=SafetyWorkflowCompletionRecord,
    summary="Request a new completion evaluation because relevant context has changed",
)
def reassess_completion_workflow(
    completion_id: str,
    request: ReassessCompletionWorkflowRequest,
    service: SafetyWorkflowCompletionService = Depends(get_safety_workflow_completion_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyWorkflowCompletionRecord:
    return service.reassess_workflow(completion_id, request, user)

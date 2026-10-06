"""Clinical Decision Traceability & Explanation API Endpoints (Phase 47).

Provides:
- Decision record creation and retrieval
- Full decision trace inspection
- Structured, audience-tailored explanations (Patient vs Clinician)
- Human oversight review submission (Approval, Rejection, Modification)
- Controlled application of approved decisions to clinical workflow
- Analytical decision comparison
- Patient and resource-scoped decision queries
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_audit_service,
    get_current_user,
)
from app.core.exceptions import (
    DecisionAccessDeniedException,
    DecisionNotFoundException,
)
from app.core.logging import request_id_ctx_var
from app.schemas.decision_review import DecisionReviewRecord, DecisionReviewRequest
from app.schemas.decision_trace import (
    DecisionComparisonResponse,
    DecisionTraceResponse,
)
from app.schemas.decisions import (
    DecisionApplyRequest,
    DecisionCreateRequest,
    DecisionRecord,
)
from app.schemas.explanations import ExplanationAudience, ExplanationResponse
from app.schemas.response import (
    StandardErrorResponse,
    StandardSuccessResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.decision_application_service import (
    DecisionApplicationService,
    decision_application_service,
)
from app.services.decision_replay_service import (
    DecisionReplayService,
    decision_replay_service,
)
from app.services.decision_review_service import (
    DecisionReviewService,
    decision_review_service,
)
from app.services.decision_service import DecisionService, decision_service
from app.services.explanation_service import (
    ExplanationService,
    explanation_service,
)

router = APIRouter(tags=["Clinical Decision Traceability & Human Oversight"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


@router.post(
    "/decisions",
    response_model=StandardSuccessResponse[DecisionRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create clinical decision record",
    description="Registers a new traceable system-generated decision or recommendation.",
)
async def create_decision_endpoint(
    request: Request,
    body: DecisionCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[DecisionRecord]:
    """Create decision trace."""
    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    created = await decision_service.create_decision(
        request=body,
        actor_id=current_user.user_id,
        actor_role=actor_role_str,
        correlation_id=_req_id(request),
    )
    return StandardSuccessResponse(
        success=True,
        data=created,
        request_id=_req_id(request),
    )


@router.get(
    "/decisions/compare",
    response_model=StandardSuccessResponse[DecisionComparisonResponse],
    summary="Compare two decision records",
    description="Analyzes input, rule, and output changes between two decision versions.",
)
async def compare_decisions_endpoint(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    base_id: str = Query(..., description="Base decision ID"),
    compared_id: str = Query(..., description="Target decision ID"),
) -> StandardSuccessResponse[DecisionComparisonResponse]:
    """Compare two decisions."""
    comparison = decision_replay_service.compare_decisions(base_id=base_id, compared_id=compared_id)
    return StandardSuccessResponse(
        success=True,
        data=comparison,
        request_id=_req_id(request),
    )


@router.get(
    "/decisions/{decision_id}",
    response_model=StandardSuccessResponse[DecisionRecord],
    summary="Get clinical decision record",
    description="Retrieves a decision record by unique identifier.",
)
async def get_decision_endpoint(
    request: Request,
    decision_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[DecisionRecord]:
    """Retrieve decision record."""
    decision = decision_service.get_decision(decision_id)
    if not decision:
        raise DecisionNotFoundException(f"Decision {decision_id} not found.")

    # Patient isolation check
    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if actor_role_str.upper() == "PATIENT" and decision.patient_id != current_user.user_id:
        raise DecisionAccessDeniedException("Cross-patient decision inspection is prohibited.")

    return StandardSuccessResponse(
        success=True,
        data=decision,
        request_id=_req_id(request),
    )


@router.get(
    "/decisions/{decision_id}/trace",
    response_model=StandardSuccessResponse[DecisionTraceResponse],
    summary="Get detailed decision trace",
    description="Retrieves end-to-end trace with input references, reviews, and downstream links.",
)
async def get_decision_trace_endpoint(
    request: Request,
    decision_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[DecisionTraceResponse]:
    """Inspect full decision trace."""
    decision = decision_service.get_decision(decision_id)
    if not decision:
        raise DecisionNotFoundException(f"Decision {decision_id} not found.")

    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if actor_role_str.upper() == "PATIENT" and decision.patient_id != current_user.user_id:
        raise DecisionAccessDeniedException("Cross-patient decision inspection is prohibited.")

    trace = decision_replay_service.get_decision_trace(decision_id)
    return StandardSuccessResponse(
        success=True,
        data=trace,
        request_id=_req_id(request),
    )


@router.get(
    "/decisions/{decision_id}/explanation",
    response_model=StandardSuccessResponse[ExplanationResponse],
    summary="Get structured decision explanation",
    description="Generates an audience-tailored explanation for clinicians or patients.",
)
async def get_decision_explanation_endpoint(
    request: Request,
    decision_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    audience: ExplanationAudience = Query(default=ExplanationAudience.CLINICIAN),
) -> StandardSuccessResponse[ExplanationResponse]:
    """Retrieve explanation."""
    decision = decision_service.get_decision(decision_id)
    if not decision:
        raise DecisionNotFoundException(f"Decision {decision_id} not found.")

    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if actor_role_str.upper() == "PATIENT":
        if decision.patient_id != current_user.user_id:
            raise DecisionAccessDeniedException("Cross-patient access denied.")
        # Force patient audience for patient caller
        audience = ExplanationAudience.PATIENT

    expl = explanation_service.generate_explanation(decision=decision, audience=audience)
    return StandardSuccessResponse(
        success=True,
        data=expl,
        request_id=_req_id(request),
    )


@router.get(
    "/decisions/{decision_id}/reviews",
    response_model=StandardSuccessResponse[List[DecisionReviewRecord]],
    summary="Get decision human oversight reviews",
    description="Returns chronological review determinations made by clinicians.",
)
async def get_decision_reviews_endpoint(
    request: Request,
    decision_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[List[DecisionReviewRecord]]:
    """List oversight reviews."""
    decision = decision_service.get_decision(decision_id)
    if not decision:
        raise DecisionNotFoundException(f"Decision {decision_id} not found.")

    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if actor_role_str.upper() == "PATIENT" and decision.patient_id != current_user.user_id:
        raise DecisionAccessDeniedException("Cross-patient access denied.")

    reviews = decision_review_service.repository.get_reviews(decision_id)
    return StandardSuccessResponse(
        success=True,
        data=reviews,
        request_id=_req_id(request),
    )


@router.post(
    "/decisions/{decision_id}/review",
    response_model=StandardSuccessResponse[DecisionRecord],
    summary="Submit human oversight review",
    description="Records clinical approval, rejection, or modification of a system recommendation.",
)
async def submit_decision_review_endpoint(
    request: Request,
    decision_id: str,
    body: DecisionReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[DecisionRecord]:
    """Submit clinical review."""
    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    updated_decision, _ = await decision_review_service.submit_review(
        decision_id=decision_id,
        request=body,
        reviewer_id=current_user.user_id,
        reviewer_role=actor_role_str,
    )
    return StandardSuccessResponse(
        success=True,
        data=updated_decision,
        request_id=_req_id(request),
    )


@router.post(
    "/decisions/{decision_id}/apply",
    response_model=StandardSuccessResponse[DecisionRecord],
    summary="Apply approved decision",
    description="Triggers controlled downstream clinical action for an approved decision.",
)
async def apply_decision_endpoint(
    request: Request,
    decision_id: str,
    body: DecisionApplyRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[DecisionRecord]:
    """Apply approved decision."""
    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    applied = await decision_application_service.apply_decision(
        decision_id=decision_id,
        request=body,
        actor_id=current_user.user_id,
        actor_role=actor_role_str,
    )
    return StandardSuccessResponse(
        success=True,
        data=applied,
        request_id=_req_id(request),
    )


@router.get(
    "/patients/{patient_id}/decisions",
    response_model=StandardSuccessResponse[List[DecisionRecord]],
    summary="List patient decisions",
    description="Retrieves decisions associated with a patient.",
)
async def list_patient_decisions_endpoint(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=100),
) -> StandardSuccessResponse[List[DecisionRecord]]:
    """List decisions by patient."""
    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if actor_role_str.upper() == "PATIENT" and patient_id != current_user.user_id:
        raise DecisionAccessDeniedException("Cross-patient access denied.")

    records = decision_service.list_by_patient(patient_id=patient_id, limit=limit)
    return StandardSuccessResponse(
        success=True,
        data=records,
        request_id=_req_id(request),
    )


@router.get(
    "/resources/{resource_type}/{resource_id}/decisions",
    response_model=StandardSuccessResponse[List[DecisionRecord]],
    summary="List resource decisions",
    description="Retrieves decisions evaluating a specific clinical resource.",
)
async def list_resource_decisions_endpoint(
    request: Request,
    resource_type: str,
    resource_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=100),
) -> StandardSuccessResponse[List[DecisionRecord]]:
    """List decisions by resource."""
    records = decision_service.list_by_resource(resource_type=resource_type, resource_id=resource_id, limit=limit)
    return StandardSuccessResponse(
        success=True,
        data=records,
        request_id=_req_id(request),
    )

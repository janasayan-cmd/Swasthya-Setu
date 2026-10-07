"""Phase 55: Clinical Safety Oversight Action Effectiveness, Outcome Validation & Continuous Feedback APIs.

TRD Section 30 Endpoints:
  POST /action-effectiveness/evaluations
  GET  /action-effectiveness/evaluations/{evaluation_id}
  GET  /action-effectiveness/evaluations/{evaluation_id}/status
  GET  /action-effectiveness/evaluations/{evaluation_id}/evidence
  GET  /action-effectiveness/evaluations/{evaluation_id}/criteria
  GET  /action-effectiveness/evaluations/{evaluation_id}/history
  GET  /action-effectiveness/evaluations/{evaluation_id}/comparison
  GET  /action-effectiveness/evaluations/{evaluation_id}/effectiveness
  POST /action-effectiveness/evaluations/{evaluation_id}/review
  POST /action-effectiveness/evaluations/{evaluation_id}/accept
  POST /action-effectiveness/evaluations/{evaluation_id}/reject
  POST /action-effectiveness/evaluations/{evaluation_id}/reassess
  POST /action-effectiveness/evaluations/{evaluation_id}/reopen
  POST /action-effectiveness/evaluations/{evaluation_id}/collect
  POST /action-effectiveness/evaluations/{evaluation_id}/finalize
  GET  /action-effectiveness/evaluations
  GET  /action-effectiveness/pending
  GET  /action-effectiveness/review-required
  GET  /action-effectiveness/regressions
  GET  /action-effectiveness/insufficient-evidence
  GET  /action-effectiveness/failed
  POST /action-effectiveness/reanalysis
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.action_effectiveness import (
    AcceptEvaluationRequest,
    CollectEvidenceRequest,
    CreateEvaluationRequest,
    EffectivenessEvaluationRecord,
    EffectivenessLifecycleState,
    EffectivenessState,
    EvaluationComparisonResponse,
    EvaluationCriteriaResponse,
    EvaluationEvidenceResponse,
    EvaluationHistoryResponse,
    EvaluationStatusResponse,
    FinalizeEvaluationRequest,
    ReanalysisRequest,
    ReassessmentRequest,
    RejectEvaluationRequest,
    ReopenEvaluationRequest,
    SubmitReviewRequest,
)
from app.schemas.response import StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.action_effectiveness_service import (
    ActionEffectivenessService,
    get_action_effectiveness_service,
)

router = APIRouter(
    prefix="/action-effectiveness",
    tags=["Clinical Safety Oversight Action Effectiveness, Outcome Validation & Continuous Feedback"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


@router.post(
    "/evaluations",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Action Effectiveness Evaluation",
)
async def create_evaluation(
    http_request: Request,
    request_body: CreateEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    eval_record = service.create_evaluation(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=eval_record, request_id=req_id)


@router.get(
    "/pending",
    response_model=StandardSuccessResponse[List[EffectivenessEvaluationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Pending Evaluations",
)
async def list_pending_evaluations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[List[EffectivenessEvaluationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_pending(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/review-required",
    response_model=StandardSuccessResponse[List[EffectivenessEvaluationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Evaluations Requiring Human Review",
)
async def list_review_required_evaluations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[List[EffectivenessEvaluationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_review_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/regressions",
    response_model=StandardSuccessResponse[List[EffectivenessEvaluationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Control Regressions",
)
async def list_regression_evaluations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[List[EffectivenessEvaluationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_regressions(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/insufficient-evidence",
    response_model=StandardSuccessResponse[List[EffectivenessEvaluationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Evaluations With Insufficient Evidence",
)
async def list_insufficient_evidence_evaluations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[List[EffectivenessEvaluationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_insufficient_evidence(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/failed",
    response_model=StandardSuccessResponse[List[EffectivenessEvaluationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Failed Effectiveness Evaluations",
)
async def list_failed_evaluations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[List[EffectivenessEvaluationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_failed(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.post(
    "/reanalysis",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Trigger Reanalysis on Evaluations",
)
async def trigger_reanalysis(
    http_request: Request,
    request_body: ReanalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    res = service.reanalysis(
        evaluation_ids=request_body.evaluation_ids,
        reason=request_body.reason,
    )
    return StandardSuccessResponse(data=res, request_id=req_id)


@router.get(
    "/evaluations",
    response_model=StandardSuccessResponse[List[EffectivenessEvaluationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Effectiveness Evaluations",
)
async def list_evaluations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    lifecycle_state: Optional[EffectivenessLifecycleState] = Query(None),
    effectiveness_state: Optional[EffectivenessState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[List[EffectivenessEvaluationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_evaluations(
        organization_id=target_org,
        facility_id=facility_id,
        lifecycle_state=lifecycle_state,
        effectiveness_state=effectiveness_state,
        limit=limit,
        offset=offset,
    )
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Evaluation Details",
)
async def get_evaluation_details(
    http_request: Request,
    evaluation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    record = service.get_evaluation(evaluation_id)
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/evaluations/{evaluation_id}/status",
    response_model=StandardSuccessResponse[EvaluationStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Evaluation Status",
)
async def get_evaluation_status(
    http_request: Request,
    evaluation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EvaluationStatusResponse]:
    req_id = _req_id(http_request)
    rec = service.get_evaluation(evaluation_id)
    resp = EvaluationStatusResponse(
        evaluation_id=rec.evaluation_id,
        action_id=rec.action_id,
        lifecycle_state=rec.lifecycle_state,
        effectiveness_state=rec.effectiveness_state,
        is_sustained=rec.is_sustained,
        regression_detected=rec.regression_detected,
        requires_human_review=rec.requires_human_review,
        version=rec.version,
        updated_at=rec.updated_at,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.get(
    "/evaluations/{evaluation_id}/evidence",
    response_model=StandardSuccessResponse[EvaluationEvidenceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Evaluation Evidence",
)
async def get_evaluation_evidence(
    http_request: Request,
    evaluation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EvaluationEvidenceResponse]:
    req_id = _req_id(http_request)
    rec = service.get_evaluation(evaluation_id)
    resp = EvaluationEvidenceResponse(
        evaluation_id=rec.evaluation_id,
        evidence_count=len(rec.evidence_items),
        evidence_items=rec.evidence_items,
        confounding_changes=rec.confounding_changes,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.get(
    "/evaluations/{evaluation_id}/criteria",
    response_model=StandardSuccessResponse[EvaluationCriteriaResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Evaluation Criteria",
)
async def get_evaluation_criteria(
    http_request: Request,
    evaluation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EvaluationCriteriaResponse]:
    req_id = _req_id(http_request)
    rec = service.get_evaluation(evaluation_id)
    resp = EvaluationCriteriaResponse(
        evaluation_id=rec.evaluation_id,
        safety_objective=rec.safety_objective,
        criteria=rec.criteria,
        observation_window=rec.observation_window,
        baseline=rec.baseline,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.get(
    "/evaluations/{evaluation_id}/history",
    response_model=StandardSuccessResponse[EvaluationHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Evaluation History",
)
async def get_evaluation_history(
    http_request: Request,
    evaluation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EvaluationHistoryResponse]:
    req_id = _req_id(http_request)
    rec = service.get_evaluation(evaluation_id)
    resp = EvaluationHistoryResponse(
        evaluation_id=rec.evaluation_id,
        reviews=rec.reviews,
        routings=rec.routings,
        reopened_count=rec.reopened_count,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        closed_at=rec.closed_at,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.get(
    "/evaluations/{evaluation_id}/comparison",
    response_model=StandardSuccessResponse[EvaluationComparisonResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Expected vs Observed Comparison",
)
async def get_evaluation_comparison(
    http_request: Request,
    evaluation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EvaluationComparisonResponse]:
    req_id = _req_id(http_request)
    rec = service.get_evaluation(evaluation_id)
    resp = EvaluationComparisonResponse(
        evaluation_id=rec.evaluation_id,
        comparisons=rec.comparisons,
        confounding_changes=rec.confounding_changes,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.get(
    "/evaluations/{evaluation_id}/effectiveness",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get Effectiveness Assessment Result",
)
async def get_evaluation_effectiveness(
    http_request: Request,
    evaluation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    rec = service.get_evaluation(evaluation_id)
    data = {
        "evaluation_id": rec.evaluation_id,
        "action_id": rec.action_id,
        "effectiveness_state": rec.effectiveness_state.value,
        "lifecycle_state": rec.lifecycle_state.value,
        "is_sustained": rec.is_sustained,
        "regression_detected": rec.regression_detected,
        "causality_disclaimer": (
            "Observed metric improvement does not establish causal proof "
            "or eliminate residual clinical risk."
        ),
        "total_criteria": len(rec.criteria),
        "conforming_criteria": sum(1 for c in rec.comparisons if c.is_conforming),
    }
    return StandardSuccessResponse(data=data, request_id=req_id)


@router.post(
    "/evaluations/{evaluation_id}/collect",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Collect Post-Action Evidence",
)
async def collect_evidence(
    http_request: Request,
    evaluation_id: str,
    request_body: CollectEvidenceRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    rec = service.collect_evidence(
        evaluation_id=evaluation_id,
        evidence_items=request_body.evidence_items,
        confounding_changes=request_body.confounding_changes,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/evaluations/{evaluation_id}/finalize",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Finalize Effectiveness Evaluation",
)
async def finalize_evaluation(
    http_request: Request,
    evaluation_id: str,
    request_body: FinalizeEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    rec = service.finalize_evaluation(
        evaluation_id=evaluation_id,
        reassess_if_needed=request_body.reassess_if_needed,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/evaluations/{evaluation_id}/review",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Submit Human Oversight Review",
)
async def submit_review(
    http_request: Request,
    evaluation_id: str,
    request_body: SubmitReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    reviewer_id = str(getattr(current_user, "id", "unknown"))
    reviewer_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.submit_review(
        evaluation_id=evaluation_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        decision=request_body.decision,
        rationale=request_body.rationale,
        limitations=request_body.limitations,
        is_ai_agent=request_body.is_ai_agent,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/evaluations/{evaluation_id}/accept",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Accept Effectiveness Evaluation",
)
async def accept_evaluation(
    http_request: Request,
    evaluation_id: str,
    request_body: AcceptEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    reviewer_id = str(getattr(current_user, "id", "unknown"))
    reviewer_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.accept_evaluation(
        evaluation_id=evaluation_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        rationale=request_body.rationale,
        limitations=request_body.limitations,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/evaluations/{evaluation_id}/reject",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Reject Effectiveness Evaluation",
)
async def reject_evaluation(
    http_request: Request,
    evaluation_id: str,
    request_body: RejectEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    reviewer_id = str(getattr(current_user, "id", "unknown"))
    reviewer_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.reject_evaluation(
        evaluation_id=evaluation_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        rationale=request_body.rationale,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/evaluations/{evaluation_id}/reassess",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Request Reassessment",
)
async def reassess_evaluation(
    http_request: Request,
    evaluation_id: str,
    request_body: ReassessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))

    rec = service.reassess_evaluation(
        evaluation_id=evaluation_id,
        actor_id=actor_id,
        reason=request_body.reason,
        additional_context=request_body.additional_context,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/evaluations/{evaluation_id}/reopen",
    response_model=StandardSuccessResponse[EffectivenessEvaluationRecord],
    status_code=status.HTTP_200_OK,
    summary="Reopen Evaluation",
)
async def reopen_evaluation(
    http_request: Request,
    evaluation_id: str,
    request_body: ReopenEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: ActionEffectivenessService = Depends(get_action_effectiveness_service),
) -> StandardSuccessResponse[EffectivenessEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))

    rec = service.reopen_evaluation(
        evaluation_id=evaluation_id,
        actor_id=actor_id,
        reason=request_body.reason,
        new_evidence=request_body.new_evidence,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)

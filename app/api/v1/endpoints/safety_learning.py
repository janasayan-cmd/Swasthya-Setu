"""Phase 50: Clinical Safety Learning, Trend Analysis & Preventive Risk Improvement APIs.

Endpoints:
- POST /safety-learning/analyses: Request trend or recurrence analysis
- GET /safety-learning/analyses/{analysis_id}: Get analysis job details
- GET /safety-learning/analyses/{analysis_id}/results: Retrieve authoritative results and metrics
- GET /safety-learning/patterns: List detected recurring safety patterns
- GET /safety-learning/patterns/{pattern_id}: Get pattern candidate details
- GET /safety-learning/recommendations: List candidate preventive recommendations
- GET /safety-learning/recommendations/{recommendation_id}: Get recommendation details
- POST /safety-learning/recommendations/{recommendation_id}/review: Human review (ACCEPT, REJECT, DEFER)
- GET /safety-learning/corrective-actions/{action_id}/effectiveness: Evaluate remediation effectiveness
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_safety_effectiveness_service,
    get_safety_learning_service,
    get_safety_pattern_service,
    get_safety_recommendation_service,
)
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_analysis import (
    SafetyAnalysisCreateRequest,
    SafetyAnalysisJob,
    SafetyAnalysisResult,
)
from app.schemas.safety_effectiveness import CorrectiveActionEffectivenessRecord
from app.schemas.safety_pattern import SafetyPatternCandidate
from app.schemas.safety_recommendation import (
    RecommendationReviewRequest,
    SafetyRecommendation,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_effectiveness_service import (
    SafetyEffectivenessService,
    safety_effectiveness_service,
)
from app.services.safety_learning_service import (
    SafetyLearningService,
    safety_learning_service,
)
from app.services.safety_pattern_service import (
    SafetyPatternService,
    safety_pattern_service,
)
from app.services.safety_recommendation_service import (
    SafetyRecommendationService,
    safety_recommendation_service,
)

router = APIRouter(tags=["Clinical Safety Learning & Trend Analysis"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


# ---------------------------------------------------------------------------
# 1. Analysis Request & Execution
# ---------------------------------------------------------------------------


@router.post(
    "/safety-learning/analyses",
    response_model=StandardSuccessResponse[SafetyAnalysisJob],
    status_code=status.HTTP_201_CREATED,
    summary="Request Safety Learning Analysis",
    description="Initiates a bounded historical safety trend, recurrence, or pattern analysis.",
)
async def request_safety_analysis(
    http_request: Request,
    request_body: SafetyAnalysisCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    learning_svc: Annotated[SafetyLearningService, Depends(get_safety_learning_service)] = None,
) -> StandardSuccessResponse[SafetyAnalysisJob]:
    svc = learning_svc or safety_learning_service
    req_id = _req_id(http_request)

    user_role = getattr(current_user, "role", "SAFETY_OFFICER")
    org_id = getattr(current_user, "organization_id", None)

    job = await svc.request_analysis(
        request=request_body,
        requested_by_id=current_user.user_id,
        requested_by_role=str(user_role),
        organization_id=org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=job,
        request_id=req_id,
    )


@router.get(
    "/safety-learning/analyses/{analysis_id}",
    response_model=StandardSuccessResponse[SafetyAnalysisJob],
    summary="Get Safety Learning Analysis Job",
    description="Retrieves status and configuration of an analysis job.",
)
async def get_safety_analysis_job(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    learning_svc: Annotated[SafetyLearningService, Depends(get_safety_learning_service)] = None,
) -> StandardSuccessResponse[SafetyAnalysisJob]:
    svc = learning_svc or safety_learning_service
    req_id = _req_id(http_request)

    job = svc.get_job(analysis_id)

    return StandardSuccessResponse(
        success=True,
        data=job,
        request_id=req_id,
    )


@router.get(
    "/safety-learning/analyses/{analysis_id}/results",
    response_model=StandardSuccessResponse[SafetyAnalysisResult],
    summary="Get Safety Learning Analysis Results",
    description="Retrieves metrics, detected patterns, and candidate recommendations.",
)
async def get_safety_analysis_result(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    learning_svc: Annotated[SafetyLearningService, Depends(get_safety_learning_service)] = None,
) -> StandardSuccessResponse[SafetyAnalysisResult]:
    svc = learning_svc or safety_learning_service
    req_id = _req_id(http_request)

    result = svc.get_result(analysis_id)

    return StandardSuccessResponse(
        success=True,
        data=result,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 2. Candidate Patterns
# ---------------------------------------------------------------------------


@router.get(
    "/safety-learning/patterns",
    response_model=StandardSuccessResponse[List[SafetyPatternCandidate]],
    summary="List Safety Pattern Candidates",
    description="Lists candidate recurring patterns identified during historical analysis.",
)
async def list_safety_patterns(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    pattern_svc: Annotated[SafetyPatternService, Depends(get_safety_pattern_service)] = None,
) -> StandardSuccessResponse[List[SafetyPatternCandidate]]:
    svc = pattern_svc or safety_pattern_service
    req_id = _req_id(http_request)

    patterns = svc.list_patterns()

    return StandardSuccessResponse(
        success=True,
        data=patterns,
        request_id=req_id,
    )


@router.get(
    "/safety-learning/patterns/{pattern_id}",
    response_model=StandardSuccessResponse[SafetyPatternCandidate],
    summary="Get Safety Pattern Candidate",
    description="Retrieves a specific pattern candidate by ID.",
)
async def get_safety_pattern(
    http_request: Request,
    pattern_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    pattern_svc: Annotated[SafetyPatternService, Depends(get_safety_pattern_service)] = None,
) -> StandardSuccessResponse[SafetyPatternCandidate]:
    svc = pattern_svc or safety_pattern_service
    req_id = _req_id(http_request)

    pattern = svc.get_pattern(pattern_id)
    if not pattern:
        from app.core.exceptions import SafetyLearningNotFoundException
        raise SafetyLearningNotFoundException(f"Pattern candidate '{pattern_id}' not found.")

    return StandardSuccessResponse(
        success=True,
        data=pattern,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 3. Preventive Recommendations & Human Review
# ---------------------------------------------------------------------------


@router.get(
    "/safety-learning/recommendations",
    response_model=StandardSuccessResponse[List[SafetyRecommendation]],
    summary="List Preventive Recommendations",
    description="Lists candidate preventive risk improvements across subsystems.",
)
async def list_recommendations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    rec_svc: Annotated[SafetyRecommendationService, Depends(get_safety_recommendation_service)] = None,
) -> StandardSuccessResponse[List[SafetyRecommendation]]:
    svc = rec_svc or safety_recommendation_service
    req_id = _req_id(http_request)

    recommendations = svc.list_recommendations()

    return StandardSuccessResponse(
        success=True,
        data=recommendations,
        request_id=req_id,
    )


@router.get(
    "/safety-learning/recommendations/{recommendation_id}",
    response_model=StandardSuccessResponse[SafetyRecommendation],
    summary="Get Preventive Recommendation",
    description="Retrieves a candidate preventive recommendation by ID.",
)
async def get_recommendation(
    http_request: Request,
    recommendation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    rec_svc: Annotated[SafetyRecommendationService, Depends(get_safety_recommendation_service)] = None,
) -> StandardSuccessResponse[SafetyRecommendation]:
    svc = rec_svc or safety_recommendation_service
    req_id = _req_id(http_request)

    rec = svc.get_recommendation(recommendation_id)
    if not rec:
        from app.core.exceptions import SafetyLearningNotFoundException
        raise SafetyLearningNotFoundException(f"Recommendation '{recommendation_id}' not found.")

    return StandardSuccessResponse(
        success=True,
        data=rec,
        request_id=req_id,
    )


@router.post(
    "/safety-learning/recommendations/{recommendation_id}/review",
    response_model=StandardSuccessResponse[SafetyRecommendation],
    summary="Review Preventive Recommendation",
    description="Human safety officer reviews, accepts, or rejects recommendation. AI autonomous review prohibited.",
)
async def review_recommendation(
    http_request: Request,
    recommendation_id: str,
    request_body: RecommendationReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    rec_svc: Annotated[SafetyRecommendationService, Depends(get_safety_recommendation_service)] = None,
) -> StandardSuccessResponse[SafetyRecommendation]:
    svc = rec_svc or safety_recommendation_service
    req_id = _req_id(http_request)

    user_role = getattr(current_user, "role", "SAFETY_OFFICER")

    rec = await svc.review_recommendation(
        recommendation_id=recommendation_id,
        request=request_body,
        reviewer_id=current_user.user_id,
        reviewer_role=str(user_role),
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=rec,
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# 4. Corrective Action Effectiveness
# ---------------------------------------------------------------------------


@router.get(
    "/safety-learning/corrective-actions/{action_id}/effectiveness",
    response_model=StandardSuccessResponse[CorrectiveActionEffectivenessRecord],
    summary="Evaluate Corrective Action Effectiveness",
    description="Evaluates whether an implemented corrective action is correlated with reduced recurrence.",
)
async def evaluate_corrective_action_effectiveness(
    http_request: Request,
    action_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    observation_days: int = Query(default=30, ge=1, le=365, description="Observation window in days"),
    eff_svc: Annotated[SafetyEffectivenessService, Depends(get_safety_effectiveness_service)] = None,
) -> StandardSuccessResponse[CorrectiveActionEffectivenessRecord]:
    svc = eff_svc or safety_effectiveness_service
    req_id = _req_id(http_request)

    record = svc.evaluate_action_effectiveness(action_id, observation_days=observation_days)

    return StandardSuccessResponse(
        success=True,
        data=record,
        request_id=req_id,
    )

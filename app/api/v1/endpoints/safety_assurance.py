"""Phase 52: Clinical Safety Assurance, Validation & Continuous Control Effectiveness Management APIs.

Endpoints:
  POST /safety-assurance/evaluations                          — Initiate control assurance evaluation
  GET  /safety-assurance/evaluations                          — List evaluations
  GET  /safety-assurance/evaluations/{evaluation_id}          — Get evaluation details
  GET  /safety-assurance/evaluations/{evaluation_id}/status   — Lightweight async status
  GET  /safety-assurance/evaluations/{evaluation_id}/evidence — Evidence references
  GET  /safety-assurance/evaluations/{evaluation_id}/effectiveness — Effectiveness score
  POST /safety-assurance/evaluations/{evaluation_id}/execute  — Execute (worker trigger)
  POST /safety-assurance/evaluations/{evaluation_id}/review   — Submit human review
  POST /safety-assurance/evaluations/{evaluation_id}/accept   — Accept assurance
  POST /safety-assurance/evaluations/{evaluation_id}/reject   — Reject assurance
  POST /safety-assurance/evaluations/{evaluation_id}/reassess — Trigger reassessment
  GET  /safety-assurance/degradations                         — List degradation records
  GET  /safety-assurance/regressions                          — List regression records
  GET  /safety-assurance/bypasses                             — List bypass records
  GET  /safety-assurance/dashboard                            — Non-PHI aggregate summary
  GET  /safety-assurance/controls/{control_id}/assurance      — Control assurance summary

Client trust boundary (NEVER trusted from request body):
  - actor_id
  - reviewer_id
  - organization_id (beyond scope restriction)
  - effectiveness_state
  - risk_state
  - control_state
  - approval_state
  - reviewer_role
  - authorization_basis
  - clinical_impact
  - evidence_verification

All of the above are derived from authenticated session context.

API behavior follows Phase 23 conventions.
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_assurance import (
    AssuranceAcceptRequest,
    AssuranceDashboardSummary,
    AssuranceEvaluationRecord,
    AssuranceEvaluationRequest,
    AssuranceEvaluationStatusResponse,
    AssuranceLifecycleState,
    AssuranceReassessRequest,
    AssuranceRejectRequest,
    AssuranceReviewRequest,
    BypassRecord,
    ControlAssuranceSummary,
    ControlEffectivenessState,
    DegradationRecord,
    DegradationState,
    EvidenceReference,
    RegressionRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_assurance_evaluation_service import (
    SafetyAssuranceEvaluationService,
    safety_assurance_evaluation_service,
)
from app.services.safety_assurance_review_service import (
    SafetyAssuranceReviewService,
    safety_assurance_review_service,
)
from app.services.safety_degradation_service import (
    SafetyDegradationService,
    safety_degradation_service,
)
from app.services.safety_assurance_metrics_service import (
    SafetyAssuranceMetricsService,
    safety_assurance_metrics_service,
)

router = APIRouter(
    prefix="/safety-assurance",
    tags=["Clinical Safety Assurance & Continuous Control Effectiveness Management"],
)


def _req_id(request: Request) -> str:
    return (
        getattr(request.state, "request_id", None)
        or request_id_ctx_var.get()
        or "req-unknown"
    )


# ===========================================================================
# Evaluation Lifecycle
# ===========================================================================


@router.post(
    "/evaluations",
    response_model=StandardSuccessResponse[AssuranceEvaluationRecord],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate Control Assurance Evaluation",
    description=(
        "Initiates a new control assurance evaluation lifecycle. "
        "Actor identity, organization scope, and reviewer role are derived "
        "from authenticated session — never from request body. "
        "Supports idempotency via idempotency_key. "
        "NEVER answers 'Is HealthSetu safe?' as a boolean."
    ),
)
async def create_assurance_evaluation(
    http_request: Request,
    request_body: AssuranceEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationRecord]:
    req_id = _req_id(http_request)

    # Actor identity from authenticated session — never from client body
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_facility_id = getattr(current_user, "facility_id", None)

    evaluation = svc.create_evaluation(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
        actor_facility_id=actor_facility_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=evaluation,
        request_id=req_id,
    )


@router.get(
    "/evaluations",
    response_model=StandardSuccessResponse[List[AssuranceEvaluationRecord]],
    summary="List Assurance Evaluations",
    description="List assurance evaluations with optional filters. Organization scope enforced from session.",
)
async def list_assurance_evaluations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    lifecycle_state: Optional[AssuranceLifecycleState] = Query(None),
    effectiveness_state: Optional[ControlEffectivenessState] = Query(None),
    bypass_detected: Optional[bool] = Query(None),
    regression_detected: Optional[bool] = Query(None),
    review_required: Optional[bool] = Query(None),
    facility_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[List[AssuranceEvaluationRecord]]:
    req_id = _req_id(http_request)
    # Organization scope from authenticated session
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_facility_id = getattr(current_user, "facility_id", None) or facility_id

    evaluations = svc.list_evaluations(
        organization_id=actor_org_id,
        facility_id=actor_facility_id,
        lifecycle_state=lifecycle_state,
        effectiveness_state=effectiveness_state,
        bypass_detected=bypass_detected,
        regression_detected=regression_detected,
        review_required=review_required,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=evaluations,
        request_id=req_id,
    )


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=StandardSuccessResponse[AssuranceEvaluationRecord],
    summary="Get Assurance Evaluation",
    description="Get full evaluation record. Organization scope enforced from session.",
)
async def get_assurance_evaluation(
    evaluation_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    evaluation = svc.get_evaluation(evaluation_id, actor_organization_id=actor_org_id)

    return StandardSuccessResponse(
        success=True,
        data=evaluation,
        request_id=req_id,
    )


@router.get(
    "/evaluations/{evaluation_id}/status",
    response_model=StandardSuccessResponse[AssuranceEvaluationStatusResponse],
    summary="Get Assurance Evaluation Status",
    description="Lightweight status endpoint for async polling. Does not expose full evidence or PHI.",
)
async def get_assurance_evaluation_status(
    evaluation_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationStatusResponse]:
    req_id = _req_id(http_request)
    evaluation_status = svc.get_evaluation_status(evaluation_id)

    return StandardSuccessResponse(
        success=True,
        data=evaluation_status,
        request_id=req_id,
    )


@router.get(
    "/evaluations/{evaluation_id}/evidence",
    response_model=StandardSuccessResponse[List[EvidenceReference]],
    summary="Get Assurance Evidence References",
    description=(
        "Returns evidence references for the evaluation. "
        "References point to authoritative records — not raw clinical data. "
        "PHI is minimized: aggregate references, not clinical payloads."
    ),
)
async def get_assurance_evidence(
    evaluation_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[List[EvidenceReference]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    evaluation = svc.get_evaluation(evaluation_id, actor_organization_id=actor_org_id)

    return StandardSuccessResponse(
        success=True,
        data=evaluation.evidence_references,
        request_id=req_id,
    )


@router.get(
    "/evaluations/{evaluation_id}/effectiveness",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get Control Effectiveness Assessment",
    description=(
        "Returns the effectiveness score dimensions for an evaluation. "
        "Score is an operational assurance indicator ONLY — not a clinical "
        "safety guarantee, risk elimination measure, or patient safety probability."
    ),
)
async def get_control_effectiveness(
    evaluation_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    evaluation = svc.get_evaluation(evaluation_id, actor_organization_id=actor_org_id)

    return StandardSuccessResponse(
        success=True,
        data={
            "evaluation_id": evaluation.evaluation_id,
            "effectiveness_state": evaluation.effectiveness_state.value,
            "degradation_state": evaluation.degradation_state.value,
            "execution_state": evaluation.execution_state.value,
            "score": evaluation.effectiveness_score.model_dump() if evaluation.effectiveness_score else None,
            "summary": evaluation.effectiveness_summary,
            "limitations": evaluation.effectiveness_limitations,
            "uncertainty_preserved": evaluation.uncertainty_preserved,
            "bypass_detected": evaluation.bypass_detected,
            "regression_detected": evaluation.regression_detected,
            "disclaimer": (
                "This assessment is an operational assurance indicator. "
                "It does not represent probability of patient safety, "
                "clinical certainty, guarantee of effectiveness, or risk elimination. "
                "CONTROL EFFECTIVE != RISK ELIMINATED. "
                "CURRENT OBSERVATION != FUTURE SAFETY."
            ),
        },
        request_id=req_id,
    )


@router.post(
    "/evaluations/{evaluation_id}/execute",
    response_model=StandardSuccessResponse[AssuranceEvaluationRecord],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute Assurance Evaluation",
    description=(
        "Triggers execution of a scheduled assurance evaluation. "
        "In production, this is called by Phase 22 async worker. "
        "Authorization is re-validated at execution time."
    ),
)
async def execute_assurance_evaluation(
    evaluation_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[Dict[str, Any]] = None,
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_org_id = getattr(current_user, "organization_id", None)

    # Worker re-validates authorization at execution time
    body = request_body or {}
    evaluation = svc.execute_evaluation(
        evaluation_id=evaluation_id,
        actor_id=actor_id,
        actor_organization_id=actor_org_id,
        request_id=req_id,
        eligible_executions=body.get("eligible_executions"),
        observed_executions=body.get("observed_executions"),
        observed_failures=body.get("observed_failures"),
        observed_bypasses=body.get("observed_bypasses"),
        valid_results=body.get("valid_results"),
        total_results=body.get("total_results"),
        expected_behavior_met=body.get("expected_behavior_met"),
        version_consistent=body.get("version_consistent"),
        provider_success_rate=body.get("provider_success_rate"),
        policy_thresholds=body.get("policy_thresholds"),
        is_high_risk_control=body.get("is_high_risk_control", False),
    )

    return StandardSuccessResponse(
        success=True,
        data=evaluation,
        request_id=req_id,
    )


@router.post(
    "/evaluations/{evaluation_id}/review",
    response_model=StandardSuccessResponse[AssuranceEvaluationRecord],
    summary="Submit Human Assurance Review",
    description=(
        "Submit a human assurance review. "
        "Reviewer identity and role are derived from authenticated session — "
        "NOT from request body. AI cannot submit reviews or approve assurance. "
        "ASSURANCE REVIEW != CLINICAL DIAGNOSIS. "
        "RECOMMENDATION != APPROVAL."
    ),
)
async def submit_assurance_review(
    evaluation_id: str,
    http_request: Request,
    request_body: AssuranceReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    review_svc: SafetyAssuranceReviewService = Depends(lambda: safety_assurance_review_service),
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationRecord]:
    req_id = _req_id(http_request)

    # All reviewer context derived from authenticated session (NEVER client body)
    reviewer_id = str(getattr(current_user, "id", "unknown"))
    reviewer_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    evaluation = review_svc.submit_review(
        evaluation_id=evaluation_id,
        review_request=request_body,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        reviewer_authorization_basis=f"role:{reviewer_role}",
        organization_id=actor_org_id,
        request_id=req_id,
    )

    # Apply the review decision to transition lifecycle state
    evaluation = review_svc.apply_review_decision(evaluation)

    return StandardSuccessResponse(
        success=True,
        data=evaluation,
        request_id=req_id,
    )


@router.post(
    "/evaluations/{evaluation_id}/accept",
    response_model=StandardSuccessResponse[AssuranceEvaluationRecord],
    summary="Accept Assurance Evaluation",
    description=(
        "Formally accept an assurance evaluation. "
        "Actor identity derived from session. "
        "APPROVAL != IMPLEMENTATION != EFFECTIVENESS != RISK ACCEPTANCE."
    ),
)
async def accept_assurance_evaluation(
    evaluation_id: str,
    http_request: Request,
    request_body: AssuranceAcceptRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    evaluation = svc.accept_evaluation(
        evaluation_id=evaluation_id,
        accept_request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=evaluation,
        request_id=req_id,
    )


@router.post(
    "/evaluations/{evaluation_id}/reject",
    response_model=StandardSuccessResponse[AssuranceEvaluationRecord],
    summary="Reject Assurance Evaluation",
    description="Reject an assurance evaluation. Triggers reassessment requirement.",
)
async def reject_assurance_evaluation(
    evaluation_id: str,
    http_request: Request,
    request_body: AssuranceRejectRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    evaluation = svc.reject_evaluation(
        evaluation_id=evaluation_id,
        reject_request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=evaluation,
        request_id=req_id,
    )


@router.post(
    "/evaluations/{evaluation_id}/reassess",
    response_model=StandardSuccessResponse[AssuranceEvaluationRecord],
    summary="Trigger Assurance Reassessment",
    description=(
        "Trigger reassessment of an accepted or monitored control. "
        "Reassessment preserves historical assurance records. "
        "HISTORICAL EFFECTIVENESS != CURRENT EFFECTIVENESS."
    ),
)
async def request_assurance_reassessment(
    evaluation_id: str,
    http_request: Request,
    request_body: AssuranceReassessRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceEvaluationRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_org_id = getattr(current_user, "organization_id", None)

    evaluation = svc.request_reassessment(
        evaluation_id=evaluation_id,
        reassess_request=request_body,
        actor_id=actor_id,
        actor_organization_id=actor_org_id,
        request_id=req_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=evaluation,
        request_id=req_id,
    )


# ===========================================================================
# Degradation, Regression, and Bypass Detection
# ===========================================================================


@router.get(
    "/degradations",
    response_model=StandardSuccessResponse[List[DegradationRecord]],
    summary="List Control Degradation Records",
    description=(
        "List detected control degradation records. "
        "CONTROL DEGRADATION != INCIDENT. "
        "CONTROL FAILURE != PATIENT HARM."
    ),
)
async def list_degradations(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    control_id: Optional[str] = Query(None),
    state: Optional[DegradationState] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: SafetyDegradationService = Depends(lambda: safety_degradation_service),
) -> StandardSuccessResponse[List[DegradationRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_facility_id = getattr(current_user, "facility_id", None)

    records = svc.list_degradations(
        control_id=control_id,
        organization_id=actor_org_id,
        facility_id=actor_facility_id,
        state=state,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=records,
        request_id=req_id,
    )


@router.get(
    "/regressions",
    response_model=StandardSuccessResponse[List[RegressionRecord]],
    summary="List Control Regression Records",
    description=(
        "List detected control regressions. "
        "A regression indicates a previously effective control has degraded. "
        "HISTORICAL EFFECTIVENESS != CURRENT EFFECTIVENESS."
    ),
)
async def list_regressions(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    control_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: SafetyDegradationService = Depends(lambda: safety_degradation_service),
) -> StandardSuccessResponse[List[RegressionRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_facility_id = getattr(current_user, "facility_id", None)

    records = svc.list_regressions(
        control_id=control_id,
        organization_id=actor_org_id,
        facility_id=actor_facility_id,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=records,
        request_id=req_id,
    )


@router.get(
    "/bypasses",
    response_model=StandardSuccessResponse[List[BypassRecord]],
    summary="List Control Bypass Records",
    description=(
        "List detected control bypass events. "
        "A bypass is a SAFETY SIGNAL — not automatically a clinical incident. "
        "Route confirmed policy-mandated events to Phase 49 only."
    ),
)
async def list_bypasses(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    control_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: SafetyDegradationService = Depends(lambda: safety_degradation_service),
) -> StandardSuccessResponse[List[BypassRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_facility_id = getattr(current_user, "facility_id", None)

    records = svc.list_bypasses(
        control_id=control_id,
        organization_id=actor_org_id,
        facility_id=actor_facility_id,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=records,
        request_id=req_id,
    )


# ===========================================================================
# Dashboard & Control Summaries
# ===========================================================================


@router.get(
    "/dashboard",
    response_model=StandardSuccessResponse[AssuranceDashboardSummary],
    summary="Assurance Dashboard Summary",
    description=(
        "Non-PHI aggregate assurance summary. "
        "Does NOT certify permanent clinical safety or eliminate risk. "
        "Operational assurance indicators only."
    ),
)
async def get_assurance_dashboard(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    facility_id: Optional[str] = Query(None),
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[AssuranceDashboardSummary]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_facility_id = getattr(current_user, "facility_id", None) or facility_id

    summary = svc.get_dashboard_summary(
        organization_id=actor_org_id,
        facility_id=actor_facility_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=summary,
        request_id=req_id,
    )


@router.get(
    "/controls/{control_id}/assurance",
    response_model=StandardSuccessResponse[Optional[ControlAssuranceSummary]],
    summary="Get Control Assurance Summary",
    description=(
        "Returns the current assurance posture for a specific control version. "
        "EFFECTIVE_OBSERVED does not mean risk eliminated or permanent effectiveness."
    ),
)
async def get_control_assurance_summary(
    control_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    control_version: str = Query(..., description="Control version to evaluate."),
    svc: SafetyAssuranceEvaluationService = Depends(lambda: safety_assurance_evaluation_service),
) -> StandardSuccessResponse[Optional[ControlAssuranceSummary]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)

    summary = svc.get_control_assurance_summary(
        control_id=control_id,
        control_version=control_version,
        organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=summary,
        request_id=req_id,
    )


# ===========================================================================
# Metrics
# ===========================================================================


@router.get(
    "/metrics",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Assurance Operational Metrics",
    description=(
        "Returns Phase 52 operational assurance metrics. "
        "Contains no PHI. For clinical safety certifications, consult "
        "authorized safety governance process."
    ),
)
async def get_assurance_metrics(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    metrics_svc: SafetyAssuranceMetricsService = Depends(lambda: safety_assurance_metrics_service),
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    summary = metrics_svc.get_summary()

    return StandardSuccessResponse(
        success=True,
        data=summary,
        request_id=req_id,
    )

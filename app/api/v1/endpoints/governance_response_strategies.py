"""
Phase 88: Clinical Safety Governance Resilience Response Strategy Optimization, Recovery Option Evaluation & Continuity Decision Support REST API Endpoints.

Base Route: /api/v1/governance-resilience-response-strategies

Provides endpoints for:
- Response strategy registry, review lifecycle & SoD approval
- Candidate recovery option generation & objective feasibility evaluation
- Capability restoration priority evaluation & sequencing
- Recovery option comparison & trade-off analysis
- Non-autonomous recovery resource planning
- Recovery recommendation packaging, review challenge & management decision recording
- Controlled continuity handoff coordination (to Phase 80)
- Operational execution tracking, deviation reporting & restoration verification
- Executive resilience response reporting
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

from app.schemas.governance_response_common import (
    ContinuityHandoffStatus,
    ExecutionTrackingStatus,
    RecoveryFeasibilityOutcome,
    RecommendationLifecycleStatus,
    ResponseStrategyCategory,
    StrategyReviewStatus,
)
from app.schemas.governance_response_strategy import (
    ApproveResponseStrategyRequest,
    CreateResponseStrategyRequest,
    ResponseStrategyRecord,
    SubmitResponseStrategyRequest,
    UpdateResponseStrategyRequest,
)
from app.schemas.governance_recovery_option import (
    CandidateRecoveryOptionRecord,
    EvaluateOptionFeasibilityRequest,
    FeasibilityAssessmentRecord,
    GenerateRecoveryOptionsRequest,
)
from app.schemas.governance_recovery_priority import (
    CreateRecoverySequenceRequest,
    EvaluateRecoveryPrioritiesRequest,
    RecoveryPriorityEvaluationRecord,
    RecoverySequenceRecord,
)
from app.schemas.governance_recovery_comparison import (
    RecoveryComparisonRecord,
    RunRecoveryComparisonRequest,
)
from app.schemas.governance_recovery_resource_planning import (
    CreateRecoveryResourcePlanRequest,
    RecoveryResourcePlanRecord,
)
from app.schemas.governance_recovery_recommendation import (
    AcknowledgeContinuityHandoffRequest,
    ChallengeRecommendationRequest,
    ContinuityHandoffRecord,
    CreateContinuityHandoffRequest,
    CreateRecoveryRecommendationRequest,
    RecoveryRecommendationRecord,
    SubmitRecommendationDecisionRequest,
    SubmitRecommendationReviewRequest,
)
from app.schemas.governance_recovery_execution import (
    RecoveryExecutionTrackingRecord,
    ReportExecutionDeviationRequest,
    SubmitRestorationVerificationRequest,
    UpdateExecutionProgressRequest,
)
from app.schemas.governance_response_reporting import (
    RecoveryComparisonsReport,
    RecoveryExecutionTrackingReport,
    RecoveryOptionsSummaryReport,
    RecoveryPrioritiesReport,
    StrategyDeviationsReport,
    StrategyFeasibilityReport,
)

from app.services.governance_response_strategy_service import get_governance_response_strategy_service
from app.services.governance_recovery_option_service import get_governance_recovery_option_service
from app.services.governance_recovery_priority_service import get_governance_recovery_priority_service
from app.services.governance_recovery_comparison_service import get_governance_recovery_comparison_service
from app.services.governance_recovery_resource_planning_service import get_governance_recovery_resource_planning_service
from app.services.governance_recovery_recommendation_service import get_governance_recovery_recommendation_service
from app.services.governance_recovery_execution_service import get_governance_recovery_execution_service
from app.services.governance_response_reporting_service import get_governance_response_reporting_service


def _ensure_not_patient(current_user: AuthenticatedUserContext = Depends(get_current_user)) -> None:
    """Patients cannot access governance response strategy operations."""
    if current_user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patients are not permitted to access clinical safety governance resilience response strategy operations.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


router = APIRouter(
    prefix="/governance-resilience-response-strategies",
    tags=["Clinical Safety Governance Resilience Response Strategies & Decision Support"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# 1. Executive Reports (Static routes placed first)
# =============================================================================

@router.get("/reports/recovery-options-summary", response_model=RecoveryOptionsSummaryReport)
def get_recovery_options_summary_report(
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_reporting_service()
    return svc.generate_recovery_options_summary(current_user.tenant_id, scenario_ref)


@router.get("/reports/strategy-feasibility", response_model=StrategyFeasibilityReport)
def get_strategy_feasibility_report(
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_reporting_service()
    return svc.generate_strategy_feasibility_report(current_user.tenant_id, scenario_ref)


@router.get("/reports/recovery-priorities", response_model=RecoveryPrioritiesReport)
def get_recovery_priorities_report(
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_reporting_service()
    return svc.generate_recovery_priorities_report(current_user.tenant_id, scenario_ref)


@router.get("/reports/recovery-comparisons", response_model=RecoveryComparisonsReport)
def get_recovery_comparisons_report(
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_reporting_service()
    return svc.generate_recovery_comparisons_report(current_user.tenant_id, scenario_ref)


@router.get("/reports/recovery-execution-tracking", response_model=RecoveryExecutionTrackingReport)
def get_recovery_execution_tracking_report(
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_reporting_service()
    return svc.generate_recovery_execution_tracking_report(current_user.tenant_id, scenario_ref)


@router.get("/reports/strategy-deviations", response_model=StrategyDeviationsReport)
def get_strategy_deviations_report(
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_reporting_service()
    return svc.generate_strategy_deviations_report(current_user.tenant_id, scenario_ref)


# =============================================================================
# 2. Candidate Recovery Options & Feasibility
# =============================================================================

@router.post("/recovery-options/generate", response_model=List[CandidateRecoveryOptionRecord], status_code=status.HTTP_201_CREATED)
def generate_recovery_options(
    req: GenerateRecoveryOptionsRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_option_service()
    return svc.generate_recovery_options(current_user.tenant_id, current_user.user_id, req)


@router.get("/recovery-options", response_model=List[CandidateRecoveryOptionRecord])
def list_recovery_options(
    strategy_ref: Optional[str] = Query(None),
    scenario_ref: Optional[str] = Query(None),
    capability_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_option_service()
    return svc.list_recovery_options(current_user.tenant_id, strategy_ref, scenario_ref, capability_ref)


@router.get("/recovery-options/{option_id}", response_model=CandidateRecoveryOptionRecord)
def get_recovery_option(
    option_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_option_service()
    return svc.get_recovery_option(option_id, current_user.tenant_id)


@router.post("/recovery-options/{option_id}/feasibility", response_model=FeasibilityAssessmentRecord, status_code=status.HTTP_201_CREATED)
def evaluate_option_feasibility(
    option_id: str,
    req: EvaluateOptionFeasibilityRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_option_service()
    return svc.evaluate_option_feasibility(current_user.tenant_id, current_user.user_id, option_id, req)


@router.get("/feasibility-assessments", response_model=List[FeasibilityAssessmentRecord])
def list_feasibility_assessments(
    option_ref: Optional[str] = Query(None),
    outcome: Optional[RecoveryFeasibilityOutcome] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_option_service()
    return svc.list_feasibility_assessments(current_user.tenant_id, option_ref, outcome)


@router.get("/feasibility-assessments/{assessment_id}", response_model=FeasibilityAssessmentRecord)
def get_feasibility_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_option_service()
    return svc.get_feasibility_assessment(assessment_id, current_user.tenant_id)


# =============================================================================
# 3. Recovery Priorities & Sequencing
# =============================================================================

@router.post("/recovery-priorities/evaluate", response_model=RecoveryPriorityEvaluationRecord, status_code=status.HTTP_201_CREATED)
def evaluate_recovery_priorities(
    req: EvaluateRecoveryPrioritiesRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_priority_service()
    return svc.evaluate_recovery_priorities(current_user.tenant_id, current_user.user_id, req)


@router.get("/recovery-priorities", response_model=List[RecoveryPriorityEvaluationRecord])
def list_recovery_priorities(
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_priority_service()
    return svc.list_recovery_priority_evaluations(current_user.tenant_id, scenario_ref)


@router.get("/recovery-priorities/{evaluation_id}", response_model=RecoveryPriorityEvaluationRecord)
def get_recovery_priority_evaluation(
    evaluation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_priority_service()
    return svc.get_recovery_priority_evaluation(evaluation_id, current_user.tenant_id)


@router.post("/recovery-sequences", response_model=RecoverySequenceRecord, status_code=status.HTTP_201_CREATED)
def create_recovery_sequence(
    req: CreateRecoverySequenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_priority_service()
    return svc.create_recovery_sequence(current_user.tenant_id, current_user.user_id, req)


@router.get("/recovery-sequences", response_model=List[RecoverySequenceRecord])
def list_recovery_sequences(
    priority_evaluation_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_priority_service()
    return svc.list_recovery_sequences(current_user.tenant_id, priority_evaluation_ref)


@router.get("/recovery-sequences/{sequence_id}", response_model=RecoverySequenceRecord)
def get_recovery_sequence(
    sequence_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_priority_service()
    return svc.get_recovery_sequence(sequence_id, current_user.tenant_id)


# =============================================================================
# 4. Recovery Comparisons
# =============================================================================

@router.post("/recovery-comparisons", response_model=RecoveryComparisonRecord, status_code=status.HTTP_201_CREATED)
def run_recovery_comparison(
    req: RunRecoveryComparisonRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_comparison_service()
    return svc.run_recovery_comparison(current_user.tenant_id, current_user.user_id, req)


@router.get("/recovery-comparisons", response_model=List[RecoveryComparisonRecord])
def list_recovery_comparisons(
    scenario_ref: Optional[str] = Query(None),
    strategy_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_comparison_service()
    return svc.list_recovery_comparisons(current_user.tenant_id, scenario_ref, strategy_ref)


@router.get("/recovery-comparisons/{comparison_id}", response_model=RecoveryComparisonRecord)
def get_recovery_comparison(
    comparison_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_comparison_service()
    return svc.get_recovery_comparison(comparison_id, current_user.tenant_id)


# =============================================================================
# 5. Recovery Resource Plans
# =============================================================================

@router.post("/recovery-resource-plans", response_model=RecoveryResourcePlanRecord, status_code=status.HTTP_201_CREATED)
def create_recovery_resource_plan(
    req: CreateRecoveryResourcePlanRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_resource_planning_service()
    return svc.create_recovery_resource_plan(current_user.tenant_id, current_user.user_id, req)


@router.get("/recovery-resource-plans", response_model=List[RecoveryResourcePlanRecord])
def list_recovery_resource_plans(
    option_ref: Optional[str] = Query(None),
    scenario_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_resource_planning_service()
    return svc.list_recovery_resource_plans(current_user.tenant_id, option_ref, scenario_ref)


@router.get("/recovery-resource-plans/{plan_id}", response_model=RecoveryResourcePlanRecord)
def get_recovery_resource_plan(
    plan_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_resource_planning_service()
    return svc.get_recovery_resource_plan(plan_id, current_user.tenant_id)


# =============================================================================
# 6. Recovery Recommendations & Decision-Support
# =============================================================================

@router.post("/recovery-recommendations", response_model=RecoveryRecommendationRecord, status_code=status.HTTP_201_CREATED)
def create_recovery_recommendation(
    req: CreateRecoveryRecommendationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.create_recommendation(current_user.tenant_id, current_user.user_id, req)


@router.get("/recovery-recommendations", response_model=List[RecoveryRecommendationRecord])
def list_recovery_recommendations(
    scenario_ref: Optional[str] = Query(None),
    status: Optional[RecommendationLifecycleStatus] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.list_recommendations(current_user.tenant_id, scenario_ref, status)


@router.get("/recovery-recommendations/{recommendation_id}", response_model=RecoveryRecommendationRecord)
def get_recovery_recommendation(
    recommendation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.get_recommendation(recommendation_id, current_user.tenant_id)


@router.post("/recovery-recommendations/{recommendation_id}/submit-review", response_model=RecoveryRecommendationRecord)
def submit_recommendation_review(
    recommendation_id: str,
    req: SubmitRecommendationReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.submit_for_review(recommendation_id, current_user.tenant_id, current_user.user_id, req)


@router.post("/recovery-recommendations/{recommendation_id}/challenge", response_model=RecoveryRecommendationRecord)
def challenge_recovery_recommendation(
    recommendation_id: str,
    req: ChallengeRecommendationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.challenge_recommendation(recommendation_id, current_user.tenant_id, current_user.user_id, req)


@router.post("/recovery-recommendations/{recommendation_id}/decision", response_model=RecoveryRecommendationRecord)
def submit_recommendation_decision(
    recommendation_id: str,
    req: SubmitRecommendationDecisionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.submit_decision(recommendation_id, current_user.tenant_id, current_user.user_id, req)


# =============================================================================
# 7. Continuity Handoffs
# =============================================================================

@router.post("/recovery-recommendations/{recommendation_id}/continuity-handoff", response_model=ContinuityHandoffRecord, status_code=status.HTTP_201_CREATED)
def create_continuity_handoff(
    recommendation_id: str,
    req: CreateContinuityHandoffRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.create_continuity_handoff(recommendation_id, current_user.tenant_id, current_user.user_id, req)


@router.get("/continuity-handoffs", response_model=List[ContinuityHandoffRecord])
def list_continuity_handoffs(
    recommendation_ref: Optional[str] = Query(None),
    status: Optional[ContinuityHandoffStatus] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.list_continuity_handoffs(current_user.tenant_id, recommendation_ref, status)


@router.get("/continuity-handoffs/{handoff_id}", response_model=ContinuityHandoffRecord)
def get_continuity_handoff(
    handoff_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.get_continuity_handoff(handoff_id, current_user.tenant_id)


@router.post("/continuity-handoffs/{handoff_id}/acknowledge", response_model=ContinuityHandoffRecord)
def acknowledge_continuity_handoff(
    handoff_id: str,
    req: AcknowledgeContinuityHandoffRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_recommendation_service()
    return svc.acknowledge_continuity_handoff(handoff_id, current_user.tenant_id, current_user.user_id, req)


# =============================================================================
# 8. Recovery Execution Tracking & Verification
# =============================================================================

@router.post("/recovery-execution-trackings", response_model=RecoveryExecutionTrackingRecord, status_code=status.HTTP_201_CREATED)
def create_execution_tracking(
    handoff_id: str = Query(...),
    strategy_id: str = Query(...),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_execution_service()
    return svc.create_execution_tracking(
        current_user.tenant_id,
        current_user.user_id,
        handoff_id,
        strategy_id,
    )


@router.get("/recovery-execution-trackings", response_model=List[RecoveryExecutionTrackingRecord])
def list_execution_trackings(
    recommendation_ref: Optional[str] = Query(None),
    status: Optional[ExecutionTrackingStatus] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_execution_service()
    return svc.list_execution_tracking(current_user.tenant_id, recommendation_ref, status)


@router.get("/recovery-execution-trackings/{tracking_id}", response_model=RecoveryExecutionTrackingRecord)
def get_execution_tracking(
    tracking_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_execution_service()
    return svc.get_execution_tracking(tracking_id, current_user.tenant_id)


@router.post("/recovery-execution-trackings/{tracking_id}/progress", response_model=RecoveryExecutionTrackingRecord)
def update_execution_progress(
    tracking_id: str,
    req: UpdateExecutionProgressRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_execution_service()
    return svc.update_execution_progress(tracking_id, current_user.tenant_id, current_user.user_id, req)


@router.post("/recovery-execution-trackings/{tracking_id}/deviation", response_model=RecoveryExecutionTrackingRecord)
def report_execution_deviation(
    tracking_id: str,
    req: ReportExecutionDeviationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_execution_service()
    return svc.report_execution_deviation(tracking_id, current_user.tenant_id, current_user.user_id, req)


@router.post("/recovery-execution-trackings/{tracking_id}/verify-restoration", response_model=RecoveryExecutionTrackingRecord)
def submit_restoration_verification(
    tracking_id: str,
    req: SubmitRestorationVerificationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_recovery_execution_service()
    return svc.submit_restoration_verification(tracking_id, current_user.tenant_id, current_user.user_id, req)


# =============================================================================
# 9. Response Strategies (Generic / Parameterized routes placed last)
# =============================================================================

@router.post("", response_model=ResponseStrategyRecord, status_code=status.HTTP_201_CREATED)
def create_response_strategy(
    req: CreateResponseStrategyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_strategy_service()
    return svc.create_response_strategy(current_user.tenant_id, current_user.user_id, req)


@router.get("", response_model=List[ResponseStrategyRecord])
def list_response_strategies(
    category: Optional[ResponseStrategyCategory] = Query(None),
    status: Optional[StrategyReviewStatus] = Query(None),
    scenario_ref: Optional[str] = Query(None),
    capability_ref: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_strategy_service()
    return svc.list_response_strategies(current_user.tenant_id, category, status, scenario_ref, capability_ref)


@router.get("/{strategy_id}", response_model=ResponseStrategyRecord)
def get_response_strategy(
    strategy_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_strategy_service()
    return svc.get_response_strategy(strategy_id, current_user.tenant_id)


@router.put("/{strategy_id}", response_model=ResponseStrategyRecord)
def update_response_strategy(
    strategy_id: str,
    req: UpdateResponseStrategyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_strategy_service()
    return svc.update_response_strategy(strategy_id, current_user.tenant_id, current_user.user_id, req)


@router.post("/{strategy_id}/submit", response_model=ResponseStrategyRecord)
def submit_response_strategy(
    strategy_id: str,
    req: SubmitResponseStrategyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_strategy_service()
    return svc.submit_response_strategy(strategy_id, current_user.tenant_id, current_user.user_id, req)


@router.post("/{strategy_id}/approve", response_model=ResponseStrategyRecord)
def approve_response_strategy(
    strategy_id: str,
    req: ApproveResponseStrategyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_strategy_service()
    return svc.approve_response_strategy(strategy_id, current_user.tenant_id, current_user.user_id, req)


@router.post("/{strategy_id}/archive", response_model=ResponseStrategyRecord)
def archive_response_strategy(
    strategy_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_response_strategy_service()
    return svc.archive_response_strategy(strategy_id, current_user.tenant_id, current_user.user_id)

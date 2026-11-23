"""Phase 87: Clinical Safety Governance Resilience Disruption Impact REST API Endpoints.

Base Route: /api/v1/governance-resilience-impact-analysis

Provides endpoints for:
- Disruption scenario registry & approval
- Direct & indirect disruption impact assessment
- Cascading failure & cross-dependency propagation analysis
- Multi-resource & compound disruption evaluation
- Fallback effectiveness comparison
- Remediation & escalation follow-up coordination
- Executive resilience reporting
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

from app.schemas.governance_disruption_common import (
    AssessmentReviewStatus,
    DisruptionScenarioCategory,
    FollowUpDestinationWorkflow,
    FollowUpStatus,
    ImpactSeverity,
    ScenarioReviewStatus,
)
from app.schemas.governance_disruption_scenario import (
    ApproveDisruptionScenarioRequest,
    CreateDisruptionScenarioRequest,
    DisruptionScenarioRecord,
    SubmitDisruptionScenarioRequest,
    UpdateDisruptionScenarioRequest,
)
from app.schemas.governance_disruption_impact import (
    AssessmentChallengeRequest,
    AssessmentEvidenceRequest,
    AssessmentReviewRequest,
    CreateImpactAssessmentRequest,
    DisruptionImpactAssessmentRecord,
    RunImpactAssessmentRequest,
)
from app.schemas.governance_cascading_failure import (
    CascadingAnalysisRecord,
    RunCascadingAnalysisRequest,
)
from app.schemas.governance_compound_disruption import (
    CompoundDisruptionScenarioRecord,
    CreateCompoundScenarioRequest,
    EvaluateCompoundScenarioRequest,
)
from app.schemas.governance_fallback_comparison import (
    FallbackComparisonRecord,
    RunFallbackComparisonRequest,
)
from app.schemas.governance_impact_remediation import (
    AcknowledgeImpactFollowUpRequest,
    CreateImpactFollowUpRequest,
    ImpactFollowUpRecord,
    SubmitImpactFollowUpRequest,
)
from app.schemas.governance_disruption_reporting import (
    CascadingDependenciesReport,
    CompoundDisruptionsReport,
    DisruptionImpactSummaryReport,
    FallbackComparisonReport,
    ImpactAssessmentCoverageReport,
)

from app.services.governance_disruption_scenario_service import get_governance_disruption_scenario_service
from app.services.governance_disruption_impact_service import get_governance_disruption_impact_service
from app.services.governance_cascading_failure_service import get_governance_cascading_failure_service
from app.services.governance_compound_disruption_service import get_governance_compound_disruption_service
from app.services.governance_fallback_comparison_service import get_governance_fallback_comparison_service
from app.services.governance_impact_remediation_service import get_governance_impact_remediation_service
from app.services.governance_disruption_reporting_service import get_governance_disruption_reporting_service


def _ensure_not_patient(current_user: AuthenticatedUserContext = Depends(get_current_user)) -> None:
    """Patients cannot access governance disruption impact operations."""
    if current_user.role == UserRole.PATIENT:
        raise AppException(
            code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            message="Patients are not permitted to access clinical safety governance resilience disruption impact operations.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


router = APIRouter(
    prefix="/governance-resilience-impact-analysis",
    tags=["Clinical Safety Governance Resilience Disruption Impact Analysis"],
    dependencies=[Depends(_ensure_not_patient)],
)


# =============================================================================
# 1. Reports (Static routes placed first)
# =============================================================================

@router.get("/reports/impact-summary", response_model=DisruptionImpactSummaryReport)
def get_impact_summary_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_reporting_service()
    return svc.impact_summary_report(current_user.tenant_id)


@router.get("/reports/cascading-dependencies", response_model=CascadingDependenciesReport)
def get_cascading_dependencies_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_reporting_service()
    return svc.cascading_dependencies_report(current_user.tenant_id)


@router.get("/reports/compound-disruptions", response_model=CompoundDisruptionsReport)
def get_compound_disruptions_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_reporting_service()
    return svc.compound_disruptions_report(current_user.tenant_id)


@router.get("/reports/fallback-comparison", response_model=FallbackComparisonReport)
def get_fallback_comparison_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_reporting_service()
    return svc.fallback_comparison_report(current_user.tenant_id)


@router.get("/reports/impact-assessment-coverage", response_model=ImpactAssessmentCoverageReport)
def get_assessment_coverage_report(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_reporting_service()
    return svc.impact_assessment_coverage_report(current_user.tenant_id)


# =============================================================================
# 2. Disruption Scenario Registry
# =============================================================================

@router.post("/scenarios", response_model=DisruptionScenarioRecord, status_code=status.HTTP_201_CREATED)
def create_scenario(
    request: CreateDisruptionScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_scenario_service()
    return svc.create_scenario(current_user.tenant_id, current_user.user_id, request)


@router.get("/scenarios", response_model=List[DisruptionScenarioRecord])
def list_scenarios(
    category: Optional[DisruptionScenarioCategory] = Query(None),
    review_status: Optional[ScenarioReviewStatus] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_scenario_service()
    return svc.list_scenarios(current_user.tenant_id, category, review_status)


@router.get("/scenarios/{scenario_id}", response_model=DisruptionScenarioRecord)
def get_scenario(
    scenario_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_scenario_service()
    return svc.get_scenario(current_user.tenant_id, scenario_id)


@router.patch("/scenarios/{scenario_id}", response_model=DisruptionScenarioRecord)
def update_scenario(
    scenario_id: str,
    request: UpdateDisruptionScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_scenario_service()
    return svc.update_scenario(current_user.tenant_id, scenario_id, current_user.user_id, request)


@router.post("/scenarios/{scenario_id}/submit", response_model=DisruptionScenarioRecord)
def submit_scenario(
    scenario_id: str,
    request: SubmitDisruptionScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_scenario_service()
    return svc.submit_scenario(current_user.tenant_id, scenario_id, current_user.user_id, request)


@router.post("/scenarios/{scenario_id}/approve", response_model=DisruptionScenarioRecord)
def approve_scenario(
    scenario_id: str,
    request: ApproveDisruptionScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_scenario_service()
    return svc.approve_scenario(current_user.tenant_id, scenario_id, current_user.user_id, request)


# =============================================================================
# 3. Cascading Failure Analysis (Static before parameterized)
# =============================================================================

@router.post("/cascading-analysis/run", response_model=CascadingAnalysisRecord, status_code=status.HTTP_201_CREATED)
def run_cascading_analysis(
    request: RunCascadingAnalysisRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_cascading_failure_service()
    return svc.run_cascading_analysis(current_user.tenant_id, current_user.user_id, request)


@router.get("/cascading-analysis", response_model=List[CascadingAnalysisRecord])
def list_cascading_analyses(
    assessment_id: Optional[str] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_cascading_failure_service()
    return svc.list_cascading_analyses(current_user.tenant_id, assessment_id)


@router.get("/cascading-analysis/{analysis_id}", response_model=CascadingAnalysisRecord)
def get_cascading_analysis(
    analysis_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_cascading_failure_service()
    return svc.get_cascading_analysis(current_user.tenant_id, analysis_id)


# =============================================================================
# 4. Multi-Resource & Compound Disruption Scenarios (Static before parameterized)
# =============================================================================

@router.post("/compound-scenarios", response_model=CompoundDisruptionScenarioRecord, status_code=status.HTTP_201_CREATED)
def create_compound_scenario(
    request: CreateCompoundScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_compound_disruption_service()
    return svc.create_compound_scenario(current_user.tenant_id, current_user.user_id, request)


@router.get("/compound-scenarios", response_model=List[CompoundDisruptionScenarioRecord])
def list_compound_scenarios(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_compound_disruption_service()
    return svc.list_compound_scenarios(current_user.tenant_id)


@router.get("/compound-scenarios/{compound_scenario_id}", response_model=CompoundDisruptionScenarioRecord)
def get_compound_scenario(
    compound_scenario_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_compound_disruption_service()
    return svc.get_compound_scenario(current_user.tenant_id, compound_scenario_id)


@router.post("/compound-scenarios/{compound_scenario_id}/evaluate", response_model=CompoundDisruptionScenarioRecord)
def evaluate_compound_scenario(
    compound_scenario_id: str,
    request: EvaluateCompoundScenarioRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_compound_disruption_service()
    return svc.evaluate_compound_scenario(current_user.tenant_id, compound_scenario_id, current_user.user_id, request)


# =============================================================================
# 5. Remediation Follow-ups (Static before parameterized)
# =============================================================================

@router.get("/follow-ups", response_model=List[ImpactFollowUpRecord])
def list_follow_ups(
    assessment_id: Optional[str] = Query(None),
    destination_workflow: Optional[FollowUpDestinationWorkflow] = Query(None),
    follow_up_status: Optional[FollowUpStatus] = Query(None, alias="status"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_impact_remediation_service()
    return svc.list_follow_ups(current_user.tenant_id, assessment_id, destination_workflow, follow_up_status)


@router.get("/follow-ups/{follow_up_id}", response_model=ImpactFollowUpRecord)
def get_follow_up(
    follow_up_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_impact_remediation_service()
    return svc.get_follow_up(current_user.tenant_id, follow_up_id)


@router.post("/follow-ups/{follow_up_id}/submit", response_model=ImpactFollowUpRecord)
def submit_follow_up(
    follow_up_id: str,
    request: SubmitImpactFollowUpRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_impact_remediation_service()
    return svc.submit_follow_up(current_user.tenant_id, follow_up_id, current_user.user_id, request)


@router.post("/follow-ups/{follow_up_id}/acknowledge", response_model=ImpactFollowUpRecord)
def acknowledge_follow_up(
    follow_up_id: str,
    request: AcknowledgeImpactFollowUpRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_impact_remediation_service()
    return svc.acknowledge_follow_up(current_user.tenant_id, follow_up_id, current_user.user_id, request)


# =============================================================================
# 6. Disruption Impact Assessments
# =============================================================================

@router.post("/assessments", response_model=DisruptionImpactAssessmentRecord, status_code=status.HTTP_201_CREATED)
def create_assessment(
    request: CreateImpactAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.create_assessment(current_user.tenant_id, current_user.user_id, request)


@router.get("/assessments", response_model=List[DisruptionImpactAssessmentRecord])
def list_assessments(
    scenario_id: Optional[str] = Query(None),
    review_status: Optional[AssessmentReviewStatus] = Query(None),
    severity: Optional[ImpactSeverity] = Query(None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.list_assessments(current_user.tenant_id, scenario_id, review_status, severity)


@router.get("/assessments/{assessment_id}", response_model=DisruptionImpactAssessmentRecord)
def get_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.get_assessment(current_user.tenant_id, assessment_id)


@router.post("/assessments/{assessment_id}/run", response_model=DisruptionImpactAssessmentRecord)
def run_assessment(
    assessment_id: str,
    request: RunImpactAssessmentRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.run_assessment(current_user.tenant_id, assessment_id, current_user.user_id, request)


@router.post("/assessments/{assessment_id}/submit-review", response_model=DisruptionImpactAssessmentRecord)
def submit_assessment_for_review(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.submit_for_review(current_user.tenant_id, assessment_id, current_user.user_id)


@router.post("/assessments/{assessment_id}/review", response_model=DisruptionImpactAssessmentRecord)
def review_assessment(
    assessment_id: str,
    request: AssessmentReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.review_assessment(current_user.tenant_id, assessment_id, current_user.user_id, request)


@router.post("/assessments/{assessment_id}/challenge", response_model=DisruptionImpactAssessmentRecord)
def challenge_assessment(
    assessment_id: str,
    request: AssessmentChallengeRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.challenge_assessment(current_user.tenant_id, assessment_id, current_user.user_id, request)


@router.post("/assessments/{assessment_id}/request-evidence", response_model=DisruptionImpactAssessmentRecord)
def request_evidence(
    assessment_id: str,
    request: AssessmentEvidenceRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_disruption_impact_service()
    return svc.request_evidence(current_user.tenant_id, assessment_id, current_user.user_id, request)


# Assessment sub-resources: Fallback comparison
@router.post("/assessments/{assessment_id}/fallback-comparison", response_model=FallbackComparisonRecord, status_code=status.HTTP_201_CREATED)
def compare_fallbacks(
    assessment_id: str,
    request: RunFallbackComparisonRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_fallback_comparison_service()
    return svc.compare_fallbacks(current_user.tenant_id, assessment_id, current_user.user_id, request)


@router.get("/assessments/{assessment_id}/fallback-comparisons", response_model=List[FallbackComparisonRecord])
def list_fallback_comparisons_for_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_fallback_comparison_service()
    return svc.list_fallback_comparisons(current_user.tenant_id, assessment_id)


# Assessment sub-resources: Remediation follow-ups
@router.post("/assessments/{assessment_id}/follow-ups", response_model=ImpactFollowUpRecord, status_code=status.HTTP_201_CREATED)
def create_follow_up(
    assessment_id: str,
    request: CreateImpactFollowUpRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_impact_remediation_service()
    return svc.create_follow_up(current_user.tenant_id, assessment_id, current_user.user_id, request)


@router.get("/assessments/{assessment_id}/follow-ups", response_model=List[ImpactFollowUpRecord])
def list_follow_ups_for_assessment(
    assessment_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
):
    svc = get_governance_impact_remediation_service()
    return svc.list_follow_ups(current_user.tenant_id, assessment_id)

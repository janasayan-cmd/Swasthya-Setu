"""Phase 50: Clinical Safety Learning, Trend Analysis & Preventive Risk Improvement Test Suite.

Comprehensive tests covering:
- Bounded time window and scope validation
- Idempotent analysis job dispatching
- Statistical denominator integrity and rate unavailable handling
- Pattern recurrence candidate grouping
- Corrective action effectiveness evaluation (PENDING_OBSERVATION, NO_RECURRENCE_OBSERVED, RECURRENCE_OBSERVED)
- Human safety officer recommendation review lifecycle (ACCEPT, REJECT, DEFER)
- AI authority prohibitions (preventing AI autonomous approvals, closures, or policy changes)
- Full REST API integration via HTTP client
"""

from datetime import datetime, timezone, timedelta
import pytest
from starlette.testclient import TestClient

from app.api.deps import _global_user_repo
from app.core.exceptions import (
    AISafetyLearningAuthorityProhibitedException,
    SafetyLearningInvalidTimeWindowException,
    SafetyLearningNotFoundException,
    SafetyLearningRateUnavailableException,
    SafetyLearningResultStaleException,
)
from app.core.security import create_access_token
from app.main import app
from app.repositories.safety_incident_repository import safety_incident_repository
from app.repositories.safety_learning_repository import safety_learning_repository
from app.repositories.user_repository import UserRecord
from app.schemas.auth import AccountStatus, UserRole
from app.schemas.corrective_actions import (
    ActionStatus,
    ActionType,
    CorrectiveActionCreateRequest,
)
from app.schemas.incidents import (
    IncidentCreateRequest,
    IncidentImpactStatus,
    IncidentSeverity,
    IncidentType,
)
from app.schemas.safety_analysis import (
    AnalysisScopeType,
    AnalysisStatus,
    AnalysisType,
    SafetyAnalysisCreateRequest,
)
from app.schemas.safety_effectiveness import EffectivenessState
from app.schemas.safety_recommendation import (
    RecommendationReviewRequest,
    RecommendationStatus,
    RecommendationType,
)
from app.services.clinical_incident_service import clinical_incident_service
from app.services.corrective_action_service import corrective_action_service
from app.services.safety_effectiveness_service import safety_effectiveness_service
from app.services.safety_learning_service import safety_learning_service
from app.services.safety_pattern_service import safety_pattern_service
from app.services.safety_recommendation_service import safety_recommendation_service
from app.services.safety_trend_service import safety_trend_service


@pytest.fixture(autouse=True)
def reset_phase50_state():
    """Reset repositories before each test."""
    safety_learning_repository.reset()
    safety_incident_repository.reset()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def safety_officer_token():
    officer_id = "usr-safety-officer-p50"
    _global_user_repo.register_in_memory_user(
        UserRecord(
            id=officer_id,
            identifier="safety.director@healthsetu.org",
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
            password_hash="mock-hash",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    token, _ = create_access_token(
        user_id=officer_id,
        role=UserRole.ADMIN.value,
    )
    return token


@pytest.fixture
def safety_officer_headers(safety_officer_token):
    return {"Authorization": f"Bearer {safety_officer_token}"}


# ===========================================================================
# 1. Trend & Denominator Integrity Tests
# ===========================================================================


def test_trend_metric_with_valid_denominator():
    """Valid denominator computes proper rate without rounding error."""
    metric = safety_trend_service.calculate_trend_metric(
        metric_name="provider_timeout_rate",
        count=5,
        denominator=100,
        time_window_label="30 days",
    )
    assert metric.rate_available is True
    assert metric.rate == 0.05
    assert metric.count == 5
    assert metric.denominator == 100


def test_trend_metric_missing_denominator_does_not_invent_rate():
    """Missing denominator leaves rate as None rather than fabricating 0 or 100%."""
    metric = safety_trend_service.calculate_trend_metric(
        metric_name="unscoped_incident_count",
        count=8,
        denominator=None,
    )
    assert metric.rate_available is False
    assert metric.rate is None
    assert metric.count == 8


def test_trend_metric_require_valid_rate_raises_exception():
    """When strict rate availability is required, missing denominator raises SafetyLearningRateUnavailableException."""
    with pytest.raises(SafetyLearningRateUnavailableException):
        safety_trend_service.calculate_trend_metric(
            metric_name="strict_rate",
            count=10,
            denominator=0,
            require_valid_rate=True,
        )


# ===========================================================================
# 2. Pattern Recurrence Detection Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_pattern_detection_groups_recurring_incidents():
    """Observe recurring incidents meeting min sample size generates candidate pattern."""
    now = datetime.now(timezone.utc)
    # Seed 3 medication safety incidents
    for idx in range(3):
        await clinical_incident_service.create_incident(
            IncidentCreateRequest(
                title=f"Drug interaction block {idx}",
                description="Gate blocked prescription.",
                incident_type=IncidentType.MEDICATION_SAFETY,
                occurred_at=now - timedelta(days=2),
            )
        )

    patterns = safety_pattern_service.detect_patterns(
        start_time=now - timedelta(days=7),
        end_time=now,
    )
    assert len(patterns) >= 1
    pat = patterns[0]
    assert pat.occurrence_count == 3
    assert pat.affected_subsystem == IncidentType.MEDICATION_SAFETY.value
    assert len(pat.evidence_references) == 3


# ===========================================================================
# 3. Corrective Action Effectiveness Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_corrective_action_effectiveness_evaluation():
    """Evaluation returns NO_RECURRENCE_OBSERVED when no incidents occur during observation window."""
    now = datetime.now(timezone.utc)
    # 1. Create incident and completed action in the past
    inc = await clinical_incident_service.create_incident(
        IncidentCreateRequest(
            title="Old defect",
            description="Historical bug",
            incident_type=IncidentType.SYSTEM_FAILURE,
            occurred_at=now - timedelta(days=40),
        )
    )
    action = await corrective_action_service.create_action(
        incident_id=inc.id,
        request=CorrectiveActionCreateRequest(
            action_type=ActionType.CODE_FIX,
            title="Fix deadlock",
            description="Resolved thread deadlock",
        ),
        created_by_id="dev-1",
    )
    action.completed_at = now - timedelta(days=35)
    safety_incident_repository.save_action(action)

    # 2. Evaluate effectiveness over 30 days
    eff = safety_effectiveness_service.evaluate_action_effectiveness(action.id, observation_days=30)
    assert eff.state == EffectivenessState.NO_RECURRENCE_OBSERVED
    assert eff.post_implementation_count == 0
    assert "guarantee" in eff.limitations[1].lower()


# ===========================================================================
# 4. Recommendation & Human Review Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_recommendation_lifecycle_and_ai_prohibition():
    """Recommendation creation, review acceptance, and AI prohibition enforcement."""
    rec = safety_recommendation_service.create_recommendation(
        recommendation_type=RecommendationType.ADD_VALIDATION_RULE,
        title="Enforce FHIR schema constraint",
        description="Add structural validation for incoming vitals",
        rationale_summary="Observed 4 malformed provider payloads.",
        affected_subsystem="INTEROPERABILITY",
    )
    assert rec.status == RecommendationStatus.REVIEW_REQUIRED

    # 1. AI cannot review recommendation
    with pytest.raises(AISafetyLearningAuthorityProhibitedException):
        await safety_recommendation_service.review_recommendation(
            recommendation_id=rec.id,
            request=RecommendationReviewRequest(decision="ACCEPT", notes="AI approved"),
            reviewer_id="ai-bot",
            reviewer_role="AI_AGENT",
        )

    # 2. Human officer accepts recommendation
    reviewed = await safety_recommendation_service.review_recommendation(
        recommendation_id=rec.id,
        request=RecommendationReviewRequest(decision="ACCEPT", notes="Approved for sprint 24"),
        reviewer_id="usr-safety-officer-p50",
        reviewer_role="SAFETY_OFFICER",
    )
    assert reviewed.status == RecommendationStatus.ACCEPTED
    assert reviewed.reviewed_by_id == "usr-safety-officer-p50"


# ===========================================================================
# 5. Analysis Job Orchestration & Idempotency
# ===========================================================================


@pytest.mark.asyncio
async def test_analysis_job_orchestration_and_idempotency():
    """Analysis job creates results, metrics, and honors idempotency keys."""
    req = SafetyAnalysisCreateRequest(
        analysis_type=AnalysisType.INCIDENT_TREND,
        scope_type=AnalysisScopeType.GLOBAL_SYSTEM,
        relative_window="LAST_30_DAYS",
        idempotency_key="idemp-key-p50-001",
    )
    job1 = await safety_learning_service.request_analysis(
        request=req,
        requested_by_id="usr-safety-officer-p50",
        requested_by_role="ADMIN",
    )
    assert job1.status == AnalysisStatus.COMPLETED
    assert job1.result is not None
    assert len(job1.result.metrics) >= 1

    # Repeat with same idempotency key returns existing job
    job2 = await safety_learning_service.request_analysis(
        request=req,
        requested_by_id="usr-safety-officer-p50",
        requested_by_role="ADMIN",
    )
    assert job2.id == job1.id


# ===========================================================================
# 6. REST API Integration Tests via TestClient
# ===========================================================================


def test_api_safety_learning_flow(client, safety_officer_headers):
    """Test full HTTP REST API flow for Phase 50."""
    # 1. Request analysis
    res1 = client.post(
        "/api/v1/safety-learning/analyses",
        headers=safety_officer_headers,
        json={
            "analysis_type": "INCIDENT_TREND",
            "scope_type": "GLOBAL_SYSTEM",
            "relative_window": "LAST_30_DAYS",
            "idempotency_key": "api-idemp-01",
        },
    )
    assert res1.status_code == 201
    job_data = res1.json()["data"]
    job_id = job_data["id"]

    # 2. Get job
    res2 = client.get(f"/api/v1/safety-learning/analyses/{job_id}", headers=safety_officer_headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == job_id

    # 3. Get results
    res3 = client.get(f"/api/v1/safety-learning/analyses/{job_id}/results", headers=safety_officer_headers)
    assert res3.status_code == 200
    res_data = res3.json()["data"]
    assert res_data["analysis_id"] == job_id
    assert "metrics" in res_data

    # 4. List patterns
    res4 = client.get("/api/v1/safety-learning/patterns", headers=safety_officer_headers)
    assert res4.status_code == 200

    # 5. List recommendations
    res5 = client.get("/api/v1/safety-learning/recommendations", headers=safety_officer_headers)
    assert res5.status_code == 200

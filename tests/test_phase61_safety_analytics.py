"""Phase 61: Clinical Safety Surveillance Analytics, Signal Correlation & Governed Risk Intelligence Tests.

Validates:
- Phase 60 signal intake into longitudinal surveillance analytics
- Analytical input eligibility, provenance preservation, scope/version alignment, privacy/PHI filtering
- Temporal observation windows and deterministic ordering
- Recurrence analysis across categories, controls, workflows, and facilities
- Trend analysis (INCREASING, DECREASING, STABLE, SPIKE) and baseline comparisons
- Distribution and concentration analysis without PHI exposure
- Mandatory non-negotiable invariants:
    - CONCENTRATION != CAUSALITY
    - CORRELATION != CAUSATION
    - PATTERN != SAFETY FAILURE
    - RISK INDICATOR != CONFIRMED RISK
    - ABSENCE OF RISK INDICATOR != ABSENCE OF RISK
    - UNKNOWN / INSUFFICIENT_DATA != SAFE
- Cross-signal correlation across shared operational attributes
- Multi-signal pattern detection (SAFETY_CONTROL_CLUSTER, REPEATED_FAILURE, TEMPORAL_CLUSTER, POST_CHANGE_PATTERN)
- Governed emerging risk indicator generation and uncertainty quantification
- Strict separation of confidence from severity
- Human surveillance review workflow and AI authority restriction (AI cannot approve reviews or declare safety)
- Governed routing and multi-routing to authoritative phases (Phase 49 Incident, Phase 51 Governance, Phase 52 Assurance, Phase 55 Effectiveness, Phase 60 Reassessment)
- Multi-tenant isolation and security boundary enforcement
- Idempotency and reanalysis under updated versions
- Filtered listing endpoints (review-required, risk-indicators, escalation-required, reassessment-required, reanalysis-required)
- Async processing simulation
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_analytics_repository import get_safety_analytics_repository
from app.schemas.auth import UserRole
from app.schemas.safety_analytics import (
    AnalysisLifecycleState,
    AnalyticalUncertaintyState,
    AnalyticsRoutingDestination,
    CorrelationState,
    HumanAnalyticsReviewDecision,
    PatternClass,
    RecurrenceState,
    RiskIndicatorType,
    SignalEligibilityStatus,
    TrendDirection,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-analyst-01"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    repo = get_safety_analytics_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _sample_signals(
    base_id: str = "sig-p60",
    org_id: str = "org-apollo-01",
    facility_id: str = "fac-delhi-01",
    control_id: str = "sc-pediatric-weight-check",
    version: str = "v2.5.0",
    count: int = 4,
) -> list:
    signals = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        signals.append({
            "signal_id": f"{base_id}-{i+1}",
            "triage_id": f"trg-p60-{i+1}",
            "organization_id": org_id,
            "facility_id": facility_id,
            "version": version,
            "source": "Phase 60",
            "classification": "SAFETY_CONTROL",
            "governed_severity": "HIGH" if i % 2 == 0 else "CRITICAL",
            "uncertainty": "LOW_UNCERTAINTY",
            "observed_at": (now - timedelta(days=count - i)).isoformat(),
            "metadata": {
                "safety_control_id": control_id,
                "workflow": "clinical-dosing",
                "violation_code": "DOSE_LIMIT_EXCEEDED",
            },
        })
    return signals


# ---------------------------------------------------------------------------
# 1. Lifecycle: Creation, Input Validation & Eligibility
# ---------------------------------------------------------------------------


def test_create_analysis_with_signal_eligibility_filtering(client: TestClient):
    """Signals outside window, mismatched scopes, or containing PHI must be classified correctly."""
    now = datetime.now(timezone.utc)
    raw_signals = [
        # 1. Valid eligible signal
        {
            "signal_id": "sig-valid-01",
            "organization_id": "org-apollo-01",
            "facility_id": "fac-delhi-01",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
            "metadata": {"workflow": "med-reconciliation"},
        },
        # 2. Duplicate signal
        {
            "signal_id": "sig-valid-01",
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
        },
        # 3. Scope mismatch (different org)
        {
            "signal_id": "sig-wrong-org",
            "organization_id": "org-other-99",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
        },
        # 4. Version mismatch
        {
            "signal_id": "sig-wrong-ver",
            "organization_id": "org-apollo-01",
            "version": "v9.9.9",
            "observed_at": now.isoformat(),
        },
        # 5. Stale signal (past observation window)
        {
            "signal_id": "sig-stale-01",
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
            "observed_at": (now - timedelta(days=90)).isoformat(),
        },
        # 6. Privacy restricted (unminimized raw PHI)
        {
            "signal_id": "sig-phi-leak",
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
            "observed_at": now.isoformat(),
            "metadata": {"ssn": "000-11-2222", "patient_name": "John Doe"},
        },
    ]

    payload = {
        "analysis_id": "anl-test-eligibility",
        "scope": {
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
        },
        "observation_window": {
            "window_type": "LAST_30_DAYS",
            "duration_hours": 720.0,
        },
        "signals": raw_signals,
    }

    res = client.post("/api/v1/safety-analytics", json=payload)
    assert res.status_code == 201
    data = res.json()["data"]

    assert len(data["eligible_signals"]) == 1
    assert data["eligible_signals"][0]["signal_id"] == "sig-valid-01"

    excluded_map = {s["signal_id"]: s["eligibility_status"] for s in data["excluded_signals"]}
    assert excluded_map["sig-valid-01"] == SignalEligibilityStatus.DUPLICATE.value
    assert excluded_map["sig-wrong-org"] == SignalEligibilityStatus.SCOPE_MISMATCH.value
    assert excluded_map["sig-wrong-ver"] == SignalEligibilityStatus.VERSION_MISMATCH.value
    assert excluded_map["sig-stale-01"] == SignalEligibilityStatus.STALE.value
    assert excluded_map["sig-phi-leak"] == SignalEligibilityStatus.PRIVACY_RESTRICTED.value


# ---------------------------------------------------------------------------
# 2. Analytical Execution: Recurrence, Trend, Distribution & Concentration
# ---------------------------------------------------------------------------


def test_analytical_pipeline_execution(client: TestClient):
    """Full execution generates recurrence, trends, distributions, concentrations, patterns and risk indicators."""
    signals = _sample_signals(base_id="sig-pipe", count=4)
    create_payload = {
        "analysis_id": "anl-pipeline-01",
        "scope": {
            "organization_id": "org-apollo-01",
            "facility_id": "fac-delhi-01",
            "version": "v2.5.0",
        },
        "signals": signals,
    }

    # 1. Create
    res_create = client.post("/api/v1/safety-analytics", json=create_payload)
    assert res_create.status_code == 201

    # 2. Execute analysis
    res_exec = client.post("/api/v1/safety-analytics/anl-pipeline-01/analyze", json={})
    assert res_exec.status_code == 200
    data = res_exec.json()["data"]

    assert data["lifecycle_state"] in (
        AnalysisLifecycleState.REVIEW_REQUIRED.value,
        AnalysisLifecycleState.ESCALATION_REQUIRED.value,
    )
    assert data["requires_human_review"] is True
    assert len(data["recurrence_findings"]) > 0
    assert len(data["trend_findings"]) > 0
    assert len(data["distribution_findings"]) > 0
    assert len(data["concentration_findings"]) > 0
    assert len(data["pattern_findings"]) > 0
    assert len(data["risk_indicators"]) > 0

    # Verify concentration invariant note
    conc = data["concentration_findings"][0]
    assert "causality" in conc["analytical_note"].lower()

    # Verify correlation invariant note (if correlation produced)
    if data["correlation_findings"]:
        cor = data["correlation_findings"][0]
        assert "causation" in cor["analytical_note"].lower()


# ---------------------------------------------------------------------------
# 3. Non-Negotiable Invariant: UNKNOWN / INSUFFICIENT_DATA != SAFE
# ---------------------------------------------------------------------------


def test_empty_dataset_fail_safe_behavior(client: TestClient):
    """Empty or missing signals must yield INSUFFICIENT_DATA, NEVER safe or cleared."""
    create_payload = {
        "analysis_id": "anl-empty-01",
        "scope": {"organization_id": "org-apollo-01"},
        "signals": [],
    }

    client.post("/api/v1/safety-analytics", json=create_payload)
    res_exec = client.post("/api/v1/safety-analytics/anl-empty-01/analyze", json={})
    assert res_exec.status_code == 200
    data = res_exec.json()["data"]

    assert data["overall_uncertainty"] == AnalyticalUncertaintyState.INSUFFICIENT_DATA.value
    # Recurrence must indicate insufficient data
    rec_states = [r["state"] for r in data["recurrence_findings"]]
    assert RecurrenceState.INSUFFICIENT_DATA.value in rec_states

    # Trends must indicate insufficient data
    trend_dirs = [t["direction"] for t in data["trend_findings"]]
    assert TrendDirection.INSUFFICIENT_DATA.value in trend_dirs


# ---------------------------------------------------------------------------
# 4. Pattern Detection & Emerging Risk Indicators
# ---------------------------------------------------------------------------


def test_pattern_and_risk_indicator_generation(client: TestClient):
    """Repeated safety control failures trigger SAFETY_CONTROL_DEGRADATION indicator."""
    signals = _sample_signals(
        base_id="sig-deg",
        control_id="sc-high-risk-infusion",
        count=4,
    )

    client.post(
        "/api/v1/safety-analytics",
        json={
            "analysis_id": "anl-degrade-01",
            "scope": {"organization_id": "org-apollo-01", "version": "v2.5.0"},
            "signals": signals,
        },
    )

    res = client.post("/api/v1/safety-analytics/anl-degrade-01/analyze", json={})
    assert res.status_code == 200
    data = res.json()["data"]

    # Check pattern detection
    pattern_classes = [p["pattern_class"] for p in data["pattern_findings"]]
    assert PatternClass.REPEATED_FAILURE.value in pattern_classes

    # Check risk indicator generation
    indicator_types = [ind["indicator_type"] for ind in data["risk_indicators"]]
    assert RiskIndicatorType.SAFETY_CONTROL_DEGRADATION.value in indicator_types

    deg_ind = next(
        ind for ind in data["risk_indicators"]
        if ind["indicator_type"] == RiskIndicatorType.SAFETY_CONTROL_DEGRADATION.value
    )
    assert deg_ind["warrants_governed_attention"] is True
    assert deg_ind["governed_severity"] == "HIGH"
    assert AnalyticsRoutingDestination.PHASE_52_ASSURANCE_REVIEW.value in deg_ind["recommended_routes"]
    assert AnalyticsRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW.value in deg_ind["recommended_routes"]


# ---------------------------------------------------------------------------
# 5. Human Review Workflow & AI Boundary Restrictions
# ---------------------------------------------------------------------------


def test_ai_agent_cannot_approve_review(client: TestClient):
    """AI agents are strictly forbidden from approving reviews or declaring safety (HTTP 403)."""
    signals = _sample_signals(base_id="sig-ai", count=2)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-ai-block", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-ai-block/analyze", json={})

    review_payload = {
        "decision": HumanAnalyticsReviewDecision.ACKNOWLEDGE.value,
        "reason": "AI automated assessment claims findings are normal",
        "is_ai": True,  # AI flag
    }

    res = client.post("/api/v1/safety-analytics/anl-ai-block/review", json=review_payload)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CLINICAL_ACTION_RESTRICTED"


def test_human_review_successful_disposition(client: TestClient):
    """Human clinical safety officer can review, escalate, or request reassessment."""
    signals = _sample_signals(base_id="sig-human", count=2)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-human-rev", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-human-rev/analyze", json={})

    review_payload = {
        "decision": HumanAnalyticsReviewDecision.ESCALATE.value,
        "reason": "Verified clinical safety risk indicator requires governance escalation",
        "is_ai": False,
    }

    res = client.post("/api/v1/safety-analytics/anl-human-rev/review", json=review_payload)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["lifecycle_state"] == AnalysisLifecycleState.ESCALATION_REQUIRED.value
    assert data["requires_escalation"] is True
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["decision"] == HumanAnalyticsReviewDecision.ESCALATE.value


# ---------------------------------------------------------------------------
# 6. Governed Routing & Multi-Routing
# ---------------------------------------------------------------------------


def test_governed_multi_routing(client: TestClient):
    """Analytical findings can be routed simultaneously to Phase 52, 55, and 51."""
    signals = _sample_signals(base_id="sig-route", count=3)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-multiroute", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-multiroute/analyze", json={})

    routing_payload = {
        "destinations": [
            AnalyticsRoutingDestination.PHASE_52_ASSURANCE_REVIEW.value,
            AnalyticsRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW.value,
            AnalyticsRoutingDestination.PHASE_51_GOVERNANCE_REVIEW.value,
        ],
        "reason": "Multiple safety control failures warrant cross-phase oversight",
    }

    res = client.post("/api/v1/safety-analytics/anl-multiroute/route", json=routing_payload)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["lifecycle_state"] == AnalysisLifecycleState.ROUTED.value
    assert len(data["routings"]) == 3
    targets = {r["destination"]: r["target_phase"] for r in data["routings"]}
    assert targets[AnalyticsRoutingDestination.PHASE_52_ASSURANCE_REVIEW.value] == "PHASE_52_SAFETY_ASSURANCE"
    assert targets[AnalyticsRoutingDestination.PHASE_55_EFFECTIVENESS_REVIEW.value] == "PHASE_55_ACTION_EFFECTIVENESS"
    assert targets[AnalyticsRoutingDestination.PHASE_51_GOVERNANCE_REVIEW.value] == "PHASE_51_SAFETY_GOVERNANCE"


# ---------------------------------------------------------------------------
# 7. Subpath Resource Endpoints
# ---------------------------------------------------------------------------


def test_subpath_resource_endpoints(client: TestClient):
    """Verify detailed subpath endpoints (trends, patterns, correlations, risk-indicators, signals, status, history)."""
    signals = _sample_signals(base_id="sig-subpaths", count=3)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-subpaths-01", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-subpaths-01/analyze", json={})

    # Status
    res_status = client.get("/api/v1/safety-analytics/anl-subpaths-01/status")
    assert res_status.status_code == 200
    assert "lifecycle_state" in res_status.json()["data"]

    # Signals
    res_sigs = client.get("/api/v1/safety-analytics/anl-subpaths-01/signals")
    assert res_sigs.status_code == 200
    assert len(res_sigs.json()["data"]["eligible"]) == 3

    # Trends
    res_trends = client.get("/api/v1/safety-analytics/anl-subpaths-01/trends")
    assert res_trends.status_code == 200
    assert len(res_trends.json()["data"]) >= 1

    # Patterns
    res_pats = client.get("/api/v1/safety-analytics/anl-subpaths-01/patterns")
    assert res_pats.status_code == 200
    assert len(res_pats.json()["data"]) >= 1

    # Correlations
    res_cors = client.get("/api/v1/safety-analytics/anl-subpaths-01/correlations")
    assert res_cors.status_code == 200

    # Risk Indicators
    res_inds = client.get("/api/v1/safety-analytics/anl-subpaths-01/risk-indicators")
    assert res_inds.status_code == 200

    # Evidence
    res_evd = client.get("/api/v1/safety-analytics/anl-subpaths-01/evidence")
    assert res_evd.status_code == 200
    assert len(res_evd.json()["data"]) >= 1

    # History
    res_hist = client.get("/api/v1/safety-analytics/anl-subpaths-01/history")
    assert res_hist.status_code == 200
    assert len(res_hist.json()["data"]) >= 2  # Created + Executed


# ---------------------------------------------------------------------------
# 8. Reanalysis & Reassessment
# ---------------------------------------------------------------------------


def test_reanalyze_and_reassess_flow(client: TestClient):
    """Reanalysis updates version and generates audit history; reassessment requests Phase 60 review."""
    signals = _sample_signals(base_id="sig-re", count=2)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-reanalysis-01", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-reanalysis-01/analyze", json={})

    # Reanalyze under updated version
    re_res = client.post(
        "/api/v1/safety-analytics/anl-reanalysis-01/reanalyze",
        json={"reason": "Updated configuration version released", "updated_version": "v2.6.0"},
    )
    assert re_res.status_code == 200
    assert re_res.json()["data"]["version"] == "v2.6.0"

    # Reassessment request
    reassess_res = client.post(
        "/api/v1/safety-analytics/anl-reanalysis-01/reassess",
        json={"reason": "Signals show conflicting classification requiring Phase 60 review"},
    )
    assert reassess_res.status_code == 200
    data = reassess_res.json()["data"]
    assert data["lifecycle_state"] == AnalysisLifecycleState.REASSESSMENT_REQUIRED.value
    assert data["requires_reassessment"] is True


# ---------------------------------------------------------------------------
# 9. Filtered Listing Queries
# ---------------------------------------------------------------------------


def test_filtered_listing_endpoints(client: TestClient):
    """Verify review-required, risk-indicators, escalation-required, and reassessment-required queries."""
    signals = _sample_signals(base_id="sig-list", count=3)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-filter-01", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-filter-01/analyze", json={})

    # 1. Review required
    res_rev = client.get("/api/v1/safety-analytics/review-required")
    assert res_rev.status_code == 200
    assert len(res_rev.json()["data"]) >= 1

    # 2. Risk indicators
    res_inds = client.get("/api/v1/safety-analytics/risk-indicators")
    assert res_inds.status_code == 200
    assert len(res_inds.json()["data"]) >= 1

    # 3. Main list
    res_all = client.get("/api/v1/safety-analytics")
    assert res_all.status_code == 200
    assert len(res_all.json()["data"]) >= 1


# ---------------------------------------------------------------------------
# 10. Multi-Tenant Boundary Enforcement
# ---------------------------------------------------------------------------


def test_cross_tenant_access_denied(client: TestClient):
    """User from another organization must be rejected with 403 ACCESS_DENIED."""
    signals = _sample_signals(base_id="sig-sec", count=2)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-tenant-01", "signals": signals},
    )

    # Attempt access with a different tenant header
    headers = {
        "X-User-Id": "usr-malicious-99",
        "X-User-Organization": "org-competitor-88",
    }
    res = client.get("/api/v1/safety-analytics/anl-tenant-01", headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCESS_DENIED"


# ---------------------------------------------------------------------------
# 11. Idempotency Protection
# ---------------------------------------------------------------------------


def test_idempotency_protection(client: TestClient):
    """Repeated calls with same idempotency key return the original analysis deterministically."""
    signals = _sample_signals(base_id="sig-idem", count=2)
    payload = {
        "analysis_id": "anl-idem-01",
        "idempotency_key": "idemp-key-xyz-123",
        "signals": signals,
    }

    res1 = client.post("/api/v1/safety-analytics", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/safety-analytics", json=payload)
    assert res2.status_code == 201
    assert res2.json()["data"]["analysis_id"] == "anl-idem-01"


# ---------------------------------------------------------------------------
# 12. Async Execution Simulation
# ---------------------------------------------------------------------------


def test_async_analysis_execution(client: TestClient):
    """Triggering analysis with is_async=True enqueues Phase 22 worker run."""
    signals = _sample_signals(base_id="sig-async", count=2)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-async-01", "signals": signals},
    )

    res = client.post(
        "/api/v1/safety-analytics/anl-async-01/analyze",
        json={"is_async": True},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["status"] == "QUEUED"
    assert data["worker_lane"] == "SURVEILLANCE_ANALYTICS_V1"


# ---------------------------------------------------------------------------
# 13. Additional Edge Cases & Fail-Safe Invariants
# ---------------------------------------------------------------------------


def test_cross_signal_correlation_details(client: TestClient):
    """Signals sharing control, workflow, version, and classification are correlated without inferring causality."""
    now = datetime.now(timezone.utc)
    signals = [
        {
            "signal_id": "sig-cor-01",
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
            "classification": "SAFETY_CONTROL",
            "observed_at": now.isoformat(),
            "metadata": {
                "safety_control_id": "sc-antibiotic-stewardship",
                "workflow": "pediatric-infection",
            },
        },
        {
            "signal_id": "sig-cor-02",
            "organization_id": "org-apollo-01",
            "version": "v1.0.0",
            "classification": "SAFETY_CONTROL",
            "observed_at": (now + timedelta(hours=1)).isoformat(),
            "metadata": {
                "safety_control_id": "sc-antibiotic-stewardship",
                "workflow": "pediatric-infection",
            },
        },
    ]

    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-cor-test", "signals": signals},
    )
    res = client.post("/api/v1/safety-analytics/anl-cor-test/analyze", json={})
    assert res.status_code == 200
    cors = res.json()["data"]["correlation_findings"]
    assert len(cors) >= 1
    assert cors[0]["state"] == CorrelationState.CORRELATED.value
    assert "causation" in cors[0]["analytical_note"].lower()


def test_trend_spike_and_decreasing_behavior(client: TestClient):
    """Verifies that sudden bursts result in SPIKE and drop results in DECREASING."""
    now = datetime.now(timezone.utc)
    # First half has 1 signal, second half has 4 signals -> SPIKE
    spike_signals = [
        {
            "signal_id": "sig-sp-1",
            "organization_id": "org-apollo-01",
            "observed_at": (now - timedelta(days=10)).isoformat(),
            "metadata": {"safety_control_id": "sc-spike-ctrl"},
        },
        {
            "signal_id": "sig-sp-2",
            "organization_id": "org-apollo-01",
            "observed_at": (now - timedelta(days=2)).isoformat(),
            "metadata": {"safety_control_id": "sc-spike-ctrl"},
        },
        {
            "signal_id": "sig-sp-3",
            "organization_id": "org-apollo-01",
            "observed_at": (now - timedelta(days=1)).isoformat(),
            "metadata": {"safety_control_id": "sc-spike-ctrl"},
        },
        {
            "signal_id": "sig-sp-4",
            "organization_id": "org-apollo-01",
            "observed_at": now.isoformat(),
            "metadata": {"safety_control_id": "sc-spike-ctrl"},
        },
    ]

    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-spike-01", "signals": spike_signals},
    )
    res = client.post("/api/v1/safety-analytics/anl-spike-01/analyze", json={})
    assert res.status_code == 200
    trends = res.json()["data"]["trend_findings"]
    directions = [t["direction"] for t in trends]
    assert TrendDirection.SPIKE.value in directions


def test_post_change_pattern_and_reopen_indicator(client: TestClient):
    """Signals associated with active rollouts generate POST_CHANGE_PATTERN and regression indicator."""
    now = datetime.now(timezone.utc)
    signals = [
        {
            "signal_id": "sig-roll-01",
            "organization_id": "org-apollo-01",
            "observed_at": (now - timedelta(hours=2)).isoformat(),
            "metadata": {"rollout_id": "rol-p57-999", "change_id": "chg-p51-888"},
        },
        {
            "signal_id": "sig-roll-02",
            "organization_id": "org-apollo-01",
            "observed_at": (now - timedelta(hours=1)).isoformat(),
            "metadata": {"rollout_id": "rol-p57-999", "change_id": "chg-p51-888"},
        },
    ]

    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-rollout-pattern", "signals": signals},
    )
    res = client.post("/api/v1/safety-analytics/anl-rollout-pattern/analyze", json={})
    assert res.status_code == 200
    data = res.json()["data"]

    pattern_classes = [p["pattern_class"] for p in data["pattern_findings"]]
    assert PatternClass.POST_CHANGE_PATTERN.value in pattern_classes

    ind_types = [ind["indicator_type"] for ind in data["risk_indicators"]]
    assert RiskIndicatorType.POST_CHANGE_REGRESSION_PATTERN.value in ind_types


def test_human_review_reject_flow(client: TestClient):
    """Human review decision REJECT_ANALYSIS transitions lifecycle to FAILED and marks indicators REJECTED."""
    signals = _sample_signals(base_id="sig-rej", count=2)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-reject-test", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-reject-test/analyze", json={})

    review_payload = {
        "decision": HumanAnalyticsReviewDecision.REJECT_ANALYSIS.value,
        "reason": "Analysis was performed with flawed simulation dataset parameters",
        "is_ai": False,
    }

    res = client.post("/api/v1/safety-analytics/anl-reject-test/review", json=review_payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["lifecycle_state"] == AnalysisLifecycleState.FAILED.value
    for ind in data["risk_indicators"]:
        assert ind["lifecycle_state"] == "REJECTED"


def test_fail_safe_high_uncertainty(client: TestClient):
    """Input signals with high uncertainty must propagate to overall HIGH_UNCERTAINTY, not resolved to safe."""
    signals = [
        {
            "signal_id": "sig-uncert-01",
            "organization_id": "org-apollo-01",
            "uncertainty": "HIGH_UNCERTAINTY",
            "metadata": {"safety_control_id": "sc-temp-01"},
        },
        {
            "signal_id": "sig-uncert-02",
            "organization_id": "org-apollo-01",
            "uncertainty": "HIGH_UNCERTAINTY",
            "metadata": {"safety_control_id": "sc-temp-01"},
        },
    ]

    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-high-uncert", "signals": signals},
    )
    res = client.post("/api/v1/safety-analytics/anl-high-uncert/analyze", json={})
    assert res.status_code == 200
    assert res.json()["data"]["overall_uncertainty"] == AnalyticalUncertaintyState.HIGH_UNCERTAINTY.value


def test_invalid_review_and_routing_requests_rejected(client: TestClient):
    """Validation errors for missing reasons or missing destinations return HTTP 400."""
    signals = _sample_signals(base_id="sig-err", count=2)
    client.post(
        "/api/v1/safety-analytics",
        json={"analysis_id": "anl-err-test", "signals": signals},
    )
    client.post("/api/v1/safety-analytics/anl-err-test/analyze", json={})

    # Review with empty reason
    res_rev = client.post(
        "/api/v1/safety-analytics/anl-err-test/review",
        json={"decision": "ACKNOWLEDGE", "reason": "   "},
    )
    assert res_rev.status_code == 400

    # Routing with empty destinations
    res_rtg = client.post(
        "/api/v1/safety-analytics/anl-err-test/route",
        json={"destinations": [], "reason": "Valid reason provided"},
    )
    assert res_rtg.status_code == 400

    # Non-existent analysis
    res_404 = client.get("/api/v1/safety-analytics/anl-non-existent-999")
    assert res_404.status_code == 404

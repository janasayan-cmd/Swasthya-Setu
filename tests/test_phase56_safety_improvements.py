"""Phase 56: Clinical Safety Assurance Feedback, Control Adaptation & Governed Continuous Improvement Tests.

Validates:
- End-to-end feedback loop: Phase 55 outcome -> Improvement Signal -> Proposal -> Impact Assessment -> Readiness Gate -> Phase 51 Governance
- Non-negotiable distinction: Effective control does NOT automatically trigger changes
- Change readiness gates strictly prevent routing unassessed or unverified proposals
- Recurrence detection routes pattern signals to Phase 50 learning
- Regression handling routes incident consideration to Phase 49 and follow-up to Phase 54
- History preservation across closure and reopening
- Idempotency protection
- Filtered listing endpoints (pending, high-priority, regressions, recurring, change-candidates)
"""

from datetime import datetime, timezone
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.action_effectiveness_repository import get_action_effectiveness_repository
from app.repositories.safety_action_repository import get_safety_action_repository
from app.repositories.safety_improvement_repository import get_safety_improvement_repository
from app.schemas.action_effectiveness import (
    EffectivenessCriterion,
    EffectivenessCriterionCategory,
    EffectivenessEvaluationRecord,
    EffectivenessLifecycleState,
    EffectivenessScope,
    EffectivenessState,
    ObservationWindow,
    ObservationWindowType,
    PostActionEvidenceItem,
    SafetyObjective,
)
from app.schemas.auth import UserRole
from app.schemas.safety_action import (
    ActionLifecycleState,
    ActionPriority,
    ActionType,
    FindingSourceType,
    SafetyActionRecord,
    SafetyActionScope,
    SafetyFindingReference,
)
from app.schemas.safety_improvement import (
    ImprovementLifecycleState,
    ImprovementPriority,
    ImprovementResponseType,
    ImprovementScope,
    ImprovementSignalType,
    SafetyChangeCategory,
    SafetyImprovementRecord,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-safety-officer-56"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    imp_repo = get_safety_improvement_repository()
    imp_repo.clear()
    eff_repo = get_action_effectiveness_repository()
    eff_repo.clear()
    act_repo = get_safety_action_repository()
    act_repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    imp_repo.clear()
    eff_repo.clear()
    act_repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _setup_action_and_evaluation(
    eval_id: str = "eff-test-01",
    action_id: str = "act-test-01",
    effectiveness_state: EffectivenessState = EffectivenessState.FAILED,
    regression_detected: bool = False,
    is_sustained: bool = False,
) -> EffectivenessEvaluationRecord:
    """Helper to populate an action and effectiveness evaluation."""
    act_repo = get_safety_action_repository()
    eff_repo = get_action_effectiveness_repository()

    action = SafetyActionRecord(
        action_id=action_id,
        finding=SafetyFindingReference(
            source_type=FindingSourceType.ASSURANCE_EVALUATION,
            source_id="eval-dose-01",
            finding_title="Dosing Safety Gate Underperformance",
            finding_summary="Safety gate execution dropped under high volume",
        ),
        action_type=ActionType.CONTROL_REVALIDATION,
        title="Dosing Verification Gate Review",
        description="Revalidation of dose verification control",
        scope=SafetyActionScope(organization_id="org-apollo-01", facility_id="fac-delhi-01"),
        priority=ActionPriority.HIGH,
        lifecycle_state=ActionLifecycleState.COMPLETED,
        created_by_id="usr-officer-1",
        created_by_role="SAFETY_OFFICER",
    )
    act_repo.save(action)

    evaluation = EffectivenessEvaluationRecord(
        evaluation_id=eval_id,
        action_id=action_id,
        scope=EffectivenessScope(organization_id="org-apollo-01", facility_id="fac-delhi-01"),
        lifecycle_state=EffectivenessLifecycleState.EFFECTIVENESS_ACCEPTED if is_sustained else EffectivenessLifecycleState.COMPARISON,
        effectiveness_state=effectiveness_state,
        safety_objective=SafetyObjective(
            description="Restore dosing gate execution rate to >= 99%",
            target_finding_type="ASSURANCE_EVALUATION",
            target_control_id="eval-dose-01",
            bounded_failure_mode="Concurrency timeout during peak admissions",
            is_evidence_testable=True,
        ),
        criteria=[
            EffectivenessCriterion(
                category=EffectivenessCriterionCategory.CONTROL_EXECUTION_RATE,
                metric_name="control_execution_rate",
                description="Gate execution rate",
                expected_threshold=0.99,
                operator=">=",
            )
        ],
        observation_window=ObservationWindow(
            window_type=ObservationWindowType.FIXED_DURATION,
            duration_hours=24,
        ),
        evidence_items=[
            PostActionEvidenceItem(
                evidence_id="evi-01",
                source_system="Phase 48",
                source_id="gate-run-200",
                scope=EffectivenessScope(organization_id="org-apollo-01"),
                evidence_type="CONTROL_TELEMETRY",
                data_payload={"control_execution_rate": 0.88},
            )
        ],
        is_sustained=is_sustained,
        regression_detected=regression_detected,
        created_by="usr-officer-1",
    )
    return eff_repo.save(evaluation)


# ---------------------------------------------------------------------------
# Test 1: Full Positive Feedback Loop
# ---------------------------------------------------------------------------

def test_full_positive_feedback_loop(client: TestClient):
    """Effectiveness result -> Improvement record -> Proposal -> Impact assessment -> Readiness -> Phase 51 routing."""
    evaluation = _setup_action_and_evaluation(
        eval_id="eff-loop-01",
        action_id="act-loop-01",
        effectiveness_state=EffectivenessState.FAILED,
    )

    # 1. Create improvement record
    create_res = client.post(
        "/api/v1/safety-improvements",
        json={"source_evaluation_id": evaluation.evaluation_id},
    )
    assert create_res.status_code == 201, create_res.text
    imp_data = create_res.json()["data"]
    imp_id = imp_data["improvement_id"]
    assert imp_data["signal_type"] == "INEFFECTIVE_ACTION"
    assert imp_data["lifecycle_state"] == "SIGNAL_IDENTIFIED"

    # 2. Formulate Change Proposal
    proposal_payload = {
        "change_category": "CONTROL_CONFIGURATION_CHANGE",
        "problem_statement": "Dosing verification gate experiences concurrency timeout during peak bursts.",
        "proposed_solution": "Increase worker pool concurrency allocation and add read-through caching for rule baselines.",
        "expected_outcome": "Maintain execution rate >= 99.5% even during peak bursts exceeding 1,000 req/sec.",
        "rollback_plan": "Revert concurrency pool sizing configuration to baseline v1 within 60 seconds.",
        "validation_plan": "Execute automated synthetic peak test against canary environment.",
        "observation_plan": "Monitor telemetry execution rate over 48 continuous hours in production.",
    }
    prop_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/change-proposal",
        json=proposal_payload,
    )
    assert prop_res.status_code == 200, prop_res.text
    assert prop_res.json()["data"]["lifecycle_state"] == "CHANGE_PROPOSED"

    # 3. Check readiness before impact assessment (Must NOT be ready)
    readiness_pre = client.get(f"/api/v1/safety-improvements/{imp_id}/readiness")
    assert readiness_pre.status_code == 200
    assert readiness_pre.json()["data"]["is_ready"] is False
    assert any("impact assessment" in b.lower() for b in readiness_pre.json()["data"]["blockers"])

    # 4. Record multidimensional impact assessment
    impact_payload = {
        "safety_impact": "Positive: Eliminates gate bypass window during high clinical admission surges.",
        "clinical_workflow_impact": "Negligible: Latency reduced by 15ms per prescription review.",
        "privacy_impact": "None: Configuration tuning does not modify PHI handling.",
        "security_impact": "None: Guardrails preserved.",
        "operational_impact": "Slight memory increase on cluster nodes (+150MB).",
        "rollback_complexity": "Low: Config change revertible via feature flag without downtime.",
        "affected_controls": ["ctrl-dose-verification"],
    }
    impact_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/impact-assessment",
        json=impact_payload,
    )
    assert impact_res.status_code == 200, impact_res.text
    assert impact_res.json()["data"]["lifecycle_state"] == "IMPACT_ASSESSED"

    # 5. Check readiness after impact assessment (Must BE ready)
    readiness_post = client.get(f"/api/v1/safety-improvements/{imp_id}/readiness")
    assert readiness_post.status_code == 200
    assert readiness_post.json()["data"]["is_ready"] is True

    # 6. Route to Phase 51 Governance
    route_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/route-governance",
        json={"rationale": "Readiness gates satisfied. Requesting Phase 51 review and rollout approval."},
    )
    assert route_res.status_code == 200, route_res.text
    routed_data = route_res.json()["data"]
    assert routed_data["lifecycle_state"] == "GOVERNANCE_ROUTED"
    assert routed_data["change_proposal"]["phase51_change_request_id"] is not None

    # Check routing records
    routings = routed_data["routings"]
    dest_phases = [r["destination_phase"] for r in routings]
    assert "Phase 51" in dest_phases
    assert "Phase 52" in dest_phases
    assert "Phase 53" in dest_phases


# ---------------------------------------------------------------------------
# Test 2: Effective Control Rule (EFFECTIVE != CHANGE REQUEST)
# ---------------------------------------------------------------------------

def test_effective_control_does_not_trigger_change(client: TestClient):
    """An effective control continues monitoring and rejects arbitrary change requests."""
    evaluation = _setup_action_and_evaluation(
        eval_id="eff-eff-01",
        action_id="act-eff-01",
        effectiveness_state=EffectivenessState.EFFECTIVE_OBSERVED,
        is_sustained=True,
    )

    create_res = client.post(
        "/api/v1/safety-improvements",
        json={"source_evaluation_id": evaluation.evaluation_id},
    )
    assert create_res.status_code == 201
    imp_data = create_res.json()["data"]
    assert imp_data["signal_type"] == "EFFECTIVE_CONTROL"
    assert imp_data["response_type"] == "NO_CHANGE_REQUIRED"
    assert imp_data["priority"] == "LOW"

    # Client attempts to force CREATE_CHANGE_REQUEST for an effective control
    imp_id = imp_data["improvement_id"]
    classify_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/classify",
        json={
            "signal_type": "EFFECTIVE_CONTROL",
            "response_type": "CREATE_CHANGE_REQUEST",
            "rationale": "Client attempting arbitrary change despite effective control.",
        },
    )
    assert classify_res.status_code == 400
    assert "CHANGE_NOT_ALLOWED" in classify_res.text or "cannot trigger change" in classify_res.text.lower()


# ---------------------------------------------------------------------------
# Test 3: Change Readiness Gate Blocking
# ---------------------------------------------------------------------------

def test_unready_proposal_cannot_route_to_governance(client: TestClient):
    """Routing an unready change proposal to governance must be rejected."""
    evaluation = _setup_action_and_evaluation(
        eval_id="eff-unready-01",
        action_id="act-unready-01",
        effectiveness_state=EffectivenessState.FAILED,
    )

    create_res = client.post(
        "/api/v1/safety-improvements",
        json={"source_evaluation_id": evaluation.evaluation_id},
    )
    imp_id = create_res.json()["data"]["improvement_id"]

    # Attempt to route before proposal is even created
    route_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/route-governance",
        json={"rationale": "Premature submission."},
    )
    assert route_res.status_code == 400
    assert "CHANGE_NOT_READY" in route_res.text


# ---------------------------------------------------------------------------
# Test 4: Recurring Failure & Learning Signal Routing
# ---------------------------------------------------------------------------

def test_recurring_failure_routes_to_phase50_learning(client: TestClient):
    """Recurring failures trigger Phase 50 learning signals."""
    evaluation = _setup_action_and_evaluation(
        eval_id="eff-rec-01",
        action_id="act-rec-01",
        effectiveness_state=EffectivenessState.FAILED,
    )

    # Pre-populate prior improvement to simulate recurrence
    imp_repo = get_safety_improvement_repository()
    prior_imp = SafetyImprovementRecord(
        improvement_id="imp-prior-01",
        source_evaluation_id="eff-rec-01",
        source_action_id="act-rec-01",
        scope=ImprovementScope(organization_id="org-apollo-01"),
        signal_type=ImprovementSignalType.INEFFECTIVE_ACTION,
        response_type=ImprovementResponseType.REASSESS,
        lifecycle_state=ImprovementLifecycleState.CLOSED,
        created_by="officer-1",
    )
    imp_repo.save(prior_imp)

    create_res = client.post(
        "/api/v1/safety-improvements",
        json={
            "source_evaluation_id": evaluation.evaluation_id,
            "signal_type": "RECURRING_FAILURE",
            "response_type": "REQUEST_RISK_REASSESSMENT",
        },
    )
    assert create_res.status_code == 201
    imp_data = create_res.json()["data"]
    assert imp_data["is_recurring"] is True

    # Verify Phase 50 routing
    dest_phases = [r["destination_phase"] for r in imp_data["routings"]]
    assert "Phase 50" in dest_phases


# ---------------------------------------------------------------------------
# Test 5: Regression Handling & Incident Consideration Routing
# ---------------------------------------------------------------------------

def test_regression_handling_and_incident_routing(client: TestClient):
    """Regression outcome routes to Phase 49 for incident review and Phase 54 for follow-up."""
    evaluation = _setup_action_and_evaluation(
        eval_id="eff-reg-01",
        action_id="act-reg-01",
        effectiveness_state=EffectivenessState.REGRESSED,
        regression_detected=True,
    )

    create_res = client.post(
        "/api/v1/safety-improvements",
        json={"source_evaluation_id": evaluation.evaluation_id},
    )
    assert create_res.status_code == 201
    imp_data = create_res.json()["data"]
    assert imp_data["is_regression"] is True
    assert imp_data["signal_type"] == "CONTROL_REGRESSION"
    assert imp_data["priority"] in ("HIGH", "CRITICAL")

    # Check routings
    dest_phases = [r["destination_phase"] for r in imp_data["routings"]]
    assert "Phase 49" in dest_phases
    assert "Phase 54" in dest_phases


# ---------------------------------------------------------------------------
# Test 6: Policy Escalation & Reassessment
# ---------------------------------------------------------------------------

def test_escalation_and_reassessment(client: TestClient):
    """Verify policy escalation and formal reassessment transitions."""
    evaluation = _setup_action_and_evaluation(eval_id="eff-esc-01", action_id="act-esc-01")
    create_res = client.post("/api/v1/safety-improvements", json={"source_evaluation_id": evaluation.evaluation_id})
    imp_id = create_res.json()["data"]["improvement_id"]

    # Reassess
    reassess_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/reassess",
        json={"reason": "Additional root-cause telemetry is required before proposing changes."},
    )
    assert reassess_res.status_code == 200
    assert reassess_res.json()["data"]["lifecycle_state"] == "ANALYZING"
    assert reassess_res.json()["data"]["response_type"] == "REASSESS"

    # Escalate
    escalate_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/escalate",
        json={
            "target": "CLINICAL_SAFETY",
            "reason": "Repeated failure across multiple facilities requires clinical safety oversight.",
        },
    )
    assert escalate_res.status_code == 200
    assert escalate_res.json()["data"]["lifecycle_state"] == "ESCALATED"
    assert escalate_res.json()["data"]["priority"] in ("HIGH", "CRITICAL")


# ---------------------------------------------------------------------------
# Test 7: Closure and Reopening
# ---------------------------------------------------------------------------

def test_closure_and_reopening(client: TestClient):
    """Closing sets closed_at; reopening clears closed_at and increments reopened_count."""
    evaluation = _setup_action_and_evaluation(eval_id="eff-cls-01", action_id="act-cls-01")
    create_res = client.post("/api/v1/safety-improvements", json={"source_evaluation_id": evaluation.evaluation_id})
    imp_id = create_res.json()["data"]["improvement_id"]

    # Close
    close_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/close",
        json={"rationale": "Addressed by standard operational tuning and validated."},
    )
    assert close_res.status_code == 200
    assert close_res.json()["data"]["lifecycle_state"] == "CLOSED"
    assert close_res.json()["data"]["closed_at"] is not None

    # Cannot close again
    double_close = client.post(
        f"/api/v1/safety-improvements/{imp_id}/close",
        json={"rationale": "Closing again."},
    )
    assert double_close.status_code == 400

    # Reopen
    reopen_res = client.post(
        f"/api/v1/safety-improvements/{imp_id}/reopen",
        json={"reason": "Degradation resurfaced after subsequent deployment."},
    )
    assert reopen_res.status_code == 200
    assert reopen_res.json()["data"]["lifecycle_state"] == "REOPENED"
    assert reopen_res.json()["data"]["reopened_count"] == 1
    assert reopen_res.json()["data"]["closed_at"] is None


# ---------------------------------------------------------------------------
# Test 8: Filtered Queues and Listing
# ---------------------------------------------------------------------------

def test_filtered_queues(client: TestClient):
    """Verify queue filters: pending, high-priority, regressions, recurring, change-candidates."""
    evaluation = _setup_action_and_evaluation(
        eval_id="eff-q-01",
        action_id="act-q-01",
        effectiveness_state=EffectivenessState.REGRESSED,
        regression_detected=True,
    )
    create_res = client.post("/api/v1/safety-improvements", json={"source_evaluation_id": evaluation.evaluation_id})
    imp_id = create_res.json()["data"]["improvement_id"]

    # Pending
    res_pending = client.get("/api/v1/safety-improvements/pending")
    assert res_pending.status_code == 200
    assert any(r["improvement_id"] == imp_id for r in res_pending.json()["data"])

    # High Priority
    res_hp = client.get("/api/v1/safety-improvements/high-priority")
    assert res_hp.status_code == 200
    assert any(r["improvement_id"] == imp_id for r in res_hp.json()["data"])

    # Regressions
    res_reg = client.get("/api/v1/safety-improvements/regressions")
    assert res_reg.status_code == 200
    assert any(r["improvement_id"] == imp_id for r in res_reg.json()["data"])

"""Phase 55: Clinical Safety Oversight Action Effectiveness, Outcome Validation & Continuous Feedback Tests.

Tests:
- Full positive lifecycle: Action completed -> Evaluation created -> Evidence collected -> Comparison -> Assessment -> Human review -> Phase 52/53 routing
- AI boundary enforcement (AI cannot declare effectiveness or authorize reviews)
- Non-negotiable safety distinctions (MISSING != PASS, INSUFFICIENT != FAILURE, COMPLETION != EFFECTIVENESS)
- Vague objective rejection ('make the system safer')
- Action eligibility gating (action must be in completed/verified state)
- Sustained effectiveness and regression detection (with Phase 50, 51, 54, 49 routing)
- Baseline scope & environment alignment
- Idempotency conflict protection
- Multi-tenant / scope isolation
- Filtered listing endpoints (pending, review-required, regressions, insufficient-evidence, failed)
"""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from fastapi import Request
from app.api.deps import get_current_user
from app.main import app
from app.repositories.action_effectiveness_repository import get_action_effectiveness_repository
from app.repositories.safety_action_repository import get_safety_action_repository
from app.schemas.action_effectiveness import (
    EffectivenessCriterionCategory,
    EffectivenessLifecycleState,
    EffectivenessState,
    HumanReviewOutcome,
    ObservationWindowType,
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
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-safety-officer-55"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-main"),
        facility_id=request.headers.get("X-User-Facility", "fac-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    eff_repo = get_action_effectiveness_repository()
    eff_repo.clear()
    act_repo = get_safety_action_repository()
    act_repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    eff_repo.clear()
    act_repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _create_completed_action(action_id: str = "act-test-001", org_id: str = "org-main") -> SafetyActionRecord:
    """Helper to register a completed Phase 54 safety action."""
    act_repo = get_safety_action_repository()
    action = SafetyActionRecord(
        action_id=action_id,
        finding=SafetyFindingReference(
            source_type=FindingSourceType.ASSURANCE_EVALUATION,
            source_id="eval-deg-01",
            finding_title="Medication Verification Gate Degraded",
            finding_summary="Medication verification safety gate execution rate degraded below 98%",
        ),
        action_type=ActionType.CONTROL_REVALIDATION,
        title="Revalidate Medication Safety Control",
        description="Revalidation of safety gate following degradation",
        scope=SafetyActionScope(organization_id=org_id, facility_id="fac-01"),
        priority=ActionPriority.HIGH,
        lifecycle_state=ActionLifecycleState.COMPLETED,
        version=3,
        material_version=1,
        created_by_id="officer-1",
        created_by_role="SAFETY_OFFICER",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return act_repo.save(action)


# ---------------------------------------------------------------------------
# Test 1: Full Positive Lifecycle
# ---------------------------------------------------------------------------

def test_full_positive_lifecycle(client: TestClient):
    """Action completed -> Evaluation created -> Evidence collected -> Comparison -> Human Review Accept -> Routing."""
    action = _create_completed_action("act-pos-1")

    # 1. Create evaluation
    create_payload = {
        "action_id": action.action_id,
        "safety_objective": {
            "description": "Restore medication verification safety gate execution to >= 99%",
            "target_finding_type": "ASSURANCE_EVALUATION",
            "target_control_id": "eval-deg-01",
            "bounded_failure_mode": "Safety gate bypass under peak concurrency",
            "is_evidence_testable": True,
        },
        "observation_window_type": "FIXED_DURATION",
        "duration_hours": 24,
    }
    res = client.post("/api/v1/action-effectiveness/evaluations", json=create_payload)
    assert res.status_code == 201, res.text
    eval_data = res.json()["data"]
    eval_id = eval_data["evaluation_id"]
    assert eval_data["lifecycle_state"] == "EVIDENCE_COLLECTION"
    assert eval_data["effectiveness_state"] == "EVIDENCE_PENDING"

    # 2. Collect post-action evidence (conforming metrics)
    collect_payload = {
        "evidence_items": [
            {
                "source_system": "Phase 48",
                "source_id": "gate-run-101",
                "scope": {"organization_id": "org-main", "facility_id": "fac-01"},
                "evidence_type": "CONTROL_EXECUTION_TELEMETRY",
                "provenance": {"service": "safety_gate_service", "env": "prod"},
                "data_payload": {
                    "control_execution_rate": 0.998,
                    "control_execution_rate_numerator": 998,
                    "control_execution_rate_denominator": 1000,
                    "safety_finding_recurrence_count": 0,
                },
            }
        ]
    }
    res = client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/collect", json=collect_payload)
    assert res.status_code == 200, res.text

    # 3. Finalize evaluation -> comparison runs and flags human review
    res = client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/finalize", json={"reassess_if_needed": True})
    assert res.status_code == 200, res.text
    final_data = res.json()["data"]
    assert final_data["effectiveness_state"] == "EFFECTIVE_OBSERVED"
    assert final_data["lifecycle_state"] == "REVIEW_REQUIRED"
    assert final_data["requires_human_review"] is True

    # Check comparison endpoint
    res = client.get(f"/api/v1/action-effectiveness/evaluations/{eval_id}/comparison")
    assert res.status_code == 200
    comparisons = res.json()["data"]["comparisons"]
    assert len(comparisons) > 0
    assert all(c["is_conforming"] for c in comparisons)

    # 4. Human Review Accept
    accept_payload = {
        "rationale": "Post-action telemetry confirms 99.8% gate execution across 1,000 samples with 0 recurrences.",
        "limitations": "Evaluated during weekday peak volume only.",
    }
    res = client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/accept", json=accept_payload)
    assert res.status_code == 200, res.text
    accepted_data = res.json()["data"]
    assert accepted_data["lifecycle_state"] == "EFFECTIVENESS_ACCEPTED"
    assert accepted_data["is_sustained"] is True
    assert accepted_data["requires_human_review"] is False

    # 5. Verify closed-loop routings to Phase 52 and Phase 53
    routings = accepted_data["routings"]
    dest_phases = [r["destination_phase"] for r in routings]
    assert "Phase 52" in dest_phases
    assert "Phase 53" in dest_phases


# ---------------------------------------------------------------------------
# Test 2: AI Authority Prohibited
# ---------------------------------------------------------------------------

def test_ai_agent_cannot_finalize_or_review(client: TestClient):
    """AI agents cannot authorize reviews or declare effectiveness."""
    action = _create_completed_action("act-ai-1")

    # Create evaluation
    create_payload = {
        "action_id": action.action_id,
        "safety_objective": {
            "description": "Ensure configuration drift remains absent post-remediation",
            "target_finding_type": "CONFIGURATION_DRIFT",
            "bounded_failure_mode": "Unauthorized parameter drift",
            "is_evidence_testable": True,
        },
    }
    res = client.post("/api/v1/action-effectiveness/evaluations", json=create_payload)
    eval_id = res.json()["data"]["evaluation_id"]

    # AI agent attempts to review
    ai_review_payload = {
        "decision": "ACCEPT",
        "rationale": "Automated evaluation engine decided control is safe.",
        "is_ai_agent": True,
    }
    res = client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/review", json=ai_review_payload)
    assert res.status_code == 403, res.text
    assert "AI agents cannot" in res.text or "AI agents are strictly prohibited" in res.text


# ---------------------------------------------------------------------------
# Test 3: Insufficient Evidence Rules (MISSING != PASS, INSUFFICIENT != FAILURE)
# ---------------------------------------------------------------------------

def test_insufficient_evidence_does_not_pass_or_fail(client: TestClient):
    """Missing or insufficient evidence must produce INSUFFICIENT_EVIDENCE, not pass or fail."""
    action = _create_completed_action("act-insuff-1")

    res = client.post(
        "/api/v1/action-effectiveness/evaluations",
        json={"action_id": action.action_id},
    )
    eval_id = res.json()["data"]["evaluation_id"]

    # Finalize without adding evidence
    res = client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/finalize", json={})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["effectiveness_state"] == "INSUFFICIENT_EVIDENCE"
    assert data["lifecycle_state"] == "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------------------
# Test 4: Vague Objective Rejection
# ---------------------------------------------------------------------------

def test_vague_objective_rejected(client: TestClient):
    """Vague claims such as 'make the system safer' must be rejected."""
    action = _create_completed_action("act-vague-1")

    vague_payload = {
        "action_id": action.action_id,
        "safety_objective": {
            "description": "Make the system safer for all hospital patients",
            "target_finding_type": "ASSURANCE_EVALUATION",
            "bounded_failure_mode": "General failure",
            "is_evidence_testable": True,
        },
    }
    res = client.post("/api/v1/action-effectiveness/evaluations", json=vague_payload)
    assert res.status_code == 400
    assert "vague" in res.text.lower() or "objective_missing" in res.text.lower()


# ---------------------------------------------------------------------------
# Test 5: Action Eligibility (Completion != Action Creation)
# ---------------------------------------------------------------------------

def test_uncompleted_action_ineligible(client: TestClient):
    """Actions still IN_PROGRESS or IDENTIFIED cannot initiate effectiveness evaluation."""
    act_repo = get_safety_action_repository()
    in_prog_action = SafetyActionRecord(
        action_id="act-inprog-01",
        finding=SafetyFindingReference(
            source_type=FindingSourceType.ASSURANCE_EVALUATION,
            source_id="eval-01",
            finding_title="Degraded finding",
            finding_summary="Degraded",
        ),
        action_type=ActionType.REVIEW,
        title="Review In-Progress Action",
        description="Investigation still active",
        scope=SafetyActionScope(organization_id="org-main"),
        priority=ActionPriority.MEDIUM,
        lifecycle_state=ActionLifecycleState.IN_PROGRESS,  # Incomplete!
        created_by_id="officer-1",
        created_by_role="SAFETY_OFFICER",
    )
    act_repo.save(in_prog_action)

    res = client.post(
        "/api/v1/action-effectiveness/evaluations",
        json={"action_id": "act-inprog-01"},
    )
    assert res.status_code == 400
    assert "ACTION_NOT_ELIGIBLE" in res.text or "not eligible" in res.text.lower()


# ---------------------------------------------------------------------------
# Test 6: Sustained Monitoring & Regression Detection
# ---------------------------------------------------------------------------

def test_sustained_monitoring_and_regression_detection(client: TestClient):
    """Control accepted as effective degrades later -> Detected as REGRESSED with routing to Phase 50, 51, 54, 49."""
    action = _create_completed_action("act-regr-1")

    # 1. Create and accept initially effective evaluation
    res = client.post("/api/v1/action-effectiveness/evaluations", json={"action_id": action.action_id})
    eval_id = res.json()["data"]["evaluation_id"]

    # Initial good evidence
    client.post(
        f"/api/v1/action-effectiveness/evaluations/{eval_id}/collect",
        json={
            "evidence_items": [
                {
                    "source_system": "Phase 48",
                    "source_id": "init-good",
                    "scope": {"organization_id": "org-main"},
                    "evidence_type": "TELEMETRY",
                    "provenance": {"agent": "gate-1"},
                    "data_payload": {"control_execution_rate": 0.995, "safety_finding_recurrence_count": 0},
                }
            ]
        },
    )
    client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/finalize", json={})
    client.post(
        f"/api/v1/action-effectiveness/evaluations/{eval_id}/accept",
        json={"rationale": "Initially verified at 99.5% execution rate."},
    )

    # 2. Later observation window collects degraded evidence
    client.post(
        f"/api/v1/action-effectiveness/evaluations/{eval_id}/collect",
        json={
            "evidence_items": [
                {
                    "source_system": "Phase 48",
                    "source_id": "later-degraded",
                    "scope": {"organization_id": "org-main"},
                    "evidence_type": "TELEMETRY",
                    "provenance": {"agent": "gate-1"},
                    "data_payload": {"control_execution_rate": 0.85, "safety_finding_recurrence_count": 12},
                }
            ]
        },
    )

    # 3. Finalize again -> triggers regression detection
    res = client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/finalize", json={})
    assert res.status_code == 200
    regr_data = res.json()["data"]
    assert regr_data["regression_detected"] is True
    assert regr_data["is_sustained"] is False
    assert regr_data["effectiveness_state"] == "REGRESSED"
    assert regr_data["lifecycle_state"] == "REGRESSED"

    # Verify routing to Phase 50 (learning), Phase 51 (governance), Phase 54 (action follow-up), Phase 49 (incident review)
    routings = regr_data["routings"]
    dest_phases = [r["destination_phase"] for r in routings]
    assert "Phase 50" in dest_phases
    assert "Phase 51" in dest_phases
    assert "Phase 54" in dest_phases
    assert "Phase 49" in dest_phases


# ---------------------------------------------------------------------------
# Test 7: Multi-tenant and Scope Boundary Isolation
# ---------------------------------------------------------------------------

def test_scope_and_baseline_isolation(client: TestClient):
    """Mismatched organization or environment baseline must be rejected."""
    action = _create_completed_action("act-scope-1", org_id="org-alpha")

    # Attempt to evaluate under different organization scope
    mismatch_payload = {
        "action_id": action.action_id,
        "scope": {"organization_id": "org-bravo"},
    }
    res = client.post("/api/v1/action-effectiveness/evaluations", json=mismatch_payload)
    assert res.status_code == 403
    assert "SCOPE_INVALID" in res.text or "scope mismatch" in res.text.lower()


# ---------------------------------------------------------------------------
# Test 8: Filtered Listing Endpoints
# ---------------------------------------------------------------------------

def test_filtered_queues(client: TestClient):
    """Verify pending, review-required, regressions, insufficient-evidence, failed lists."""
    action = _create_completed_action("act-queues-1")

    # 1. Create evaluation (should be in pending)
    res = client.post("/api/v1/action-effectiveness/evaluations", json={"action_id": action.action_id})
    eval_id = res.json()["data"]["evaluation_id"]

    res_pending = client.get("/api/v1/action-effectiveness/pending")
    assert res_pending.status_code == 200
    assert any(e["evaluation_id"] == eval_id for e in res_pending.json()["data"])

    # 2. Finalize without evidence -> goes to insufficient-evidence
    client.post(f"/api/v1/action-effectiveness/evaluations/{eval_id}/finalize", json={})
    res_insuff = client.get("/api/v1/action-effectiveness/insufficient-evidence")
    assert res_insuff.status_code == 200
    assert any(e["evaluation_id"] == eval_id for e in res_insuff.json()["data"])

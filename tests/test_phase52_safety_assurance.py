"""Tests for Phase 52: Clinical Safety Assurance & Continuous Control Effectiveness Management."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.safety_assurance import (
    AssuranceLifecycleState,
    AssuranceReviewDecision,
    ControlCategory,
    ControlEffectivenessState,
)
from app.repositories.safety_assurance_repository import safety_assurance_repository
from app.services.safety_assurance_metrics_service import safety_assurance_metrics_service

from fastapi import Request
from app.api.deps import get_current_user
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

client = TestClient(app)


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-789"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-123"),
        facility_id=request.headers.get("X-User-Facility", "fac-456"),
    )


@pytest.fixture(autouse=True)
def reset_assurance_state():
    """Reset the in-memory assurance repository and metrics before each test."""
    safety_assurance_repository.reset()
    safety_assurance_metrics_service.reset()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    safety_assurance_repository.reset()
    safety_assurance_metrics_service.reset()


@pytest.fixture
def auth_headers():
    """Returns headers for an authenticated safety officer."""
    return {
        "Authorization": "Bearer test_token",
        "X-User-Role": "SAFETY_OFFICER",
        "X-User-Organization": "org-123",
        "X-User-Facility": "fac-456",
        "X-User-Id": "usr-789",
    }


def test_create_assurance_evaluation(auth_headers):
    """Test initiating an assurance evaluation."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=1)
    
    payload = {
        "control_id": "ctrl-med-gate-01",
        "control_version": "v1.2",
        "control_category": ControlCategory.MEDICATION_SAFETY_GATE.value,
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
        "idempotency_key": "idem-1",
        "evaluation_reason": "Routine assurance check",
    }

    response = client.post(
        "/api/v1/safety-assurance/evaluations",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["control_id"] == "ctrl-med-gate-01"
    assert data["lifecycle_state"] == AssuranceLifecycleState.SCHEDULED.value
    assert data["organization_id"] == "org-123"  # From auth context
    
    # Verify idempotency
    response2 = client.post(
        "/api/v1/safety-assurance/evaluations",
        json=payload,
        headers=auth_headers,
    )
    assert response2.status_code == 202
    assert response2.json()["data"]["evaluation_id"] == data["evaluation_id"]


def test_execute_and_review_high_risk_outcome(auth_headers):
    """Test evaluating a control with bypasses, requiring human review."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=1)
    
    # 1. Schedule
    sched_resp = client.post(
        "/api/v1/safety-assurance/evaluations",
        json={
            "control_id": "ctrl-triage-02",
            "control_version": "v2.0",
            "control_category": ControlCategory.TRIAGE_SAFETY_GATE.value,
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        },
        headers=auth_headers,
    )
    eval_id = sched_resp.json()["data"]["evaluation_id"]

    # 2. Execute (simulate bypasses detected)
    exec_resp = client.post(
        f"/api/v1/safety-assurance/evaluations/{eval_id}/execute",
        json={
            "eligible_executions": 100,
            "observed_executions": 95,
            "observed_bypasses": 5,
            "expected_behavior_met": True,
            "version_consistent": True,
            "policy_thresholds": {
                "bypass_rate_threshold": 0.01  # We have 5% bypass, so this triggers degradation
            }
        },
        headers=auth_headers,
    )
    assert exec_resp.status_code == 202
    exec_data = exec_resp.json()["data"]
    
    assert exec_data["bypass_detected"] is True
    assert exec_data["bypass_count"] == 5
    assert exec_data["effectiveness_state"] == ControlEffectivenessState.DEGRADED.value
    assert exec_data["lifecycle_state"] == AssuranceLifecycleState.REVIEW_REQUIRED.value
    assert exec_data["review_required"] is True

    # 3. Submit Review (Mark Degraded)
    rev_resp = client.post(
        f"/api/v1/safety-assurance/evaluations/{eval_id}/review",
        json={
            "evaluation_version": exec_data["version"],
            "decision": AssuranceReviewDecision.MARK_DEGRADED.value,
            "review_summary": "Bypass rate unacceptable. Control degraded.",
            "ai_material_reviewed": False,
        },
        headers=auth_headers,
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()["data"]
    assert rev_data["lifecycle_state"] == AssuranceLifecycleState.DEGRADED.value
    assert rev_data["effectiveness_state"] == ControlEffectivenessState.DEGRADED.value


def test_dashboard_summary_and_metrics(auth_headers):
    """Test dashboard aggregation and metrics endpoint."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=1)
    
    # Add an evaluation
    client.post(
        "/api/v1/safety-assurance/evaluations",
        json={
            "control_id": "ctrl-test-01",
            "control_version": "v1.0",
            "control_category": ControlCategory.HUMAN_REVIEW_REQUIREMENT.value,
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
        },
        headers=auth_headers,
    )

    dash_resp = client.get("/api/v1/safety-assurance/dashboard", headers=auth_headers)
    assert dash_resp.status_code == 200
    assert dash_resp.json()["data"]["controls_total"] == 1
    
    metrics_resp = client.get("/api/v1/safety-assurance/metrics", headers=auth_headers)
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["data"]["counters"]["assurance_evaluations_total"] == 1

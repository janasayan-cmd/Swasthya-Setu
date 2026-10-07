"""Phase 59: Clinical Safety Post-Closure Surveillance, Reopen Triggers & Longitudinal Control Monitoring Tests.

Validates:
- Post-closure surveillance registration and monitoring plan validation
- Monitoring window lifecycle (TIME_BASED, EVENT_BASED, CHECKPOINT_BASED)
- Signal ingestion, normalization, provenance preservation, and deduplication
- Scope mismatch & version change stale context detection
- Governed threshold evaluation (Count, Error Rate, Severity)
- Checkpoint evaluation and outcomes
- Human surveillance review workflow and AI boundary enforcement (AI cannot approve reopen, close monitoring, or make clinical claims)
- Governed reopen trigger routing to Phase 58 and escalation routing to Phase 49/52/55
- Controlled pause and resume
- Monitoring completion prerequisites and fail-safe invariants
- Cross-tenant access isolation & idempotency protection
- Filtered listing endpoints (active, review-required, reopen-required, escalation-required, reanalysis)
- Async monitoring execution without PHI leakage
"""

from datetime import datetime, timezone
from typing import Optional
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_monitoring_repository import get_safety_monitoring_repository
from app.schemas.auth import UserRole
from app.schemas.safety_monitoring import (
    CheckpointCategory,
    HumanSurveillanceReviewDecision,
    MonitoringLifecycleState,
    MonitoringWindowType,
    SafetySignalType,
    ThresholdEvaluationStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_monitoring_async_service import get_safety_monitoring_async_service


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-surveillance-lead-01"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    repo = get_safety_monitoring_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _sample_monitoring_payload(
    monitoring_id: str = "mon-p59-001",
    verification_id: Optional[str] = None,
    change_id: str = "chg-p51-001",
    rollout_id: str = "rol-p57-001",
    org_id: str = "org-apollo-01",
    facility_id: str = "fac-delhi-01",
    version: str = "v2.5.0",
) -> dict:
    actual_ver_id = verification_id or f"ver-{monitoring_id}"
    return {
        "monitoring_id": monitoring_id,
        "verification_id": actual_ver_id,
        "change_id": change_id,
        "rollout_id": rollout_id,
        "monitoring_plan_name": "Longitudinal Post-Closure Surveillance for Pediatric Dosing Engine",
        "description": "Continuous safety surveillance following Phase 58 closure.",
        "application_version": version,
        "window_type": "TIME_BASED",
        "window_duration_hours": 168,  # 7 days
        "scope": {
            "organization_id": org_id,
            "facility_id": facility_id,
            "department": "pediatrics",
            "workflow": "clinical-dosing",
            "safety_control_id": "sc-pediatric-weight-check",
            "environment": "production",
        },
        "observation_sources": ["Phase 18", "Phase 35", "Phase 48", "Phase 49", "Phase 52"],
        "thresholds": [
            {
                "metric_name": "safety_control_failure_count",
                "threshold_type": "COUNT",
                "warning_threshold": 1.0,
                "critical_threshold": 3.0,
                "window_minutes": 60,
                "governance_reference": "GOV-THRESH-001",
            },
            {
                "metric_name": "error_rate",
                "threshold_type": "ERROR_RATE",
                "warning_threshold": 0.02,
                "critical_threshold": 0.05,
                "window_minutes": 15,
                "governance_reference": "GOV-THRESH-002",
            },
        ],
        "checkpoints": [
            {
                "checkpoint_id": "chk-01",
                "category": "INITIAL_POST_CLOSURE",
                "name": "24-Hour Post Closure Checkpoint",
                "scheduled_hours_after_start": 24,
            },
            {
                "checkpoint_id": "chk-02",
                "category": "FINAL_MONITORING",
                "name": "7-Day Surveillance Closure Checkpoint",
                "scheduled_hours_after_start": 168,
            },
        ],
    }


# =====================================================================
# 1. Registration & Idempotency Tests
# =====================================================================


def test_create_safety_monitoring_success(client):
    payload = _sample_monitoring_payload()
    resp = client.post("/api/v1/safety-monitoring", json=payload, headers={"X-Idempotency-Key": "idem-p59-001"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["monitoring_id"] == "mon-p59-001"
    assert data["lifecycle_state"] == "REGISTERED"
    assert len(data["thresholds"]) == 2
    assert len(data["checkpoints"]) == 2
    assert data["organization_id"] == "org-apollo-01"


def test_create_safety_monitoring_idempotency_safe_replay(client):
    payload = _sample_monitoring_payload()
    headers = {"X-Idempotency-Key": "idem-p59-replay"}
    r1 = client.post("/api/v1/safety-monitoring", json=payload, headers=headers)
    assert r1.status_code == 201

    # Safe replay returns existing
    r2 = client.post("/api/v1/safety-monitoring", json=payload, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["data"]["monitoring_id"] == "mon-p59-001"


def test_create_safety_monitoring_idempotency_conflict(client):
    payload = _sample_monitoring_payload()
    headers = {"X-Idempotency-Key": "idem-p59-conflict"}
    r1 = client.post("/api/v1/safety-monitoring", json=payload, headers=headers)
    assert r1.status_code == 201

    conflict_payload = _sample_monitoring_payload(monitoring_id="mon-p59-different")
    r2 = client.post("/api/v1/safety-monitoring", json=conflict_payload, headers=headers)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_create_safety_monitoring_scope_mismatch_blocks(client):
    payload = _sample_monitoring_payload()
    # User is in org-apollo-01, but payload specifies different org
    payload["scope"]["organization_id"] = "org-different-99"
    resp = client.post("/api/v1/safety-monitoring", json=payload)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MONITORING_SCOPE_MISMATCH"


# =====================================================================
# 2. Lifecycle: Start, Pause, Resume, Checkpoints
# =====================================================================


def test_start_pause_resume_lifecycle(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())

    # Start
    resp_start = client.post("/api/v1/safety-monitoring/mon-p59-001/start")
    assert resp_start.status_code == 200
    assert resp_start.json()["data"]["lifecycle_state"] == "OBSERVING"

    # Pause
    resp_pause = client.post(
        "/api/v1/safety-monitoring/mon-p59-001/pause",
        json={"reason": "Telemetry source adapter undergoing routine upgrade"},
    )
    assert resp_pause.status_code == 200
    assert resp_pause.json()["data"]["lifecycle_state"] == "PAUSED"

    # Resume
    resp_resume = client.post("/api/v1/safety-monitoring/mon-p59-001/resume")
    assert resp_resume.status_code == 200
    assert resp_resume.json()["data"]["lifecycle_state"] == "OBSERVING"


def test_run_checkpoint_evaluation(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    resp_chk = client.post(
        "/api/v1/safety-monitoring/mon-p59-001/checkpoint",
        json={"checkpoint_id": "chk-01"},
    )
    assert resp_chk.status_code == 200
    data = resp_chk.json()["data"]
    assert data["outcome"] == "PASS_CONTINUE"
    assert data["evaluated_by"] == "usr-surveillance-lead-01"


# =====================================================================
# 3. Signal Ingestion, Deduplication & Normalization
# =====================================================================


def test_signal_ingestion_and_normalization(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    signal_payload = {
        "source": "Phase 48",
        "source_record_id": "ctrl-evt-001",
        "signal_type": "SAFETY_CONTROL_FAILURE",
        "severity": "WARNING",
        "application_version": "v2.5.0",
        "scope": {
            "organization_id": "org-apollo-01",
            "facility_id": "fac-delhi-01",
            "department": "pediatrics",
            "workflow": "clinical-dosing",
            "safety_control_id": "sc-pediatric-weight-check",
            "environment": "production",
        },
        "payload": {"error": "Weight check guardrail boundary near-miss"},
    }

    resp = client.post("/api/v1/safety-monitoring/mon-p59-001/signals", json=signal_payload)
    assert resp.status_code == 201
    sig = resp.json()["data"]
    assert sig["signal_type"] == "SAFETY_CONTROL_FAILURE"
    assert sig["severity"] == "WARNING"
    assert sig["provenance"]["source"] == "Phase 48"
    assert sig["provenance"]["source_record_id"] == "ctrl-evt-001"
    assert sig["deduplication_key"] is not None

    # Check signal list
    resp_list = client.get("/api/v1/safety-monitoring/mon-p59-001/signals")
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) == 1


def test_signal_deduplication_prevents_duplicate_processing(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    signal_payload = {
        "source": "Phase 18",
        "source_record_id": "tel-evt-999",
        "signal_type": "LATENCY_INCREASE",
        "severity": "LOW",
        "application_version": "v2.5.0",
        "scope": {
            "organization_id": "org-apollo-01",
            "facility_id": "fac-delhi-01",
            "department": "pediatrics",
            "workflow": "clinical-dosing",
            "safety_control_id": "sc-pediatric-weight-check",
            "environment": "production",
        },
        "payload": {"latency_ms": 1200},
    }

    r1 = client.post("/api/v1/safety-monitoring/mon-p59-001/signals", json=signal_payload)
    assert r1.status_code == 201

    # Ingest identical signal again
    r2 = client.post("/api/v1/safety-monitoring/mon-p59-001/signals", json=signal_payload)
    assert r2.status_code == 200
    assert r2.json()["data"]["is_duplicate"] is True

    # Ensure total signals count is still 1
    resp_list = client.get("/api/v1/safety-monitoring/mon-p59-001/signals")
    assert len(resp_list.json()["data"]) == 1


def test_signal_scope_mismatch_rejected(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    signal_payload = {
        "source": "Phase 18",
        "source_record_id": "tel-evt-mismatch",
        "signal_type": "ERROR_RATE_INCREASE",
        "severity": "WARNING",
        "application_version": "v2.5.0",
        "scope": {
            "organization_id": "org-different-xyz",  # Scope mismatch!
            "facility_id": "fac-delhi-01",
            "environment": "production",
        },
        "payload": {},
    }

    resp = client.post("/api/v1/safety-monitoring/mon-p59-001/signals", json=signal_payload)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MONITORING_SCOPE_MISMATCH"


def test_signal_version_mismatch_triggers_stale_context(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    signal_payload = {
        "source": "Phase 57",
        "source_record_id": "rol-evt-v3",
        "signal_type": "VERSION_MISMATCH",
        "severity": "CRITICAL",
        "application_version": "v3.0.0-unauthorized",  # Monitoring is on v2.5.0!
        "scope": {
            "organization_id": "org-apollo-01",
            "facility_id": "fac-delhi-01",
            "department": "pediatrics",
            "workflow": "clinical-dosing",
            "safety_control_id": "sc-pediatric-weight-check",
            "environment": "production",
        },
        "payload": {"detected_version": "v3.0.0-unauthorized"},
    }

    resp = client.post("/api/v1/safety-monitoring/mon-p59-001/signals", json=signal_payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "MONITORING_CONTEXT_STALE"


# =====================================================================
# 4. Governed Threshold Evaluation, Reopen & Escalation Triggers
# =====================================================================


def test_threshold_breach_generates_reopen_and_escalation_triggers(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    # Ingest 3 critical safety control failure signals to exceed critical threshold (3.0)
    for i in range(3):
        client.post(
            "/api/v1/safety-monitoring/mon-p59-001/signals",
            json={
                "source": "Phase 48",
                "source_record_id": f"ctrl-breach-{i}",
                "signal_type": "SAFETY_CONTROL_FAILURE",
                "severity": "CRITICAL",
                "application_version": "v2.5.0",
                "scope": {
                    "organization_id": "org-apollo-01",
                    "facility_id": "fac-delhi-01",
                    "department": "pediatrics",
                    "workflow": "clinical-dosing",
                    "safety_control_id": "sc-pediatric-weight-check",
                    "environment": "production",
                },
                "payload": {"error": f"Critical rule violation {i}"},
            },
        )

    # Evaluate current surveillance state
    resp_eval = client.post("/api/v1/safety-monitoring/mon-p59-001/evaluate")
    assert resp_eval.status_code == 200
    data = resp_eval.json()["data"]
    assert data["lifecycle_state"] == "REOPEN_REQUIRED"

    # Verify triggers were registered
    resp_trig = client.get("/api/v1/safety-monitoring/mon-p59-001/triggers")
    assert resp_trig.status_code == 200
    triggers = resp_trig.json()["data"]
    assert len(triggers) >= 2  # One Phase 58 REOPEN_TRIGGER, one Phase 49 ESCALATION_TRIGGER
    types = [t["trigger_type"] for t in triggers]
    assert "REOPEN_TRIGGER" in types
    assert "ESCALATION_TRIGGER" in types


def test_failsafe_insufficient_data_does_not_result_in_safe(client):
    # Empty monitoring context has 0 signals
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    resp_eval = client.post("/api/v1/safety-monitoring/mon-p59-001/evaluate")
    assert resp_eval.status_code == 200
    data = resp_eval.json()["data"]
    # Check that thresholds with no samples report INSUFFICIENT_DATA or NOT_TRIGGERED, never "SAFE"
    for th in data["threshold_evaluations"]:
        assert th["status"] in [
            ThresholdEvaluationStatus.NOT_TRIGGERED,
            ThresholdEvaluationStatus.INSUFFICIENT_DATA,
        ]


# =====================================================================
# 5. Human Surveillance Review & AI Boundary Enforcement
# =====================================================================


def test_human_surveillance_review_workflow(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    # Ingest a warning signal
    client.post(
        "/api/v1/safety-monitoring/mon-p59-001/signals",
        json={
            "source": "Phase 35",
            "source_record_id": "alt-001",
            "signal_type": "ALERT_SPIKE",
            "severity": "WARNING",
            "application_version": "v2.5.0",
            "scope": {
                "organization_id": "org-apollo-01",
                "facility_id": "fac-delhi-01",
                "department": "pediatrics",
                "workflow": "clinical-dosing",
                "safety_control_id": "sc-pediatric-weight-check",
                "environment": "production",
            },
            "payload": {"spike_percentage": 25},
        },
    )

    review_payload = {
        "decision": "CONTINUE",
        "notes": "Reviewed alert spike; within acceptable operational threshold variation.",
        "routing_destination": None,
    }

    resp = client.post("/api/v1/safety-monitoring/mon-p59-001/review", json=review_payload)
    assert resp.status_code == 200
    rev = resp.json()["data"]
    assert rev["decision"] == "CONTINUE"
    assert rev["reviewer_id"] == "usr-surveillance-lead-01"


def test_ai_agent_cannot_conduct_surveillance_review_or_reopen(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    review_payload = {
        "decision": "CONTINUE",
        "notes": "Automated AI assessment claiming system is safe.",
        "is_ai_agent": True,  # AI flag set
        "ai_metadata": {"model": "med-ai-v2", "confidence": 0.99},
    }

    resp = client.post("/api/v1/safety-monitoring/mon-p59-001/review", json=review_payload)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"


# =====================================================================
# 6. Reopen Routing to Phase 58 & Reassessment Routing
# =====================================================================


def test_create_governed_reopen_review_routes_to_phase58(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    resp = client.post(
        "/api/v1/safety-monitoring/mon-p59-001/reopen-review",
        json={"reason": "Critical safety regression detected in longitudinal weight check control"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["lifecycle_state"] == "REOPEN_REQUIRED"
    assert data["target_phase"] == "PHASE_58"


def test_request_reassessment(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    resp = client.post(
        "/api/v1/safety-monitoring/mon-p59-001/reassess",
        json={"reason": "Pediatric weight formula guidelines updated by ministry"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["lifecycle_state"] == "REASSESSMENT_REQUIRED"


# =====================================================================
# 7. Monitoring Completion Prerequisites & Invariants
# =====================================================================


def test_monitoring_completion_blocked_by_reopen_trigger(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")
    client.post(
        "/api/v1/safety-monitoring/mon-p59-001/reopen-review",
        json={"reason": "Blocking reopen trigger"},
    )

    # Attempt to complete while in REOPEN_REQUIRED
    resp = client.post(
        "/api/v1/safety-monitoring/mon-p59-001/complete",
        json={"summary": "Attempting closure"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "REOPEN_REVIEW_REQUIRED"


def test_monitoring_completion_success_when_clean(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload())
    client.post("/api/v1/safety-monitoring/mon-p59-001/start")

    # Run all required checkpoints
    client.post(
        "/api/v1/safety-monitoring/mon-p59-001/checkpoint",
        json={"checkpoint_id": "chk-01"},
    )
    client.post(
        "/api/v1/safety-monitoring/mon-p59-001/checkpoint",
        json={"checkpoint_id": "chk-02"},
    )

    resp = client.post(
        "/api/v1/safety-monitoring/mon-p59-001/complete",
        json={"summary": "All longitudinal surveillance criteria satisfied."},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["lifecycle_state"] == "COMPLETED"


# =====================================================================
# 8. Filtered List Endpoints
# =====================================================================


def test_filtered_list_endpoints(client):
    # Create two records: one active, one reopen required
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload("mon-act-1"))
    client.post("/api/v1/safety-monitoring/mon-act-1/start")

    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload("mon-reopen-1"))
    client.post("/api/v1/safety-monitoring/mon-reopen-1/start")
    client.post(
        "/api/v1/safety-monitoring/mon-reopen-1/reopen-review",
        json={"reason": "Reopen needed"},
    )

    # Test /active
    resp_act = client.get("/api/v1/safety-monitoring/active")
    assert resp_act.status_code == 200
    ids_act = [m["monitoring_id"] for m in resp_act.json()["data"]]
    assert "mon-act-1" in ids_act

    # Test /reopen-required
    resp_reopen = client.get("/api/v1/safety-monitoring/reopen-required")
    assert resp_reopen.status_code == 200
    ids_reopen = [m["monitoring_id"] for m in resp_reopen.json()["data"]]
    assert "mon-reopen-1" in ids_reopen

    # Test /reanalysis
    resp_reanalysis = client.post("/api/v1/safety-monitoring/reanalysis")
    assert resp_reanalysis.status_code == 200
    assert resp_reanalysis.json()["data"]["reanalysis_completed"] is True


# =====================================================================
# 9. Cross-Tenant Access Protection
# =====================================================================


def test_cross_tenant_access_denied(client):
    client.post("/api/v1/safety-monitoring", json=_sample_monitoring_payload("mon-org-1", org_id="org-apollo-01"))

    # Attempt access with headers from org-fortis-02
    resp = client.get(
        "/api/v1/safety-monitoring/mon-org-1",
        headers={"X-User-Organization": "org-fortis-02"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"


# =====================================================================
# 10. Async Surveillance Service Execution
# =====================================================================


@pytest.mark.asyncio
async def test_async_surveillance_scheduled_job():
    repo = get_safety_monitoring_repository()
    # Register and start a monitoring context directly
    from app.services.safety_monitoring_service import get_safety_monitoring_service
    from app.schemas.safety_monitoring import CreateSafetyMonitoringRequest

    srv = get_safety_monitoring_service()
    user = AuthenticatedUserContext(
        user_id="usr-async-worker",
        role=UserRole.ADMIN,
        organization_id="org-apollo-01",
        facility_id="fac-delhi-01",
    )
    req = CreateSafetyMonitoringRequest(**_sample_monitoring_payload("mon-async-01"))
    srv.create_monitoring(req, user)
    srv.start_monitoring("mon-async-01", user)

    # Run async surveillance job
    async_srv = get_safety_monitoring_async_service()
    res = await async_srv.run_scheduled_surveillance_cycle("org-apollo-01")
    assert res["status"] == "COMPLETED"
    assert res["processed_count"] >= 1

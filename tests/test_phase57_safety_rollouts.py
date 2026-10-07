"""Phase 57: Clinical Safety Change Validation, Controlled Rollout Governance & Post-Deployment Verification Tests.

Validates:
- Pre-implementation readiness validation & failure-safe gates (TRD Section 7, 53)
- Version alignment between approval and target deployment (TRD Section 9)
- Dependency health verification (TRD Section 10)
- Controlled stage progression: PREPARATION -> CANARY -> LIMITED -> EXPANDED -> FULL (TRD Section 12)
- Checkpoint completion enforcement before stage promotion (TRD Section 12, 14)
- AI boundary constraints (AI cannot authorize, expand, or promote rollouts) (TRD Section 31)
- Pause and resumption workflow (TRD Section 17)
- Rollback execution, post-rollback verification, and reopening (TRD Section 18, 19, 20)
- Closed-loop routing to Phase 52 assurance, Phase 55 effectiveness, Phase 56 feedback, Phase 48 safety (TRD Section 25, 26, 27, 29)
- Cross-tenant access isolation & idempotency protection (TRD Section 32, 35)
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_rollout_repository import get_safety_rollout_repository
from app.schemas.auth import UserRole
from app.schemas.safety_rollout import (
    ApprovalStatus,
    ApprovalVerificationRecord,
    CheckpointStatus,
    DependencyStatus,
    RolloutDependency,
    RolloutLifecycleState,
    RolloutScope,
    RolloutStage,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-safety-officer-57"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    repo = get_safety_rollout_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _sample_rollout_payload(
    change_id: str = "chg-test-57-01",
    approved_ver: str = "v2.4.0",
    target_ver: str = "v2.4.0",
    org_id: str = "org-apollo-01",
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED,
    is_valid_approval: bool = True,
    expires_in_days: int = 30,
    dep_status: DependencyStatus = DependencyStatus.AVAILABLE,
    idempotency_key: str = None,
):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=expires_in_days) if expires_in_days else None

    return {
        "change_id": change_id,
        "change_proposal_id": "prop-56-001",
        "scope": {
            "environment": "production",
            "organization_id": org_id,
            "facility_id": "fac-delhi-01",
            "department_id": "dep-icu-01",
            "target_workflows": ["wf-prescribe-medication"],
            "target_controls": ["ctrl-renal-dose-gate"],
        },
        "approved_version": approved_ver,
        "target_version": target_ver,
        "approval": {
            "approver_id": "usr-governance-lead",
            "approver_role": "CLINICAL_SAFETY_OFFICER",
            "approval_status": approval_status.value,
            "change_version": approved_ver,
            "approved_at": now.isoformat(),
            "expires_at": expires.isoformat() if expires else None,
            "is_valid": is_valid_approval,
        },
        "dependencies": [
            {
                "name": "clinical-rules-db",
                "dependency_type": "DATABASE",
                "required_version": "v1.8.0",
                "current_version": "v1.8.0",
                "status": dep_status.value,
            }
        ],
        "rollback_plan": "Revert to safe container image v2.3.9 and restore ruleset replica",
        "validation_plan": "Monitor canary telemetry, execute test patient order sets, verify Phase 48 intercept",
        "observation_plan": "Observe next 500 clinical orders or 24 hours with zero safety-gate bypasses",
        "idempotency_key": idempotency_key,
    }


# ===========================================================================
# 1. Creation & Idempotency Tests
# ===========================================================================


def test_create_rollout_success(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["change_id"] == "chg-test-57-01"
    assert data["current_stage"] == "PREPARATION"
    assert data["lifecycle_state"] in ("READY", "READINESS_CHECK")
    assert len(data["checkpoints"]) >= 2
    assert len(data["history"]) >= 1


def test_create_rollout_idempotency_replay_and_conflict(client):
    payload = _sample_rollout_payload(idempotency_key="idemp-key-57-001")
    resp1 = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp1.status_code == 201
    first_id = resp1.json()["data"]["rollout_id"]

    # Safe replay
    resp2 = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["data"]["rollout_id"] == first_id

    # Conflict with modified payload
    conflict_payload = dict(payload)
    conflict_payload["target_version"] = "v2.4.1"
    resp3 = client.post("/api/v1/safety-rollouts", json=conflict_payload)
    assert resp3.status_code == 409
    assert resp3.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_duplicate_active_rollout_conflict(client):
    payload = _sample_rollout_payload(change_id="chg-duplicate-test")
    resp1 = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "CONCURRENCY_CONFLICT"


# ===========================================================================
# 2. Readiness & Failure-Safe Rules (TRD Section 7, 53)
# ===========================================================================


def test_readiness_failure_on_expired_approval(client):
    # Expired 5 days ago
    payload = _sample_rollout_payload(expires_in_days=-5)
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp.status_code == 201
    rollout_id = resp.json()["data"]["rollout_id"]

    # Validate readiness
    read_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}/readiness")
    assert read_resp.status_code == 200
    rdata = read_resp.json()["data"]
    assert rdata["is_ready"] is False
    assert rdata["approval_valid"] is False
    assert any("expired" in b.lower() for b in rdata["blockers"])

    # Attempting to start rollout must fail
    start_resp = client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 5})
    assert start_resp.status_code == 400
    assert start_resp.json()["error"]["code"] == "READINESS_FAILED"


def test_readiness_failure_on_version_mismatch(client):
    payload = _sample_rollout_payload(approved_ver="v2.4.0", target_ver="v2.5.0")
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp.status_code == 201
    rollout_id = resp.json()["data"]["rollout_id"]

    read_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}/readiness")
    rdata = read_resp.json()["data"]
    assert rdata["is_ready"] is False
    assert rdata["version_matched"] is False
    assert any("version mismatch" in b.lower() for b in rdata["blockers"])


def test_readiness_failure_on_unknown_or_unavailable_dependency(client):
    # TRD Section 53: UNKNOWN != PASS
    payload = _sample_rollout_payload(dep_status=DependencyStatus.UNKNOWN)
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    assert resp.status_code == 201
    rollout_id = resp.json()["data"]["rollout_id"]

    read_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}/readiness")
    rdata = read_resp.json()["data"]
    assert rdata["is_ready"] is False
    assert rdata["dependencies_satisfied"] is False


# ===========================================================================
# 3. Controlled Stage Progression & Checkpoints (TRD Section 12, 13, 14)
# ===========================================================================


def test_start_rollout_and_enter_canary(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]

    start_resp = client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 10})
    assert start_resp.status_code == 200
    sdata = start_resp.json()["data"]
    assert sdata["current_stage"] == "CANARY"
    assert sdata["lifecycle_state"] == "CANARY"
    # Controls verified & Phase 48 notified
    assert len(sdata["safety_controls_verified"]) >= 1
    assert any(r["destination_phase"] == "Phase 48" for r in sdata["routings"])


def test_stage_advancement_requires_checkpoint_completion(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]
    client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 5})

    # Try advancing CANARY -> LIMITED without validating checkpoints
    advance_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/advance",
        json={"target_stage": "LIMITED", "rationale": "Canary deployed, want to proceed", "is_ai_agent": False},
    )
    assert advance_resp.status_code == 400
    assert advance_resp.json()["error"]["code"] == "VALIDATION_FAILED"


def test_stage_advancement_denied_for_ai_boundary(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]
    client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 5})

    # AI system attempting to promote rollout
    advance_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/advance",
        json={"target_stage": "LIMITED", "rationale": "AI model recommended expansion", "is_ai_agent": True},
    )
    assert advance_resp.status_code == 400
    assert advance_resp.json()["error"]["code"] == "STAGE_ADVANCEMENT_DENIED"


def test_stage_advancement_cannot_skip_stages(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]
    client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 5})

    # Try advancing CANARY directly to FULL
    advance_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/advance",
        json={"target_stage": "FULL", "rationale": "Attempting to skip to full rollout", "is_ai_agent": False},
    )
    assert advance_resp.status_code == 400
    assert advance_resp.json()["error"]["code"] == "STAGE_ADVANCEMENT_DENIED"


# ===========================================================================
# 4. End-to-End Progression to Completion & Cross-Phase Routing
# ===========================================================================


def test_full_controlled_progression_and_completion(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]

    # 1. Start CANARY
    client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 5})

    # Validate CANARY checkpoints
    chk_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}/checkpoints")
    for cp in chk_resp.json()["data"]["checkpoints"]:
        if cp["stage"] == "CANARY":
            client.post(
                f"/api/v1/safety-rollouts/{rollout_id}/validate-stage",
                json={
                    "checkpoint_id": cp["checkpoint_id"],
                    "observed_state": "VERIFIED_OK",
                    "status": "PASSED",
                    "evidence_notes": "Nominal canary telemetry verified",
                },
            )

    # 2. Advance CANARY -> LIMITED
    adv1 = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/advance",
        json={"target_stage": "LIMITED", "rationale": "Canary checkpoints fully passed", "is_ai_agent": False},
    )
    assert adv1.status_code == 200
    assert adv1.json()["data"]["current_stage"] == "LIMITED"

    # Validate LIMITED checkpoints
    chk_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}/checkpoints")
    for cp in chk_resp.json()["data"]["checkpoints"]:
        if cp["stage"] == "LIMITED":
            client.post(
                f"/api/v1/safety-rollouts/{rollout_id}/validate-stage",
                json={
                    "checkpoint_id": cp["checkpoint_id"],
                    "observed_state": "FACILITY_STABLE",
                    "status": "PASSED",
                },
            )

    # 3. Advance LIMITED -> EXPANDED
    adv2 = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/advance",
        json={"target_stage": "EXPANDED", "rationale": "Limited facility verified", "is_ai_agent": False},
    )
    assert adv2.status_code == 200

    # Validate EXPANDED checkpoints
    chk_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}/checkpoints")
    for cp in chk_resp.json()["data"]["checkpoints"]:
        if cp["stage"] == "EXPANDED":
            client.post(
                f"/api/v1/safety-rollouts/{rollout_id}/validate-stage",
                json={
                    "checkpoint_id": cp["checkpoint_id"],
                    "observed_state": "MULTI_FACILITY_NOMINAL",
                    "status": "PASSED",
                },
            )

    # 4. Advance EXPANDED -> FULL
    adv3 = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/advance",
        json={"target_stage": "FULL", "rationale": "Expanded multi-facility passed", "is_ai_agent": False},
    )
    assert adv3.status_code == 200
    assert adv3.json()["data"]["current_stage"] == "FULL"

    # Validate FULL stage checkpoints
    chk_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}/checkpoints")
    for cp in chk_resp.json()["data"]["checkpoints"]:
        if cp["stage"] == "FULL":
            client.post(
                f"/api/v1/safety-rollouts/{rollout_id}/validate-stage",
                json={
                    "checkpoint_id": cp["checkpoint_id"],
                    "observed_state": "FULL_SCOPE_HEALTHY",
                    "status": "PASSED",
                },
            )

    # 5. Complete rollout with post-deployment observation evidence
    comp_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/complete",
        json={
            "observation_evidence_id": "obs-evi-full-001",
            "rationale": "Observed 500 orders over 24h with zero safety gates bypassed",
        },
    )
    assert comp_resp.status_code == 200
    cdata = comp_resp.json()["data"]
    assert cdata["lifecycle_state"] == "COMPLETED"
    assert cdata["completed_at"] is not None

    # Verify downstream routing to Phase 52 (Assurance) and Phase 55 (Effectiveness)
    destinations = [r["destination_phase"] for r in cdata["routings"]]
    assert "Phase 52" in destinations
    assert "Phase 55" in destinations


# ===========================================================================
# 5. Pause, Resume & Rollback Tests
# ===========================================================================


def test_pause_and_resume_rollout(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]
    client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 5})

    # Pause
    pause_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/pause",
        json={"reason": "Suspicious latency spike observed in ICU drug orders"},
    )
    assert pause_resp.status_code == 200
    pdata = pause_resp.json()["data"]
    assert pdata["is_paused"] is True
    assert pdata["lifecycle_state"] == "PAUSED"

    # Stage advance while paused must be rejected
    adv_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/advance",
        json={"target_stage": "LIMITED", "rationale": "Trying to advance while paused", "is_ai_agent": False},
    )
    assert adv_resp.status_code == 400
    assert adv_resp.json()["error"]["code"] == "ROLLOUT_PAUSED"

    # Resume
    resume_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/resume",
        json={"rationale": "ICU latency identified as network switch maintenance, resolved"},
    )
    assert resume_resp.status_code == 200
    rdata = resume_resp.json()["data"]
    assert rdata["is_paused"] is False
    assert rdata["lifecycle_state"] == "CANARY"


def test_rollback_and_post_rollback_validation(client):
    payload = _sample_rollout_payload()
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]
    client.post(f"/api/v1/safety-rollouts/{rollout_id}/start", json={"canary_scope_percentage": 5})

    # Initiate rollback
    rb_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/rollback",
        json={"reason": "Unacceptable dosage calculation discrepancy detected", "target_version": "v2.3.9"},
    )
    assert rb_resp.status_code == 200
    rb_data = rb_resp.json()["data"]
    assert rb_data["is_rolled_back"] is True
    assert rb_data["lifecycle_state"] == "ROLLING_BACK"

    # Routing to Phase 51 Governance & Phase 56 Improvement Feedback
    destinations = [r["destination_phase"] for r in rb_data["routings"]]
    assert "Phase 51" in destinations
    assert "Phase 56" in destinations

    # Validate rollback with failed safety controls -> must reject
    fail_val = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/validate-rollback",
        json={"verified_version": "v2.3.9", "safety_controls_intact": False},
    )
    assert fail_val.status_code == 400
    assert fail_val.json()["error"]["code"] == "ROLLBACK_VALIDATION_FAILED"

    # Validate rollback with intact controls -> must succeed
    succ_val = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/validate-rollback",
        json={"verified_version": "v2.3.9", "safety_controls_intact": True, "evidence_notes": "Replica healthy"},
    )
    assert succ_val.status_code == 200
    assert succ_val.json()["data"]["lifecycle_state"] == "ROLLED_BACK"

    # Reopen rolled-back rollout
    reopen_resp = client.post(
        f"/api/v1/safety-rollouts/{rollout_id}/reopen",
        json={"reason": "Reopening for corrective action investigation and root cause review"},
    )
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["data"]["lifecycle_state"] == "REASSESSMENT_REQUIRED"
    assert reopen_resp.json()["data"]["reopened_count"] == 1


# ===========================================================================
# 6. Listing Filters, Multi-Tenant & Reanalysis (TRD Section 32, 37)
# ===========================================================================


def test_listing_filters_and_reanalysis(client):
    p1 = _sample_rollout_payload(change_id="chg-list-01")
    resp1 = client.post("/api/v1/safety-rollouts", json=p1)
    rid1 = resp1.json()["data"]["rollout_id"]

    p2 = _sample_rollout_payload(change_id="chg-list-02")
    resp2 = client.post("/api/v1/safety-rollouts", json=p2)
    rid2 = resp2.json()["data"]["rollout_id"]

    client.post(f"/api/v1/safety-rollouts/{rid1}/start", json={"canary_scope_percentage": 5})
    client.post(f"/api/v1/safety-rollouts/{rid2}/pause", json={"reason": "Paused for routine hold testing"})

    # Check /pending
    pend = client.get("/api/v1/safety-rollouts/pending")
    assert pend.status_code == 200
    assert len(pend.json()["data"]) >= 1

    # Check /paused
    paused = client.get("/api/v1/safety-rollouts/paused")
    assert paused.status_code == 200
    assert any(r["rollout_id"] == rid2 for r in paused.json()["data"])

    # Check /active
    active = client.get("/api/v1/safety-rollouts/active")
    assert active.status_code == 200
    assert any(r["rollout_id"] == rid1 for r in active.json()["data"])

    # Reanalysis
    reanalysis = client.post(
        "/api/v1/safety-rollouts/reanalysis",
        json={"rollout_ids": [rid1, rid2], "reason": "Periodic governance health audit"},
    )
    assert reanalysis.status_code == 200
    assert len(reanalysis.json()["data"]) == 2


def test_cross_tenant_access_denied(client):
    payload = _sample_rollout_payload(org_id="org-other-hospital")
    resp = client.post("/api/v1/safety-rollouts", json=payload)
    rollout_id = resp.json()["data"]["rollout_id"]

    # Non-admin user from org-apollo-01 attempting to access org-other-hospital
    def mock_other_tenant(request: Request) -> AuthenticatedUserContext:
        return AuthenticatedUserContext(
            user_id="usr-doctor-delhi",
            role=UserRole.DOCTOR,
            organization_id="org-apollo-01",
        )

    app.dependency_overrides[get_current_user] = mock_other_tenant
    get_resp = client.get(f"/api/v1/safety-rollouts/{rollout_id}")
    assert get_resp.status_code == 403
    assert get_resp.json()["error"]["code"] == "ACCESS_DENIED"

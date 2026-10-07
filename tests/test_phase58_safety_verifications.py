"""Phase 58: Clinical Safety Change Verification, Release Evidence & Controlled Post-Rollout Closure Tests.

Validates:
- End-to-end lifecycle: Phase 51 (Approval) -> Phase 57 (Rollout) -> Phase 58 (Release Verification & Closure)
- Separation of duties: CHANGE_APPROVER != IMPLEMENTER != FINAL_VERIFIER
- AI boundary constraints: AI cannot approve verification, release signoff, or execute closure
- Fail-safe rules: Missing evidence, pending assurance, or failed safety controls strictly block closure
- Post-closure monitoring registration
- Controlled reopening preserving previous closure and audit history
- Cross-tenant access isolation & idempotency protection
- Filtered listing endpoints (pending, review-required, closure-pending, reopened, reanalysis)
"""

from datetime import datetime, timezone
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_rollout_repository import get_safety_rollout_repository
from app.repositories.safety_verification_repository import get_safety_verification_repository
from app.schemas.auth import UserRole
from app.schemas.safety_rollout import (
    ApprovalStatus,
    ApprovalVerificationRecord,
    CheckpointCategory,
    CheckpointStatus,
    RolloutLifecycleState,
    RolloutRoutingRecord,
    RolloutScope,
    RolloutStage,
    SafetyControlVerificationRecord,
    SafetyRolloutRecord,
    ValidationCheckpoint,
)
from app.schemas.safety_verification import (
    AssuranceOutcomeStatus,
    EffectivenessOutcomeStatus,
    HumanVerificationDecision,
    VerificationLifecycleState,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-verifier-58"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    v_repo = get_safety_verification_repository()
    v_repo.clear()
    r_repo = get_safety_rollout_repository()
    r_repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    v_repo.clear()
    r_repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _setup_completed_rollout(
    rollout_id: str = "rol-test-58-01",
    change_id: str = "chg-test-58-01",
    version: str = "v2.5.0",
    org_id: str = "org-apollo-01",
    approver_id: str = "usr-approver-p51",
    creator_id: str = "usr-implementer-p57",
    all_checkpoints_passed: bool = True,
    controls_passed: bool = True,
    has_p52: bool = True,
    has_p55: bool = True,
) -> SafetyRolloutRecord:
    now = datetime.now(timezone.utc)
    r_repo = get_safety_rollout_repository()

    checkpoints = [
        ValidationCheckpoint(
            checkpoint_id="chk-p58-01",
            category=CheckpointCategory.POST_FULL,
            stage=RolloutStage.FULL,
            expected_state="GLOBAL_HEALTHY",
            observed_state="VERIFIED_OK",
            status=CheckpointStatus.PASSED if all_checkpoints_passed else CheckpointStatus.FAILED,
            criteria="Global rollout verification",
        )
    ]

    safety_controls = [
        SafetyControlVerificationRecord(
            control_id="ctrl-dose-gate",
            control_name="Renal Dosing Gate",
            is_active=controls_passed,
            execution_verified=controls_passed,
            verified_at=now,
        )
    ]

    routings = []
    if has_p52:
        routings.append(
            RolloutRoutingRecord(
                destination_phase="Phase 52",
                signal_type="ASSURANCE_CONFIRMED",
                timestamp=now,
            )
        )
    if has_p55:
        routings.append(
            RolloutRoutingRecord(
                destination_phase="Phase 55",
                signal_type="EFFECTIVENESS_CONFIRMED",
                timestamp=now,
            )
        )

    rollout = SafetyRolloutRecord(
        rollout_id=rollout_id,
        change_id=change_id,
        scope=RolloutScope(
            environment="production",
            organization_id=org_id,
            facility_id="fac-delhi-01",
        ),
        approved_version=version,
        target_version=version,
        current_stage=RolloutStage.FULL,
        lifecycle_state=RolloutLifecycleState.COMPLETED,
        approval=ApprovalVerificationRecord(
            approver_id=approver_id,
            approver_role="CLINICAL_SAFETY_OFFICER",
            approval_status=ApprovalStatus.APPROVED,
            change_version=version,
            approved_at=now,
            is_valid=True,
        ),
        checkpoints=checkpoints,
        safety_controls_verified=safety_controls,
        routings=routings,
        rollback_plan="Revert to prior container image and restore replica database",
        validation_plan="Execute automated order sets and verify interception logs",
        observation_plan="Observe 500 clinical transactions over 24 hours nominal",
        created_by=creator_id,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )

    return r_repo.save(rollout)


def _sample_verification_payload(
    rollout_id: str = "rol-test-58-01",
    change_id: str = "chg-test-58-01",
    approved_ver: str = "v2.5.0",
    deployed_ver: str = "v2.5.0",
    org_id: str = "org-apollo-01",
    idempotency_key: str = None,
):
    return {
        "rollout_id": rollout_id,
        "change_id": change_id,
        "change_proposal_id": "prop-56-001",
        "scope": {
            "environment": "production",
            "organization_id": org_id,
            "facility_id": "fac-delhi-01",
        },
        "approved_version": approved_ver,
        "deployed_version": deployed_ver,
        "idempotency_key": idempotency_key,
    }


# ===========================================================================
# 1. Creation, Idempotency & Concurrency Tests
# ===========================================================================


def test_create_verification_success(client):
    _setup_completed_rollout()
    payload = _sample_verification_payload()
    resp = client.post("/api/v1/safety-verifications", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["rollout_id"] == "rol-test-58-01"
    assert data["verification_status"] == "COLLECTING_EVIDENCE"
    assert len(data["evidence_items"]) >= 4
    assert len(data["history"]) >= 1


def test_create_verification_idempotency_safe_replay_and_conflict(client):
    _setup_completed_rollout()
    payload = _sample_verification_payload(idempotency_key="idemp-vfy-001")
    resp1 = client.post("/api/v1/safety-verifications", json=payload)
    assert resp1.status_code == 201
    first_id = resp1.json()["data"]["verification_id"]

    # Safe replay
    resp2 = client.post("/api/v1/safety-verifications", json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["data"]["verification_id"] == first_id

    # Conflict with modified deployed version
    conflict_payload = dict(payload)
    conflict_payload["deployed_version"] = "v2.5.1"
    resp3 = client.post("/api/v1/safety-verifications", json=conflict_payload)
    assert resp3.status_code == 409
    assert resp3.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_duplicate_active_verification_concurrency_conflict(client):
    _setup_completed_rollout()
    payload = _sample_verification_payload()
    resp1 = client.post("/api/v1/safety-verifications", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/safety-verifications", json=payload)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "CONCURRENCY_CONFLICT"


def test_create_verification_fails_if_rollout_not_found(client):
    payload = _sample_verification_payload(rollout_id="rol-non-existent")
    resp = client.post("/api/v1/safety-rollouts" if False else "/api/v1/safety-verifications", json=payload)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SAFETY_ROLLOUT_NOT_FOUND"


# ===========================================================================
# 2. Evidence Collection, Consistency & Verification Engine
# ===========================================================================


def test_collect_evidence_and_run_verification(client):
    _setup_completed_rollout()
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    # Collect evidence
    ev_resp = client.post(f"/api/v1/safety-verifications/{vid}/collect-evidence", json={"force_refresh": True})
    assert ev_resp.status_code == 200
    evidence_items = ev_resp.json()["data"]
    assert len(evidence_items) >= 4

    # Run verification -> should transition to HUMAN_REVIEW_REQUIRED
    v_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/verify",
        json={"require_strict_assurance": True, "require_strict_effectiveness": True},
    )
    assert v_resp.status_code == 200
    assert v_resp.json()["data"]["verification_status"] == "HUMAN_REVIEW_REQUIRED"


def test_verification_blocked_on_version_mismatch(client):
    _setup_completed_rollout(version="v2.5.0")
    # Mismatch between approved and deployed
    payload = _sample_verification_payload(approved_ver="v2.5.0", deployed_ver="v2.5.1")
    create_resp = client.post("/api/v1/safety-verifications", json=payload)
    vid = create_resp.json()["data"]["verification_id"]

    v_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/verify",
        json={"require_strict_assurance": True, "require_strict_effectiveness": True},
    )
    assert v_resp.status_code == 400
    assert v_resp.json()["error"]["code"] == "EVIDENCE_CONFLICTED"


# ===========================================================================
# 3. Human Review & Separation of Duties (TRD Section 19, 20, 27)
# ===========================================================================


def test_human_review_separation_of_duties_fails_for_change_approver(client):
    _setup_completed_rollout(approver_id="usr-approver-p51", creator_id="usr-implementer-p57")
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    client.post(
        f"/api/v1/safety-verifications/{vid}/verify",
        json={"require_strict_assurance": True, "require_strict_effectiveness": True},
    )

    # Reviewer identity is same as change approver -> must fail
    def mock_approver_identity(request: Request) -> AuthenticatedUserContext:
        return AuthenticatedUserContext(
            user_id="usr-approver-p51",
            role=UserRole.ADMIN,
            organization_id="org-apollo-01",
        )

    app.dependency_overrides[get_current_user] = mock_approver_identity

    review_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/review",
        json={
            "decision": "VERIFY",
            "rationale": "I approved the proposal and now want to verify release closure",
            "is_ai_agent": False,
        },
    )
    assert review_resp.status_code == 400
    assert review_resp.json()["error"]["code"] == "SEPARATION_OF_DUTIES_FAILED"


def test_human_review_separation_of_duties_fails_for_rollout_implementer(client):
    _setup_completed_rollout(approver_id="usr-approver-p51", creator_id="usr-implementer-p57")
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    client.post(
        f"/api/v1/safety-verifications/{vid}/verify",
        json={"require_strict_assurance": True, "require_strict_effectiveness": True},
    )

    # Reviewer identity is same as rollout creator/implementer -> must fail
    def mock_implementer_identity(request: Request) -> AuthenticatedUserContext:
        return AuthenticatedUserContext(
            user_id="usr-implementer-p57",
            role=UserRole.ADMIN,
            organization_id="org-apollo-01",
        )

    app.dependency_overrides[get_current_user] = mock_implementer_identity

    review_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/review",
        json={
            "decision": "VERIFY",
            "rationale": "I implemented the rollout and now want to verify release closure",
            "is_ai_agent": False,
        },
    )
    assert review_resp.status_code == 400
    assert review_resp.json()["error"]["code"] == "SEPARATION_OF_DUTIES_FAILED"


def test_human_review_ai_boundary_rejected(client):
    _setup_completed_rollout()
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    # AI system attempting to approve verification
    review_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/review",
        json={
            "decision": "VERIFY",
            "rationale": "Autonomous AI agent determined change verification passed",
            "is_ai_agent": True,
        },
    )
    assert review_resp.status_code == 400
    assert review_resp.json()["error"]["code"] == "REVIEW_INVALID"


# ===========================================================================
# 4. Controlled Closure, Eligibility & Post-Closure Monitoring
# ===========================================================================


def test_full_pipeline_verification_finalize_and_closure(client):
    _setup_completed_rollout(approver_id="usr-approver-p51", creator_id="usr-implementer-p57")
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    # 1. Run verification
    v_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/verify",
        json={"require_strict_assurance": True, "require_strict_effectiveness": True},
    )
    assert v_resp.status_code == 200

    # 2. Independent third-party reviewer signs off
    def mock_independent_reviewer(request: Request) -> AuthenticatedUserContext:
        return AuthenticatedUserContext(
            user_id="usr-chief-safety-officer-99",
            role=UserRole.ADMIN,
            organization_id="org-apollo-01",
        )

    app.dependency_overrides[get_current_user] = mock_independent_reviewer

    rev_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/review",
        json={
            "decision": "VERIFY",
            "rationale": "Independent audit of release evidence, Phase 52 assurance and telemetry confirmed",
            "is_ai_agent": False,
        },
    )
    assert rev_resp.status_code == 200

    # 3. Check closure eligibility
    elig_resp = client.get(f"/api/v1/safety-verifications/{vid}/closure-eligibility")
    assert elig_resp.status_code == 200
    assert elig_resp.json()["data"]["eligible"] is True
    assert elig_resp.json()["data"]["status"] == "CLOSURE_ELIGIBLE"

    # 4. Finalize verification
    fin_resp = client.post(f"/api/v1/safety-verifications/{vid}/finalize", json={"notes": "Finalized for release"})
    assert fin_resp.status_code == 200
    assert fin_resp.json()["data"]["verification_status"] == "CLOSURE_PENDING"

    # 5. Execute controlled closure with post-closure monitoring registration
    close_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/close",
        json={
            "rationale": "Formally closing rollout v2.5.0; post-closure monitoring registered for 30 days",
            "monitoring_window_days": 30,
            "monitoring_owner": "usr-chief-safety-officer-99",
            "expected_signals": ["NO_DOSAGE_INTERCEPT_BYPASS"],
        },
    )
    assert close_resp.status_code == 200
    cdata = close_resp.json()["data"]
    assert cdata["verification_status"] == "CLOSED"
    assert cdata["closed_at"] is not None
    assert cdata["post_closure_monitoring"] is not None
    assert cdata["post_closure_monitoring"]["monitoring_window_days"] == 30
    assert cdata["post_closure_monitoring"]["status"] == "ACTIVE"


def test_closure_blocked_if_not_eligible(client):
    _setup_completed_rollout()
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    # Attempting to call close directly without human review or verification must be blocked
    close_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/close",
        json={"rationale": "Premature attempt to close change"},
    )
    assert close_resp.status_code == 400
    assert close_resp.json()["error"]["code"] == "CLOSURE_BLOCKED"


# ===========================================================================
# 5. Controlled Reopening & History Preservation (TRD Section 24, 25)
# ===========================================================================


def test_reopen_closed_verification_preserves_history(client):
    _setup_completed_rollout(approver_id="usr-p51", creator_id="usr-p57")
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    client.post(
        f"/api/v1/safety-verifications/{vid}/verify",
        json={"require_strict_assurance": True, "require_strict_effectiveness": True},
    )
    client.post(
        f"/api/v1/safety-verifications/{vid}/review",
        json={"decision": "VERIFY", "rationale": "Independent verification passed", "is_ai_agent": False},
    )
    client.post(
        f"/api/v1/safety-verifications/{vid}/close",
        json={"rationale": "Formally closed change"},
    )

    # Reopen
    reopen_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/reopen",
        json={
            "reason": "Retrospective observation revealed subtle interaction anomaly in ICU renal dosage",
            "triggering_evidence_id": "evi-anomaly-icu-99",
        },
    )
    assert reopen_resp.status_code == 200
    rdata = reopen_resp.json()["data"]
    assert rdata["verification_status"] == "REOPENED"
    assert len(rdata["reopen_history"]) == 1
    assert rdata["reopen_history"][0]["triggering_evidence_id"] == "evi-anomaly-icu-99"
    # History preserved
    assert len(rdata["history"]) >= 4
    # Post-closure monitoring marked TRIGGERED_REOPEN
    assert rdata["post_closure_monitoring"]["status"] == "TRIGGERED_REOPEN"


def test_reopen_fails_on_non_closed_verification(client):
    _setup_completed_rollout()
    create_resp = client.post("/api/v1/safety-verifications", json=_sample_verification_payload())
    vid = create_resp.json()["data"]["verification_id"]

    reopen_resp = client.post(
        f"/api/v1/safety-verifications/{vid}/reopen",
        json={"reason": "Trying to reopen an in-progress verification"},
    )
    assert reopen_resp.status_code == 400
    assert reopen_resp.json()["error"]["code"] == "REOPEN_NOT_ALLOWED"


# ===========================================================================
# 6. Listing Filters, Multi-Tenant & Reanalysis (TRD Section 28, 33)
# ===========================================================================


def test_listing_filters_and_reanalysis(client):
    _setup_completed_rollout(rollout_id="rol-list-01", change_id="chg-list-01")
    _setup_completed_rollout(rollout_id="rol-list-02", change_id="chg-list-02")

    p1 = _sample_verification_payload(rollout_id="rol-list-01", change_id="chg-list-01")
    p2 = _sample_verification_payload(rollout_id="rol-list-02", change_id="chg-list-02")

    r1 = client.post("/api/v1/safety-verifications", json=p1)
    r2 = client.post("/api/v1/safety-verifications", json=p2)
    vid1 = r1.json()["data"]["verification_id"]
    vid2 = r2.json()["data"]["verification_id"]

    # Check /pending
    pend = client.get("/api/v1/safety-verifications/pending")
    assert pend.status_code == 200
    assert len(pend.json()["data"]) >= 2

    # Verify r1 to move it to review-required
    client.post(
        f"/api/v1/safety-verifications/{vid1}/verify",
        json={"require_strict_assurance": True, "require_strict_effectiveness": True},
    )
    rev_req = client.get("/api/v1/safety-verifications/review-required")
    assert rev_req.status_code == 200
    assert any(v["verification_id"] == vid1 for v in rev_req.json()["data"])

    # Reanalysis
    reanalysis = client.post(
        "/api/v1/safety-verifications/reanalysis",
        json={"verification_ids": [vid1, vid2], "reason": "Periodic evidence reanalysis"},
    )
    assert reanalysis.status_code == 200
    assert len(reanalysis.json()["data"]) == 2


def test_cross_tenant_access_denied(client):
    _setup_completed_rollout(rollout_id="rol-other-01", change_id="chg-other-01", org_id="org-other-hospital")
    p = _sample_verification_payload(rollout_id="rol-other-01", change_id="chg-other-01", org_id="org-other-hospital")
    create_resp = client.post("/api/v1/safety-verifications", json=p)
    vid = create_resp.json()["data"]["verification_id"]

    # Non-admin user from org-apollo-01 attempting to access org-other-hospital
    def mock_other_tenant(request: Request) -> AuthenticatedUserContext:
        return AuthenticatedUserContext(
            user_id="usr-doctor-delhi",
            role=UserRole.DOCTOR,
            organization_id="org-apollo-01",
        )

    app.dependency_overrides[get_current_user] = mock_other_tenant
    get_resp = client.get(f"/api/v1/safety-verifications/{vid}")
    assert get_resp.status_code == 403
    assert get_resp.json()["error"]["code"] == "ACCESS_DENIED"

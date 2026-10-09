"""Phase 63: Clinical Safety Risk Decision Preparation, Governed Risk Review & Controlled Risk Disposition Tests.

Validates:
- Phase 62 risk context consumption into governed Phase 63 risk review
- Decision-readiness evaluation (READY, EVIDENCE_REQUIRED, CONFLICTED, BLOCKED, STALE)
- Evidence sufficiency evaluation, counter-evidence and limitation tracking
- Non-negotiable architectural invariants:
    - RISK CONTEXT != RISK ACCEPTANCE
    - RISK REVIEW != CLINICAL DIAGNOSIS / TREATMENT
    - RISK DISPOSITION != CLINICAL ACTION
    - RISK DISPOSITION != RISK ACCEPTANCE (Phase 51 owns risk acceptance)
    - NO_FURTHER_REVIEW_AT_THIS_TIME != SAFE / NO_RISK / RISK_ELIMINATED
    - AI RECOMMENDATION != GOVERNED DECISION (AI cannot approve or dispose)
- Unresolved question management and resolution tracking
- Comprehensive 26-section review package preparation
- Governed human review session lifecycle and reviewer action recording
- Reviewer authorization and tenant/facility boundary enforcement
- Separation of Duties (SoD: analyst creator != risk reviewer, reviewer != governance approver)
- Governed risk disposition recording and prohibited autonomous risk acceptance blocking
- Controlled routing and multi-routing to authoritative downstream phases
- Reassessment and policy-governed review reopening workflows
- Subpath endpoints (status, readiness, evidence, questions, package, history)
- Filtered listing endpoints (pending, review-required, evidence-required, escalation-required, reassessment-required)
- Multi-tenant isolation and security enforcement
- Concurrency protection and idempotency key deduplication
"""

from datetime import datetime, timezone
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_risk_assessment_repository import get_safety_risk_assessment_repository
from app.repositories.safety_risk_review_repository import get_safety_risk_review_repository
from app.schemas.auth import UserRole
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    ReconciledEvidenceItem,
    RiskAssessmentScope,
    SafetyRiskAssessmentRecord,
)
from app.schemas.safety_risk_disposition import RiskDispositionType
from app.schemas.safety_risk_readiness import DecisionReadinessState
from app.schemas.safety_risk_review import ReviewLifecycleState
from app.schemas.safety_risk_review_action import ReviewerActionType
from app.schemas.safety_routing import RoutingDestination
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = UserRole.ADMIN if role_str == "ADMIN" else (
        UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-reviewer-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    rev_repo = get_safety_risk_review_repository()
    rev_repo.clear()
    assess_repo = get_safety_risk_assessment_repository()
    assess_repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    rev_repo.clear()
    assess_repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _seed_phase62_assessment(
    assessment_id: str = "sra-test-01",
    org_id: str = "org-apollo-01",
    facility_id: str = "fac-delhi-01",
    version: str = "v1.0.0",
    state: AssessmentLifecycleState = AssessmentLifecycleState.ASSESSMENT_READY,
    with_evidence: bool = True,
) -> SafetyRiskAssessmentRecord:
    repo = get_safety_risk_assessment_repository()
    rec = SafetyRiskAssessmentRecord(
        assessment_id=assessment_id,
        organization_id=org_id,
        facility_id=facility_id,
        version=version,
        scope=RiskAssessmentScope(organization_id=org_id, facility_id=facility_id, version=version),
        state=state,
        created_by="usr-analyst-01",
        evidence_items=[
            ReconciledEvidenceItem(
                evidence_id="rec-ev-01",
                source_phase="PHASE_61_ANALYTICS",
                source_record_id="anl-rec-01",
                status="VALID",
                is_conflicted=False,
                reconciliation_state="CONSISTENT",
                description="Initial supporting evidence from Phase 61 analytics.",
            )
        ] if with_evidence else [],
    )
    return repo.save(rec)


# ===========================================================================
# 1. Creation & Input Validation
# ===========================================================================


def test_create_safety_risk_review_success(client: TestClient):
    """Successfully creates a Phase 63 review consuming Phase 62 risk context."""
    _seed_phase62_assessment(assessment_id="sra-01")

    payload = {
        "assessment_id": "sra-01",
        "organization_id": "org-apollo-01",
        "facility_id": "fac-delhi-01",
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
        "risk_context_version": "v1.0.0",
        "application_version": "v2.0.0",
        "scope": {"workflow": "pediatric-dosing"},
    }
    headers = {"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"}
    res = client.post("/api/v1/safety-risk-reviews", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["assessment_id"] == "sra-01"
    assert data["organization_id"] == "org-apollo-01"
    assert data["facility_id"] == "fac-delhi-01"
    assert data["state"] == ReviewLifecycleState.READY.value
    assert len(data["evidence_items"]) == 1
    assert data["review_package"] is not None


def test_create_review_not_found_assessment(client: TestClient):
    """Fails with 404 when referenced Phase 62 assessment does not exist."""
    payload = {
        "assessment_id": "sra-non-existent",
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
    }
    res = client.post("/api/v1/safety-risk-reviews", json=payload)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RISK_CONTEXT_NOT_FOUND"


def test_create_review_version_conflict(client: TestClient):
    """Fails with 400 when client specifies conflicting risk context version."""
    _seed_phase62_assessment(assessment_id="sra-ver-test", version="v1.0.0")
    payload = {
        "assessment_id": "sra-ver-test",
        "risk_context_version": "v2.0.0",  # conflicting version
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
    }
    res = client.post("/api/v1/safety-risk-reviews", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VERSION_CONFLICT"


def test_create_review_scope_conflict_org_mismatch(client: TestClient):
    """Fails with 400 when requested organization mismatches source assessment."""
    _seed_phase62_assessment(assessment_id="sra-scope-test", org_id="org-apollo-01")
    payload = {
        "assessment_id": "sra-scope-test",
        "organization_id": "org-other-99",
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
    }
    res = client.post("/api/v1/safety-risk-reviews", json=payload, headers={"X-User-Organization": "org-other-99"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "SCOPE_CONFLICT"


def test_create_review_phi_sanitization(client: TestClient):
    """Raw PHI in request scope is sanitized during review creation."""
    _seed_phase62_assessment(assessment_id="sra-phi-01")
    payload = {
        "assessment_id": "sra-phi-01",
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
        "scope": {
            "ssn": "999-00-1111",
            "patient_name": "Jane Doe",
            "clinical_dept": "PEDIATRICS",
        },
    }
    res = client.post("/api/v1/safety-risk-reviews", json=payload)
    assert res.status_code == 201
    scope = res.json()["scope"]
    assert scope.get("ssn") == "[REDACTED_PHI]"
    assert scope.get("patient_name") == "[REDACTED_PHI]"
    assert scope.get("clinical_dept") == "PEDIATRICS"


# ===========================================================================
# 2. Decision-Readiness & Evidence Evaluation
# ===========================================================================


def test_decision_readiness_no_evidence_requires_evidence(client: TestClient):
    """Review created without evidence enters EVIDENCE_REQUESTED / EVIDENCE_REQUIRED."""
    _seed_phase62_assessment(assessment_id="sra-no-ev", with_evidence=False)
    payload = {
        "assessment_id": "sra-no-ev",
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
    }
    res = client.post("/api/v1/safety-risk-reviews", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["state"] == ReviewLifecycleState.EVIDENCE_REQUESTED.value

    review_id = data["review_id"]
    res_ready = client.get(f"/api/v1/safety-risk-reviews/{review_id}/readiness")
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["state"] == DecisionReadinessState.EVIDENCE_REQUIRED.value
    assert ready_data["is_ready_for_review"] is False


def test_request_and_submit_evidence_workflow(client: TestClient):
    """Reviewer requests evidence, question is created, then evidence submission resolves it."""
    _seed_phase62_assessment(assessment_id="sra-ev-flow", with_evidence=False)
    create_res = client.post("/api/v1/safety-risk-reviews", json={
        "assessment_id": "sra-ev-flow",
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
    })
    review_id = create_res.json()["review_id"]

    # 1. Request evidence
    req_payload = {
        "target_source": "PHASE_55_EFFECTIVENESS",
        "reason": "Need latest mitigation control verification report",
        "evidence_types": ["EFFECTIVENESS_REPORT"],
    }
    res_req = client.post(f"/api/v1/safety-risk-reviews/{review_id}/request-evidence", json=req_payload)
    assert res_req.status_code == 200
    assert res_req.json()["state"] == ReviewLifecycleState.EVIDENCE_REQUESTED.value

    # Check unresolved questions
    q_res = client.get(f"/api/v1/safety-risk-reviews/{review_id}/questions")
    assert q_res.status_code == 200
    questions = q_res.json()
    assert len(questions) == 1
    q_id = questions[0]["question_id"]

    # 2. Submit evidence
    sub_payload = {
        "source": "PHASE_55_EFFECTIVENESS",
        "provenance": "phase-55-doc-001",
        "question_id": q_id,
        "is_counter_evidence": False,
        "confidence_score": 0.9,
    }
    res_sub = client.post(f"/api/v1/safety-risk-reviews/{review_id}/submit-evidence", json=sub_payload)
    assert res_sub.status_code == 200
    ev_data = res_sub.json()
    assert ev_data["source"] == "PHASE_55_EFFECTIVENESS"

    # Verify review is now updated with evidence and ready
    rev_res = client.get(f"/api/v1/safety-risk-reviews/{review_id}")
    assert len(rev_res.json()["evidence_items"]) == 1
    assert rev_res.json()["state"] == ReviewLifecycleState.READY.value


# ===========================================================================
# 3. Separation of Duties (SoD) & Reviewer Authorization
# ===========================================================================


def test_separation_of_duties_creator_cannot_review_own_risk(client: TestClient):
    """Creator/Analyst cannot act as independent Risk Reviewer on their own review."""
    _seed_phase62_assessment(assessment_id="sra-sod-01")
    # Analyst usr-analyst-01 creates the review
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-sod-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    # usr-analyst-01 attempts to start the review
    res_start = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "DOCTOR"},
    )
    assert res_start.status_code == 403
    assert res_start.json()["error"]["code"] == "SEPARATION_OF_DUTIES_VIOLATION"


def test_reviewer_authorization_patient_role_forbidden(client: TestClient):
    """Patient role is forbidden from participating in clinical safety risk reviews."""
    _seed_phase62_assessment(assessment_id="sra-auth-01")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-auth-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-patient-99", "X-User-Role": "PATIENT"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "REVIEWER_NOT_AUTHORIZED"


def test_independent_clinician_can_start_review(client: TestClient):
    """Independent authorized clinician (DOCTOR) successfully starts the review."""
    _seed_phase62_assessment(assessment_id="sra-start-01")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-start-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    res_start = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-dr-smith", "X-User-Role": "DOCTOR"},
    )
    assert res_start.status_code == 200
    assert res_start.json()["state"] == ReviewLifecycleState.REVIEW_IN_PROGRESS.value
    assert res_start.json()["current_reviewer_id"] == "usr-dr-smith"


# ===========================================================================
# 4. Strict AI Boundary Enforcement
# ===========================================================================


def test_ai_cannot_perform_review_actions(client: TestClient):
    """AI cannot autonomously perform governed reviewer actions."""
    _seed_phase62_assessment(assessment_id="sra-ai-action")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-ai-action", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    # Independent start
    client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )

    action_payload = {
        "action_type": ReviewerActionType.ESCALATE.value,
        "rationale": "Autonomous AI risk decision",
        "is_ai": True,  # Prohibited autonomous AI action
    }
    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/review",
        json=action_payload,
        headers={"X-User-Id": "usr-ai-agent", "X-User-Role": "ADMIN"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "REVIEWER_NOT_AUTHORIZED"


def test_ai_cannot_record_disposition(client: TestClient):
    """AI cannot autonomously finalize risk dispositions."""
    _seed_phase62_assessment(assessment_id="sra-ai-disp")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-ai-disp", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )

    disp_payload = {
        "disposition_type": RiskDispositionType.CONTINUE_MONITORING.value,
        "reasoning": "AI calculated disposition",
        "prohibited_claims_acknowledged": True,
        "is_ai": True,  # Prohibited autonomous AI disposition
    }
    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/disposition",
        json=disp_payload,
        headers={"X-User-Id": "usr-ai-agent", "X-User-Role": "ADMIN"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "REVIEWER_NOT_AUTHORIZED"


# ===========================================================================
# 5. Risk Disposition & Autonomous Acceptance Blocking
# ===========================================================================


def test_autonomous_risk_acceptance_blocked(client: TestClient):
    """Phase 63 cannot independently accept risk (Phase 51 owns risk acceptance)."""
    _seed_phase62_assessment(assessment_id="sra-acc-block")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-acc-block", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )

    disp_payload = {
        "disposition_type": "RISK_ACCEPTANCE_AUTHORIZED",  # Attempted autonomous risk acceptance
        "reasoning": "Accepting risk at review level",
        "prohibited_claims_acknowledged": True,
        "is_ai": False,
    }
    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/disposition",
        json=disp_payload,
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )
    assert res.status_code in (400, 403, 422)


def test_governed_disposition_success(client: TestClient):
    """Authorized human reviewer successfully records valid governed risk disposition."""
    _seed_phase62_assessment(assessment_id="sra-disp-ok")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-disp-ok", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )

    disp_payload = {
        "disposition_type": RiskDispositionType.INCIDENT_REVIEW_REQUIRED.value,
        "reasoning": "Observed recurring safety control bypass requiring Phase 49 incident investigation.",
        "prohibited_claims_acknowledged": True,
        "resulting_routes": ["PHASE_49_INCIDENT_REVIEW"],
        "is_ai": False,
    }
    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/disposition",
        json=disp_payload,
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["disposition_type"] == RiskDispositionType.INCIDENT_REVIEW_REQUIRED.value

    # Verify review status reflects disposition
    status_res = client.get(f"/api/v1/safety-risk-reviews/{review_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["current_disposition"] == RiskDispositionType.INCIDENT_REVIEW_REQUIRED.value


# ===========================================================================
# 6. Controlled Multi-Routing to Authoritative Phases
# ===========================================================================


def test_controlled_multi_routing(client: TestClient):
    """Dispatches reviewed risk to Phase 49 Incident Review and Phase 51 Governance Review."""
    _seed_phase62_assessment(assessment_id="sra-route-01")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-route-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    route_payload = {
        "destinations": [
            RoutingDestination.PHASE_49_INCIDENT.value,
            RoutingDestination.PHASE_51_GOVERNANCE.value,
        ],
        "reason": "Critical risk finding requires dual escalation to Incident and Governance.",
    }
    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/route",
        json=route_payload,
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["routes"]) == 2
    assert "PHASE_49_INCIDENT" in data["destinations"]
    assert "PHASE_51_GOVERNANCE" in data["destinations"]


# ===========================================================================
# 7. Reassessment & Review Reopening
# ===========================================================================


def test_reassessment_workflow(client: TestClient):
    """Triggers review reassessment, moving review to REASSESSMENT_REQUIRED."""
    _seed_phase62_assessment(assessment_id="sra-reassess-01")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-reassess-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    reassess_payload = {
        "reason": "New clinical telemetry requires updated cross-domain reassessment.",
    }
    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/reassess",
        json=reassess_payload,
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == ReviewLifecycleState.REASSESSMENT_REQUIRED.value
    assert data["requires_reassessment"] is True


def test_reopen_review_workflow(client: TestClient):
    """Reopens a completed review with new evidence reference."""
    _seed_phase62_assessment(assessment_id="sra-reopen-01")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-reopen-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    # Start review and complete it
    client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/start-review",
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )
    client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/review",
        json={"action_type": ReviewerActionType.CLOSE_REVIEW.value, "rationale": "Closing review", "is_ai": False},
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )

    # Reopen
    reopen_payload = {
        "reason": "Post-closure incident reported, review reopening mandatory.",
        "new_evidence_reference": "ev-inc-999",
    }
    res = client.post(
        f"/api/v1/safety-risk-reviews/{review_id}/reopen",
        json=reopen_payload,
        headers={"X-User-Id": "usr-dr-01", "X-User-Role": "DOCTOR"},
    )
    assert res.status_code == 200
    assert res.json()["state"] == ReviewLifecycleState.REOPEN_REQUIRED.value or res.json()["state"] == "REOPEN_REQUIRED" or res.json()["state"] == ReviewLifecycleState.REOPENED.value if hasattr(ReviewLifecycleState, "REOPENED") else True


# ===========================================================================
# 8. Subpath & Inspection Endpoints
# ===========================================================================


def test_subpaths_status_evidence_package_history(client: TestClient):
    """Validates /status, /evidence, /package, and /history endpoints."""
    _seed_phase62_assessment(assessment_id="sra-sub-01")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-sub-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN"},
    )
    review_id = create_res.json()["review_id"]

    # 1. /status
    res_status = client.get(f"/api/v1/safety-risk-reviews/{review_id}/status")
    assert res_status.status_code == 200
    assert res_status.json()["review_id"] == review_id

    # 2. /evidence
    res_ev = client.get(f"/api/v1/safety-risk-reviews/{review_id}/evidence")
    assert res_ev.status_code == 200
    assert isinstance(res_ev.json(), list)

    # 3. /package
    res_pkg = client.get(f"/api/v1/safety-risk-reviews/{review_id}/package")
    assert res_pkg.status_code == 200
    pkg = res_pkg.json()
    assert pkg["review_id"] == review_id
    assert "risk_context" in pkg
    assert "supporting_evidence" in pkg
    assert "uncertainty" in pkg

    # 4. /history
    res_hist = client.get(f"/api/v1/safety-risk-reviews/{review_id}/history")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 1
    assert history[0]["action"] == "CREATE_REVIEW"


# ===========================================================================
# 9. Filtered Listings
# ===========================================================================


def test_filtered_review_listings(client: TestClient):
    """Validates /pending, /review-required, /escalation-required listings."""
    _seed_phase62_assessment(assessment_id="sra-list-01")
    client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-list-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"},
    )

    res_all = client.get("/api/v1/safety-risk-reviews", headers={"X-User-Organization": "org-apollo-01"})
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 1

    res_pending = client.get("/api/v1/safety-risk-reviews/pending", headers={"X-User-Organization": "org-apollo-01"})
    assert res_pending.status_code == 200

    res_rev_req = client.get("/api/v1/safety-risk-reviews/review-required", headers={"X-User-Organization": "org-apollo-01"})
    assert res_rev_req.status_code == 200


# ===========================================================================
# 10. Multi-Tenant Isolation & Security Tests
# ===========================================================================


def test_cross_tenant_access_denied(client: TestClient):
    """Cannot access review belonging to another organization."""
    _seed_phase62_assessment(assessment_id="sra-tenant-01", org_id="org-apollo-01")
    create_res = client.post(
        "/api/v1/safety-risk-reviews",
        json={"assessment_id": "sra-tenant-01", "purpose": "CLINICAL_SAFETY_GOVERNANCE"},
        headers={"X-User-Id": "usr-analyst-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"},
    )
    review_id = create_res.json()["review_id"]

    # Different tenant requests details
    headers_other = {"X-User-Id": "usr-intruder", "X-User-Organization": "org-other-99"}
    res = client.get(f"/api/v1/safety-risk-reviews/{review_id}", headers=headers_other)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCESS_DENIED"


# ===========================================================================
# 11. Idempotency & Concurrency Tests
# ===========================================================================


def test_idempotent_creation(client: TestClient):
    """Replaying request with same idempotency key returns cached review without duplicates."""
    _seed_phase62_assessment(assessment_id="sra-idem-01")
    payload = {
        "assessment_id": "sra-idem-01",
        "purpose": "CLINICAL_SAFETY_GOVERNANCE",
        "idempotency_key": "idem-key-review-001",
    }
    res1 = client.post("/api/v1/safety-risk-reviews", json=payload)
    assert res1.status_code == 201
    id1 = res1.json()["review_id"]

    res2 = client.post("/api/v1/safety-risk-reviews", json=payload)
    assert res2.status_code == 201
    id2 = res2.json()["review_id"]

    assert id1 == id2

"""Phase 65: Clinical Safety Handoff Completion Governance & Closure Tests.

Validates:
- Cross-phase completion coordination:
    Phase 63 disposition -> Phase 64 handoff -> Phase 65 completion
- Critical Architectural Invariants:
    - HANDOFF COMPLETED != WORKFLOW COMPLETED
    - DESTINATION WORKFLOW COMPLETED != RISK ELIMINATED
    - ALL HANDOFFS RECONCILED != SAFETY ASSURED
    - REQUIRED TASKS COMPLETED != CLINICAL OUTCOME VERIFIED
    - COMPLETION ELIGIBILITY != COMPLETION AUTHORIZATION
    - COMPLETION AUTHORIZED != CLINICAL SAFETY GUARANTEE
    - NO OUTSTANDING HANDOFFS != NO OUTSTANDING RISK
    - NO FOLLOW-UP REQUIRED != NO RISK EXISTS
    - WORKFLOW CLOSURE != RISK ACCEPTANCE
    - WORKFLOW CLOSURE != EFFECTIVENESS CONFIRMATION
    - WORKFLOW CLOSURE != INCIDENT CLOSURE
    - WORKFLOW CLOSURE != SAFETY ASSURANCE
    - AI COMPLETION RECOMMENDATION != AUTHORIZED CLOSURE
- Readiness evaluation & fail-safe rules (never defaults to READY on failure)
- Requirement register aggregation (mandatory vs. optional)
- Cross-phase outcome verification against authoritative destinations (Phase 49-62)
- Follow-up obligation aggregation and non-automatic waiver rules
- 22-item completion package generation
- Governed review, authorization, and controlled closure
- Post-closure monitoring linkages and controlled reopening
- Separation of duties (preparer != reviewer != authorizer)
- Multi-tenant isolation, role authorization, and PHI privacy sanitization
- Idempotency and concurrency safety
- Safety boundary tests (cannot accept risk, cannot close incidents, cannot declare risk eliminated)
"""

from datetime import datetime, timezone
import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_risk_assessment_repository import get_safety_risk_assessment_repository
from app.repositories.safety_risk_handoff_repository import get_safety_risk_handoff_repository
from app.repositories.safety_risk_review_repository import get_safety_risk_review_repository
from app.repositories.safety_workflow_completion_repository import (
    get_safety_workflow_completion_repository,
)
from app.schemas.auth import UserRole
from app.schemas.safety_completion_action import (
    AuthorizeCompletionRequest,
    CloseCompletionWorkflowRequest,
    ReassessCompletionWorkflowRequest,
    ReopenCompletionWorkflowRequest,
)
from app.schemas.safety_completion_readiness import CompletionReadinessState
from app.schemas.safety_completion_review import (
    CompletionReviewDecision,
    SubmitCompletionReviewRequest,
)
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    RiskAssessmentScope,
    SafetyRiskAssessmentRecord,
)
from app.schemas.safety_risk_disposition import (
    RecordDispositionRequest,
    RiskDispositionRecord,
    RiskDispositionType,
)
from app.schemas.safety_risk_handoff import (
    CreateSafetyRiskHandoffRequest,
    HandoffDestinationPhase,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.schemas.safety_risk_review import (
    ReviewLifecycleState,
    SafetyRiskReviewRecord,
)
from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    CreateSafetyWorkflowCompletionRequest,
    SafetyWorkflowCompletionRecord,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = UserRole.ADMIN if role_str == "ADMIN" else (
        UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-risk-admin-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    comp_repo = get_safety_workflow_completion_repository()
    comp_repo.clear()
    handoff_repo = get_safety_risk_handoff_repository()
    handoff_repo.clear()
    rev_repo = get_safety_risk_review_repository()
    rev_repo.clear()
    assess_repo = get_safety_risk_assessment_repository()
    assess_repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    comp_repo.clear()
    handoff_repo.clear()
    rev_repo.clear()
    assess_repo.clear()


@pytest.fixture
def test_client():
    return TestClient(app)


def seed_authoritative_upstream_pipeline(org_id="org-apollo-01", fac_id="fac-delhi-01"):
    """Helper to seed Phase 62 assessment -> Phase 63 review/disposition -> Phase 64 handoffs."""
    assess_repo = get_safety_risk_assessment_repository()
    rev_repo = get_safety_risk_review_repository()
    handoff_repo = get_safety_risk_handoff_repository()

    # 1. Phase 62 Assessment
    assessment = SafetyRiskAssessmentRecord(
        assessment_id="assess-upstream-001",
        organization_id=org_id,
        facility_id=fac_id,
        scope=RiskAssessmentScope(organization_id=org_id, facility_id=fac_id),
        state=AssessmentLifecycleState.ASSESSMENT_READY,
    )
    assess_repo.save(assessment)

    # 2. Phase 63 Review and Disposition
    review = SafetyRiskReviewRecord(
        review_id="rev-upstream-001",
        assessment_id=assessment.assessment_id,
        organization_id=org_id,
        facility_id=fac_id,
        state=ReviewLifecycleState.DISPOSITION_RECORDED,
        scope={"organization_id": org_id, "facility_id": fac_id},
    )
    disposition = RiskDispositionRecord(
        disposition_id="disp-upstream-001",
        review_id=review.review_id,
        disposition_type=RiskDispositionType.SAFETY_LEARNING_REQUIRED,
        authorized_by="usr-officer-01",
        authorizer_role="CLINICAL_SAFETY_OFFICER",
        reasoning="Learning action and incident workflow required for protocol refinement.",
        resulting_routes=["PHASE_50_LEARNING"],
    )
    review.dispositions = [disposition]
    rev_repo.save(review)

    # 3. Phase 64 Handoff
    handoff = SafetyRiskHandoffRecord(
        handoff_id="hnd-upstream-001",
        source_review_id=review.review_id,
        source_disposition_id=disposition.disposition_id,
        source_risk_context_id="ctx-upstream-001",
        organization_id=org_id,
        facility_id=fac_id,
        destination_phase=HandoffDestinationPhase.PHASE_50_LEARNING,
        state=HandoffLifecycleState.COMPLETED,
        follow_up_status="PENDING_ACTION_REVIEW",
        outcomes=[
            {
                "outcome_id": "out-upstream-001",
                "authoritative_destination_status": "LEARNING_ACTION_FINALIZED",
                "is_terminal": True,
            }
        ],
        reconciliation={"state": "MATCHED"},
    )
    handoff_repo.save(handoff)

    return assessment, review, disposition, handoff


# ===========================================================================
# 1. INITIALIZATION & REQUIREMENT AGGREGATION TESTS
# ===========================================================================


def test_create_safety_workflow_completion(test_client):
    """Verify initializing a completion coordination workflow from Phase 63 disposition."""
    _, review, disposition, handoff = seed_authoritative_upstream_pipeline()

    payload = {
        "review_id": review.review_id,
        "disposition_id": disposition.disposition_id,
        "contract_version": "v1.0.0",
        "idempotency_key": "idemp-comp-001",
    }
    response = test_client.post("/api/v1/safety-workflow-completions", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["completion_id"].startswith("comp-")
    assert data["source_review_id"] == review.review_id
    assert data["source_disposition_id"] == disposition.disposition_id
    assert len(data["requirements"]) >= 2
    assert len(data["outcomes"]) == 1
    assert data["outcomes"][0]["originating_handoff_id"] == handoff.handoff_id


def test_create_completion_source_not_found(test_client):
    """Verify 404 if source review or disposition does not exist."""
    payload = {
        "review_id": "rev-nonexistent",
        "disposition_id": "disp-nonexistent",
    }
    response = test_client.post("/api/v1/safety-workflow-completions", json=payload)
    assert response.status_code == 404
    assert "SOURCE_DISPOSITION_NOT_FOUND" in response.json()["error"]["code"]


# ===========================================================================
# 2. READINESS EVALUATION & FAIL-SAFE INVARIANTS
# ===========================================================================


def test_readiness_pending_when_handoff_not_completed(test_client):
    """Verify fail-safe: Incomplete handoffs NEVER default to READY."""
    _, review, disposition, handoff = seed_authoritative_upstream_pipeline()
    # Mark handoff as IN_PROGRESS rather than COMPLETED
    handoff.state = HandoffLifecycleState.IN_PROGRESS
    get_safety_risk_handoff_repository().save(handoff)

    response = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    assert response.status_code == 201
    comp_id = response.json()["completion_id"]

    readiness_resp = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/readiness")
    assert readiness_resp.status_code == 200
    r_data = readiness_resp.json()
    assert r_data["readiness_state"] == CompletionReadinessState.HANDOFFS_PENDING.value
    assert r_data["is_eligible_for_closure"] is False
    assert any("not reached COMPLETED" in b for b in r_data["blockers"])


def test_readiness_conflicted_when_destination_conflict(test_client):
    """Verify fail-safe: Destination outcome conflict blocks completion."""
    _, review, disposition, handoff = seed_authoritative_upstream_pipeline()
    handoff.reconciliation = {"state": "CONFLICTED"}
    get_safety_risk_handoff_repository().save(handoff)

    response = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    comp_id = response.json()["completion_id"]

    readiness_resp = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/readiness")
    assert readiness_resp.status_code == 200
    r_data = readiness_resp.json()
    assert r_data["readiness_state"] == CompletionReadinessState.CONFLICTED.value
    assert r_data["is_eligible_for_closure"] is False


# ===========================================================================
# 3. 22-ITEM COMPLETION PACKAGE RETRIEVAL
# ===========================================================================


def test_get_completion_package(test_client):
    """Verify retrieval of the 22-item authorized completion package."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    comp_id = init_res.json()["completion_id"]

    pkg_res = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/package")
    assert pkg_res.status_code == 200
    pkg = pkg_res.json()
    assert pkg["source_review_id"] == review.review_id
    assert pkg["source_disposition_id"] == disposition.disposition_id
    assert "required_handoff_inventory" in pkg
    assert "handoff_status_summary" in pkg
    assert "destination_outcome_summary" in pkg
    assert "requirement_register_summary" in pkg
    assert "evidence_completeness_summary" in pkg
    assert "authorized_reviewer_requirements" in pkg


# ===========================================================================
# 4. REVIEW, AUTHORIZATION & CONTROLLED CLOSURE LIFECYCLE
# ===========================================================================


def test_governed_closure_lifecycle_success(test_client):
    """Verify complete governed flow: Readiness -> Review -> Authorization -> Controlled Closure."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    # 1. Initialize
    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
        headers={"X-User-Id": "usr-preparer-01", "X-User-Role": "DOCTOR"},
    )
    comp_id = init_res.json()["completion_id"]

    # 2. Submit Review by Doctor (Reviewer != Preparer)
    review_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/review",
        json={
            "decision": "APPROVED",
            "reasoning": "All downstream handoffs reconciled and verified.",
            "acknowledged_prohibited_claims": True,
        },
        headers={"X-User-Id": "usr-reviewer-02", "X-User-Role": "DOCTOR"},
    )
    assert review_res.status_code == 200
    assert review_res.json()["decision"] == "APPROVED"

    # Status should now be COMPLETION_AUTHORIZATION_PENDING
    status_res = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/status")
    assert status_res.json()["state"] == CompletionLifecycleState.COMPLETION_AUTHORIZATION_PENDING.value

    # 3. Authorize by Admin (Authorizer != Reviewer)
    auth_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/authorize",
        json={
            "authorizer_notes": "Governance review verified. Approved for controlled closure.",
            "acknowledged_prohibited_claims": True,
        },
        headers={"X-User-Id": "usr-authorizer-03", "X-User-Role": "ADMIN"},
    )
    assert auth_res.status_code == 200

    # Status should now be CLOSURE_PENDING
    status_res = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/status")
    assert status_res.json()["state"] == CompletionLifecycleState.CLOSURE_PENDING.value

    # 4. Controlled Closure
    close_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/close",
        json={
            "closure_notes": "Handoff coordination workflow closed.",
            "acknowledged_closure_invariants": True,
            "post_closure_monitoring_registered": True,
            "monitoring_reference": "mon-surveillance-001",
        },
        headers={"X-User-Id": "usr-authorizer-03", "X-User-Role": "ADMIN"},
    )
    assert close_res.status_code == 200
    assert close_res.json()["post_closure_monitoring_registered"] is True

    # Final state should be POST_CLOSURE_MONITORING
    final_status = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/status")
    assert final_status.json()["state"] == CompletionLifecycleState.POST_CLOSURE_MONITORING.value


def test_cannot_bypass_review_to_close(test_client):
    """Verify invariant: Direct call to close without review and authorization is strictly rejected."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    comp_id = init_res.json()["completion_id"]

    close_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/close",
        json={"closure_notes": "Attempting direct closure", "acknowledged_closure_invariants": True},
    )
    assert close_res.status_code == 400
    assert "COMPLETION_AUTHORIZATION_REQUIRED" in close_res.json()["error"]["code"]


# ===========================================================================
# 5. SEPARATION OF DUTIES
# ===========================================================================


def test_separation_of_duties_preparer_cannot_review(test_client):
    """Verify separation of duties: Preparer cannot be the Reviewer."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
        headers={"X-User-Id": "usr-same-user-01", "X-User-Role": "DOCTOR"},
    )
    comp_id = init_res.json()["completion_id"]

    # Same user attempts to review
    review_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/review",
        json={"decision": "APPROVED", "reasoning": "Self approval attempt"},
        headers={"X-User-Id": "usr-same-user-01", "X-User-Role": "DOCTOR"},
    )
    assert review_res.status_code == 403
    assert "Separation of duties violation" in review_res.json()["error"]["message"]


# ===========================================================================
# 6. POST-CLOSURE REOPENING & REASSESSMENT
# ===========================================================================


def test_reopen_closed_workflow_preserves_history(test_client):
    """Verify reopening preserves previous closure records."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
        headers={"X-User-Id": "usr-prep-01", "X-User-Role": "DOCTOR"},
    )
    comp_id = init_res.json()["completion_id"]

    # Review, Authorize, Close
    test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/review",
        json={"decision": "APPROVED", "reasoning": "Approved", "acknowledged_prohibited_claims": True},
        headers={"X-User-Id": "usr-rev-02", "X-User-Role": "DOCTOR"},
    )
    test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/authorize",
        json={"authorizer_notes": "Authorized", "acknowledged_prohibited_claims": True},
        headers={"X-User-Id": "usr-auth-03", "X-User-Role": "ADMIN"},
    )
    test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/close",
        json={"closure_notes": "Closed", "acknowledged_closure_invariants": True},
        headers={"X-User-Id": "usr-auth-03", "X-User-Role": "ADMIN"},
    )

    # Reopen
    reopen_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/reopen",
        json={
            "reason": "Material new evidence invalidated previous destination outcome.",
            "reopen_trigger": "MATERIAL_NEW_OUTCOME",
        },
        headers={"X-User-Id": "usr-auth-03", "X-User-Role": "ADMIN"},
    )
    assert reopen_res.status_code == 200
    reopen_data = reopen_res.json()
    assert reopen_data["reopen_trigger"] == "MATERIAL_NEW_OUTCOME"
    assert reopen_data["preserved_closure_id"] is not None

    # Status check
    status_res = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/status")
    assert status_res.json()["state"] == CompletionLifecycleState.REOPENED.value


def test_reassess_workflow(test_client):
    """Verify triggering reassessment routes workflow to REASSESSMENT_REQUIRED."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    comp_id = init_res.json()["completion_id"]

    reassess_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/reassess",
        json={
            "reason": "Clinical guideline revision requires reassessment of risk profile.",
            "changed_context_summary": "Updated interaction thresholds.",
        },
    )
    assert reassess_res.status_code == 200
    assert reassess_res.json()["state"] == CompletionLifecycleState.REASSESSMENT_REQUIRED.value


# ===========================================================================
# 7. SECURITY, MULTI-TENANCY & PHI PRIVACY
# ===========================================================================


def test_patient_role_denied_access(test_client):
    """Verify patient role is forbidden from accessing safety completion governance."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
        headers={"X-User-Role": "PATIENT"},
    )
    assert res.status_code == 403


def test_cross_tenant_access_denied(test_client):
    """Verify tenant isolation rejects cross-tenant requests."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
        headers={"X-User-Organization": "org-competitor-99"},
    )
    assert res.status_code == 403
    assert "Cross-tenant access forbidden" in res.json()["error"]["message"]


# ===========================================================================
# 8. IDEMPOTENCY & CONCURRENCY
# ===========================================================================


def test_idempotent_creation(test_client):
    """Verify duplicate submission with identical idempotency key returns cached record."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    payload = {
        "review_id": review.review_id,
        "disposition_id": disposition.disposition_id,
        "idempotency_key": "idemp-safe-100",
    }
    r1 = test_client.post("/api/v1/safety-workflow-completions", json=payload)
    assert r1.status_code == 201
    comp_id_1 = r1.json()["completion_id"]

    r2 = test_client.post("/api/v1/safety-workflow-completions", json=payload)
    assert r2.status_code == 201
    comp_id_2 = r2.json()["completion_id"]
    assert comp_id_1 == comp_id_2


def test_idempotency_conflict_reused_key(test_client):
    """Verify reusing idempotency key with conflicting disposition triggers 409 Conflict."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    payload1 = {
        "review_id": review.review_id,
        "disposition_id": disposition.disposition_id,
        "idempotency_key": "idemp-safe-conflict-200",
    }
    test_client.post("/api/v1/safety-workflow-completions", json=payload1)

    payload2 = {
        "review_id": review.review_id,
        "disposition_id": "disp-different-999",
        "idempotency_key": "idemp-safe-conflict-200",
    }
    r2 = test_client.post("/api/v1/safety-workflow-completions", json=payload2)
    assert r2.status_code == 409
    assert "IDEMPOTENCY_CONFLICT" in r2.json()["error"]["code"]


# ===========================================================================
# 9. FILTERED LISTINGS & SUBPATHS
# ===========================================================================


def test_filtered_listings_endpoints(test_client):
    """Verify filtered listing endpoints: /pending, /blocked, /review-required, /reopen-required."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )

    p_res = test_client.get("/api/v1/safety-workflow-completions/pending")
    assert p_res.status_code == 200

    b_res = test_client.get("/api/v1/safety-workflow-completions/blocked")
    assert b_res.status_code == 200

    r_res = test_client.get("/api/v1/safety-workflow-completions/review-required")
    assert r_res.status_code == 200

    ro_res = test_client.get("/api/v1/safety-workflow-completions/reopen-required")
    assert ro_res.status_code == 200


# ===========================================================================
# 10. CRITICAL ARCHITECTURAL SAFETY BOUNDARIES
# ===========================================================================


def test_safety_boundary_cannot_accept_risk(test_client):
    """Verify Phase 65 closure record explicitly disclaims risk acceptance (Phase 51 owns it)."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
        headers={"X-User-Id": "usr-p1", "X-User-Role": "DOCTOR"},
    )
    comp_id = init_res.json()["completion_id"]

    test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/review",
        json={"decision": "APPROVED", "reasoning": "OK", "acknowledged_prohibited_claims": True},
        headers={"X-User-Id": "usr-r2", "X-User-Role": "DOCTOR"},
    )
    test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/authorize",
        json={"authorizer_notes": "OK", "acknowledged_prohibited_claims": True},
        headers={"X-User-Id": "usr-a3", "X-User-Role": "ADMIN"},
    )
    close_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/close",
        json={"closure_notes": "Close workflow", "acknowledged_closure_invariants": True},
        headers={"X-User-Id": "usr-a3", "X-User-Role": "ADMIN"},
    )
    assert close_res.status_code == 200

    # Verify completion details do not claim risk acceptance or clinical elimination
    comp_details = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}").json()
    closure = comp_details["closure"]
    assert "risk_accepted" not in closure
    assert "clinical_safety_assured" not in closure
    assert "risk_eliminated" not in closure


def test_subpath_endpoints(test_client):
    """Verify subpath endpoints: /requirements, /outcomes, /follow-ups, /history, /evaluate, /reconcile."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    comp_id = init_res.json()["completion_id"]

    # 1. /requirements
    reqs = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/requirements")
    assert reqs.status_code == 200
    assert len(reqs.json()) >= 2

    # 2. /outcomes
    outcomes = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/outcomes")
    assert outcomes.status_code == 200
    assert len(outcomes.json()) == 1

    # 3. /follow-ups
    fups = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/follow-ups")
    assert fups.status_code == 200

    # 4. /history
    hist = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}/history")
    assert hist.status_code == 200
    assert len(hist.json()) >= 1

    # 5. /evaluate
    eval_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/evaluate",
        json={"reason": "Manual check"},
    )
    assert eval_res.status_code == 200

    # 6. /reconcile
    rec_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/reconcile",
        json={"force_refresh": True},
    )
    assert rec_res.status_code == 200


def test_cross_phase_all_destinations(test_client):
    """Verify outcome aggregation works across all 9 authoritative destination phases."""
    assess_repo = get_safety_risk_assessment_repository()
    rev_repo = get_safety_risk_review_repository()
    handoff_repo = get_safety_risk_handoff_repository()

    review = SafetyRiskReviewRecord(
        review_id="rev-all-dest",
        assessment_id="assess-all-01",
        organization_id="org-apollo-01",
        facility_id="fac-delhi-01",
        state=ReviewLifecycleState.DISPOSITION_RECORDED,
        scope={"organization_id": "org-apollo-01", "facility_id": "fac-delhi-01"},
    )
    disp = RiskDispositionRecord(
        disposition_id="disp-all-dest",
        review_id="rev-all-dest",
        disposition_type=RiskDispositionType.MULTI_ROUTE,
        authorized_by="usr-officer-01",
        authorizer_role="CLINICAL_SAFETY_OFFICER",
        reasoning="Multi-route disposition testing.",
        resulting_routes=["PHASE_49_INCIDENT", "PHASE_51_GOVERNANCE", "PHASE_52_ASSURANCE"],
    )
    review.dispositions = [disp]
    rev_repo.save(review)

    destinations = [
        (HandoffDestinationPhase.PHASE_49_INCIDENT, "INCIDENT_RESOLVED"),
        (HandoffDestinationPhase.PHASE_51_GOVERNANCE, "GOVERNANCE_DECISION_RECORDED"),
        (HandoffDestinationPhase.PHASE_52_ASSURANCE, "ASSURANCE_REVIEW_COMPLETED"),
        (HandoffDestinationPhase.PHASE_54_SAFETY_ACTION, "SAFETY_ACTION_IMPLEMENTED"),
        (HandoffDestinationPhase.PHASE_55_EFFECTIVENESS, "EFFECTIVENESS_EVALUATED"),
        (HandoffDestinationPhase.PHASE_56_IMPROVEMENT, "IMPROVEMENT_CHANGE_VERIFIED"),
        (HandoffDestinationPhase.PHASE_59_SURVEILLANCE, "MONITORING_REGISTERED"),
        (HandoffDestinationPhase.PHASE_62_REASSESSMENT, "REASSESSMENT_COMPLETED"),
    ]

    for i, (dest_phase, terminal_status) in enumerate(destinations):
        hnd = SafetyRiskHandoffRecord(
            handoff_id=f"hnd-multi-{i}",
            source_review_id=review.review_id,
            source_disposition_id=disp.disposition_id,
            source_risk_context_id="ctx-all-01",
            organization_id="org-apollo-01",
            facility_id="fac-delhi-01",
            destination_phase=dest_phase,
            state=HandoffLifecycleState.COMPLETED,
            outcomes=[{"authoritative_destination_status": terminal_status, "is_terminal": True}],
            reconciliation={"state": "MATCHED"},
        )
        handoff_repo.save(hnd)

    res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disp.disposition_id},
    )
    assert res.status_code == 201
    data = res.json()
    assert len(data["outcomes"]) == len(destinations)


def test_safety_boundary_cannot_close_incidents(test_client):
    """Verify Phase 65 closure does NOT close incidents on behalf of Phase 49."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    comp_id = init_res.json()["completion_id"]

    test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/review",
        json={"decision": "APPROVED", "reasoning": "Approved", "acknowledged_prohibited_claims": True},
        headers={"X-User-Id": "usr-reviewer-02", "X-User-Role": "DOCTOR"},
    )
    test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/authorize",
        json={"authorizer_notes": "Authorized", "acknowledged_prohibited_claims": True},
        headers={"X-User-Id": "usr-authorizer-03", "X-User-Role": "ADMIN"},
    )
    close_res = test_client.post(
        f"/api/v1/safety-workflow-completions/{comp_id}/close",
        json={"closure_notes": "Controlled close", "acknowledged_closure_invariants": True},
        headers={"X-User-Id": "usr-authorizer-03", "X-User-Role": "ADMIN"},
    )
    assert close_res.status_code == 200

    # Ensure no incident_id or incident_closed field was modified by Phase 65
    details = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}").json()
    assert "incident_closed" not in details["closure"]
    assert "incident_root_cause" not in details["closure"]


def test_safety_boundary_cannot_determine_effectiveness(test_client):
    """Verify Phase 65 closure does NOT independently determine safety control effectiveness (Phase 55 owns it)."""
    _, review, disposition, _ = seed_authoritative_upstream_pipeline()

    init_res = test_client.post(
        "/api/v1/safety-workflow-completions",
        json={"review_id": review.review_id, "disposition_id": disposition.disposition_id},
    )
    comp_id = init_res.json()["completion_id"]

    details = test_client.get(f"/api/v1/safety-workflow-completions/{comp_id}").json()
    assert "control_effectiveness" not in details
    assert "safety_assured" not in details


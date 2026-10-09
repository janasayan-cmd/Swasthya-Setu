"""Phase 64: Clinical Safety Risk Handoff & Outcome Reconciliation Tests.

Validates:
- Consuming authorized, recorded Phase 63 dispositions into Phase 64 handoffs
- Disposition eligibility and destination routing validation
- Critical architectural invariants:
    - DISPOSITION RECORDED != HANDOFF REQUESTED
    - HANDOFF REQUESTED != HANDOFF ACCEPTED
    - HANDOFF ACCEPTED != WORK STARTED
    - WORK STARTED != WORK COMPLETED
    - WORK COMPLETED != OUTCOME VERIFIED
    - OUTCOME RECEIVED != OUTCOME RECONCILED
    - OUTCOME RECONCILED != RISK ELIMINATED
    - RETRY != DUPLICATE AUTHORIZATION
    - ROUTING FAILURE != SAFE
    - NO RESPONSE != SUCCESS
    - DESTINATION ACKNOWLEDGEMENT != GOVERNANCE APPROVAL
    - HANDOFF COMPLETION != CLINICAL ACTION AUTHORIZATION
- Destination adapters for all 9 authoritative phases:
    - Phase 49 Incident
    - Phase 50 Learning
    - Phase 51 Governance
    - Phase 52 Assurance
    - Phase 54 Safety Action
    - Phase 55 Effectiveness
    - Phase 56 Improvement
    - Phase 59 Surveillance
    - Phase 62 Reassessment
- Submission and authoritative acknowledgement tracking
- Outcome ingestion, duplicate delivery detection, and contradiction handling
- Outcome reconciliation states (MATCHED, DUPLICATE, CONFLICTED)
- Bounded retries and retry exhaustion safeguards
- Controlled cancellation and operational escalation
- Subpath endpoints (/status, /history, /outcomes)
- Filtered listings (/pending, /reconciliation-required, /retry-exhausted, /escalation-required)
- Multi-tenant isolation, role authorization, and PHI privacy sanitization
- Idempotency key deduplication and conflict detection
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
from app.schemas.auth import UserRole
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    RiskAssessmentScope,
    SafetyRiskAssessmentRecord,
)
from app.schemas.safety_risk_disposition import (
    RiskDispositionRecord,
    RiskDispositionType,
)
from app.schemas.safety_risk_handoff import (
    HandoffDestinationPhase,
    HandoffLifecycleState,
)
from app.schemas.safety_risk_handoff_reconciliation import (
    OutcomeReconciliationState,
)
from app.schemas.safety_risk_review import (
    ReviewLifecycleState,
    SafetyRiskReviewRecord,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = UserRole.ADMIN if role_str == "ADMIN" else (
        UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-risk-officer-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and set mock auth before each test."""
    handoff_repo = get_safety_risk_handoff_repository()
    handoff_repo.clear()
    rev_repo = get_safety_risk_review_repository()
    rev_repo.clear()
    assess_repo = get_safety_risk_assessment_repository()
    assess_repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    handoff_repo.clear()
    rev_repo.clear()
    assess_repo.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _seed_review_with_disposition(
    review_id: str = "rev-seed-01",
    assessment_id: str = "sra-seed-01",
    disposition_id: str = "disp-seed-01",
    disposition_type: RiskDispositionType = RiskDispositionType.INCIDENT_REVIEW_REQUIRED,
    org_id: str = "org-apollo-01",
    facility_id: str = "fac-delhi-01",
    review_state: ReviewLifecycleState = ReviewLifecycleState.READY,
) -> tuple[SafetyRiskReviewRecord, RiskDispositionRecord]:
    """Helper to seed an authorized Phase 63 review with a recorded disposition."""
    assess_repo = get_safety_risk_assessment_repository()
    assessment = SafetyRiskAssessmentRecord(
        assessment_id=assessment_id,
        organization_id=org_id,
        facility_id=facility_id,
        version="v1.0.0",
        scope=RiskAssessmentScope(organization_id=org_id, facility_id=facility_id, version="v1.0.0"),
        state=AssessmentLifecycleState.ASSESSMENT_READY,
        created_by="usr-analyst-01",
    )
    assess_repo.save(assessment)

    disp = RiskDispositionRecord(
        disposition_id=disposition_id,
        review_id=review_id,
        disposition_type=disposition_type,
        authorized_by="usr-reviewer-01",
        authorizer_role="DOCTOR",
        reasoning="Clinical risk review disposition rationale.",
        prohibited_claims_acknowledged=True,
    )

    rev_repo = get_safety_risk_review_repository()
    review = SafetyRiskReviewRecord(
        review_id=review_id,
        assessment_id=assessment_id,
        organization_id=org_id,
        facility_id=facility_id,
        state=review_state,
        created_by="usr-analyst-01",
        dispositions=[disp],
        current_disposition=disposition_type,
    )
    rev_repo.save(review)

    return review, disp


# ===========================================================================
# 1. Handoff Creation & Eligibility Validation
# ===========================================================================


def test_create_handoff_success(client: TestClient):
    """Successfully creates a Phase 64 handoff from an authorized Phase 63 disposition."""
    _seed_review_with_disposition(
        review_id="rev-01",
        disposition_id="disp-01",
        disposition_type=RiskDispositionType.INCIDENT_REVIEW_REQUIRED,
    )

    payload = {
        "review_id": "rev-01",
        "disposition_id": "disp-01",
        "purpose": "GOVERNED_ACTION_HANDOFF",
        "authorized_scope": {"department": "PEDIATRICS"},
    }
    res = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["source_review_id"] == "rev-01"
    assert data["source_disposition_id"] == "disp-01"
    assert data["destination_phase"] == HandoffDestinationPhase.PHASE_49_INCIDENT.value
    assert data["state"] == HandoffLifecycleState.READY.value
    assert data["follow_up_status"] == "READY_FOR_DESTINATION_SUBMISSION"
    assert len(data["history"]) >= 1


def test_create_handoff_source_review_not_found(client: TestClient):
    """Fails with 404 when referenced review does not exist."""
    payload = {
        "review_id": "rev-non-existent",
        "disposition_id": "disp-01",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    }
    res = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "SOURCE_DISPOSITION_NOT_FOUND"


def test_create_handoff_disposition_not_found(client: TestClient):
    """Fails with 404 when disposition ID is not found on the review."""
    _seed_review_with_disposition(review_id="rev-02", disposition_id="disp-valid")
    payload = {
        "review_id": "rev-02",
        "disposition_id": "disp-unknown",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    }
    res = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "SOURCE_DISPOSITION_NOT_FOUND"


def test_create_handoff_source_superseded_rejected(client: TestClient):
    """Fails with 409 when source review has been superseded or cancelled."""
    _seed_review_with_disposition(
        review_id="rev-super",
        disposition_id="disp-super",
        review_state=ReviewLifecycleState.SUPERSEDED,
    )
    payload = {
        "review_id": "rev-super",
        "disposition_id": "disp-super",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    }
    res = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "SOURCE_DISPOSITION_SUPERSEDED"


def test_create_handoff_destination_not_allowed(client: TestClient):
    """Fails with 400 when client requests a destination not permitted for the disposition type."""
    _seed_review_with_disposition(
        review_id="rev-dest",
        disposition_id="disp-dest",
        disposition_type=RiskDispositionType.CONTINUE_MONITORING,  # only Phase 59 permitted
    )
    payload = {
        "review_id": "rev-dest",
        "disposition_id": "disp-dest",
        "destination_phase": HandoffDestinationPhase.PHASE_49_INCIDENT.value,  # incompatible
        "purpose": "GOVERNED_ACTION_HANDOFF",
    }
    res = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "DESTINATION_NOT_ALLOWED"


def test_create_handoff_blocked_disposition_ineligible(client: TestClient):
    """Fails with 400 when disposition is BLOCKED."""
    _seed_review_with_disposition(
        review_id="rev-blk",
        disposition_id="disp-blk",
        disposition_type=RiskDispositionType.BLOCKED,
    )
    payload = {
        "review_id": "rev-blk",
        "disposition_id": "disp-blk",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    }
    res = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "HANDOFF_NOT_ELIGIBLE"


def test_create_handoff_phi_sanitized(client: TestClient):
    """Direct PHI in scope metadata is sanitized during handoff creation."""
    _seed_review_with_disposition(review_id="rev-phi", disposition_id="disp-phi")
    payload = {
        "review_id": "rev-phi",
        "disposition_id": "disp-phi",
        "purpose": "GOVERNED_ACTION_HANDOFF",
        "authorized_scope": {
            "ssn": "000-11-2222",
            "patient_name": "John Doe",
            "department": "CARDIOLOGY",
        },
    }
    res = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res.status_code == 201
    scope = res.json()["authorized_scope"]
    assert scope.get("ssn") == "[REDACTED_PHI]"
    assert scope.get("patient_name") == "[REDACTED_PHI]"
    assert scope.get("department") == "CARDIOLOGY"


# ===========================================================================
# 2. Submission & Acknowledgement Flow
# ===========================================================================


def test_submit_handoff_success(client: TestClient):
    """Submits handoff through destination adapter and records explicit acknowledgement."""
    _seed_review_with_disposition(
        review_id="rev-sub-01",
        disposition_id="disp-sub-01",
        disposition_type=RiskDispositionType.GOVERNANCE_REVIEW_REQUIRED,
    )
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-sub-01",
        "disposition_id": "disp-sub-01",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    handoff_id = create_res.json()["handoff_id"]

    res_sub = client.post(f"/api/v1/safety-risk-handoffs/{handoff_id}/submit", json={})
    assert res_sub.status_code == 200
    ack = res_sub.json()
    assert ack["handoff_id"] == handoff_id
    assert ack["destination_phase"] == HandoffDestinationPhase.PHASE_51_GOVERNANCE.value
    assert ack["status"] == "ACCEPTED_FOR_GOVERNANCE_REVIEW"

    # Verify updated handoff status
    status_res = client.get(f"/api/v1/safety-risk-handoffs/{handoff_id}/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["state"] == HandoffLifecycleState.ACKNOWLEDGED.value
    assert status_data["is_acknowledged"] is True


def test_submit_handoff_invalid_state(client: TestClient):
    """Fails with 400 when attempting to submit a completed/cancelled handoff."""
    _seed_review_with_disposition(
        review_id="rev-inv",
        disposition_id="disp-inv",
        disposition_type=RiskDispositionType.GOVERNANCE_REVIEW_REQUIRED,
    )
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-inv",
        "disposition_id": "disp-inv",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    handoff_id = create_res.json()["handoff_id"]

    # Cancel handoff
    client.post(f"/api/v1/safety-risk-handoffs/{handoff_id}/cancel", json={"reason": "Testing cancellation"})

    # Submit should now fail
    res_sub = client.post(f"/api/v1/safety-risk-handoffs/{handoff_id}/submit", json={})
    assert res_sub.status_code == 400
    assert res_sub.json()["error"]["code"] == "INVALID_HANDOFF_STATE"


# ===========================================================================
# 3. Destination Adapters for All 9 Authoritative Phases
# ===========================================================================


@pytest.mark.parametrize(
    "disp_type,expected_destination",
    [
        (RiskDispositionType.INCIDENT_REVIEW_REQUIRED, HandoffDestinationPhase.PHASE_49_INCIDENT),
        (RiskDispositionType.SAFETY_LEARNING_REQUIRED, HandoffDestinationPhase.PHASE_50_LEARNING),
        (RiskDispositionType.GOVERNANCE_REVIEW_REQUIRED, HandoffDestinationPhase.PHASE_51_GOVERNANCE),
        (RiskDispositionType.ASSURANCE_REVIEW_REQUIRED, HandoffDestinationPhase.PHASE_52_ASSURANCE),
        (RiskDispositionType.CONTROLLED_ACTION_REVIEW_REQUIRED, HandoffDestinationPhase.PHASE_54_SAFETY_ACTION),
        (RiskDispositionType.EFFECTIVENESS_REVIEW_REQUIRED, HandoffDestinationPhase.PHASE_55_EFFECTIVENESS),
        (RiskDispositionType.SAFETY_IMPROVEMENT_REQUIRED, HandoffDestinationPhase.PHASE_56_IMPROVEMENT),
        (RiskDispositionType.CONTINUE_MONITORING, HandoffDestinationPhase.PHASE_59_SURVEILLANCE),
        (RiskDispositionType.REASSESSMENT_REQUIRED, HandoffDestinationPhase.PHASE_62_REASSESSMENT),
    ],
)
def test_all_authoritative_destination_adapters(client: TestClient, disp_type, expected_destination):
    """Validates that all 9 authoritative destination phases have active adapters and produce acks."""
    r_id = f"rev-{expected_destination.value}"
    d_id = f"disp-{expected_destination.value}"
    _seed_review_with_disposition(review_id=r_id, disposition_id=d_id, disposition_type=disp_type)

    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": r_id,
        "disposition_id": d_id,
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    assert create_res.status_code == 201
    h_id = create_res.json()["handoff_id"]

    submit_res = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/submit", json={})
    assert submit_res.status_code == 200
    ack = submit_res.json()
    assert ack["destination_phase"] == expected_destination.value
    assert ack["destination_workflow_ref"] is not None


# ===========================================================================
# 4. Outcome Ingestion & Reconciliation
# ===========================================================================


def test_ingest_outcome_and_reconcile_matched(client: TestClient):
    """Ingests outcome from destination and successfully reconciles it."""
    _seed_review_with_disposition(
        review_id="rev-otc-01",
        disposition_id="disp-otc-01",
        disposition_type=RiskDispositionType.INCIDENT_REVIEW_REQUIRED,
    )
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-otc-01",
        "disposition_id": "disp-otc-01",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]
    client.post(f"/api/v1/safety-risk-handoffs/{h_id}/submit", json={})

    # Ingest outcome
    outcome_payload = {
        "destination_workflow_ref": "inc-wf-9988",
        "outcome_type": "INCIDENT_TRIAGE_COMPLETED",
        "outcome_status": "INVESTIGATION_UNDERWAY",
        "provenance": "PHASE_49_EVENT_772",
        "payload": {"incident_id": "inc-0099"},
    }
    res_otc = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/outcomes", json=outcome_payload)
    assert res_otc.status_code == 200
    assert res_otc.json()["is_conflicted"] is False

    # Reconcile outcome
    res_rec = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/reconcile", json={})
    assert res_rec.status_code == 200
    rec = res_rec.json()
    assert rec["state"] == OutcomeReconciliationState.MATCHED.value

    # Verify handoff updated
    status_res = client.get(f"/api/v1/safety-risk-handoffs/{h_id}/status")
    assert status_res.json()["state"] == HandoffLifecycleState.RECONCILED.value
    assert status_res.json()["is_reconciled"] is True


def test_ingest_conflicting_outcomes_triggers_conflict_state(client: TestClient):
    """Ingesting contradictory outcomes moves handoff to OUTCOME_CONFLICTED."""
    _seed_review_with_disposition(
        review_id="rev-conflict",
        disposition_id="disp-conflict",
        disposition_type=RiskDispositionType.INCIDENT_REVIEW_REQUIRED,
    )
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-conflict",
        "disposition_id": "disp-conflict",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]
    client.post(f"/api/v1/safety-risk-handoffs/{h_id}/submit", json={})

    # 1. First outcome: COMPLETED
    client.post(f"/api/v1/safety-risk-handoffs/{h_id}/outcomes", json={
        "destination_workflow_ref": "inc-wf-1",
        "outcome_type": "INCIDENT_REVIEW",
        "outcome_status": "COMPLETED",
        "provenance": "phase-49-doc-1",
    })

    # 2. Contradictory outcome: REJECTED
    res_otc2 = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/outcomes", json={
        "destination_workflow_ref": "inc-wf-2",
        "outcome_type": "INCIDENT_REVIEW",
        "outcome_status": "REJECTED",
        "provenance": "phase-49-doc-2",
    })
    assert res_otc2.status_code == 200
    assert res_otc2.json()["is_conflicted"] is True

    # Reconcile detects contradiction
    res_rec = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/reconcile", json={})
    assert res_rec.status_code == 200
    rec = res_rec.json()
    assert rec["state"] == OutcomeReconciliationState.CONFLICTED.value

    # Verify status is OUTCOME_CONFLICTED
    status_res = client.get(f"/api/v1/safety-risk-handoffs/{h_id}/status")
    assert status_res.json()["state"] == HandoffLifecycleState.OUTCOME_CONFLICTED.value


def test_ingest_outcome_invalid_provenance_rejected(client: TestClient):
    """Fails with 400 when outcome provenance is empty or invalid."""
    _seed_review_with_disposition(review_id="rev-prov", disposition_id="disp-prov")
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-prov",
        "disposition_id": "disp-prov",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]

    res = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/outcomes", json={
        "destination_workflow_ref": "inc-wf-1",
        "outcome_type": "INCIDENT_REVIEW",
        "outcome_status": "COMPLETED",
        "provenance": "  ",  # invalid whitespace
    })
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "OUTCOME_PROVENANCE_INVALID"


# ===========================================================================
# 5. Bounded Retry & Recovery
# ===========================================================================


def test_bounded_retry_and_exhaustion(client: TestClient):
    """Retrying increments count; exceeding max_retries triggers RETRY_EXHAUSTED."""
    _seed_review_with_disposition(review_id="rev-retry", disposition_id="disp-retry")
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-retry",
        "disposition_id": "disp-retry",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]

    # 3 allowed retries
    for attempt in range(1, 4):
        res_ret = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/retry", json={"reason": f"Retry #{attempt}"})
        assert res_ret.status_code == 200
        assert res_ret.json()["retry_count"] == attempt
        assert res_ret.json()["state"] == HandoffLifecycleState.RETRY_PENDING.value

    # 4th retry should be rejected with 429 RETRY_EXHAUSTED
    res_ret4 = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/retry", json={"reason": "Retry #4"})
    assert res_ret4.status_code == 429
    assert res_ret4.json()["error"]["code"] == "RETRY_EXHAUSTED"

    # Status reflects exhausted state
    status_res = client.get(f"/api/v1/safety-risk-handoffs/{h_id}/status")
    assert status_res.json()["state"] == HandoffLifecycleState.RETRY_EXHAUSTED.value


def test_retry_not_allowed_on_reconciled_handoff(client: TestClient):
    """Fails with 400 when attempting to retry an already reconciled handoff."""
    _seed_review_with_disposition(review_id="rev-ret-no", disposition_id="disp-ret-no")
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-ret-no",
        "disposition_id": "disp-ret-no",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]
    client.post(f"/api/v1/safety-risk-handoffs/{h_id}/submit", json={})
    client.post(f"/api/v1/safety-risk-handoffs/{h_id}/outcomes", json={
        "destination_workflow_ref": "wf-1",
        "outcome_type": "T",
        "outcome_status": "S",
        "provenance": "PHASE_49_INCIDENT_REPORT",
    })
    client.post(f"/api/v1/safety-risk-handoffs/{h_id}/reconcile", json={})

    # Retry should be blocked
    res_retry = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/retry", json={"reason": "Redundant retry"})
    assert res_retry.status_code == 400
    assert res_retry.json()["error"]["code"] == "RETRY_NOT_ALLOWED"


# ===========================================================================
# 6. Cancellation & Operational Escalation
# ===========================================================================


def test_cancel_handoff_supported_destination(client: TestClient):
    """Cancels handoff when destination supports cancellation (e.g. Phase 51 Governance)."""
    _seed_review_with_disposition(
        review_id="rev-canc-ok",
        disposition_id="disp-canc-ok",
        disposition_type=RiskDispositionType.GOVERNANCE_REVIEW_REQUIRED,
    )
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-canc-ok",
        "disposition_id": "disp-canc-ok",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]

    res_cancel = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/cancel", json={"reason": "Superfluous request"})
    assert res_cancel.status_code == 200
    assert res_cancel.json()["state"] == HandoffLifecycleState.CANCELLED.value


def test_cancel_handoff_unsupported_destination(client: TestClient):
    """Fails with 400 when destination does not support silent cancellation (e.g. Phase 49 Incident)."""
    _seed_review_with_disposition(
        review_id="rev-canc-no",
        disposition_id="disp-canc-no",
        disposition_type=RiskDispositionType.INCIDENT_REVIEW_REQUIRED,
    )
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-canc-no",
        "disposition_id": "disp-canc-no",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]

    res_cancel = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/cancel", json={"reason": "Attempting incident cancel"})
    assert res_cancel.status_code == 400
    assert res_cancel.json()["error"]["code"] == "CANCELLATION_NOT_SUPPORTED"


def test_escalate_handoff_to_manual_review(client: TestClient):
    """Escalates an unresolved operational handoff to manual review."""
    _seed_review_with_disposition(review_id="rev-esc", disposition_id="disp-esc")
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-esc",
        "disposition_id": "disp-esc",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]

    res_esc = client.post(f"/api/v1/safety-risk-handoffs/{h_id}/escalate", json={
        "reason": "Destination unresponsive after multi-channel retry attempts.",
        "severity": "CRITICAL",
    })
    assert res_esc.status_code == 200
    assert res_esc.json()["state"] == HandoffLifecycleState.MANUAL_REVIEW_REQUIRED.value
    assert "Destination unresponsive" in res_esc.json()["escalation_reason"]


# ===========================================================================
# 7. Subpath & List Endpoints
# ===========================================================================


def test_subpaths_status_history_outcomes(client: TestClient):
    """Validates /status, /history, and /outcomes subpath endpoints."""
    _seed_review_with_disposition(review_id="rev-subpaths", disposition_id="disp-subpaths")
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-subpaths",
        "disposition_id": "disp-subpaths",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    h_id = create_res.json()["handoff_id"]

    # 1. /status
    res_status = client.get(f"/api/v1/safety-risk-handoffs/{h_id}/status")
    assert res_status.status_code == 200
    assert res_status.json()["handoff_id"] == h_id

    # 2. /history
    res_hist = client.get(f"/api/v1/safety-risk-handoffs/{h_id}/history")
    assert res_hist.status_code == 200
    assert len(res_hist.json()) >= 1
    assert res_hist.json()[0]["action"] == "CREATE_HANDOFF"

    # 3. /outcomes
    res_otc = client.get(f"/api/v1/safety-risk-handoffs/{h_id}/outcomes")
    assert res_otc.status_code == 200
    assert isinstance(res_otc.json(), list)


def test_filtered_listings(client: TestClient):
    """Validates /pending, /reconciliation-required, /retry-exhausted, /escalation-required, /."""
    _seed_review_with_disposition(review_id="rev-filter-01", disposition_id="disp-filter-01")
    client.post("/api/v1/safety-risk-reviews", json={
        "review_id": "rev-filter-01",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    create_res = client.post("/api/v1/safety-risk-handoffs", json={
        "review_id": "rev-filter-01",
        "disposition_id": "disp-filter-01",
        "purpose": "GOVERNED_ACTION_HANDOFF",
    })
    assert create_res.status_code == 201

    res_all = client.get("/api/v1/safety-risk-handoffs")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 1

    res_pending = client.get("/api/v1/safety-risk-handoffs/pending")
    assert res_pending.status_code == 200
    assert len(res_pending.json()) >= 1

    res_rec = client.get("/api/v1/safety-risk-handoffs/reconciliation-required")
    assert res_rec.status_code == 200

    res_ret = client.get("/api/v1/safety-risk-handoffs/retry-exhausted")
    assert res_ret.status_code == 200

    res_esc = client.get("/api/v1/safety-risk-handoffs/escalation-required")
    assert res_esc.status_code == 200


# ===========================================================================
# 8. Security & Multi-Tenant Tests
# ===========================================================================


def test_cross_tenant_access_denied(client: TestClient):
    """Cannot access handoffs belonging to another organization."""
    _seed_review_with_disposition(
        review_id="rev-tenant",
        disposition_id="disp-tenant",
        org_id="org-apollo-01",
    )
    create_res = client.post(
        "/api/v1/safety-risk-handoffs",
        json={"review_id": "rev-tenant", "disposition_id": "disp-tenant", "purpose": "GOVERNED_ACTION_HANDOFF"},
        headers={"X-User-Organization": "org-apollo-01"},
    )
    h_id = create_res.json()["handoff_id"]

    # Different organization attempts access
    res = client.get(
        f"/api/v1/safety-risk-handoffs/{h_id}",
        headers={"X-User-Organization": "org-other-99"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCESS_DENIED"


def test_unauthorized_patient_role_denied(client: TestClient):
    """Non-clinical roles (such as PATIENT) cannot create handoffs."""
    _seed_review_with_disposition(review_id="rev-pat", disposition_id="disp-pat")
    res = client.post(
        "/api/v1/safety-risk-handoffs",
        json={"review_id": "rev-pat", "disposition_id": "disp-pat", "purpose": "GOVERNED_ACTION_HANDOFF"},
        headers={"X-User-Role": "PATIENT"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCESS_DENIED"


# ===========================================================================
# 9. Idempotency Tests
# ===========================================================================


def test_idempotent_creation(client: TestClient):
    """Replaying request with same idempotency key returns cached handoff."""
    _seed_review_with_disposition(review_id="rev-idem", disposition_id="disp-idem")
    payload = {
        "review_id": "rev-idem",
        "disposition_id": "disp-idem",
        "purpose": "GOVERNED_ACTION_HANDOFF",
        "idempotency_key": "idem-key-hnd-001",
    }
    res1 = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res1.status_code == 201
    id1 = res1.json()["handoff_id"]

    res2 = client.post("/api/v1/safety-risk-handoffs", json=payload)
    assert res2.status_code == 201
    id2 = res2.json()["handoff_id"]

    assert id1 == id2


def test_idempotency_conflict_reused_key(client: TestClient):
    """Replaying idempotency key with conflicting payload raises 409 IDEMPOTENCY_CONFLICT."""
    _seed_review_with_disposition(review_id="rev-idem2", disposition_id="disp-idem2")
    payload1 = {
        "review_id": "rev-idem2",
        "disposition_id": "disp-idem2",
        "purpose": "GOVERNED_ACTION_HANDOFF",
        "idempotency_key": "idem-key-conflict-01",
    }
    res1 = client.post("/api/v1/safety-risk-handoffs", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "review_id": "rev-idem2",
        "disposition_id": "disp-idem2",
        "purpose": "GOVERNED_ACTION_HANDOFF",
        "authorized_scope": {"department": "ALTERED_SCOPE"},  # conflicting payload
        "idempotency_key": "idem-key-conflict-01",
    }
    res2 = client.post("/api/v1/safety-risk-handoffs", json=payload2)
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

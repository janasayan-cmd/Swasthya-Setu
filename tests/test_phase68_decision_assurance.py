"""Phase 68: Clinical Safety Governance Decision Assurance & Traceability Tests.

Validates:
- Scenario 1: Decision registration, retrieval & tenant-scoped listing
- Scenario 2: Full Decision Assurance Run - Clean Pass (VERIFIED) & sub-aspect endpoints
- Scenario 3: Decision Provenance Failure (PROVENANCE_INCOMPLETE)
- Scenario 4: Historical Authorization Missing (AUTHORIZATION_UNVERIFIABLE) & queue lookup
- Scenario 5: Revoked/Invalid Historical Authorization (AUTHORIZATION_INVALID)
- Scenario 6: Separation-of-Duties Violation (Self-Approval Detected)
- Scenario 7: Policy Version & Temporal Applicability Window Mismatch (POLICY_MISMATCH)
- Scenario 8: Evidence Assurance Status Taxonomy (EVIDENCE_INCOMPLETE, EVIDENCE_CONFLICTED)
- Scenario 9: Cross-Workflow Inconsistency & Contradiction Detection (DECISION_CONFLICT)
- Scenario 10: Assurance Finding Review & Governed Resolution
- Scenario 11: Governed Decision Correction & Revocation Review Coordination
- Scenario 12: Aggregated Summary Reporting & Specialized Queue Filtering
- Scenario 13: Tenant Isolation & Patient Role Access Restrictions
- Scenario 14: Verification Idempotency Enforcement
"""

from datetime import datetime, timedelta, timezone
import os

# Set testing environment variables before importing app
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_decision_assurance_repository import (
    get_governance_decision_assurance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.decision_assurance import (
    AssuranceLifecycleState,
    AuthorizationVerificationStatus,
    DecisionSourcePhase,
    EvidenceAssuranceStatus,
    SeparationOfDutiesStatus,
)
from app.schemas.decision_assurance_finding import (
    AssuranceFindingCategory,
    FindingReviewOutcome,
    FindingSeverity,
)
from app.schemas.decision_correction_coordination import (
    CorrectionRequestStatus,
)
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = (
        UserRole.ADMIN
        if role_str == "ADMIN"
        else (UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT)
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-gov-lead-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and configure auth dependency override."""
    repo = get_governance_decision_assurance_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    repo.clear()


@pytest.fixture
def test_client():
    return TestClient(app)


# ===========================================================================
# Scenario 1: Decision Registration, Retrieval & Listing
# ===========================================================================

def test_scenario_1_decision_registration_and_retrieval(test_client: TestClient):
    """Test registering an authoritative governance decision reference and retrieving it."""
    payload = {
        "source_phase": "PHASE_63",
        "source_record_id": "srr-risk-review-101",
        "source_version": "v1.2.0",
        "decision_type": "RISK_DISPOSITION",
        "decision_title": "Authorized Clinical Safety Disposition - Anaphylaxis Signal",
        "decision_outcome": "APPROVED_WITH_CONDITIONS",
        "patient_id": "pat-cardio-99",
        "decided_by_id": "usr-lead-clinician-01",
        "decided_by_role": "DOCTOR",
        "decided_by_scope": "facility",
        "decided_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "requester_id": "usr-clinical-analyst-02",
        "approver_id": "usr-governance-director-03",
        "authorization_evidence_ref": "auth-sig-token-abc12345",
        "policy_reference": "pol-clinical-safety-2026",
        "policy_version": "v2.1.0",
        "policy_effective_date": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "supporting_evidence_refs": ["ev-lab-result-55", "ev-trial-data-77"],
        "rationale": "Clinical risk disposition reviewed against updated 2026 protocol.",
    }

    res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "decision_id" in data
    assert data["source_phase"] == "PHASE_63"
    assert data["decision_outcome"] == "APPROVED_WITH_CONDITIONS"
    assert data["organization_id"] == "org-apollo-01"

    decision_id = data["decision_id"]

    # Retrieve decision
    get_res = test_client.get(f"/api/v1/governance-decision-assurance/decisions/{decision_id}")
    assert get_res.status_code == 200
    assert get_res.json()["decision_id"] == decision_id

    # List decisions
    list_res = test_client.get("/api/v1/governance-decision-assurance/decisions?source_phase=PHASE_63")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["decision_id"] == decision_id


# ===========================================================================
# Scenario 2: Full Decision Assurance Run - Clean Pass (VERIFIED)
# ===========================================================================

def test_scenario_2_full_decision_assurance_clean_pass(test_client: TestClient):
    """Test full evaluation pipeline where all dimensions pass, yielding VERIFIED."""
    # 1. Register compliant decision
    reg_payload = {
        "source_phase": "PHASE_65",
        "source_record_id": "wfc-completion-coord-200",
        "source_version": "v1.0.0",
        "decision_type": "COMPLETION_AUTHORIZATION",
        "decision_title": "Sign-off on Patient Handoff Follow-up Closure",
        "decision_outcome": "COMPLETED",
        "patient_id": "pat-icu-88",
        "decided_by_id": "usr-senior-doc-05",
        "decided_by_role": "DOCTOR",
        "decided_by_scope": "facility",
        "decided_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "requester_id": "usr-nurse-coord-06",
        "approver_id": "usr-senior-doc-05",
        "authorization_evidence_ref": "auth-sig-valid-998877",
        "policy_reference": "pol-handoff-completion-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        "supporting_evidence_refs": ["ev-discharge-summary-01"],
        "rationale": "Follow-up verification confirmed all clinical outcomes stabilized.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    decision_id = reg_res.json()["decision_id"]

    # 2. Trigger verification
    verify_payload = {
        "policy_version": "v1.0.0",
        "idempotency_key": "idem-key-test-001",
        "correlation_id": "corr-pass-001",
    }
    verify_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json=verify_payload,
    )
    assert verify_res.status_code == 200
    assurance = verify_res.json()
    assert assurance["lifecycle_state"] == "VERIFIED"
    assert assurance["provenance_verified"] is True
    assert assurance["authorization_status"] == "AUTHORIZED"
    assert assurance["separation_of_duties_status"] == "COMPLIANT"
    assert assurance["policy_compliance_verified"] is True
    assert assurance["evidence_assurance_status"] == "EVIDENCE_VALID"
    assert assurance["cross_workflow_consistent"] is True
    assert assurance["findings_count"] == 0

    # 3. Check sub-aspect inspection endpoints
    prov_res = test_client.get(f"/api/v1/governance-decision-assurance/decisions/{decision_id}/provenance")
    assert prov_res.status_code == 200
    assert prov_res.json()["provenance_verified"] is True

    auth_res = test_client.get(f"/api/v1/governance-decision-assurance/decisions/{decision_id}/authorization")
    assert auth_res.status_code == 200
    assert auth_res.json()["authorization_status"] == "AUTHORIZED"

    pol_res = test_client.get(f"/api/v1/governance-decision-assurance/decisions/{decision_id}/policy-compliance")
    assert pol_res.status_code == 200
    assert pol_res.json()["policy_compliance_verified"] is True

    ev_res = test_client.get(f"/api/v1/governance-decision-assurance/decisions/{decision_id}/evidence-integrity")
    assert ev_res.status_code == 200
    assert ev_res.json()["evidence_assurance_status"] == "EVIDENCE_VALID"


# ===========================================================================
# Scenario 3: Provenance Failure (PROVENANCE_INCOMPLETE)
# ===========================================================================

def test_scenario_3_decision_provenance_failure(test_client: TestClient):
    """Test verification failure when decision timestamp is in the future."""
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    reg_payload = {
        "source_phase": "PHASE_51",
        "source_record_id": "ra-risk-accept-300",
        "decision_type": "RISK_ACCEPTANCE",
        "decision_title": "Premature Future Decision",
        "decision_outcome": "ACCEPTED",
        "decided_by_id": "usr-admin-01",
        "decided_by_role": "ADMIN",
        "decided_at": future_time,
        "policy_reference": "pol-risk-v1",
        "policy_version": "v1.0.0",
        "supporting_evidence_refs": ["ev-baseline-01"],
        "rationale": "Future dated risk acceptance.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    decision_id = reg_res.json()["decision_id"]

    verify_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json={"policy_version": "v1.0.0"},
    )
    assert verify_res.status_code == 200
    assurance = verify_res.json()
    assert assurance["lifecycle_state"] == "PROVENANCE_INCOMPLETE"
    assert assurance["provenance_verified"] is False
    assert assurance["findings_count"] >= 1


# ===========================================================================
# Scenario 4: Missing Historical Authorization (AUTHORIZATION_UNVERIFIABLE)
# ===========================================================================

def test_scenario_4_historical_authorization_missing(test_client: TestClient):
    """Test that missing authorization evidence flags AUTHORIZATION_UNVERIFIABLE without assuming authority."""
    reg_payload = {
        "source_phase": "PHASE_58",
        "source_record_id": "ver-rollout-closure-400",
        "decision_type": "GOVERNED_CLOSURE",
        "decision_title": "Closure Without Auth Token Recorded",
        "decision_outcome": "CLOSED",
        "decided_by_id": "usr-qa-lead-09",
        "decided_by_role": "DOCTOR",
        "decided_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "authorization_evidence_ref": None,  # Missing historical evidence
        "policy_reference": "pol-closure-v1",
        "policy_version": "v1.0.0",
        "supporting_evidence_refs": ["ev-qa-report-01"],
        "rationale": "Closure was recorded but authorization credential token was omitted.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    decision_id = reg_res.json()["decision_id"]

    verify_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json={},
    )
    assert verify_res.status_code == 200
    assurance = verify_res.json()
    assert assurance["lifecycle_state"] == "AUTHORIZATION_UNVERIFIABLE"
    assert assurance["authorization_status"] == "HISTORICAL_UNVERIFIABLE"

    # Verify presence in specialized queue
    q_res = test_client.get("/api/v1/governance-decision-assurance/queues/authorization-unverifiable")
    assert q_res.status_code == 200
    items = q_res.json()
    assert any(item["decision_id"] == decision_id for item in items)


# ===========================================================================
# Scenario 5: Revoked or Invalid Historical Authorization (AUTHORIZATION_INVALID)
# ===========================================================================

def test_scenario_5_revoked_historical_authorization(test_client: TestClient):
    """Test that revoked credential references yield AUTHORIZATION_INVALID."""
    reg_payload = {
        "source_phase": "PHASE_54",
        "source_record_id": "act-orchestration-500",
        "decision_type": "ACTION_APPROVAL",
        "decision_title": "Approval with Revoked Credential",
        "decision_outcome": "APPROVED",
        "decided_by_id": "usr-former-staff-99",
        "decided_by_role": "STAFF",
        "decided_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "authorization_evidence_ref": "auth-token-revoked-by-admin",
        "policy_reference": "pol-action-v1",
        "policy_version": "v1.0.0",
        "supporting_evidence_refs": ["ev-action-plan-01"],
        "rationale": "Approval under an invalid/revoked credential token.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    decision_id = reg_res.json()["decision_id"]

    verify_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json={},
    )
    assert verify_res.status_code == 200
    assurance = verify_res.json()
    assert assurance["lifecycle_state"] == "AUTHORIZATION_INVALID"
    assert assurance["authorization_status"] == "REVOKED"


# ===========================================================================
# Scenario 6: Separation-of-Duties Violation (Self-Approval Detected)
# ===========================================================================

def test_scenario_6_separation_of_duties_self_approval(test_client: TestClient):
    """Test detection of self-approval breach when requester and approver are identical."""
    reg_payload = {
        "source_phase": "PHASE_51",
        "source_record_id": "ra-risk-accept-600",
        "decision_type": "RISK_ACCEPTANCE",
        "decision_title": "Self-Approved Risk Acceptance",
        "decision_outcome": "ACCEPTED",
        "decided_by_id": "usr-doctor-sam-01",
        "decided_by_role": "DOCTOR",
        "decided_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        "requester_id": "usr-doctor-sam-01",
        "approver_id": "usr-doctor-sam-01",  # Self-approval!
        "authorization_evidence_ref": "auth-sig-sam-01",
        "policy_reference": "pol-risk-accept-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
        "supporting_evidence_refs": ["ev-self-assessment-01"],
        "rationale": "Physician requested and self-approved exemption.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    decision_id = reg_res.json()["decision_id"]

    verify_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json={},
    )
    assert verify_res.status_code == 200
    assurance = verify_res.json()
    assert assurance["lifecycle_state"] == "SEPARATION_OF_DUTIES_VIOLATION"
    assert assurance["separation_of_duties_status"] == "SELF_APPROVAL_DETECTED"


# ===========================================================================
# Scenario 7: Policy Version & Temporal Applicability Window Mismatch
# ===========================================================================

def test_scenario_7_policy_temporal_window_mismatch(test_client: TestClient):
    """Test failure when decision pre-dates the effective date of the referenced policy."""
    now = datetime.now(timezone.utc)
    decided_at = (now - timedelta(days=40)).isoformat()
    policy_effective = (now - timedelta(days=10)).isoformat()  # Policy effective 30 days AFTER decision!

    reg_payload = {
        "source_phase": "PHASE_67",
        "source_record_id": "gesc-decision-700",
        "decision_type": "ESCALATION_RESOLUTION",
        "decision_title": "Decision Pre-dating Policy Enactment",
        "decision_outcome": "RESOLVED",
        "decided_by_id": "usr-director-01",
        "decided_by_role": "ADMIN",
        "decided_at": decided_at,
        "authorization_evidence_ref": "auth-token-valid-777",
        "policy_reference": "pol-future-standards-2027",
        "policy_version": "v3.0.0",
        "policy_effective_date": policy_effective,
        "supporting_evidence_refs": ["ev-resolution-doc-01"],
        "rationale": "Resolution referencing future governance policy.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    decision_id = reg_res.json()["decision_id"]

    verify_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json={"policy_version": "v3.0.0"},
    )
    assert verify_res.status_code == 200
    assurance = verify_res.json()
    assert assurance["lifecycle_state"] == "POLICY_MISMATCH"
    assert assurance["policy_compliance_verified"] is False

    # Check policy mismatch queue
    q_res = test_client.get("/api/v1/governance-decision-assurance/queues/policy-mismatch")
    assert q_res.status_code == 200
    items = q_res.json()
    assert any(item["decision_id"] == decision_id for item in items)


# ===========================================================================
# Scenario 8: Evidence Assurance Status Taxonomy
# ===========================================================================

def test_scenario_8_evidence_assurance_taxonomy(test_client: TestClient):
    """Test evidence assurance taxonomy for missing and invalidated clinical evidence."""
    # Case A: Missing evidence
    now = datetime.now(timezone.utc)
    reg_missing = {
        "source_phase": "PHASE_63",
        "source_record_id": "srr-risk-801",
        "decision_type": "RISK_DISPOSITION",
        "decision_title": "Decision Lacking Required Clinical Evidence",
        "decision_outcome": "RISK_ACCEPTED",
        "decided_by_id": "usr-clinician-02",
        "decided_by_role": "DOCTOR",
        "decided_at": (now - timedelta(hours=5)).isoformat(),
        "authorization_evidence_ref": "auth-sig-valid-801",
        "policy_reference": "pol-risk-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (now - timedelta(days=5)).isoformat(),
        "supporting_evidence_refs": [],  # Completely missing
        "rationale": "Risk accepted without supporting diagnostic evidence.",
    }
    res_a = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_missing)
    dec_a_id = res_a.json()["decision_id"]

    ver_a = test_client.post(f"/api/v1/governance-decision-assurance/decisions/{dec_a_id}/verify", json={})
    assert ver_a.status_code == 200
    assert ver_a.json()["lifecycle_state"] == "EVIDENCE_INCOMPLETE"
    assert ver_a.json()["evidence_assurance_status"] == "EVIDENCE_MISSING"

    # Case B: Invalidated evidence
    reg_invalidated = {
        "source_phase": "PHASE_63",
        "source_record_id": "srr-risk-802",
        "decision_type": "RISK_DISPOSITION",
        "decision_title": "Decision Based on Retracted Evidence",
        "decision_outcome": "APPROVED",
        "decided_by_id": "usr-clinician-02",
        "decided_by_role": "DOCTOR",
        "decided_at": (now - timedelta(hours=5)).isoformat(),
        "authorization_evidence_ref": "auth-sig-valid-802",
        "policy_reference": "pol-risk-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (now - timedelta(days=5)).isoformat(),
        "supporting_evidence_refs": ["ev-lab-invalidated-by-pathology"],
        "rationale": "Disposition referencing subsequently invalidated test.",
    }
    res_b = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_invalidated)
    dec_b_id = res_b.json()["decision_id"]

    ver_b = test_client.post(f"/api/v1/governance-decision-assurance/decisions/{dec_b_id}/verify", json={})
    assert ver_b.status_code == 200
    assert ver_b.json()["lifecycle_state"] == "EVIDENCE_CONFLICTED"
    assert ver_b.json()["evidence_assurance_status"] == "EVIDENCE_INVALIDATED"


# ===========================================================================
# Scenario 9: Cross-Workflow Decision Consistency & Contradiction Detection
# ===========================================================================

def test_scenario_9_cross_workflow_decision_conflict(test_client: TestClient):
    """Test contradictory outcome detection across workflows (e.g. CLOSED vs CRITICAL_RISK_ACTIVE)."""
    now = datetime.now(timezone.utc)

    # 1. Register prior decision in Phase 49 stating active critical risk
    prior_payload = {
        "source_phase": "PHASE_49",
        "source_record_id": "inc-incident-901",
        "decision_type": "INCIDENT_CLASSIFICATION",
        "decision_title": "Active Critical Safety Incident",
        "decision_outcome": "CRITICAL_RISK_ACTIVE",
        "decided_by_id": "usr-safety-lead-01",
        "decided_by_role": "DOCTOR",
        "decided_at": (now - timedelta(hours=6)).isoformat(),
        "authorization_evidence_ref": "auth-sig-901",
        "policy_reference": "pol-incident-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (now - timedelta(days=20)).isoformat(),
        "supporting_evidence_refs": ["ev-telemetry-01"],
        "rationale": "High-urgency telemetry anomaly classified as active critical risk.",
    }
    prior_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=prior_payload)
    prior_dec_id = prior_res.json()["decision_id"]

    # 2. Register contradictory decision in Phase 58 attempting to close without resolving incident
    contradictory_payload = {
        "source_phase": "PHASE_58",
        "source_record_id": "ver-closure-902",
        "decision_type": "GOVERNED_CLOSURE",
        "decision_title": "Premature Closure with Contradictory Upstream Incident",
        "decision_outcome": "CLOSED",
        "decided_by_id": "usr-release-admin-02",
        "decided_by_role": "ADMIN",
        "decided_at": (now - timedelta(hours=2)).isoformat(),
        "authorization_evidence_ref": "auth-sig-902",
        "policy_reference": "pol-closure-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (now - timedelta(days=20)).isoformat(),
        "supporting_evidence_refs": ["ev-checklist-01"],
        "related_decision_ids": [prior_dec_id],
        "rationale": "Rollout closed administratively while active incident remains.",
    }
    con_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=contradictory_payload)
    con_dec_id = con_res.json()["decision_id"]

    # 3. Verify contradictory decision
    ver_res = test_client.post(f"/api/v1/governance-decision-assurance/decisions/{con_dec_id}/verify", json={})
    assert ver_res.status_code == 200
    assurance = ver_res.json()
    assert assurance["lifecycle_state"] == "DECISION_CONFLICT"
    assert assurance["cross_workflow_consistent"] is False

    # Check consistency checks endpoint
    chk_res = test_client.get(f"/api/v1/governance-decision-assurance/decisions/{con_dec_id}/consistency-checks")
    assert chk_res.status_code == 200
    checks = chk_res.json()
    assert len(checks) >= 1
    assert checks[0]["is_consistent"] is False
    assert checks[0]["conflict_type"] == "CONTRADICTORY_OUTCOME"

    # Check conflicts queue
    q_res = test_client.get("/api/v1/governance-decision-assurance/queues/decision-conflicts")
    assert q_res.status_code == 200
    items = q_res.json()
    assert any(item["decision_id"] == con_dec_id for item in items)


# ===========================================================================
# Scenario 10: Finding Review and Governed Resolution
# ===========================================================================

def test_scenario_10_finding_review_and_resolution(test_client: TestClient):
    """Test specialist review and administrative/doctor resolution of assurance findings."""
    # 1. Trigger verification that yields findings (e.g. missing auth)
    now = datetime.now(timezone.utc)
    reg_payload = {
        "source_phase": "PHASE_64",
        "source_record_id": "sho-handoff-1001",
        "decision_type": "HANDOFF_DISPOSITION",
        "decision_title": "Handoff Finding Test",
        "decision_outcome": "RECONCILED",
        "decided_by_id": "usr-doc-10",
        "decided_by_role": "DOCTOR",
        "decided_at": (now - timedelta(hours=1)).isoformat(),
        "authorization_evidence_ref": None,  # Will produce finding
        "policy_reference": "pol-handoff-v1",
        "policy_version": "v1.0.0",
        "supporting_evidence_refs": ["ev-summary-01"],
        "rationale": "Handoff disposition lacking historical credential ref.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    dec_id = reg_res.json()["decision_id"]

    test_client.post(f"/api/v1/governance-decision-assurance/decisions/{dec_id}/verify", json={})

    # 2. Retrieve findings
    findings_res = test_client.get("/api/v1/governance-decision-assurance/findings")
    assert findings_res.status_code == 200
    findings = findings_res.json()
    assert len(findings) >= 1
    finding_id = findings[0]["finding_id"]

    # 3. Specialist review on finding
    rev_payload = {
        "review_outcome": "CONFIRMED_BREACH",
        "review_rationale": "Historical credential token missing from audit log. Confirmed breach of Phase 64 protocol.",
        "recommended_action": "Request authoritative decision owner provide signing evidence.",
    }
    rev_res = test_client.post(
        f"/api/v1/governance-decision-assurance/findings/{finding_id}/review",
        json=rev_payload,
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["review_outcome"] == "CONFIRMED_BREACH"

    # 4. Resolve finding with documented rationale
    res_payload = {
        "resolution_rationale": "Authoritative owner located archived key from HSM logs. Audit confirmed valid.",
        "supporting_evidence_refs": ["ev-hsm-log-entry-999"],
    }
    res_res = test_client.post(
        f"/api/v1/governance-decision-assurance/findings/{finding_id}/resolve",
        json=res_payload,
    )
    assert res_res.status_code == 200
    assert res_res.json()["is_resolved"] is True
    assert res_res.json()["resolved_by"] == "usr-gov-lead-01"


# ===========================================================================
# Scenario 11: Governed Decision Correction & Revocation Review Coordination
# ===========================================================================

def test_scenario_11_correction_and_revocation_coordination(test_client: TestClient):
    """Test submitting correction and revocation review requests and receiving owner responses."""
    now = datetime.now(timezone.utc)
    reg_payload = {
        "source_phase": "PHASE_63",
        "source_record_id": "srr-review-1101",
        "source_version": "v1.0.0",
        "decision_type": "RISK_DISPOSITION",
        "decision_title": "Flawed Risk Disposition",
        "decision_outcome": "APPROVED",
        "decided_by_id": "usr-doc-22",
        "decided_by_role": "DOCTOR",
        "decided_at": (now - timedelta(hours=4)).isoformat(),
        "authorization_evidence_ref": "auth-sig-token-1101",
        "policy_reference": "pol-risk-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (now - timedelta(days=15)).isoformat(),
        "supporting_evidence_refs": ["ev-record-01"],
        "rationale": "Disposition rendered with outdated dosage formula.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    dec_id = reg_res.json()["decision_id"]

    # 1. Submit Correction Request
    corr_payload = {
        "reason": "Dosage formula in supporting evidence was superseded by revised 2026 guidelines.",
        "suggested_correction": "Amend disposition to APPROVED_WITH_CONDITIONS specifying weight-adjusted dosage.",
        "finding_refs": ["gfind-test-01"],
    }
    corr_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{dec_id}/correction-requests",
        json=corr_payload,
    )
    assert corr_res.status_code == 201
    corr_data = corr_res.json()
    assert corr_data["request_type"] == "CORRECTION"
    assert corr_data["status"] == "SUBMITTED"
    assert corr_data["target_phase"] == "PHASE_63"
    request_id = corr_data["request_id"]

    # 2. Authoritative owner responds to correction request
    respond_payload = {
        "status": "ACCEPTED_AND_AMENDED",
        "response_notes": "Phase 63 clinical safety committee reconvened and accepted recommended amendment.",
        "authoritative_action_taken": "AMENDED",
        "updated_record_version": "v1.1.0",
    }
    resp_res = test_client.post(
        f"/api/v1/governance-decision-assurance/correction-requests/{request_id}/respond",
        json=respond_payload,
    )
    assert resp_res.status_code == 200
    updated_corr = resp_res.json()
    assert updated_corr["status"] == "ACCEPTED_AND_AMENDED"
    assert updated_corr["authoritative_action_taken"] == "AMENDED"
    assert updated_corr["updated_record_version"] == "v1.1.0"

    # 3. Submit Revocation Review Request
    rev_payload = {
        "reason": "Severe contraindication discovered post-decision.",
        "revocation_grounds": "Safety signal escalated to critical level.",
    }
    rev_res = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{dec_id}/revocation-review-requests",
        json=rev_payload,
    )
    assert rev_res.status_code == 201
    assert rev_res.json()["request_type"] == "REVOCATION_REVIEW"

    # 4. List all correction/revocation requests for decision
    list_corr_res = test_client.get(
        f"/api/v1/governance-decision-assurance/decisions/{dec_id}/correction-requests"
    )
    assert list_corr_res.status_code == 200
    assert len(list_corr_res.json()) == 2


# ===========================================================================
# Scenario 12: Aggregated Summary Reporting & Queue Monitoring
# ===========================================================================

def test_scenario_12_summary_reporting_and_queues(test_client: TestClient):
    """Test generating summary reports and querying specialized queues."""
    report_res = test_client.get("/api/v1/governance-decision-assurance/reports/summary")
    assert report_res.status_code == 200
    rep = report_res.json()
    assert "total_decisions_registered" in rep
    assert "verified_count" in rep
    assert "authorization_unverifiable_count" in rep
    assert "conflicted_count" in rep
    assert rep["organization_id"] == "org-apollo-01"


# ===========================================================================
# Scenario 13: Tenant Isolation & Patient Role Restrictions
# ===========================================================================

def test_scenario_13_tenant_isolation_and_patient_role_restrictions(test_client: TestClient):
    """Test cross-tenant access denial and prohibition of patient role."""
    now = datetime.now(timezone.utc)
    reg_payload = {
        "source_phase": "PHASE_63",
        "source_record_id": "srr-risk-1301",
        "decision_type": "RISK_DISPOSITION",
        "decision_title": "Tenant Isolation Test",
        "decision_outcome": "APPROVED",
        "decided_by_id": "usr-lead-01",
        "decided_by_role": "DOCTOR",
        "decided_at": (now - timedelta(hours=1)).isoformat(),
        "authorization_evidence_ref": "auth-sig-1301",
        "policy_reference": "pol-risk-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (now - timedelta(days=10)).isoformat(),
        "supporting_evidence_refs": ["ev-ref-01"],
        "rationale": "Tenant isolation verification.",
    }
    # Register under org-apollo-01
    res = test_client.post(
        "/api/v1/governance-decision-assurance/decisions",
        json=reg_payload,
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert res.status_code == 201
    decision_id = res.json()["decision_id"]

    # 1. Attempt access from org-other -> 403 Forbidden
    other_res = test_client.get(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}",
        headers={"X-User-Organization": "org-other-hospital"},
    )
    assert other_res.status_code == 403
    assert other_res.json()["error"]["code"] == "CROSS_TENANT_ACCESS_FORBIDDEN"

    # 2. Attempt registration by PATIENT role -> 403 Forbidden
    pat_res = test_client.post(
        "/api/v1/governance-decision-assurance/decisions",
        json=reg_payload,
        headers={"X-User-Role": "PATIENT"},
    )
    assert pat_res.status_code == 403
    assert pat_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


# ===========================================================================
# Scenario 14: Verification Idempotency Enforcement
# ===========================================================================

def test_scenario_14_verification_idempotency(test_client: TestClient):
    """Test that identical idempotency keys return the identical assurance run."""
    now = datetime.now(timezone.utc)
    reg_payload = {
        "source_phase": "PHASE_65",
        "source_record_id": "wfc-completion-1401",
        "decision_type": "COMPLETION_AUTHORIZATION",
        "decision_title": "Idempotent Verification Test",
        "decision_outcome": "COMPLETED",
        "decided_by_id": "usr-lead-01",
        "decided_by_role": "DOCTOR",
        "decided_at": (now - timedelta(hours=1)).isoformat(),
        "authorization_evidence_ref": "auth-sig-1401",
        "policy_reference": "pol-handoff-v1",
        "policy_version": "v1.0.0",
        "policy_effective_date": (now - timedelta(days=10)).isoformat(),
        "supporting_evidence_refs": ["ev-ref-1401"],
        "rationale": "Idempotent check run.",
    }
    reg_res = test_client.post("/api/v1/governance-decision-assurance/decisions", json=reg_payload)
    decision_id = reg_res.json()["decision_id"]

    idem_key = "idem-token-run-unique-1401"
    run1 = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json={"idempotency_key": idem_key},
    )
    assert run1.status_code == 200
    assurance_1 = run1.json()

    # Re-run with identical idempotency key
    run2 = test_client.post(
        f"/api/v1/governance-decision-assurance/decisions/{decision_id}/verify",
        json={"idempotency_key": idem_key},
    )
    assert run2.status_code == 200
    assurance_2 = run2.json()

    assert assurance_1["assurance_id"] == assurance_2["assurance_id"]

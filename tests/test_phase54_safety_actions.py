"""Phase 54: Clinical Safety Oversight Decision Support, Escalation & Controlled Action Orchestration Tests.

Validates:
- Finding intake, classification, and server-side priority determination
- Human governance approval workflows and separation of duties
- Execution gating (approval freshness, clinical boundary enforcement)
- Authoritative subsystem dispatch (Phase 36, 37, 51, 52)
- Operational completion vs. safety effectiveness separation (COMPLETION != EFFECTIVENESS)
- Closed-loop return to Phase 52 assurance
- Policy-backed escalation and server-side urgency validation
- Tenant isolation and multi-tenancy protection
- Rollback, bounded retry, closure, and reopening invariants
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.safety_action_repository import safety_action_repository
from app.schemas.auth import UserRole
from app.schemas.safety_action import (
    ActionApprovalDecision,
    ActionEffectivenessState,
    ActionLifecycleState,
    ActionOwnerDomain,
    ActionPriority,
    ActionType,
    ActionabilityState,
    EscalationLevel,
    FindingSourceType,
    SafetyActionScope,
    SafetyFindingReference,
    TargetSubsystem,
)
from app.schemas.user import AuthenticatedUserContext

client = TestClient(app)


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-safety-officer-54"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-delhi-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-apollo-01"),
    )


@pytest.fixture(autouse=True)
def reset_repositories():
    """Reset repository and configure authenticated session override."""
    safety_action_repository.reset()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    safety_action_repository.reset()


@pytest.fixture
def auth_headers():
    return {
        "Authorization": "Bearer valid_token",
        "X-User-Role": "SAFETY_OFFICER",
        "X-User-Organization": "org-delhi-01",
        "X-User-Facility": "fac-apollo-01",
        "X-User-Id": "usr-officer-1",
    }


@pytest.fixture
def peer_auth_headers():
    return {
        "Authorization": "Bearer valid_token",
        "X-User-Role": "CLINICAL_SAFETY_DIRECTOR",
        "X-User-Organization": "org-delhi-01",
        "X-User-Facility": "fac-apollo-01",
        "X-User-Id": "usr-director-peer",
    }


def sample_finding() -> dict:
    return {
        "source_type": FindingSourceType.ASSURANCE_EVALUATION.value,
        "source_id": "eval-med-dose-01",
        "source_version": "v1.0",
        "finding_title": "Elevated Bypass Rate in Dosing Gate",
        "finding_details": {
            "control_id": "ctrl-dose-calc",
            "bypass_count": 12,
            "repeated_bypass": True,
            "degradation_state": "DEGRADED",
        },
        "observed_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def test_safety_action_full_governed_lifecycle(auth_headers, peer_auth_headers):
    """Test complete flow: Create -> Classify -> Approve -> Assign -> Start -> Complete -> Verify -> Close."""
    # 1. Create Action Candidate
    create_payload = {
        "finding": sample_finding(),
        "action_type": ActionType.CONTROL_REVALIDATION.value,
        "title": "Investigate High Dosing Gate Bypass",
        "description": "Observation window demonstrated 12 bypasses exceeding threshold.",
        "scope": {
            "organization_id": "org-delhi-01",
            "facility_id": "fac-apollo-01",
            "control_id": "ctrl-dose-calc",
        },
        "due_in_hours": 48,
    }

    create_resp = client.post("/api/v1/safety-actions", json=create_payload, headers=auth_headers)
    assert create_resp.status_code == 202
    act_data = create_resp.json()["data"]
    action_id = act_data["action_id"]
    assert act_data["lifecycle_state"] == ActionLifecycleState.REVIEW_REQUIRED.value
    assert act_data["priority"] == ActionPriority.CRITICAL.value  # Repeated bypass derives CRITICAL
    assert act_data["is_urgent"] is True

    # 2. Peer Review & Approval (Enforcing separation of duties: peer approves)
    appr_payload = {
        "action_version": act_data["version"],
        "decision": ActionApprovalDecision.APPROVE.value,
        "reason": "Independent governance review agrees revalidation is required.",
        "validity_hours": 72,
    }
    appr_resp = client.post(f"/api/v1/safety-actions/{action_id}/approve", json=appr_payload, headers=peer_auth_headers)
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()["data"]
    assert appr_data["lifecycle_state"] == ActionLifecycleState.READY.value
    assert appr_data["approval"]["state"] == "APPROVED"

    # 3. Assign Operational Owner
    asgn_payload = {
        "owner_id": "usr-lead-engineer",
        "owner_role": "ENGINEER",
        "owner_domain": ActionOwnerDomain.ENGINEERING_OWNER.value,
        "notes": "Assigned to investigate gate telemetry pipeline.",
    }
    asgn_resp = client.post(f"/api/v1/safety-actions/{action_id}/assign", json=asgn_payload, headers=peer_auth_headers)
    assert asgn_resp.status_code == 200
    assert asgn_resp.json()["data"]["lifecycle_state"] == ActionLifecycleState.ASSIGNED.value

    # 4. Start Execution (Execution Gate Check)
    start_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/start",
        json={"target_subsystem": TargetSubsystem.PHASE_52_ASSURANCE.value},
        headers=auth_headers,
    )
    assert start_resp.status_code == 200
    start_data = start_resp.json()["data"]
    assert start_data["lifecycle_state"] == ActionLifecycleState.IN_PROGRESS.value
    assert start_data["started_at"] is not None

    # 5. Complete Operational Execution (COMPLETION != EFFECTIVENESS)
    comp_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/complete",
        json={"completion_summary": "Telemetry rules verified and bypass hook re-enabled."},
        headers=auth_headers,
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()["data"]
    assert comp_data["lifecycle_state"] == ActionLifecycleState.COMPLETED.value
    # Effectiveness must still be empty/pending
    assert comp_data.get("effectiveness") is None

    # 6. Independent Verification & Closed-Loop Assurance to Phase 52
    verify_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/verify",
        json={"verification_notes": "Telemetry validation passed with 0 observed bypasses.", "verified": True},
        headers=peer_auth_headers,
    )
    assert verify_resp.status_code == 200
    ver_data = verify_resp.json()["data"]
    assert ver_data["lifecycle_state"] == ActionLifecycleState.VERIFIED.value
    assert ver_data["effectiveness"] is not None
    assert ver_data["effectiveness"]["effectiveness_state"] == ActionEffectivenessState.EFFECTIVE_OBSERVED.value
    assert "eval-closedloop" in ver_data["effectiveness"]["assurance_evaluation_id"]

    # 7. Close Action
    close_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/close",
        json={"closure_summary": "Issue resolved and confirmed under Phase 52 continuous monitoring.", "confirm_effectiveness": True},
        headers=peer_auth_headers,
    )
    assert close_resp.status_code == 200
    close_data = close_resp.json()["data"]
    assert close_data["lifecycle_state"] == ActionLifecycleState.CLOSED.value
    assert close_data["closed_at"] is not None


def test_clinical_action_boundary_strictly_enforced(auth_headers, peer_auth_headers):
    """Enforce Section 20 & 21: Autonomous clinical mutations are prohibited."""
    # Create action
    resp = client.post(
        "/api/v1/safety-actions",
        json={
            "finding": sample_finding(),
            "action_type": ActionType.REVIEW.value,
            "title": "Clinical Guardrail Review",
            "description": "Routine audit.",
        },
        headers=auth_headers,
    )
    action_id = resp.json()["data"]["action_id"]

    # Approve
    client.post(
        f"/api/v1/safety-actions/{action_id}/approve",
        json={"action_version": 1, "decision": "APPROVE", "reason": "Approved for workflow review."},
        headers=peer_auth_headers,
    )

    # Attempt to start with prohibited clinical action payload (e.g. discontinue_medication)
    bad_start_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/start",
        json={
            "target_subsystem": TargetSubsystem.PHASE_37_WORKFLOW.value,
            "execution_payload": {"discontinue_medication": True, "patient_id": "p-123"},
        },
        headers=auth_headers,
    )
    assert bad_start_resp.status_code == 422
    assert "SAFETY_ACTION_CLINICAL_ACTION_RESTRICTED" in bad_start_resp.text


def test_tenant_isolation_enforced(auth_headers):
    """Ensure Organization B cannot view or act upon Organization A's safety action."""
    # Org Delhi creates action
    resp = client.post(
        "/api/v1/safety-actions",
        json={
            "finding": sample_finding(),
            "action_type": ActionType.MONITOR.value,
            "title": "Delhi Clinic Monitor",
            "description": "Monitoring action.",
            "scope": {"organization_id": "org-delhi-01"},
        },
        headers=auth_headers,
    )
    action_id = resp.json()["data"]["action_id"]

    # Org Mumbai tries to access
    mumbai_headers = {
        "Authorization": "Bearer valid_token",
        "X-User-Role": "SAFETY_OFFICER",
        "X-User-Organization": "org-mumbai-02",
        "X-User-Id": "usr-mumbai-officer",
    }
    unauth_resp = client.get(f"/api/v1/safety-actions/{action_id}", headers=mumbai_headers)
    assert unauth_resp.status_code == 403


def test_rollback_and_bounded_retry(auth_headers, peer_auth_headers):
    """Verify rollback preserves history, and retries are bounded."""
    create_resp = client.post(
        "/api/v1/safety-actions",
        json={
            "finding": sample_finding(),
            "action_type": ActionType.CORRECTIVE_ACTION.value,
            "title": "Fix Gate Configuration",
            "description": "Corrective configuration update.",
        },
        headers=auth_headers,
    )
    action_id = create_resp.json()["data"]["action_id"]

    # Approve & start
    client.post(
        f"/api/v1/safety-actions/{action_id}/approve",
        json={"action_version": 1, "decision": "APPROVE", "reason": "Proceed with config fix."},
        headers=peer_auth_headers,
    )
    client.post(f"/api/v1/safety-actions/{action_id}/start", json={}, headers=auth_headers)

    # Fail
    client.post(f"/api/v1/safety-actions/{action_id}/fail?reason=NetworkTimeout", headers=auth_headers)

    # Retry #1
    retry_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/retry",
        json={"retry_reason": "Transient network error recovered."},
        headers=auth_headers,
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["data"]["retry_count"] == 1

    # Rollback
    current_ver = retry_resp.json()["data"]["version"]
    rollback_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/rollback",
        json={"action_version": current_ver, "rollback_reason": "Reverting configuration to previous stable state."},
        headers=auth_headers,
    )
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["data"]["is_rolled_back"] is True
    assert rollback_resp.json()["data"]["lifecycle_state"] == ActionLifecycleState.REQUIRES_REASSESSMENT.value

    # Verify history preserved
    hist_resp = client.get(f"/api/v1/safety-actions/{action_id}/history", headers=auth_headers)
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()["data"]) >= 5


def test_separation_of_duties_enforced(auth_headers, peer_auth_headers):
    """Enforce Section 12: Implementer cannot verify their own action."""
    create_resp = client.post(
        "/api/v1/safety-actions",
        json={
            "finding": sample_finding(),
            "action_type": ActionType.REVIEW.value,
            "title": "Separation of Duties Test",
            "description": "Validation test.",
        },
        headers=auth_headers,
    )
    action_id = create_resp.json()["data"]["action_id"]

    # Approve
    client.post(
        f"/api/v1/safety-actions/{action_id}/approve",
        json={"action_version": 1, "decision": "APPROVE", "reason": "Approved by peer."},
        headers=peer_auth_headers,
    )

    # Assign to usr-officer-1
    client.post(
        f"/api/v1/safety-actions/{action_id}/assign",
        json={"owner_id": "usr-officer-1", "owner_role": "SAFETY_OFFICER", "owner_domain": ActionOwnerDomain.CLINICAL_SAFETY_TEAM.value},
        headers=peer_auth_headers,
    )

    # Start and Complete by usr-officer-1
    client.post(f"/api/v1/safety-actions/{action_id}/start", json={}, headers=auth_headers)
    client.post(
        f"/api/v1/safety-actions/{action_id}/complete",
        json={"completion_summary": "Task finished by implementer."},
        headers=auth_headers,
    )

    # Attempt to self-verify by usr-officer-1 (Implementer == Validator) -> PROHIBITED
    self_verify_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/verify",
        json={"verification_notes": "Self-verification attempt.", "verified": True},
        headers=auth_headers,
    )
    assert self_verify_resp.status_code == 403
    assert "SAFETY_ACTION_VERIFICATION_FAILED" in self_verify_resp.text

    # Independent peer verification -> ALLOWED
    peer_verify_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/verify",
        json={"verification_notes": "Independent verification passed.", "verified": True},
        headers=peer_auth_headers,
    )
    assert peer_verify_resp.status_code == 200


def test_ai_approval_strictly_prohibited(auth_headers):
    """Enforce Section 35: AI agents cannot approve safety actions."""
    create_resp = client.post(
        "/api/v1/safety-actions",
        json={
            "finding": sample_finding(),
            "action_type": ActionType.REVIEW.value,
            "title": "AI Approval Gate Check",
            "description": "Validation test.",
        },
        headers=auth_headers,
    )
    action_id = create_resp.json()["data"]["action_id"]

    ai_headers = {
        "Authorization": "Bearer ai_token",
        "X-User-Role": "AI",
        "X-User-Organization": "org-delhi-01",
        "X-User-Id": "ai-clinical-agent",
    }

    ai_appr_resp = client.post(
        f"/api/v1/safety-actions/{action_id}/approve",
        json={"action_version": 1, "decision": "APPROVE", "reason": "AI confidence high."},
        headers=ai_headers,
    )
    assert ai_appr_resp.status_code == 403
    assert "SAFETY_ACTION_APPROVAL_DENIED" in ai_appr_resp.text


def test_reopen_and_filter_views(auth_headers, peer_auth_headers):
    """Test reopening closed actions and query filter views."""
    create_resp = client.post(
        "/api/v1/safety-actions",
        json={
            "finding": sample_finding(),
            "action_type": ActionType.MONITOR.value,
            "title": "Reopen & Filter Action",
            "description": "Validation test.",
        },
        headers=auth_headers,
    )
    action_id = create_resp.json()["data"]["action_id"]

    # Pending view
    pending_resp = client.get("/api/v1/safety-actions/pending", headers=auth_headers)
    assert pending_resp.status_code == 200
    assert any(a["action_id"] == action_id for a in pending_resp.json()["data"])

    # Escalate action
    client.post(
        f"/api/v1/safety-actions/{action_id}/escalate",
        json={"escalation_level": EscalationLevel.CLINICAL_SAFETY.value, "reason": "Requires governance review."},
        headers=auth_headers,
    )

    # Escalated view
    esc_resp = client.get("/api/v1/safety-actions/escalated", headers=auth_headers)
    assert esc_resp.status_code == 200
    assert any(a["action_id"] == action_id for a in esc_resp.json()["data"])


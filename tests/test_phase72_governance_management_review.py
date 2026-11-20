"""Phase 72: Clinical Safety Governance Management Review, Executive Oversight & Decision Follow-Through Tests.

Validates:
- Scenario 1: Review programme lifecycle (creation, update, approval, filtering)
- Scenario 2: Review meeting lifecycle (creation, scheduling, rescheduling, cancellation)
- Scenario 3: Participant management, authority assignment, conflict declarations, and attendance confirmation
- Scenario 4: Meeting readiness evaluation (quorum, approved programme, chairperson, agenda)
- Scenario 5: Agenda item management and topic categorization
- Scenario 6: Cross-phase input consolidation (Phases 49-71)
- Scenario 7: Reproducible review package compilation and version locking
- Scenario 8: Meeting commencement and discussion minute recording
- Scenario 9: Decision authority enforcement (attendance alone does not confer authority; 403 DECISION_AUTHORIZATION_FAILED)
- Scenario 10: Authoritative decision lifecycle (recording, approval, deferral, and versioned supersession)
- Scenario 11: Follow-through commitment assignment, progress reporting, verification, and escalation
- Scenario 12: Previous decisions reconciliation across review meetings
- Scenario 13: Management review report generation, approval, and finalization
- Scenario 14: Review closure gating enforcement (400 REVIEW_CLOSURE_CONDITIONS_UNMET) and successful closure
- Scenario 15: Review reopening with documented justification
- Scenario 16: Executive review analytics and governance conformance rate
- Scenario 17: Tenant boundary isolation
- Scenario 18: Patient role access rejection (403 Forbidden)
"""

from datetime import datetime, timedelta, timezone
import os

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_management_review_repository import (
    get_governance_management_review_repository,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    try:
        role_enum = UserRole(role_str)
    except ValueError:
        role_enum = UserRole.SUPPORT_OPERATOR if role_str != "PATIENT" else UserRole.PATIENT
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-gov-lead-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and configure auth dependency override."""
    repo = get_governance_management_review_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# SCENARIOS
# =============================================================================

def test_scenario_01_programme_lifecycle(client: TestClient):
    """Scenario 1: Programme creation, update, approval, and listing."""
    # 1. Create programme
    payload = {
        "name": "Annual Clinical Safety Governance Programme 2026",
        "description": "Executive review programme evaluating cross-service clinical risk, audit intelligence, and safety actions.",
        "objectives": ["Monitor safety posture", "Review systemic audit findings"],
        "category": "CLINICAL_SAFETY_GOVERNANCE",
        "frequency": "QUARTERLY",
        "participating_units": ["Emergency", "Cardiology", "Pharmacy"],
        "applicable_domains": ["Clinical Informatics", "Medication Safety"],
    }
    resp = client.post("/api/v1/governance-management-reviews/programmes", json=payload)
    assert resp.status_code == 201
    prog = resp.json()
    prog_id = prog["programme_id"]
    assert prog["status"] == "DRAFT"
    assert prog["name"] == payload["name"]

    # 2. Update programme
    update_payload = {"name": "Annual Clinical Safety Governance Programme 2026-2027"}
    resp = client.put(f"/api/v1/governance-management-reviews/programmes/{prog_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == update_payload["name"]

    # 3. Approve programme
    approve_payload = {
        "approval_policy_ref": "POL-GOV-SAFE-2026",
        "approval_rationale": "Approved by Clinical Safety Executive Board.",
    }
    resp = client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json=approve_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"
    assert resp.json()["approved_by"] == "usr-gov-lead-01"

    # 4. List programmes
    resp = client.get("/api/v1/governance-management-reviews/programmes")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["programme_id"] == prog_id


def test_scenario_02_review_meeting_lifecycle(client: TestClient):
    """Scenario 2: Review creation, scheduling, rescheduling, and cancellation."""
    # Setup approved programme
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog A", "description": "Desc A"},
    )
    prog_id = prog_resp.json()["programme_id"]
    client.post(
        f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve",
        json={"approval_policy_ref": "POL-1"},
    )

    # 1. Create Review
    planned_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    rev_payload = {
        "programme_id": prog_id,
        "title": "Q1 2026 Clinical Safety Governance Review",
        "objectives": ["Evaluate Q1 systemic findings"],
        "planned_date": planned_date,
        "duration_minutes": 90,
        "chairperson_id": "usr-chair-01",
    }
    resp = client.post("/api/v1/governance-management-reviews/reviews", json=rev_payload)
    assert resp.status_code == 201
    rev = resp.json()
    rev_id = rev["review_id"]
    assert rev["status"] == "DRAFT"

    # 2. Schedule Review
    sched_payload = {
        "planned_date": planned_date,
        "chairperson_id": "usr-chair-01",
        "notes": "Confirmed for Boardroom A",
    }
    resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/schedule", json=sched_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SCHEDULED"

    # 3. Reschedule Review
    new_date = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    resched_payload = {
        "new_planned_date": new_date,
        "rescheduled_reason": "Executive conflict on original date.",
    }
    resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/reschedule", json=resched_payload)
    assert resp.status_code == 200
    assert resp.json()["rescheduled_reason"] == resched_payload["rescheduled_reason"]
    assert datetime.fromisoformat(resp.json()["planned_date"].replace("Z", "+00:00")) == datetime.fromisoformat(new_date)

    # 4. Cancel a review
    cancel_payload = {"cancellation_reason": "Emergency operations activation."}
    resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/cancel", json=cancel_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_scenario_03_participant_management_and_authority(client: TestClient):
    """Scenario 3: Participant roster, attendance confirmation, and conflict declarations."""
    # Setup programme & review
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog P", "description": "Desc P"},
    )
    prog_id = prog_resp.json()["programme_id"]
    client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json={"approval_policy_ref": "POL-1"})

    rev_resp = client.post(
        "/api/v1/governance-management-reviews/reviews",
        json={
            "programme_id": prog_id,
            "title": "Review P",
            "planned_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "chairperson_id": "usr-chair-01",
        },
    )
    rev_id = rev_resp.json()["review_id"]

    # Add participant with decision authority
    part_payload = {
        "user_id": "usr-exec-02",
        "user_name": "Dr. Sarah Lin",
        "role": "EXECUTIVE_REVIEWER",
        "has_decision_authority": True,
    }
    resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants", json=part_payload)
    assert resp.status_code == 201
    part = resp.json()
    assert part["has_decision_authority"] is True

    # Add participant with conflict declaration
    part2_payload = {
        "user_id": "usr-auditor-03",
        "user_name": "Dr. Alex Wong",
        "role": "AUDIT_REPRESENTATIVE",
        "has_decision_authority": False,
        "conflict_declared": True,
        "conflict_details": "Previously managed Cardiology unit under review.",
    }
    resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants", json=part2_payload)
    assert resp.status_code == 201
    assert resp.json()["conflict_declared"] is True

    # Confirm attendance
    confirm_payload = {
        "attendance_status": "CONFIRMED",
        "conflict_declared": False,
    }
    headers = {"X-User-Id": "usr-exec-02"}
    resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/confirm-attendance",
        json=confirm_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["attendance_status"] == "CONFIRMED"

    # List participants
    resp = client.get(f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants")
    assert resp.status_code == 200
    # chairperson + 2 participants = 3 total
    assert len(resp.json()) == 3


def test_scenario_04_readiness_validation(client: TestClient):
    """Scenario 4: Meeting readiness evaluation (deficiencies, limitations, ready)."""
    # Create review under draft (unapproved) programme
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog Draft", "description": "Desc"},
    )
    prog_id = prog_resp.json()["programme_id"]

    rev_resp = client.post(
        "/api/v1/governance-management-reviews/reviews",
        json={
            "programme_id": prog_id,
            "title": "Review Readiness Test",
            "planned_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )
    rev_id = rev_resp.json()["review_id"]

    # Readiness should be NOT_READY because programme not approved, no chair, no quorum, no agenda
    resp = client.get(f"/api/v1/governance-management-reviews/reviews/{rev_id}/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "NOT_READY"
    assert data["is_ready"] is False
    assert len(data["deficiencies"]) > 0

    # Fix prerequisites: approve programme, assign chair, add quorum participant, add agenda item
    client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json={"approval_policy_ref": "POL-1"})
    client.put(f"/api/v1/governance-management-reviews/reviews/{rev_id}", json={"chairperson_id": "usr-chair-01"})
    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants",
        json={"user_id": "usr-chair-01", "role": "CHAIRPERSON", "has_decision_authority": True},
    )
    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants",
        json={"user_id": "usr-member-02", "role": "CLINICAL_SAFETY_REPRESENTATIVE", "has_decision_authority": False},
    )
    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/agenda-items",
        json={"title": "Topic 1", "description": "Desc 1"},
    )

    # Check readiness again -> should now be READY or READY_WITH_LIMITATIONS (e.g. package not yet generated)
    resp = client.get(f"/api/v1/governance-management-reviews/reviews/{rev_id}/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_ready"] is True
    assert data["checks"]["programme_approved"] is True
    assert data["checks"]["chairperson_assigned"] is True
    assert data["checks"]["quorum_participants"] is True
    assert data["checks"]["agenda_defined"] is True


def test_scenario_05_06_07_agenda_inputs_package(client: TestClient):
    """Scenarios 5, 6, 7: Agenda items, cross-phase input consolidation, review package compile & lock."""
    # Setup programme & review
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog Agenda", "description": "Desc"},
    )
    prog_id = prog_resp.json()["programme_id"]
    client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json={"approval_policy_ref": "POL-1"})

    rev_resp = client.post(
        "/api/v1/governance-management-reviews/reviews",
        json={
            "programme_id": prog_id,
            "title": "Review Package Test",
            "planned_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "chairperson_id": "usr-chair-01",
        },
    )
    rev_id = rev_resp.json()["review_id"]

    # 1. Add agenda items
    agenda1_payload = {
        "title": "Status of Prior Clinical Safety Corrective Actions",
        "description": "Review outstanding CAPAs from Phase 54 and Phase 55.",
        "category": "STATUS_OF_PREVIOUS_ACTIONS",
        "priority": "HIGH",
        "allocated_minutes": 25,
        "order": 1,
    }
    resp1 = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/agenda-items", json=agenda1_payload)
    assert resp1.status_code == 201
    agenda1_id = resp1.json()["agenda_item_id"]

    agenda2_payload = {
        "title": "Systemic Audit Intelligence Patterns",
        "description": "Review repeat finding clusters detected in Phase 71.",
        "category": "AUDIT_FINDINGS_AND_INTELLIGENCE",
        "priority": "CRITICAL",
        "allocated_minutes": 35,
        "order": 2,
    }
    resp2 = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/agenda-items", json=agenda2_payload)
    assert resp2.status_code == 201

    # 2. Collect inputs from Phase 71 intelligence and Phase 70 audit
    inp1 = {
        "source_phase": "PHASE_71",
        "source_id": "gsis-pat-401",
        "source_type": "SYSTEMIC_ISSUE_CANDIDATE",
        "summary": "High recurrence of medication reconciliation timing gaps.",
        "details": {"recurrence_count": 4, "severity": "HIGH"},
    }
    r_inp1 = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/inputs/collect", json=inp1)
    assert r_inp1.status_code == 201
    assert r_inp1.json()["source_phase"] == "PHASE_71"

    # List inputs
    list_inp_resp = client.get(f"/api/v1/governance-management-reviews/reviews/{rev_id}/inputs")
    assert list_inp_resp.status_code == 200
    assert len(list_inp_resp.json()) == 1

    # 3. Generate Review Package
    pkg_payload = {
        "package_title": "Executive Review Dossier - Q1 2026",
        "executive_summary": "Consolidated intelligence package including 2 agenda topics and 1 systemic issue finding.",
        "lock_package": False,
    }
    pkg_resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/packages/generate", json=pkg_payload)
    assert pkg_resp.status_code == 201
    pkg = pkg_resp.json()
    assert pkg["version"] == 1
    assert len(pkg["agenda_item_ids"]) == 2
    assert len(pkg["input_ids"]) == 1
    pkg_id = pkg["package_id"]

    # Lock Package
    lock_resp = client.post(f"/api/v1/governance-management-reviews/packages/{pkg_id}/lock")
    assert lock_resp.status_code == 200
    assert lock_resp.json()["status"] == "LOCKED"


def test_scenario_08_09_10_meeting_discussions_and_decisions(client: TestClient):
    """Scenarios 8, 9, 10: Meeting discussions, decision authority enforcement, and decision supersession."""
    # Setup programme & review
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog Dec", "description": "Desc"},
    )
    prog_id = prog_resp.json()["programme_id"]
    client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json={"approval_policy_ref": "POL-1"})

    rev_resp = client.post(
        "/api/v1/governance-management-reviews/reviews",
        json={
            "programme_id": prog_id,
            "title": "Decision Meeting",
            "planned_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "chairperson_id": "usr-chair-01",
        },
    )
    rev_id = rev_resp.json()["review_id"]

    # Add participants: one with authority, one without
    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants",
        json={"user_id": "usr-exec-auth", "role": "EXECUTIVE_REVIEWER", "has_decision_authority": True},
    )
    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants",
        json={"user_id": "usr-analyst-no-auth", "role": "OBSERVER", "has_decision_authority": False},
    )

    # Start review meeting
    start_resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "IN_PROGRESS"

    # Record discussion
    disc_payload = {
        "topic": "Clinical Workflow Automation Risks",
        "discussion_notes": "Discussed medication alerting fatigue and physician bypass rate.",
        "key_points": ["Alert fatigue identified in ICU", "Need for threshold review"],
    }
    disc_resp = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/discussions", json=disc_payload)
    assert disc_resp.status_code == 201

    # Unauthorized decision attempt: analyst user lacks decision authority
    dec_payload = {
        "title": "Mandatory Alert Modification",
        "category": "SYSTEM_MODIFICATION",
        "rationale": "Alter ICU alert sensitivity.",
    }
    no_auth_headers = {"X-User-Id": "usr-analyst-no-auth", "X-User-Role": "SUPPORT_OPERATOR"}
    fail_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/decisions",
        json=dec_payload,
        headers=no_auth_headers,
    )
    assert fail_resp.status_code == 403
    assert fail_resp.json()["error"]["code"] == "DECISION_AUTHORIZATION_FAILED"

    # Authorized decision attempt: executive with explicit authority
    auth_headers = {"X-User-Id": "usr-exec-auth", "X-User-Role": "ADMIN"}
    ok_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/decisions",
        json=dec_payload,
        headers=auth_headers,
    )
    assert ok_resp.status_code == 201
    dec1 = ok_resp.json()
    assert dec1["status"] == "APPROVED"
    dec1_id = dec1["decision_id"]

    # Superseding decision: Record revised decision that supersedes dec1
    revised_dec_payload = {
        "title": "Mandatory Alert Modification - Revised Scope",
        "category": "SYSTEM_MODIFICATION",
        "rationale": "Updated scope including Emergency Department alongside ICU.",
        "supersedes_decision_id": dec1_id,
    }
    superseding_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/decisions",
        json=revised_dec_payload,
        headers=auth_headers,
    )
    assert superseding_resp.status_code == 201
    dec2 = superseding_resp.json()
    assert dec2["supersedes_decision_id"] == dec1_id

    # Verify that prior decision dec1 is now SUPERSEDED
    old_dec_resp = client.get(f"/api/v1/governance-management-reviews/decisions/{dec1_id}")
    assert old_dec_resp.status_code == 200
    assert old_dec_resp.json()["status"] == "SUPERSEDED"
    assert old_dec_resp.json()["superseded_by_id"] == dec2["decision_id"]


def test_scenario_11_commitments_verification_and_escalation(client: TestClient):
    """Scenario 11: Management commitment assignment, progress, verification, and escalation."""
    # Setup programme, review, and decision
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog Commit", "description": "Desc"},
    )
    prog_id = prog_resp.json()["programme_id"]
    client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json={"approval_policy_ref": "POL-1"})

    rev_resp = client.post(
        "/api/v1/governance-management-reviews/reviews",
        json={
            "programme_id": prog_id,
            "title": "Review Commit",
            "planned_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "chairperson_id": "usr-chair-01",
        },
    )
    rev_id = rev_resp.json()["review_id"]

    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants",
        json={"user_id": "usr-chair-01", "role": "CHAIRPERSON", "has_decision_authority": True},
    )

    dec_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/decisions",
        json={
            "title": "Initiate Alert Tuning CAPA",
            "category": "CORRECTIVE_ACTION_INITIATION",
            "rationale": "Corrective action required under Phase 54.",
        },
        headers={"X-User-Id": "usr-chair-01", "X-User-Role": "ADMIN"},
    )
    dec_id = dec_resp.json()["decision_id"]

    # 1. Create Follow-Through Commitment
    due_date = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    comm_payload = {
        "decision_id": dec_id,
        "title": "Deploy Revised Alert Sensitivity Matrix",
        "description": "Implement updated CDS alert thresholds across emergency department.",
        "responsible_owner_id": "usr-clinical-lead-05",
        "accountable_lead_id": "usr-cso-01",
        "priority": "HIGH",
        "due_date": due_date,
        "linked_capa_id": "capa-phase54-001",
    }
    comm_resp = client.post("/api/v1/governance-management-reviews/commitments", json=comm_payload)
    assert comm_resp.status_code == 201
    comm = comm_resp.json()
    comm_id = comm["commitment_id"]
    assert comm["status"] == "ASSIGNED"
    assert comm["linked_capa_id"] == "capa-phase54-001"

    # 2. Update Progress
    prog_payload = {
        "progress_percentage": 50,
        "note": "Updated CDS configuration files validated in staging.",
    }
    p_resp = client.post(f"/api/v1/governance-management-reviews/commitments/{comm_id}/progress", json=prog_payload)
    assert p_resp.status_code == 200
    assert p_resp.json()["status"] == "IN_PROGRESS"
    assert p_resp.json()["progress_percentage"] == 50

    # 3. Submit Verification
    verif_sub_payload = {
        "completion_evidence_refs": ["doc-cds-stg-audit-01"],
        "summary_of_implementation": "Thresholds adjusted and verified in production environment.",
    }
    sub_resp = client.post(f"/api/v1/governance-management-reviews/commitments/{comm_id}/submit-verification", json=verif_sub_payload)
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "PENDING_VERIFICATION"

    # 4. Formally Verify Commitment
    verif_payload = {
        "verified": True,
        "verification_notes": "Audit confirmed false positive rate dropped by 65%. Verified complete.",
    }
    ver_resp = client.post(f"/api/v1/governance-management-reviews/commitments/{comm_id}/verify", json=verif_payload)
    assert ver_resp.status_code == 200
    assert ver_resp.json()["status"] == "VERIFIED"
    assert ver_resp.json()["progress_percentage"] == 100

    # 5. Create another commitment and Escalate it
    comm2_payload = {
        "decision_id": dec_id,
        "title": "Procure Clinical Decision Support Simulator",
        "description": "Hardware budget approval required.",
        "responsible_owner_id": "usr-ops-lead-09",
        "accountable_lead_id": "usr-cso-01",
        "priority": "CRITICAL",
        "due_date": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),  # Overdue
    }
    comm2_resp = client.post("/api/v1/governance-management-reviews/commitments", json=comm2_payload)
    comm2_id = comm2_resp.json()["commitment_id"]

    esc_payload = {
        "escalated_to": "usr-chief-medical-officer",
        "escalation_reason": "Budget release delayed by procurement committee.",
        "urgency": "CRITICAL",
    }
    esc_resp = client.post(f"/api/v1/governance-management-reviews/commitments/{comm2_id}/escalate", json=esc_payload)
    assert esc_resp.status_code == 201
    assert esc_resp.json()["commitment_id"] == comm2_id

    # Check commitment status is now ESCALATED
    c2_check = client.get(f"/api/v1/governance-management-reviews/commitments/{comm2_id}")
    assert c2_check.status_code == 200
    assert c2_check.json()["status"] == "ESCALATED"


def test_scenario_12_13_14_15_reconciliation_report_closure_reopen(client: TestClient):
    """Scenarios 12, 13, 14, 15: Prior decision reconciliation, report generation/approval, closure gating, and reopening."""
    # Setup programme & review
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog Close", "description": "Desc"},
    )
    prog_id = prog_resp.json()["programme_id"]
    client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json={"approval_policy_ref": "POL-1"})

    rev_resp = client.post(
        "/api/v1/governance-management-reviews/reviews",
        json={
            "programme_id": prog_id,
            "title": "Review To Close",
            "planned_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "chairperson_id": "usr-chair-01",
        },
    )
    rev_id = rev_resp.json()["review_id"]

    # Add participants & agenda
    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants",
        json={"user_id": "usr-chair-01", "role": "CHAIRPERSON", "has_decision_authority": True},
    )
    agenda_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/agenda-items",
        json={"title": "Topic A", "description": "Desc A"},
    )
    agenda_id = agenda_resp.json()["agenda_item_id"]

    # Start meeting
    client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/start")

    # Record decision
    dec_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/decisions",
        json={"title": "Decision A", "category": "PROCESS_CHANGE", "rationale": "Rationale A"},
        headers={"X-User-Id": "usr-chair-01", "X-User-Role": "ADMIN"},
    )
    dec_id = dec_resp.json()["decision_id"]

    # Assign commitment
    comm_resp = client.post(
        "/api/v1/governance-management-reviews/commitments",
        json={
            "decision_id": dec_id,
            "title": "Action A",
            "description": "Desc A",
            "responsible_owner_id": "usr-owner-01",
            "accountable_lead_id": "usr-chair-01",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        },
    )

    # 1. Reconciliation of previous decisions
    recon_resp = client.get(f"/api/v1/governance-management-reviews/reviews/{rev_id}/reconcile-previous")
    assert recon_resp.status_code == 200
    assert isinstance(recon_resp.json(), list)

    # 2. Try closing review before concluding agenda and generating report -> 400 REVIEW_CLOSURE_CONDITIONS_UNMET
    close_attempt = client.post(f"/api/v1/governance-management-reviews/reviews/{rev_id}/close", json={"closure_notes": "Close early"})
    assert close_attempt.status_code == 400
    assert close_attempt.json()["error"]["code"] == "REVIEW_CLOSURE_CONDITIONS_UNMET"

    # Check closure status
    check_resp = client.get(f"/api/v1/governance-management-reviews/reviews/{rev_id}/closure-check")
    assert check_resp.status_code == 200
    assert check_resp.json()["can_close"] is False

    # Conclude agenda item
    client.put(
        f"/api/v1/governance-management-reviews/agenda-items/{agenda_id}",
        json={"discussion_status": "CONCLUDED"},
    )

    # Generate Report
    rep_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/reports/generate",
        json={"title": "Formal Executive Report", "executive_summary": "All items reviewed."},
    )
    assert rep_resp.status_code == 201
    rep_id = rep_resp.json()["report_id"]

    # Approve Report
    appr_rep = client.post(
        f"/api/v1/governance-management-reviews/reports/{rep_id}/approve",
        json={"approval_notes": "Approved by executive leadership."},
    )
    assert appr_rep.status_code == 200
    assert appr_rep.json()["status"] == "APPROVED"

    # Now verify closure readiness is True
    check_resp = client.get(f"/api/v1/governance-management-reviews/reviews/{rev_id}/closure-check")
    assert check_resp.status_code == 200
    assert check_resp.json()["can_close"] is True

    # Close Review
    close_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/close",
        json={"closure_notes": "Formal review successfully completed."},
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "COMPLETED"
    assert close_resp.json()["metadata"]["closure_type"] == "COMPLETED_WITH_OPEN_ACTIONS"

    # 3. Reopen review for follow-up
    reopen_payload = {
        "reopening_reason": "New systemic adverse incident requires immediate governance review.",
        "reopened_by": "usr-chair-01",
    }
    reopen_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/reopen",
        json=reopen_payload,
    )
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "FOLLOW_UP"
    assert len(reopen_resp.json()["metadata"]["reopenings"]) == 1


def test_scenario_16_analytics_overview(client: TestClient):
    """Scenario 16: Executive review analytics overview calculation."""
    # Setup programme & review
    prog_resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Prog Analytics", "description": "Desc"},
    )
    prog_id = prog_resp.json()["programme_id"]
    client.post(f"/api/v1/governance-management-reviews/programmes/{prog_id}/approve", json={"approval_policy_ref": "POL-1"})

    rev_resp = client.post(
        "/api/v1/governance-management-reviews/reviews",
        json={
            "programme_id": prog_id,
            "title": "Review Analytics",
            "planned_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "chairperson_id": "usr-chair-01",
        },
    )
    rev_id = rev_resp.json()["review_id"]

    client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/participants",
        json={"user_id": "usr-chair-01", "role": "CHAIRPERSON", "has_decision_authority": True},
    )

    dec_resp = client.post(
        f"/api/v1/governance-management-reviews/reviews/{rev_id}/decisions",
        json={"title": "Policy Decision", "category": "POLICY_ADOPTION_OR_REVISION", "rationale": "Policy update"},
        headers={"X-User-Id": "usr-chair-01", "X-User-Role": "ADMIN"},
    )

    # Get analytics
    resp = client.get("/api/v1/governance-management-reviews/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_programmes"] >= 1
    assert data["total_reviews"] >= 1
    assert data["total_decisions"] >= 1
    assert "POLICY_ADOPTION_OR_REVISION" in data["decisions_by_category"]
    assert "compliance_conformance_rate" in data


def test_scenario_17_tenant_boundary_isolation(client: TestClient):
    """Scenario 17: Tenant boundary isolation between distinct healthcare organizations."""
    # Create programme under Org A
    headers_org_a = {"X-User-Organization": "org-apollo-01"}
    resp = client.post(
        "/api/v1/governance-management-reviews/programmes",
        json={"name": "Org A Programme", "description": "Desc A"},
        headers=headers_org_a,
    )
    assert resp.status_code == 201

    # Query programmes from Org B -> should NOT see Org A's programme
    headers_org_b = {"X-User-Organization": "org-fortis-02"}
    resp_b = client.get("/api/v1/governance-management-reviews/programmes", headers=headers_org_b)
    assert resp_b.status_code == 200
    assert len(resp_b.json()) == 0


def test_scenario_18_patient_role_authorization_rejection(client: TestClient):
    """Scenario 18: Patient role is rejected with 403 Forbidden on management review endpoints."""
    patient_headers = {"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-99"}

    # Attempt to access programmes
    resp = client.get("/api/v1/governance-management-reviews/programmes", headers=patient_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Attempt to access reviews
    resp = client.get("/api/v1/governance-management-reviews/reviews", headers=patient_headers)
    assert resp.status_code == 403

    # Attempt to access analytics
    resp = client.get("/api/v1/governance-management-reviews/analytics/overview", headers=patient_headers)
    assert resp.status_code == 403

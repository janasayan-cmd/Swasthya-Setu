"""Phase 85: Clinical Safety Governance Resilience Role-Coverage Continuity, Succession Readiness & Authorized Backup Coordination Tests.

Comprehensive test suite verifying:
- Scenario 1: Critical Governance Responsibility Creation
- Scenario 2: Critical Governance Responsibility Update & Review
- Scenario 3: Role-Coverage Arrangement Creation in DRAFT state
- Scenario 4: Coverage Arrangement Submission for Review
- Scenario 5: Coverage Approval Rejection — Creator Self-Approval Separation of Duties Violation
- Scenario 6: Coverage Approval Rejection — Designated Backup Self-Approval Violation
- Scenario 7: Coverage Approval Rejection — Unverified Backups Denied
- Scenario 8: Independent Backup Verification — Deficient State
- Scenario 9: Independent Backup Verification — Full Verification Success
- Scenario 10: Valid Independent Coverage Arrangement Approval
- Scenario 11: Coverage Arrangement Suspension & Closure
- Scenario 12: Single-Person Dependency Detection — Critical Risk
- Scenario 13: Personnel Concentration & Bottleneck Analysis
- Scenario 14: Coverage Scenario Stress Testing — Primary Absent Simulation
- Scenario 15: Coverage Scenario Stress Testing — Mass Unavailability / SPOF Revealed
- Scenario 16: Succession Plan Lifecycle & Separation of Duties
- Scenario 17: Handover Initiation & Self-Handover Prohibition
- Scenario 18: Handover Acknowledgement & Completion Lifecycle
- Scenario 19: Coverage Gap Lifecycle & Evidence-Backed Resolution
- Scenario 20: Executive & Operational Reports & Patient Access Rejection
"""

import os
from datetime import datetime, timedelta

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_role_coverage_repository import (
    get_governance_role_coverage_repository,
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
        user_id=request.headers.get("X-User-Id", "usr-lead-01"),
        email=request.headers.get("X-User-Email", "lead@healthsetu.org"),
        role=role_enum,
        organization_id="org-apollo-01",
    )


@pytest.fixture(autouse=True)
def setup_test_environment():
    app.dependency_overrides[get_current_user] = mock_current_user
    repo = get_governance_role_coverage_repository()
    repo.clear()
    yield
    repo.clear()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Critical Governance Responsibility Creation
# =============================================================================

def test_scenario_01_create_critical_responsibility(client):
    payload = {
        "role_title": "Clinical Safety Officer",
        "responsibility_name": "Safety Escalation Authorization & Review",
        "description": "Authorizes safety risk mitigations and signs off on incident safety escalations.",
        "criticality_tier": "TIER_1_ESSENTIAL",
        "coverage_scope": "ORGANIZATION",
        "max_acceptable_outage_hours": 2.0,
        "primary_owner_id": "usr-cso-01",
        "primary_owner_name": "Dr. Aris Thorne",
        "required_capability_framework_id": "fwk-cso-2026",
        "required_capability_ids": ["cap-escalation-signoff", "cap-risk-appraisal"],
        "review_cycle_days": 90,
    }
    resp = client.post("/api/v1/governance-resilience-role-coverage/responsibilities", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["responsibility_id"].startswith("cresp-")
    assert data["role_title"] == "Clinical Safety Officer"
    assert data["criticality_tier"] == "TIER_1_ESSENTIAL"
    assert data["status"] == "ACTIVE"
    assert "administrative governance instruments" in data["disclaimer"]


# =============================================================================
# Scenario 2: Critical Governance Responsibility Update & Review
# =============================================================================

def test_scenario_02_update_and_review_responsibility(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Continuity Coordinator",
            "responsibility_name": "Oxygen Manifold Switchover Oversight",
            "description": "Coordinates degraded mode manifold operations.",
            "criticality_tier": "TIER_2_CRITICAL",
            "coverage_scope": "FACILITY",
            "max_acceptable_outage_hours": 1.0,
            "primary_owner_id": "usr-coord-01",
            "primary_owner_name": "Elena Vance",
            "review_cycle_days": 60,
        },
    )
    resp_id = create_resp.json()["responsibility_id"]

    # Update description
    update_resp = client.put(
        f"/api/v1/governance-resilience-role-coverage/responsibilities/{resp_id}",
        json={"description": "Updated continuity oversight description.", "max_acceptable_outage_hours": 0.5},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["max_acceptable_outage_hours"] == 0.5

    # Review
    review_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/responsibilities/{resp_id}/review",
        json={"review_notes": "Quarterly review complete. Thresholds validated.", "next_review_cycle_days": 90},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["last_reviewed_at"] is not None


# =============================================================================
# Scenario 3: Role-Coverage Arrangement Creation in DRAFT state
# =============================================================================

def test_scenario_03_create_coverage_arrangement(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Incident Review Chair",
            "responsibility_name": "Incident Triage Review",
            "description": "Presides over daily clinical incident triage sessions.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "coverage_scope": "ORGANIZATION",
            "primary_owner_id": "usr-chair-01",
            "primary_owner_name": "Dr. Sarah Chen",
        },
    )
    resp_id = create_resp.json()["responsibility_id"]

    payload = {
        "responsibility_id": resp_id,
        "designated_backups": [
            {
                "backup_user_id": "usr-backup-01",
                "backup_user_name": "Dr. Marcus Brody",
                "precedence": "PRIMARY_BACKUP",
                "is_available": True,
            }
        ],
        "activation_condition": "Primary owner on leave or unplanned outage > 1 hour.",
    }
    resp = client.post("/api/v1/governance-resilience-role-coverage/coverages", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["coverage_id"].startswith("cov-")
    assert data["status"] == "DRAFT"
    assert len(data["designated_backups"]) == 1
    assert "administrative governance instruments" in data["disclaimer"]


# =============================================================================
# Scenario 4: Coverage Arrangement Submission for Review
# =============================================================================

def test_scenario_04_submit_coverage_arrangement(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Safety Risk Lead",
            "responsibility_name": "Risk Register Maintenance",
            "description": "Reviews risk assessments across departments.",
            "criticality_tier": "TIER_2_CRITICAL",
            "coverage_scope": "ORGANIZATION",
            "primary_owner_id": "usr-lead-01",
            "primary_owner_name": "Dr. Alex Cross",
        },
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-02",
                    "backup_user_name": "Rachel Adams",
                    "precedence": "PRIMARY_BACKUP",
                }
            ],
        },
    )
    cov_id = cov_resp.json()["coverage_id"]

    submit_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/submit",
        json={"submission_notes": "Submitting for governance board review."},
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "UNDER_REVIEW"


# =============================================================================
# Scenario 5: Coverage Approval Rejection — Creator Self-Approval Violation
# =============================================================================

def test_scenario_05_creator_self_approval_violation(client):
    # Created by usr-lead-01
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Continuity Officer",
            "responsibility_name": "Continuity Management",
            "description": "Oversees continuity drills.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-primary-01",
            "primary_owner_name": "Sam Porter",
        },
        headers={"X-User-Id": "usr-creator-01"},
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-99",
                    "backup_user_name": "David Miller",
                    "precedence": "PRIMARY_BACKUP",
                }
            ],
        },
        headers={"X-User-Id": "usr-creator-01"},
    )
    cov_id = cov_resp.json()["coverage_id"]

    client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/submit",
        json={},
        headers={"X-User-Id": "usr-creator-01"},
    )

    # Attempt approval by same creator
    approve_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/approve",
        json={"approval_notes": "Attempting self-approval."},
        headers={"X-User-Id": "usr-creator-01"},
    )
    assert approve_resp.status_code == 403
    assert approve_resp.json()["error"]["code"] == "ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 6: Coverage Approval Rejection — Backup Self-Approval Violation
# =============================================================================

def test_scenario_06_designated_backup_self_approval_violation(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Continuity Officer",
            "responsibility_name": "Continuity Management",
            "description": "Oversees continuity drills.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-primary-01",
            "primary_owner_name": "Sam Porter",
        },
        headers={"X-User-Id": "usr-creator-01"},
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-77",
                    "backup_user_name": "George King",
                    "precedence": "PRIMARY_BACKUP",
                    "capability_verified": True,
                    "authorization_verified": True,
                }
            ],
        },
        headers={"X-User-Id": "usr-creator-01"},
    )
    cov_id = cov_resp.json()["coverage_id"]

    client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/submit",
        json={},
        headers={"X-User-Id": "usr-creator-01"},
    )

    # Attempt approval by designated backup usr-backup-77
    approve_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/approve",
        json={"approval_notes": "Attempting approval as designated backup."},
        headers={"X-User-Id": "usr-backup-77"},
    )
    assert approve_resp.status_code == 403
    assert approve_resp.json()["error"]["code"] == "ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 7: Coverage Approval Rejection — Unverified Backups Denied
# =============================================================================

def test_scenario_07_unverified_backup_coverage_denied(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Continuity Lead",
            "responsibility_name": "Emergency Operations Oversight",
            "description": "Coordinates degraded operations.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-primary-01",
            "primary_owner_name": "Sam Porter",
        },
        headers={"X-User-Id": "usr-creator-01"},
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-unverified",
                    "backup_user_name": "Tom Unverified",
                    "precedence": "PRIMARY_BACKUP",
                    "capability_verified": False,
                    "authorization_verified": False,
                }
            ],
        },
        headers={"X-User-Id": "usr-creator-01"},
    )
    cov_id = cov_resp.json()["coverage_id"]

    client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/submit",
        json={},
        headers={"X-User-Id": "usr-creator-01"},
    )

    # Approver usr-director-01 attempts approval
    approve_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/approve",
        json={"approval_notes": "Approving without verified backup."},
        headers={"X-User-Id": "usr-director-01"},
    )
    assert approve_resp.status_code == 400
    assert approve_resp.json()["error"]["code"] == "UNVERIFIED_BACKUP_COVERAGE_DENIED"


# =============================================================================
# Scenario 8: Independent Backup Verification — Deficient State
# =============================================================================

def test_scenario_08_backup_verification_deficient(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Escalation Lead",
            "responsibility_name": "Emergency Incident Escalation",
            "description": "Reviews escalated critical incidents.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-primary-02",
            "primary_owner_name": "Dr. Nancy Drew",
        },
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-cand-01",
                    "backup_user_name": "Candidate One",
                    "precedence": "PRIMARY_BACKUP",
                }
            ],
        },
    )
    cov_id = cov_resp.json()["coverage_id"]

    verify_payload = {
        "coverage_id": cov_id,
        "responsibility_id": resp_id,
        "backup_user_id": "usr-backup-cand-01",
        "capability_verified": False,
        "authorization_verified": False,
        "availability_confirmed": True,
        "deficiencies": ["Phase 84 practical demonstration pending."],
    }
    resp = client.post("/api/v1/governance-resilience-role-coverage/verifications", json=verify_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "DEFICIENT"
    assert len(data["deficiencies"]) >= 2


# =============================================================================
# Scenario 9: Independent Backup Verification — Full Verification Success
# =============================================================================

def test_scenario_09_backup_verification_success(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Escalation Lead",
            "responsibility_name": "Emergency Incident Escalation",
            "description": "Reviews escalated critical incidents.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-primary-02",
            "primary_owner_name": "Dr. Nancy Drew",
        },
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-cand-02",
                    "backup_user_name": "Candidate Two",
                    "precedence": "PRIMARY_BACKUP",
                }
            ],
        },
    )
    cov_id = cov_resp.json()["coverage_id"]

    future_expiry = (datetime.utcnow() + timedelta(days=120)).isoformat()
    verify_payload = {
        "coverage_id": cov_id,
        "responsibility_id": resp_id,
        "backup_user_id": "usr-backup-cand-02",
        "capability_assessment_ref": "ass-phase84-001",
        "capability_verified": True,
        "authorization_ref": "del-auth-2026-99",
        "authorization_verified": True,
        "authorization_expires_at": future_expiry,
        "availability_confirmed": True,
        "verification_notes": "All Phase 84 competencies and formal delegation confirmed.",
    }
    resp = client.post("/api/v1/governance-resilience-role-coverage/verifications", json=verify_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "VERIFIED"
    assert data["capability_verified"] is True
    assert data["authorization_verified"] is True

    # Check that coverage arrangement updated
    cov_check = client.get(f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}").json()
    assert cov_check["designated_backups"][0]["capability_verified"] is True
    assert cov_check["designated_backups"][0]["authorization_verified"] is True


# =============================================================================
# Scenario 10: Valid Independent Coverage Arrangement Approval
# =============================================================================

def test_scenario_10_valid_independent_coverage_approval(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Continuity Director",
            "responsibility_name": "Command Center Activation",
            "description": "Declares degraded mode command center activation.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-dir-01",
            "primary_owner_name": "Director Lee",
        },
        headers={"X-User-Id": "usr-planner-01"},
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-ready",
                    "backup_user_name": "Major Tom",
                    "precedence": "PRIMARY_BACKUP",
                    "capability_verified": True,
                    "authorization_verified": True,
                    "is_available": True,
                }
            ],
        },
        headers={"X-User-Id": "usr-planner-01"},
    )
    cov_id = cov_resp.json()["coverage_id"]

    client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/submit",
        json={"submission_notes": "Ready for approval."},
        headers={"X-User-Id": "usr-planner-01"},
    )

    approve_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/approve",
        json={"approval_notes": "Approved by Clinical Safety Governance Board Chair."},
        headers={"X-User-Id": "usr-chairperson-01"},
    )
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["status"] == "ACTIVE"
    assert data["approved_by"] == "usr-chairperson-01"


# =============================================================================
# Scenario 11: Coverage Arrangement Suspension & Closure
# =============================================================================

def test_scenario_11_coverage_suspension_and_closure(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Continuity Director",
            "responsibility_name": "Command Center Activation",
            "description": "Declares degraded mode command center activation.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-dir-01",
            "primary_owner_name": "Director Lee",
        },
        headers={"X-User-Id": "usr-planner-01"},
    )
    resp_id = create_resp.json()["responsibility_id"]

    cov_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-ready",
                    "backup_user_name": "Major Tom",
                    "precedence": "PRIMARY_BACKUP",
                    "capability_verified": True,
                    "authorization_verified": True,
                    "is_available": True,
                }
            ],
        },
        headers={"X-User-Id": "usr-planner-01"},
    )
    cov_id = cov_resp.json()["coverage_id"]

    client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/submit",
        json={},
        headers={"X-User-Id": "usr-planner-01"},
    )
    client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/approve",
        json={"approval_notes": "Approved."},
        headers={"X-User-Id": "usr-chairperson-01"},
    )

    # Suspend
    suspend_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/suspend",
        json={"reason": "Backup personnel on medical leave."},
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "SUSPENDED"

    # Close
    close_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/coverages/{cov_id}/close",
        json={"closure_reason": "Superseded by restructuring."},
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"


# =============================================================================
# Scenario 12: Single-Person Dependency Detection — Critical Risk
# =============================================================================

def test_scenario_12_single_person_dependency_critical_risk(client):
    # Tier 1 responsibility with NO backups
    client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Chief Medical Safety Officer",
            "responsibility_name": "Executive Safety Signoff",
            "description": "Sole authority for hospital clinical safety shutdown.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-cmso-sole",
            "primary_owner_name": "Dr. Sole Authority",
        },
    )

    analysis_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/dependencies/analyze",
        json={"include_tier2": True, "bottleneck_threshold": 3},
    )
    assert analysis_resp.status_code == 200
    data = analysis_resp.json()
    deps = data["single_person_dependencies"]
    assert len(deps) >= 1
    sole_dep = next(d for d in deps if d["primary_owner_id"] == "usr-cmso-sole")
    assert sole_dep["is_single_person_dependent"] is True
    assert sole_dep["risk_rating"] == "CRITICAL"
    assert sole_dep["verified_backups_count"] == 0


# =============================================================================
# Scenario 13: Personnel Concentration & Bottleneck Analysis
# =============================================================================

def test_scenario_13_personnel_concentration_bottleneck(client):
    # User 'usr-superman' assigned to 3 critical responsibilities
    for i in range(3):
        r_resp = client.post(
            "/api/v1/governance-resilience-role-coverage/responsibilities",
            json={
                "role_title": f"Critical Lead {i}",
                "responsibility_name": f"Responsibility {i}",
                "description": f"Critical function {i}",
                "criticality_tier": "TIER_1_ESSENTIAL",
                "primary_owner_id": "usr-superman",
                "primary_owner_name": "Clark Kent",
            },
        )
        resp_id = r_resp.json()["responsibility_id"]
        # Add a coverage arrangement
        client.post(
            "/api/v1/governance-resilience-role-coverage/coverages",
            json={
                "responsibility_id": resp_id,
                "designated_backups": [
                    {
                        "backup_user_id": "usr-backup-gen",
                        "backup_user_name": "Generic Backup",
                        "capability_verified": True,
                        "authorization_verified": True,
                    }
                ],
            },
        )

    analysis_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/dependencies/analyze",
        json={"include_tier2": True, "bottleneck_threshold": 3},
    )
    assert analysis_resp.status_code == 200
    concs = analysis_resp.json()["personnel_concentrations"]
    superman_conc = next(c for c in concs if c["user_id"] == "usr-superman")
    assert superman_conc["is_bottleneck"] is True
    assert superman_conc["total_critical_roles_covered"] >= 3
    assert superman_conc["risk_rating"] in ("HIGH", "CRITICAL")


# =============================================================================
# Scenario 14: Coverage Scenario Stress Testing — Primary Absent Simulation
# =============================================================================

def test_scenario_14_scenario_primary_absent_simulation(client):
    r_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Triage Lead",
            "responsibility_name": "Triage Supervision",
            "description": "Supervises degraded triage.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-primary-triage",
            "primary_owner_name": "Dr. Triage Primary",
        },
    )
    resp_id = r_resp.json()["responsibility_id"]

    client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-backup-triage",
                    "backup_user_name": "Dr. Triage Backup",
                    "capability_verified": True,
                    "authorization_verified": True,
                    "is_available": True,
                }
            ],
        },
    )

    eval_payload = {
        "scenario_type": "PRIMARY_ABSENT",
        "scenario_name": "Primary Triage Doctor Unplanned Sickness",
        "simulated_unavailable_user_ids": ["usr-primary-triage"],
    }
    resp = client.post("/api/v1/governance-resilience-role-coverage/scenarios/evaluate", json=eval_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_type"] == "PRIMARY_ABSENT"
    assert data["partially_covered_count"] >= 1
    assert data["uncovered_count"] == 0
    assert data["overall_coverage_resilience_percentage"] == 100.0


# =============================================================================
# Scenario 15: Coverage Scenario Stress Testing — Mass Unavailability / SPOF
# =============================================================================

def test_scenario_15_scenario_mass_unavailability_spof(client):
    r_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "ICU Safety Officer",
            "responsibility_name": "ICU Power Backup Oversight",
            "description": "ICU continuity during main substation failure.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-icu-primary",
            "primary_owner_name": "Dr. ICU Lead",
        },
    )
    resp_id = r_resp.json()["responsibility_id"]

    client.post(
        "/api/v1/governance-resilience-role-coverage/coverages",
        json={
            "responsibility_id": resp_id,
            "designated_backups": [
                {
                    "backup_user_id": "usr-icu-backup",
                    "backup_user_name": "Dr. ICU Secondary",
                    "capability_verified": True,
                    "authorization_verified": True,
                    "is_available": True,
                }
            ],
        },
    )

    # Both primary and backup are unavailable in disaster
    eval_payload = {
        "scenario_type": "MASS_UNAVAILABILITY",
        "scenario_name": "Severe Snowstorm Staff Shortage",
        "simulated_unavailable_user_ids": ["usr-icu-primary", "usr-icu-backup"],
    }
    resp = client.post("/api/v1/governance-resilience-role-coverage/scenarios/evaluate", json=eval_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["uncovered_count"] >= 1
    assert resp_id in data["uncovered_responsibility_ids"]
    assert len(data["single_points_of_failure_revealed"]) >= 1


# =============================================================================
# Scenario 16: Succession Plan Lifecycle & Separation of Duties
# =============================================================================

def test_scenario_16_succession_plan_lifecycle_and_separation_of_duties(client):
    r_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Clinical Director of Quality",
            "responsibility_name": "Quality Audit Governance",
            "description": "Leads annual clinical audit committee.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-dir-qual",
            "primary_owner_name": "Dr. Quality Director",
        },
    )
    resp_id = r_resp.json()["responsibility_id"]

    plan_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/succession-plans",
        json={
            "responsibility_id": resp_id,
            "candidates": [
                {
                    "user_id": "usr-candidate-01",
                    "user_name": "Dr. Candidate Future",
                    "readiness_tier": "READY_NEAR_TERM",
                    "is_nominated_emergency_successor": True,
                }
            ],
            "review_cycle_days": 180,
        },
        headers={"X-User-Id": "usr-creator-plan"},
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["succession_plan_id"]
    assert plan_resp.json()["status"] == "DRAFT"

    # Creator self-approval rejected
    self_appr = client.post(
        f"/api/v1/governance-resilience-role-coverage/succession-plans/{plan_id}/approve",
        json={"notes": "Self approving."},
        headers={"X-User-Id": "usr-creator-plan"},
    )
    assert self_appr.status_code == 403
    assert self_appr.json()["error"]["code"] == "ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION"

    # Nominated candidate approval rejected
    cand_appr = client.post(
        f"/api/v1/governance-resilience-role-coverage/succession-plans/{plan_id}/approve",
        json={"notes": "Candidate approving."},
        headers={"X-User-Id": "usr-candidate-01"},
    )
    assert cand_appr.status_code == 403
    assert cand_appr.json()["error"]["code"] == "ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent approval
    ind_appr = client.post(
        f"/api/v1/governance-resilience-role-coverage/succession-plans/{plan_id}/approve",
        json={"notes": "Board approved succession pipeline."},
        headers={"X-User-Id": "usr-independent-exec"},
    )
    assert ind_appr.status_code == 200
    assert ind_appr.json()["status"] == "APPROVED"


# =============================================================================
# Scenario 17: Handover Initiation & Self-Handover Prohibition
# =============================================================================

def test_scenario_17_handover_initiation_and_self_prohibition(client):
    r_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "On-Duty Clinical Safety Lead",
            "responsibility_name": "Shift Triage Safety",
            "description": "Duty lead for inpatient safety escalation.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-shift-lead-01",
            "primary_owner_name": "Dr. Outgoing Lead",
        },
    )
    resp_id = r_resp.json()["responsibility_id"]

    # Attempt handover to self
    self_handover = client.post(
        "/api/v1/governance-resilience-role-coverage/handovers",
        json={
            "responsibility_id": resp_id,
            "incoming_user_id": "usr-shift-lead-01",
            "handover_reason": "Testing self handover",
        },
        headers={"X-User-Id": "usr-shift-lead-01"},
    )
    assert self_handover.status_code == 400
    assert self_handover.json()["error"]["code"] == "ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION"

    # Valid handover initiation with open governance items
    valid_handover = client.post(
        "/api/v1/governance-resilience-role-coverage/handovers",
        json={
            "responsibility_id": resp_id,
            "incoming_user_id": "usr-shift-lead-02",
            "handover_reason": "Planned shift rotation and leave.",
            "open_governance_items": [
                {
                    "item_type": "SAFETY_ESCALATION",
                    "source_phase": "Phase 67",
                    "item_reference_id": "esc-phase67-402",
                    "summary": "Pending review of contrast dye allergic reaction escalation.",
                    "urgency_level": "CRITICAL",
                },
                {
                    "item_type": "MANAGEMENT_DECISION",
                    "source_phase": "Phase 72",
                    "item_reference_id": "dec-phase72-101",
                    "summary": "Implementation of pediatric infusion pump safeguard.",
                    "urgency_level": "HIGH",
                },
            ],
            "outgoing_checklist_completed": True,
            "outgoing_signoff_notes": "All active alerts briefed to incoming lead.",
        },
        headers={"X-User-Id": "usr-shift-lead-01"},
    )
    assert valid_handover.status_code == 201
    data = valid_handover.json()
    assert data["handover_id"].startswith("hand-")
    assert data["status"] == "PENDING_INCOMING_ACKNOWLEDGEMENT"
    assert len(data["open_governance_items"]) == 2


# =============================================================================
# Scenario 18: Handover Acknowledgement & Completion Lifecycle
# =============================================================================

def test_scenario_18_handover_acknowledgement_and_completion(client):
    r_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "On-Duty Clinical Safety Lead",
            "responsibility_name": "Shift Triage Safety",
            "description": "Duty lead for inpatient safety escalation.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-shift-lead-01",
            "primary_owner_name": "Dr. Outgoing Lead",
        },
    )
    resp_id = r_resp.json()["responsibility_id"]

    hand_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/handovers",
        json={
            "responsibility_id": resp_id,
            "incoming_user_id": "usr-shift-lead-02",
            "handover_reason": "Shift handover",
        },
        headers={"X-User-Id": "usr-shift-lead-01"},
    )
    hand_id = hand_resp.json()["handover_id"]

    # Unauthorized user tries to acknowledge
    unauth_ack = client.post(
        f"/api/v1/governance-resilience-role-coverage/handovers/{hand_id}/acknowledge",
        json={"incoming_acknowledgement_notes": "Acknowledged by imposter."},
        headers={"X-User-Id": "usr-stranger"},
    )
    assert unauth_ack.status_code == 403
    assert unauth_ack.json()["error"]["code"] == "ROLE_COVERAGE_ACCESS_DENIED"

    # Incoming user acknowledges
    ack_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/handovers/{hand_id}/acknowledge",
        json={"incoming_acknowledgement_notes": "Received briefing and open escalation files."},
        headers={"X-User-Id": "usr-shift-lead-02"},
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"

    # Supervisor completes handover
    comp_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/handovers/{hand_id}/complete",
        json={"completion_notes": "Supervisor verified transfer of operational keys and tokens."},
        headers={"X-User-Id": "usr-supervisor-99"},
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "COMPLETED"
    assert comp_resp.json()["supervisor_reviewed_by"] == "usr-supervisor-99"


# =============================================================================
# Scenario 19: Coverage Gap Lifecycle & Evidence-Backed Resolution
# =============================================================================

def test_scenario_19_coverage_gap_lifecycle_and_resolution(client):
    r_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Oxygen Infrastructure Lead",
            "responsibility_name": "Manifold Valve Safety",
            "description": "Critical valve monitoring.",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-valve-01",
            "primary_owner_name": "Bob Valve",
        },
    )
    resp_id = r_resp.json()["responsibility_id"]

    # 1. Create Gap
    gap_resp = client.post(
        "/api/v1/governance-resilience-role-coverage/gaps",
        json={
            "responsibility_id": resp_id,
            "category": "NO_BACKUP_DESIGNATED",
            "severity": "CRITICAL",
            "title": "Zero designated backup for oxygen manifold valve safety",
            "description": "Essential role has only primary owner identified.",
        },
    )
    assert gap_resp.status_code == 201
    gap_id = gap_resp.json()["gap_id"]
    assert gap_resp.json()["status"] == "IDENTIFIED"

    # 2. Assign Gap
    assign_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/gaps/{gap_id}/assign",
        json={"assigned_to": "usr-remediator-01", "notes": "Assigned to identify qualified backup."},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "ASSIGNED"

    # 3. Escalate to Phase 67 Safety Escalation
    esc_resp = client.post(
        f"/api/v1/governance-resilience-role-coverage/gaps/{gap_id}/escalate",
        json={
            "escalated_to_phase": "PHASE_67_ESCALATION",
            "escalation_reference_id": "esc-safety-2026-90",
            "escalation_notes": "Escalated due to lack of response within 48h SLA.",
        },
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["status"] == "ESCALATED"

    # 4. Attempt resolution without evidence link -> Fails
    fail_resolve = client.post(
        f"/api/v1/governance-resilience-role-coverage/gaps/{gap_id}/resolve",
        json={"remediation_notes": "Trying to resolve without linking coverage or succession plan."},
    )
    assert fail_resolve.status_code == 400
    assert fail_resolve.json()["error"]["code"] == "INVALID_COVERAGE_GAP_STATE"

    # 5. Resolve with verified coverage arrangement link
    success_resolve = client.post(
        f"/api/v1/governance-resilience-role-coverage/gaps/{gap_id}/resolve",
        json={
            "remediation_notes": "Qualified backup certified and appointed under cov-oxy-001.",
            "verified_coverage_id": "cov-oxy-001",
        },
        headers={"X-User-Id": "usr-auditor-01"},
    )
    assert success_resolve.status_code == 200
    assert success_resolve.json()["status"] == "VERIFIED_RESOLVED"
    assert success_resolve.json()["resolution_verified_by"] == "usr-auditor-01"


# =============================================================================
# Scenario 20: Executive Reports & Patient Access Rejection
# =============================================================================

def test_scenario_20_reports_and_patient_access_rejection(client):
    # Setup some responsibilities
    client.post(
        "/api/v1/governance-resilience-role-coverage/responsibilities",
        json={
            "role_title": "Reporting Test Lead",
            "responsibility_name": "Test Resp",
            "description": "For testing reports",
            "criticality_tier": "TIER_1_ESSENTIAL",
            "primary_owner_id": "usr-rep-lead",
            "primary_owner_name": "Test Reporter",
        },
    )

    # 1. Summary Report
    sum_resp = client.get("/api/v1/governance-resilience-role-coverage/reports/summary")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["total_critical_responsibilities"] >= 1
    assert "TIER_1_ESSENTIAL" in sum_data["tier_distribution"]

    # 2. Dependency Report
    dep_resp = client.get("/api/v1/governance-resilience-role-coverage/reports/dependencies")
    assert dep_resp.status_code == 200
    assert "single_person_dependencies" in dep_resp.json()

    # 3. Deficiencies Report
    def_resp = client.get("/api/v1/governance-resilience-role-coverage/reports/deficiencies")
    assert def_resp.status_code == 200
    assert "deficient_verifications" in def_resp.json()

    # 4. Expiring Schedule Report
    exp_resp = client.get("/api/v1/governance-resilience-role-coverage/reports/expiring-schedule?days=90")
    assert exp_resp.status_code == 200
    assert "expiring_items" in exp_resp.json()

    # 5. Patient Access Rejection (HTTP 403 INSUFFICIENT_PERMISSIONS)
    patient_resp = client.get(
        "/api/v1/governance-resilience-role-coverage/reports/summary",
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-01"},
    )
    assert patient_resp.status_code == 403
    assert patient_resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "Patients are not permitted" in patient_resp.json()["error"]["message"]

"""Phase 84: Clinical Safety Governance Resilience Capability Assessment Tests.

Comprehensive test suite verifying:
- Scenario 1: Capability framework creation in DRAFT state with disclaimer and version 1
- Scenario 2: Framework submission and creator self-approval separation of duties rejection (HTTP 400)
- Scenario 3: Independent approval and publication of capability framework
- Scenario 4: Material update on published framework increments version and resets state
- Scenario 5: Role-based competency requirement mapping and independent approval
- Scenario 6: Capability assessment creation in PLANNED state
- Scenario 7: Assessment scheduling with subject self-assessor rejection and valid assignment
- Scenario 8: Evidence submission for scheduled capability assessment
- Scenario 9: Assessment review with subject self-review rejection and valid scoring
- Scenario 10: Assessment verification separation of duties (assessor/subject rejected) and independent verification
- Scenario 11: Practical capability demonstration recording and participant self-review rejection
- Scenario 12: Team readiness assessment detecting critical role vacancy (no score averaging)
- Scenario 13: Team readiness assessment detecting backup coverage deficit
- Scenario 14: Team readiness assessment with full coverage verifying readiness
- Scenario 15: Delegated-authority readiness assessment and delegate self-assessment rejection
- Scenario 16: Capability gap detection, identifier self-validation rejection, and independent validation
- Scenario 17: Disposition of validated capability gap to Phase 54 CAPA
- Scenario 18: Operational readiness assessment, assessor self-verification rejection, and independent verification
- Scenario 19: Capability development remediation proposal lifecycle and reassessment trigger
- Scenario 20: Patient role authorization rejection (HTTP 403 INSUFFICIENT_PERMISSIONS)
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
from app.repositories.governance_resilience_capability_repository import (
    get_governance_resilience_capability_repository,
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
    repo = get_governance_resilience_capability_repository()
    repo.clear()
    yield
    repo.clear()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Capability Framework Creation
# =============================================================================

def test_scenario_01_create_capability_framework(client):
    payload = {
        "framework_name": "Clinical Safety Governance Resilience Capability Framework 2026",
        "description": "Enterprise capability assessment criteria covering degraded mode operations.",
        "capabilities": [
            {
                "capability_id": "cap-oxy-manifold",
                "name": "Oxygen Manifold Switchover Coordination",
                "description": "Ability to coordinate manual oxygen manifold failure switchover.",
                "domain": "GOVERNANCE_CONTINUITY",
                "organizational_scope": "GLOBAL",
                "applicable_roles": ["CONTINUITY_COORDINATOR", "NURSE_IN_CHARGE"],
                "required_proficiency": "PROFICIENT",
                "assessment_method": "PRACTICAL_DEMONSTRATION",
                "required_evidence_types": ["DRILL_OBSERVATION", "CHECKLIST_SUBMISSION"],
                "assessment_frequency_days": 180,
            }
        ],
    }
    response = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json=payload,
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["framework_name"] == payload["framework_name"]
    assert data["lifecycle_state"] == "DRAFT"
    assert data["version"] == 1
    assert data["created_by"] == "usr-author-01"
    assert len(data["capabilities"]) == 1
    assert "administrative governance instruments" in data["disclaimer"]


# =============================================================================
# Scenario 2: Framework Submission & Creator Self-Approval Violation (HTTP 400)
# =============================================================================

def test_scenario_02_framework_creator_self_approval_violation(client):
    create_res = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "ICU Resilience Framework", "description": "Criteria for ICU."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    fid = create_res.json()["framework_id"]

    # Submit framework
    sub_res = client.post(
        f"/api/v1/governance-resilience-capability/frameworks/{fid}/submit",
        json={"notes": "Submitted for approval."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["lifecycle_state"] == "SUBMITTED"

    # Creator attempts to approve own framework (should fail 400)
    appr_res = client.post(
        f"/api/v1/governance-resilience-capability/frameworks/{fid}/approve",
        json={"notes": "Creator approval attempt."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "ADMIN"},
    )
    assert appr_res.status_code == 400
    assert appr_res.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 3: Independent Approval and Publication of Framework
# =============================================================================

def test_scenario_03_independent_approval_and_publication(client):
    create_res = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Trauma Network Resilience Framework", "description": "Criteria for trauma."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_res.json()["framework_id"]
    client.post(f"/api/v1/governance-resilience-capability/frameworks/{fid}/submit", json={}, headers={"X-User-Id": "usr-author-01"})

    # Independent approver approves
    appr_res = client.post(
        f"/api/v1/governance-resilience-capability/frameworks/{fid}/approve",
        json={"notes": "Approved by Clinical Safety Officer."},
        headers={"X-User-Id": "usr-cso-02"},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["lifecycle_state"] == "APPROVED"
    assert appr_res.json()["approved_by"] == "usr-cso-02"

    # Publish framework
    pub_res = client.post(
        f"/api/v1/governance-resilience-capability/frameworks/{fid}/publish",
        json={"notes": "Published organization-wide."},
        headers={"X-User-Id": "usr-cso-02"},
    )
    assert pub_res.status_code == 200
    assert pub_res.json()["lifecycle_state"] == "PUBLISHED"
    assert pub_res.json()["published_at"] is not None


# =============================================================================
# Scenario 4: Material Update on Published Framework Increments Version
# =============================================================================

def test_scenario_04_published_framework_material_update(client):
    create_res = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Emergency Department Framework", "description": "Initial."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_res.json()["framework_id"]
    client.post(f"/api/v1/governance-resilience-capability/frameworks/{fid}/submit", json={}, headers={"X-User-Id": "usr-author-01"})
    client.post(f"/api/v1/governance-resilience-capability/frameworks/{fid}/approve", json={}, headers={"X-User-Id": "usr-cso-02"})
    client.post(f"/api/v1/governance-resilience-capability/frameworks/{fid}/publish", json={}, headers={"X-User-Id": "usr-cso-02"})

    # Update published framework
    update_res = client.patch(
        f"/api/v1/governance-resilience-capability/frameworks/{fid}",
        json={"description": "Updated criteria with enhanced triage requirements."},
        headers={"X-User-Id": "usr-author-01"},
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["version"] == 2
    assert data["lifecycle_state"] == "DRAFT"

    # Verify versions endpoint
    vers = client.get(f"/api/v1/governance-resilience-capability/frameworks/{fid}/versions").json()
    assert len(vers) >= 2


# =============================================================================
# Scenario 5: Role Competency Requirement Mapping & Approval
# =============================================================================

def test_scenario_05_role_competency_mapping_and_approval(client):
    create_f = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Hospital Framework", "description": "General."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_f.json()["framework_id"]

    req_payload = {
        "role_name": "CONTINUITY_PLAN_OWNER",
        "framework_id": fid,
        "framework_version": 1,
        "required_capabilities": [
            {
                "capability_id": "cap-plan-review",
                "required_proficiency": "PROFICIENT",
                "mandatory_for_primary": True,
                "mandatory_for_backup": True,
            }
        ],
    }
    create_req = client.post(
        "/api/v1/governance-resilience-capability/role-requirements",
        json=req_payload,
        headers={"X-User-Id": "usr-author-01"},
    )
    assert create_req.status_code == 201
    rid = create_req.json()["requirement_id"]
    assert create_req.json()["status"] == "DRAFT"

    # Approve role requirement
    appr_req = client.post(
        f"/api/v1/governance-resilience-capability/role-requirements/{rid}/approve",
        json={},
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert appr_req.status_code == 200
    assert appr_req.json()["status"] == "APPROVED"


# =============================================================================
# Scenario 6: Capability Assessment Creation in PLANNED State
# =============================================================================

def test_scenario_06_create_capability_assessment(client):
    create_f = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Surgical Framework", "description": "Surgical."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_f.json()["framework_id"]

    create_ass = client.post(
        "/api/v1/governance-resilience-capability/assessments",
        json={
            "framework_id": fid,
            "applicable_role": "SURGICAL_CONTINUITY_LEAD",
            "subject_user_id": "usr-surgeon-01",
        },
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert create_ass.status_code == 201
    data = create_ass.json()
    assert data["lifecycle_state"] == "PLANNED"
    assert data["applicable_role"] == "SURGICAL_CONTINUITY_LEAD"
    assert data["subject_user_id"] == "usr-surgeon-01"


# =============================================================================
# Scenario 7: Assessment Scheduling & Subject Self-Assessor Rejection (HTTP 400)
# =============================================================================

def test_scenario_07_assessment_scheduling_self_assessor_rejection(client):
    create_f = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Pharmacy Framework", "description": "Pharmacy."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_f.json()["framework_id"]

    create_ass = client.post(
        "/api/v1/governance-resilience-capability/assessments",
        json={"framework_id": fid, "applicable_role": "PHARMACY_LEAD", "subject_user_id": "usr-pharmacist-01"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    aid = create_ass.json()["assessment_id"]

    # Subject assigned as own assessor (should fail 400)
    sched_fail = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/schedule",
        json={"scheduled_date": "2026-12-01T10:00:00Z", "assessor_id": "usr-pharmacist-01"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert sched_fail.status_code == 400
    assert sched_fail.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Distinct assessor assigned
    sched_ok = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/schedule",
        json={"scheduled_date": "2026-12-01T10:00:00Z", "assessor_id": "usr-assessor-02"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert sched_ok.status_code == 200
    assert sched_ok.json()["lifecycle_state"] == "SCHEDULED"
    assert sched_ok.json()["assessor_id"] == "usr-assessor-02"


# =============================================================================
# Scenario 8: Evidence Submission for Scheduled Assessment
# =============================================================================

def test_scenario_08_submit_assessment_evidence(client):
    create_f = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Radiology Framework", "description": "Radiology."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_f.json()["framework_id"]
    create_ass = client.post(
        "/api/v1/governance-resilience-capability/assessments",
        json={"framework_id": fid, "applicable_role": "RADIOLOGY_LEAD", "subject_user_id": "usr-radiologist-01"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    aid = create_ass.json()["assessment_id"]

    sub_evd = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/submit-evidence",
        json={"evidence_references": ["p81-exercise-doc-01", "p80-checklist-02"], "notes": "Exercise logs."},
        headers={"X-User-Id": "usr-radiologist-01"},
    )
    assert sub_evd.status_code == 200
    assert sub_evd.json()["lifecycle_state"] == "EVIDENCE_SUBMITTED"
    assert len(sub_evd.json()["evidence_references"]) == 2


# =============================================================================
# Scenario 9: Assessment Review with Subject Self-Review Rejection (HTTP 400)
# =============================================================================

def test_scenario_09_assessment_review_and_self_review_rejection(client):
    create_f = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Pathology Framework", "description": "Pathology."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_f.json()["framework_id"]
    create_ass = client.post(
        "/api/v1/governance-resilience-capability/assessments",
        json={"framework_id": fid, "applicable_role": "PATHOLOGY_LEAD", "subject_user_id": "usr-pathologist-01"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    aid = create_ass.json()["assessment_id"]

    # Subject attempts self-review (should fail 400)
    rev_fail = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/review",
        json={"assessment_outcome": "DEMONSTRATED", "reviewer_comments": "Self evaluation."},
        headers={"X-User-Id": "usr-pathologist-01"},
    )
    assert rev_fail.status_code == 400
    assert rev_fail.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Assessor performs review
    rev_ok = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/review",
        json={"assessment_outcome": "DEMONSTRATED", "reviewer_comments": "Demonstrated full specimen cold-chain capability."},
        headers={"X-User-Id": "usr-assessor-02"},
    )
    assert rev_ok.status_code == 200
    assert rev_ok.json()["lifecycle_state"] == "ASSESSED"
    assert rev_ok.json()["assessment_outcome"] == "DEMONSTRATED"
    assert rev_ok.json()["assessor_id"] == "usr-assessor-02"


# =============================================================================
# Scenario 10: Verification Separation of Duties (Assessor/Subject Prohibited)
# =============================================================================

def test_scenario_10_assessment_verification_separation_of_duties(client):
    create_f = client.post(
        "/api/v1/governance-resilience-capability/frameworks",
        json={"framework_name": "Dialysis Framework", "description": "Dialysis."},
        headers={"X-User-Id": "usr-author-01"},
    )
    fid = create_f.json()["framework_id"]
    create_ass = client.post(
        "/api/v1/governance-resilience-capability/assessments",
        json={"framework_id": fid, "applicable_role": "DIALYSIS_LEAD", "subject_user_id": "usr-nurse-01"},
        headers={"X-User-Id": "usr-lead-01"},
    )
    aid = create_ass.json()["assessment_id"]
    client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/review",
        json={"assessment_outcome": "DEMONSTRATED"},
        headers={"X-User-Id": "usr-assessor-02"},
    )

    # Subject attempts to verify (should fail 400)
    v_subj = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/verify",
        json={"verified": True},
        headers={"X-User-Id": "usr-nurse-01"},
    )
    assert v_subj.status_code == 400
    assert v_subj.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Assessor attempts to verify own assessment (should fail 400)
    v_assr = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/verify",
        json={"verified": True},
        headers={"X-User-Id": "usr-assessor-02"},
    )
    assert v_assr.status_code == 400
    assert v_assr.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent third party verifies
    v_indep = client.post(
        f"/api/v1/governance-resilience-capability/assessments/{aid}/verify",
        json={"verified": True, "verification_notes": "Audited evidence and verified."},
        headers={"X-User-Id": "usr-auditor-03"},
    )
    assert v_indep.status_code == 200
    assert v_indep.json()["lifecycle_state"] == "VERIFIED"
    assert v_indep.json()["verifier_id"] == "usr-auditor-03"


# =============================================================================
# Scenario 11: Practical Demonstration Recording & Review
# =============================================================================

def test_scenario_11_practical_demonstration_recording(client):
    demo_res = client.post(
        "/api/v1/governance-resilience-capability/demonstrations",
        json={
            "capability_id": "cap-switchover",
            "participant_user_id": "usr-eng-01",
            "method": "SIMULATED_GOVERNANCE_DISRUPTION",
            "expected_behavior": "Transfer grid power to diesel generator within 90s.",
            "observed_behavior": "Generator started in 45s; full load established in 80s.",
            "outcome": "SUCCESSFUL",
            "evidence_references": ["p80-drill-log-99"],
        },
        headers={"X-User-Id": "usr-assessor-02"},
    )
    assert demo_res.status_code == 201
    did = demo_res.json()["demonstration_id"]
    assert demo_res.json()["outcome"] == "SUCCESSFUL"
    assert demo_res.json()["review_status"] == "RECORDED"

    # Participant self-review attempt (should fail 400)
    rev_fail = client.post(
        f"/api/v1/governance-resilience-capability/demonstrations/{did}/review",
        json={"review_status": "REVIEWED"},
        headers={"X-User-Id": "usr-eng-01"},
    )
    assert rev_fail.status_code == 400
    assert rev_fail.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent reviewer reviews
    rev_ok = client.post(
        f"/api/v1/governance-resilience-capability/demonstrations/{did}/review",
        json={"review_status": "REVIEWED", "reviewer_notes": "Timing verified by telemetry logs."},
        headers={"X-User-Id": "usr-evaluator-03"},
    )
    assert rev_ok.status_code == 200
    assert rev_ok.json()["review_status"] == "REVIEWED"


# =============================================================================
# Scenario 12: Team Readiness Detecting Critical Vacancy (No Score Averaging)
# =============================================================================

def test_scenario_12_team_readiness_critical_role_vacant(client):
    team_payload = {
        "team_name": "ICU_Emergency_Continuity_Team",
        "department_id": "dept-icu",
        "facility_id": "fac-apollo-main",
        "framework_id": "cfw-001",
        "role_coverage": [
            {
                "role_name": "ICU_CONTINUITY_COORDINATOR",
                "primary_user_id": None,  # Vacant!
                "backup_user_id": "usr-backup-02",
                "has_verified_evidence": False,
                "is_vacant": True,
            },
            {
                "role_name": "LEAD_RESPIRATORY_THERAPIST",
                "primary_user_id": "usr-therapist-01",
                "backup_user_id": "usr-therapist-02",
                "has_verified_evidence": True,
                "is_vacant": False,
            },
        ],
    }
    response = client.post(
        "/api/v1/governance-resilience-capability/teams/ICU_Emergency_Continuity_Team/assess-readiness",
        json=team_payload,
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["readiness_outcome"] == "CRITICAL_ROLES_VACANT"
    assert "ICU_CONTINUITY_COORDINATOR" in data["critical_vacancies"]


# =============================================================================
# Scenario 13: Team Readiness Detecting Backup Deficit
# =============================================================================

def test_scenario_13_team_readiness_backup_deficit(client):
    team_payload = {
        "team_name": "Surgical_Resilience_Team",
        "framework_id": "cfw-001",
        "role_coverage": [
            {
                "role_name": "SURGICAL_COMMANDER",
                "primary_user_id": "usr-surgeon-01",
                "backup_user_id": None,  # Missing backup!
                "has_verified_evidence": True,
                "is_vacant": False,
            }
        ],
    }
    response = client.post(
        "/api/v1/governance-resilience-capability/teams/Surgical_Resilience_Team/assess-readiness",
        json=team_payload,
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["readiness_outcome"] == "BACKUP_COVERAGE_DEFICIT"
    assert "SURGICAL_COMMANDER" in data["backup_deficits"]


# =============================================================================
# Scenario 14: Team Readiness Full Coverage Verified Ready
# =============================================================================

def test_scenario_14_team_readiness_verified_ready(client):
    team_payload = {
        "team_name": "Emergency_Command_Team",
        "framework_id": "cfw-001",
        "role_coverage": [
            {
                "role_name": "INCIDENT_COMMANDER",
                "primary_user_id": "usr-cmo-01",
                "backup_user_id": "usr-cmo-02",
                "has_verified_evidence": True,
                "is_vacant": False,
            }
        ],
    }
    response = client.post(
        "/api/v1/governance-resilience-capability/teams/Emergency_Command_Team/assess-readiness",
        json=team_payload,
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert response.status_code == 200
    assert response.json()["readiness_outcome"] == "VERIFIED_READY"


# =============================================================================
# Scenario 15: Delegated-Authority Readiness & Self-Assessment Rejection
# =============================================================================

def test_scenario_15_delegated_authority_readiness(client):
    payload = {
        "delegated_authority_reference": "del-auth-ref-2026-01",
        "delegate_user_id": "usr-registrar-01",
        "delegator_role": "CHIEF_MEDICAL_OFFICER",
        "authorized_scope": "EMERGENCY_TRANSFER_APPROVALS",
        "awareness_demonstrated": True,
        "documentation_capability_verified": True,
        "escalation_pathway_verified": True,
        "practical_scenario_demonstrated": True,
    }

    # Delegate self-assessment attempt (should fail 400)
    self_del = client.post(
        "/api/v1/governance-resilience-capability/delegated-authority-readiness/assess",
        json=payload,
        headers={"X-User-Id": "usr-registrar-01"},
    )
    assert self_del.status_code == 400
    assert self_del.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Assessor assesses readiness
    del_ok = client.post(
        "/api/v1/governance-resilience-capability/delegated-authority-readiness/assess",
        json=payload,
        headers={"X-User-Id": "usr-assessor-02"},
    )
    assert del_ok.status_code == 200
    assert del_ok.json()["status"] == "VERIFIED_READY"


# =============================================================================
# Scenario 16: Capability Gap Detection & Independent Validation
# =============================================================================

def test_scenario_16_capability_gap_detection_and_validation(client):
    gap_res = client.post(
        "/api/v1/governance-resilience-capability/capability-gaps",
        json={
            "category": "MISSING_BACKUP_COVERAGE",
            "severity": "HIGH",
            "title": "No Qualified Backup for Blood Bank Cold Chain Lead",
            "description": "Blood bank relies solely on single staff member for temperature excursion protocols.",
            "affected_role": "BLOOD_BANK_CONTINUITY_LEAD",
        },
        headers={"X-User-Id": "usr-auditor-01"},
    )
    assert gap_res.status_code == 201
    gid = gap_res.json()["gap_id"]
    assert gap_res.json()["status"] == "DETECTED"

    # Identifier self-validation attempt (should fail 400)
    val_fail = client.post(
        f"/api/v1/governance-resilience-capability/capability-gaps/{gid}/validate",
        json={"is_valid": True},
        headers={"X-User-Id": "usr-auditor-01"},
    )
    assert val_fail.status_code == 400
    assert val_fail.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent validator validates
    val_ok = client.post(
        f"/api/v1/governance-resilience-capability/capability-gaps/{gid}/validate",
        json={"is_valid": True, "validation_notes": "Confirmed zero trained backup personnel."},
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert val_ok.status_code == 200
    assert val_ok.json()["status"] == "VALIDATED"


# =============================================================================
# Scenario 17: Disposition of Validated Gap to Phase 54 CAPA
# =============================================================================

def test_scenario_17_disposition_gap_to_capa(client):
    gap_res = client.post(
        "/api/v1/governance-resilience-capability/capability-gaps",
        json={
            "category": "REPEATED_UNSUCCESSFUL_DEMONSTRATION",
            "severity": "CRITICAL",
            "title": "Repeated Generator Switch Failure in West Wing",
            "description": "Technicians missed target RTO during two consecutive simulation drills.",
        },
        headers={"X-User-Id": "usr-eng-lead-01"},
    )
    gid = gap_res.json()["gap_id"]

    # Attempt disposition before validation (should fail 400)
    disp_fail = client.post(
        f"/api/v1/governance-resilience-capability/capability-gaps/{gid}/disposition",
        json={"disposition_type": "CAPA_REFERRAL", "notes": "Root cause analysis."},
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert disp_fail.status_code == 400
    assert disp_fail.json()["error"]["code"] == "INVALID_CAPABILITY_GAP_STATE"

    # Validate gap
    client.post(
        f"/api/v1/governance-resilience-capability/capability-gaps/{gid}/validate",
        json={"is_valid": True},
        headers={"X-User-Id": "usr-lead-02"},
    )

    # Disposition to Phase 54 CAPA
    disp_ok = client.post(
        f"/api/v1/governance-resilience-capability/capability-gaps/{gid}/disposition",
        json={"disposition_type": "CAPA_REFERRAL", "notes": "Initiate corrective action for electrical switch team."},
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert disp_ok.status_code == 200
    assert disp_ok.json()["status"] == "CAPA_REFERRED"
    assert disp_ok.json()["capa_referral_id"].startswith("capa-p84-")


# =============================================================================
# Scenario 18: Operational Readiness Assessment & Verification
# =============================================================================

def test_scenario_18_operational_readiness_assessment_and_verification(client):
    rdy_res = client.post(
        "/api/v1/governance-resilience-capability/readiness/assess",
        json={
            "scope_type": "FACILITY",
            "scope_id": "fac-apollo-main",
            "outcome": "READY_SUBJECT_TO_CONDITIONS",
            "conditions": "Require secondary fuel delivery contract confirmation.",
        },
        headers={"X-User-Id": "usr-assessor-01"},
    )
    assert rdy_res.status_code == 201
    rid = rdy_res.json()["readiness_id"]
    assert rdy_res.json()["outcome"] == "READY_SUBJECT_TO_CONDITIONS"

    # Assessor self-verification attempt (should fail 400)
    v_fail = client.post(
        f"/api/v1/governance-resilience-capability/readiness/{rid}/verify",
        json={"verified": True},
        headers={"X-User-Id": "usr-assessor-01"},
    )
    assert v_fail.status_code == 400
    assert v_fail.json()["error"]["code"] == "CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent verifier verifies
    v_ok = client.post(
        f"/api/v1/governance-resilience-capability/readiness/{rid}/verify",
        json={"verified": True, "conditions": "Fuel contract verified on file."},
        headers={"X-User-Id": "usr-cso-02"},
    )
    assert v_ok.status_code == 200
    assert v_ok.json()["outcome"] == "VERIFIED_READY"
    assert v_ok.json()["verifier_id"] == "usr-cso-02"


# =============================================================================
# Scenario 19: Capability Development Proposal & Reassessment Trigger
# =============================================================================

def test_scenario_19_development_proposal_and_reassessment(client):
    # Propose capability development
    prop_res = client.post(
        "/api/v1/governance-resilience-capability/development-proposals",
        json={
            "target_capability_id": "cap-switchover",
            "target_role_or_team": "ELECTRICAL_MAINTENANCE_TEAM",
            "proposed_intervention": "SUPERVISED_PRACTICAL_DEMO",
            "rationalization": "Address drill timing deficit.",
            "expected_improvement": "Achieve generator switchover within 60s.",
            "assigned_owner": "usr-eng-lead-01",
        },
        headers={"X-User-Id": "usr-author-01"},
    )
    assert prop_res.status_code == 201
    pid = prop_res.json()["proposal_id"]
    assert prop_res.json()["status"] == "PROPOSED"

    # Approve proposal
    appr_prop = client.post(
        f"/api/v1/governance-resilience-capability/development-proposals/{pid}/approve",
        json={},
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert appr_prop.status_code == 200
    assert appr_prop.json()["status"] == "APPROVED"

    # Trigger reassessment
    rea_res = client.post(
        "/api/v1/governance-resilience-capability/reassessments",
        json={
            "subject_type": "TEAM",
            "subject_id": "ELECTRICAL_MAINTENANCE_TEAM",
            "trigger_reason": "REPEATED_UNSUCCESSFUL_DEMONSTRATION",
            "notes": "Reassessment scheduled post remediation drill.",
        },
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert rea_res.status_code == 201
    reid = rea_res.json()["reassessment_id"]
    assert rea_res.json()["status"] == "TRIGGERED"

    # Complete reassessment
    comp_rea = client.post(
        f"/api/v1/governance-resilience-capability/reassessments/{reid}/complete",
        json={"outcome_notes": "Team demonstrated 55s switchover under supervised conditions."},
        headers={"X-User-Id": "usr-lead-02"},
    )
    assert comp_rea.status_code == 200
    assert comp_rea.json()["status"] == "COMPLETED"


# =============================================================================
# Scenario 20: Security & Patient Role Access Denial (HTTP 403)
# =============================================================================

def test_scenario_20_patient_role_access_denied(client):
    response = client.get(
        "/api/v1/governance-resilience-capability/frameworks",
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-01"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "Patients are not permitted to access" in response.json()["error"]["message"]

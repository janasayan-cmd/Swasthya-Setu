"""Phase 80: Clinical Safety Governance Strategic Resilience, Continuity Planning & Recovery Assurance Tests.

Comprehensive test suite verifying:
- Scenario 1: Critical capability inventory lifecycle (DRAFT -> SUBMITTED -> APPROVED)
- Scenario 2: Capability approval separation of duties (owner cannot approve own capability -> 403)
- Scenario 3: Continuity requirements management (RTO, RPO, MTPD, MBCO) and capability linkage
- Scenario 4: Dependency mapping and SPOF detection
- Scenario 5: Dependency validation workflow
- Scenario 6: Version-controlled continuity plan lifecycle (DRAFT -> SUBMITTED -> APPROVED)
- Scenario 7: Continuity plan approval separation of duties (owner cannot approve own plan -> 403)
- Scenario 8: Material plan revision preserving approved version baseline in version_history
- Scenario 9: Disruption registration, tracking, and closure with resolution evidence
- Scenario 10: Continuity activation authorization and separation of duties (requestor cannot authorize own activation -> 403)
- Scenario 11: Coordinator activation acknowledgement
- Scenario 12: Alternative operating arrangement tracking and deactivation
- Scenario 13: Temporary decision logging and authoritative reconciliation (preserving provenance)
- Scenario 14: Decision reconciliation conflict detection and resolution
- Scenario 15: Governance recovery coordination, milestones, and independent verification
- Scenario 16: Continuity exercise scheduling, execution, and weakness evaluation
- Scenario 17: Continuity gap detection and authoritative corrective action routing (Phase 54 CAPA)
- Scenario 18: Assurance reporting and idempotent routine maintenance scan
- Scenario 19: Multi-tenant boundary isolation
- Scenario 20: Patient role authorization enforcement (HTTP 403 Forbidden across all endpoints)
"""

from datetime import datetime, timezone
import os

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_continuity_repository import (
    get_governance_continuity_repository,
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
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_current_user] = mock_current_user
    repo = get_governance_continuity_repository()
    repo.clear()
    yield
    repo.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Critical Capability Inventory Lifecycle
# =============================================================================

def test_scenario_1_critical_capability_lifecycle(client: TestClient):
    author_headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    approver_headers = {"X-User-Id": "usr-approver-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    create_payload = {
        "name": "Clinical Safety Emergency Triage Escalation",
        "description": "24x7 triage escalation for critical clinical incidents and high-risk alerts.",
        "responsible_department": "Clinical Governance & Risk Management",
        "accountable_owner_id": "usr-author-01",
        "supporting_roles": ["Clinical Safety Officer", "On-Call Risk Manager"],
        "related_workflow": "PHASE_49_INCIDENT_ESCALATION",
        "criticality": "TIER_1_CRITICAL",
        "minimum_operational_requirements": "Continuous availability of at least 1 qualified clinician.",
        "max_acceptable_interruption_hours": 2.0,
        "recovery_priority": 1,
        "review_date": "2026-12-31T00:00:00Z",
    }
    resp = client.post("/api/v1/governance-continuity/capabilities", headers=author_headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    cap_data = resp.json()
    cap_id = cap_data["capability_id"]
    assert cap_data["status"] == "DRAFT"
    assert "administrative coordination instruments" in cap_data["disclaimer"]

    # Submit
    sub_resp = client.post(f"/api/v1/governance-continuity/capabilities/{cap_id}/submit", headers=author_headers, json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # Approve by independent approver
    appr_resp = client.post(
        f"/api/v1/governance-continuity/capabilities/{cap_id}/approve",
        headers=approver_headers,
        json={"approval_reference": "GOV-APP-2026-001"},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"
    assert appr_resp.json()["approved_by"] == "usr-approver-02"


# =============================================================================
# Scenario 2: Capability Classification Separation of Duties (403)
# =============================================================================

def test_scenario_2_capability_separation_of_duties(client: TestClient):
    author_headers = {"X-User-Id": "usr-owner-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    create_payload = {
        "name": "Medication Safety Alert Distribution",
        "description": "Immediate dissemination of high-risk medication recalls.",
        "responsible_department": "Pharmacy Governance",
        "accountable_owner_id": "usr-owner-01",
        "related_workflow": "PHASE_63_RISK_REVIEW",
        "criticality": "TIER_1_CRITICAL",
        "minimum_operational_requirements": "Automated alert dispatch within 1 hour.",
        "max_acceptable_interruption_hours": 1.0,
        "recovery_priority": 1,
        "review_date": "2026-12-31T00:00:00Z",
    }
    resp = client.post("/api/v1/governance-continuity/capabilities", headers=author_headers, json=create_payload)
    cap_id = resp.json()["capability_id"]

    client.post(f"/api/v1/governance-continuity/capabilities/{cap_id}/submit", headers=author_headers, json={})

    # Owner attempts to approve own capability -> 403 Forbidden
    self_appr = client.post(
        f"/api/v1/governance-continuity/capabilities/{cap_id}/approve",
        headers=author_headers,
        json={"approval_reference": "SELF-APP-001"},
    )
    assert self_appr.status_code == 403
    assert self_appr.json()["error"]["code"] == "CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 3: Continuity Requirements Management and Capability Linkage
# =============================================================================

def test_scenario_3_continuity_requirements_management(client: TestClient):
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    appr_headers = {"X-User-Id": "usr-dir-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Register capability first
    cap_resp = client.post(
        "/api/v1/governance-continuity/capabilities",
        headers=headers,
        json={
            "name": "Clinical Governance Incident Review Panel",
            "description": "Weekly panel reviewing serious clinical adverse events.",
            "responsible_department": "Quality & Safety",
            "accountable_owner_id": "usr-lead-01",
            "related_workflow": "PHASE_72_MANAGEMENT_REVIEW",
            "criticality": "TIER_2_ESSENTIAL",
            "minimum_operational_requirements": "Quorum of 3 clinical reviewers.",
            "max_acceptable_interruption_hours": 24.0,
            "recovery_priority": 2,
            "review_date": "2026-12-31T00:00:00Z",
        },
    )
    cap_id = cap_resp.json()["capability_id"]

    # Create continuity requirements
    req_payload = {
        "capability_id": cap_id,
        "required_operating_hours": "08:00-18:00 Mon-Fri",
        "max_acceptable_interruption_hours": 24.0,
        "recovery_time_objective_hours": 12.0,
        "recovery_point_objective_hours": 4.0,
        "maximum_tolerable_period_disruption_hours": 48.0,
        "minimum_continuity_objective": "Convene emergency virtual quorum within 12 hours.",
        "required_staffing_coverage": "2 core panel members and 1 designated safety lead.",
        "required_escalation_arrangements": "Escalate to Chief Medical Officer if quorum unavailable.",
        "required_manual_alternatives": "Offline paper dossiers delivered by secure hospital courier.",
        "evidence_required_to_verify": "Signed quorum decision log and manual dossier audit trail.",
    }
    req_resp = client.post("/api/v1/governance-continuity/requirements", headers=headers, json=req_payload)
    assert req_resp.status_code == 201, req_resp.text
    req_id = req_resp.json()["requirement_id"]
    assert req_resp.json()["recovery_time_objective_hours"] == 12.0

    # Submit and approve
    client.post(f"/api/v1/governance-continuity/requirements/{req_id}/submit", headers=headers, json={})
    appr_resp = client.post(
        f"/api/v1/governance-continuity/requirements/{req_id}/approve",
        headers=appr_headers,
        json={"approval_reference": "REQ-APP-2026-044"},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"

    # Verify requirement ID is linked on capability
    updated_cap = client.get(f"/api/v1/governance-continuity/capabilities/{cap_id}", headers=headers).json()
    assert updated_cap["continuity_requirement_id"] == req_id


# =============================================================================
# Scenario 4: Dependency Mapping and Single Point of Failure (SPOF) Detection
# =============================================================================

def test_scenario_4_dependency_mapping_and_spofs(client: TestClient):
    headers = {"X-User-Id": "usr-planner-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    cap_resp = client.post(
        "/api/v1/governance-continuity/capabilities",
        headers=headers,
        json={
            "name": "Blood Product Safety Governance",
            "description": "Transfusion safety monitoring and reaction reporting.",
            "responsible_department": "Haematology & Safety",
            "accountable_owner_id": "usr-planner-01",
            "related_workflow": "PHASE_49_INCIDENT_INVESTIGATION",
            "criticality": "TIER_1_CRITICAL",
            "minimum_operational_requirements": "Continuous transfusion reaction reporting.",
            "max_acceptable_interruption_hours": 2.0,
            "recovery_priority": 1,
            "review_date": "2026-12-31T00:00:00Z",
        },
    )
    cap_id = cap_resp.json()["capability_id"]

    # Dependency 1: Personnel dependency without validated alternative -> SPOF
    dep1_resp = client.post(
        "/api/v1/governance-continuity/dependencies",
        headers=headers,
        json={
            "source_capability_id": cap_id,
            "dependency_type": "PERSONNEL",
            "target_reference": "usr-solo-haematologist-01",
            "criticality": "CRITICAL",
            "responsible_owner_id": "usr-planner-01",
            "availability_requirements": "Must review transfusion reactions within 30 minutes.",
            "has_validated_alternative": False,
        },
    )
    assert dep1_resp.status_code == 201
    assert dep1_resp.json()["is_single_point_of_failure"] is True

    # Dependency 2: System dependency with validated alternative
    dep2_resp = client.post(
        "/api/v1/governance-continuity/dependencies",
        headers=headers,
        json={
            "source_capability_id": cap_id,
            "dependency_type": "SYSTEM",
            "target_reference": "BloodBank-LIS-Integration",
            "criticality": "HIGH",
            "responsible_owner_id": "usr-planner-01",
            "availability_requirements": "Real-time HL7 feed with secondary backup.",
            "has_validated_alternative": True,
            "alternative_arrangement_description": "Secondary secure database replica.",
        },
    )
    assert dep2_resp.status_code == 201
    assert dep2_resp.json()["is_single_point_of_failure"] is False

    # Evaluate SPOFs
    spof_eval = client.post("/api/v1/governance-continuity/dependencies/evaluate-spofs", headers=headers)
    assert spof_eval.status_code == 200
    spof_data = spof_eval.json()
    assert spof_data["total_dependencies"] == 2
    assert len(spof_data["single_points_of_failure"]) == 1
    assert spof_data["single_points_of_failure"][0]["target_reference"] == "usr-solo-haematologist-01"


# =============================================================================
# Scenario 5: Dependency Validation Workflow
# =============================================================================

def test_scenario_5_dependency_validation(client: TestClient):
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    cap_resp = client.post(
        "/api/v1/governance-continuity/capabilities",
        headers=headers,
        json={
            "name": "Clinical Governance Notification Bridge",
            "description": "Automated paging of clinical risk executives.",
            "responsible_department": "Safety IT",
            "accountable_owner_id": "usr-lead-01",
            "related_workflow": "PHASE_67_ESCALATION",
            "criticality": "TIER_1_CRITICAL",
            "minimum_operational_requirements": "Immediate alert dispatch.",
            "max_acceptable_interruption_hours": 1.0,
            "recovery_priority": 1,
            "review_date": "2026-12-31T00:00:00Z",
        },
    )
    cap_id = cap_resp.json()["capability_id"]

    dep_resp = client.post(
        "/api/v1/governance-continuity/dependencies",
        headers=headers,
        json={
            "source_capability_id": cap_id,
            "dependency_type": "EXTERNAL",
            "target_reference": "Telco-SMS-Gateway",
            "criticality": "CRITICAL",
            "responsible_owner_id": "usr-lead-01",
            "has_validated_alternative": False,
        },
    )
    dep_id = dep_resp.json()["dependency_id"]

    # Validate dependency with backup gateway
    val_resp = client.post(
        f"/api/v1/governance-continuity/dependencies/{dep_id}/validate",
        headers=headers,
        json={
            "status": "VALIDATED",
            "has_validated_alternative": True,
            "alternative_arrangement_description": "Secondary satellite telecom gateway operational.",
            "is_single_point_of_failure": False,
            "evidence_reference": "DOC-TELCO-FAILOVER-TEST-2026",
            "validation_notes": "Live test confirmed failover within 45 seconds.",
        },
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["status"] == "VALIDATED"
    assert val_data["is_single_point_of_failure"] is False
    assert "DOC-TELCO-FAILOVER-TEST-2026" in val_data["evidence_references"]


# =============================================================================
# Scenario 6: Version-Controlled Continuity Plan Lifecycle
# =============================================================================

def test_scenario_6_continuity_plan_lifecycle(client: TestClient):
    author_headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    approver_headers = {"X-User-Id": "usr-approver-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    plan_payload = {
        "title": "Hospital-Wide Clinical Safety Governance Continuity Plan",
        "covered_capability_ids": ["GCC-TEST-001"],
        "plan_owner_id": "usr-author-01",
        "activation_conditions": "Any IT disruption exceeding 1 hour or physical facility evacuation.",
        "disruption_categories": ["TECHNOLOGY_OUTAGE", "FACILITY_DISRUPTION"],
        "escalation_procedures": "Notify Clinical Safety Officer and convene Emergency Response Quorum.",
        "communication_arrangements": "Secondary satellite radio and dedicated mobile phone tree.",
        "alternative_operating_procedures": "Execute manual Paper Form-SAF-701.",
        "delegation_arrangements": "Deputy CMO assumes decision authority if CMO is uncontactable.",
    }
    resp = client.post("/api/v1/governance-continuity/plans", headers=author_headers, json=plan_payload)
    assert resp.status_code == 201, resp.text
    plan_id = resp.json()["plan_id"]
    assert resp.json()["status"] == "DRAFT"
    assert resp.json()["version"] == 1

    # Submit
    client.post(f"/api/v1/governance-continuity/plans/{plan_id}/submit", headers=author_headers, json={})

    # Approve
    appr_resp = client.post(
        f"/api/v1/governance-continuity/plans/{plan_id}/approve",
        headers=approver_headers,
        json={"approval_reference": "EXEC-PLAN-APPROVED-2026-99"},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"
    assert appr_resp.json()["authorized_approver_id"] == "usr-approver-02"


# =============================================================================
# Scenario 7: Continuity Plan Separation of Duties (403)
# =============================================================================

def test_scenario_7_continuity_plan_separation_of_duties(client: TestClient):
    author_headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    resp = client.post(
        "/api/v1/governance-continuity/plans",
        headers=author_headers,
        json={
            "title": "Pharmacy Continuity Plan",
            "covered_capability_ids": ["GCC-PHARM-01"],
            "plan_owner_id": "usr-author-01",
            "activation_conditions": "Pharmacy system failure.",
            "disruption_categories": ["TECHNOLOGY_OUTAGE"],
            "escalation_procedures": "Notify Pharmacy Director.",
            "communication_arrangements": "Cellular phone chain.",
            "alternative_operating_procedures": "Manual prescription logging.",
            "delegation_arrangements": "Senior Clinical Pharmacist.",
        },
    )
    plan_id = resp.json()["plan_id"]
    client.post(f"/api/v1/governance-continuity/plans/{plan_id}/submit", headers=author_headers, json={})

    # Author attempts to approve own plan -> 403 Forbidden
    self_appr = client.post(
        f"/api/v1/governance-continuity/plans/{plan_id}/approve",
        headers=author_headers,
        json={"approval_reference": "SELF-APP-PLAN"},
    )
    assert self_appr.status_code == 403
    assert self_appr.json()["error"]["code"] == "CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 8: Material Plan Revision Preserving Baseline
# =============================================================================

def test_scenario_8_material_plan_revision(client: TestClient):
    author_headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    approver_headers = {"X-User-Id": "usr-approver-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    resp = client.post(
        "/api/v1/governance-continuity/plans",
        headers=author_headers,
        json={
            "title": "Clinical Risk Governance Plan",
            "covered_capability_ids": ["GCC-RISK-01"],
            "plan_owner_id": "usr-author-01",
            "activation_conditions": "Prolonged disruption > 2 hours.",
            "disruption_categories": ["PROLONGED_INTERRUPTION"],
            "escalation_procedures": "Escalate to Risk Lead.",
            "communication_arrangements": "Mobile bridge.",
            "alternative_operating_procedures": "Manual risk registers.",
            "delegation_arrangements": "Deputy Risk Officer.",
        },
    )
    plan_id = resp.json()["plan_id"]
    client.post(f"/api/v1/governance-continuity/plans/{plan_id}/submit", headers=author_headers, json={})
    client.post(f"/api/v1/governance-continuity/plans/{plan_id}/approve", headers=approver_headers, json={"approval_reference": "REV-01"})

    # Material revision
    rev_resp = client.post(
        f"/api/v1/governance-continuity/plans/{plan_id}/revise",
        headers=author_headers,
        json={
            "revision_reason": "Updated emergency communication bridge to satellite telephony.",
            "updated_alternative_procedures": "Execute Cloud-based offline backup synchronization.",
        },
    )
    assert rev_resp.status_code == 200, rev_resp.text
    rev_data = rev_resp.json()
    assert rev_data["version"] == 2
    assert rev_data["status"] == "UNDER_REVISION"
    assert len(rev_data["version_history"]) == 1
    assert rev_data["version_history"][0]["version"] == 1
    assert rev_data["version_history"][0]["alternative_operating_procedures"] == "Manual risk registers."


# =============================================================================
# Scenario 9: Disruption Registration, Tracking, and Closure
# =============================================================================

def test_scenario_9_disruption_lifecycle(client: TestClient):
    headers = {"X-User-Id": "usr-ops-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    dis_payload = {
        "category": "TECHNOLOGY_OUTAGE",
        "description": "Hospital core switch failure impacting clinical incident reporting portal.",
        "affected_capability_ids": ["GCC-INC-01"],
        "source_incident_reference": "INC-IT-2026-888",
        "detection_timestamp": "2026-11-21T08:00:00Z",
        "reported_impact": "Emergency Department unable to submit electronic safety incident reports.",
        "responsible_coordinator_id": "usr-ops-01",
    }
    resp = client.post("/api/v1/governance-continuity/disruptions", headers=headers, json=dis_payload)
    assert resp.status_code == 201, resp.text
    dis_id = resp.json()["disruption_id"]
    assert resp.json()["status"] == "ACTIVE"

    # Update impact
    upd_resp = client.put(
        f"/api/v1/governance-continuity/disruptions/{dis_id}",
        headers=headers,
        json={"reported_impact": "Secondary failover switch activated; testing connectivity.", "recovery_status": "IN_PROGRESS"},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["recovery_status"] == "IN_PROGRESS"

    # Close disruption
    close_resp = client.post(
        f"/api/v1/governance-continuity/disruptions/{dis_id}/close",
        headers=headers,
        json={
            "resolution_notes": "Switch replaced, all portal services verified fully operational.",
            "verification_evidence_reference": "VER-SWITCH-RESTORED-2026",
        },
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"


# =============================================================================
# Scenario 10: Continuity Activation Authorization and Separation of Duties
# =============================================================================

def test_scenario_10_activation_authorization_separation_of_duties(client: TestClient):
    requestor_headers = {"X-User-Id": "usr-requestor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    authorizer_headers = {"X-User-Id": "usr-cmo-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Seed disruption
    dis_resp = client.post(
        "/api/v1/governance-continuity/disruptions",
        headers=requestor_headers,
        json={
            "category": "WORKFORCE_SHORTAGE",
            "description": "Severe winter blizzard prevents 70% of clinical safety staff from reaching hospital.",
            "affected_capability_ids": ["GCC-SAF-01"],
            "detection_timestamp": "2026-11-21T06:00:00Z",
            "reported_impact": "Triage staff shortage.",
            "responsible_coordinator_id": "usr-requestor-01",
        },
    )
    dis_id = dis_resp.json()["disruption_id"]

    # Propose activation
    act_resp = client.post(
        "/api/v1/governance-continuity/activations",
        headers=requestor_headers,
        json={
            "triggering_disruption_id": dis_id,
            "affected_capability_ids": ["GCC-SAF-01"],
            "applicable_plan_id": "GCP-WEATHER-01",
            "responsible_coordinator_id": "usr-requestor-01",
            "activation_rationale": "Severe weather trigger threshold met.",
        },
    )
    assert act_resp.status_code == 201
    act_id = act_resp.json()["activation_id"]
    assert act_resp.json()["status"] == "PROPOSED"

    # Requestor attempts to authorize own activation -> 403 Forbidden
    self_auth = client.post(
        f"/api/v1/governance-continuity/activations/{act_id}/authorize",
        headers=requestor_headers,
        json={"status": "ACTIVATED", "decision_rationale": "I authorize my own activation."},
    )
    assert self_auth.status_code == 403
    assert self_auth.json()["error"]["code"] == "CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Authorized CMO approves activation
    good_auth = client.post(
        f"/api/v1/governance-continuity/activations/{act_id}/authorize",
        headers=authorizer_headers,
        json={
            "status": "ACTIVATED",
            "decision_rationale": "Authorized severe weather continuity plan activation.",
            "alternative_arrangements_approved": ["Remote triage telemedicine escalation"],
        },
    )
    assert good_auth.status_code == 200
    assert good_auth.json()["status"] == "ACTIVATED"
    assert good_auth.json()["authorized_decision_maker_id"] == "usr-cmo-02"


# =============================================================================
# Scenario 11: Coordinator Activation Acknowledgement
# =============================================================================

def test_scenario_11_coordinator_acknowledgement(client: TestClient):
    req_headers = {"X-User-Id": "usr-req-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    coord_headers = {"X-User-Id": "usr-coord-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    dis_resp = client.post(
        "/api/v1/governance-continuity/disruptions",
        headers=req_headers,
        json={
            "category": "EXTERNAL_SERVICE_OUTAGE",
            "description": "Cloud service provider regional outage.",
            "affected_capability_ids": ["GCC-01"],
            "detection_timestamp": "2026-11-21T07:00:00Z",
            "reported_impact": "Cloud triage dashboard down.",
            "responsible_coordinator_id": "usr-coord-02",
        },
    )
    dis_id = dis_resp.json()["disruption_id"]

    act_resp = client.post(
        "/api/v1/governance-continuity/activations",
        headers=req_headers,
        json={
            "triggering_disruption_id": dis_id,
            "affected_capability_ids": ["GCC-01"],
            "applicable_plan_id": "GCP-CLOUD-01",
            "responsible_coordinator_id": "usr-coord-02",
            "activation_rationale": "Cloud outage.",
        },
    )
    act_id = act_resp.json()["activation_id"]

    # Coordinator acknowledges activation
    ack_resp = client.post(
        f"/api/v1/governance-continuity/activations/{act_id}/acknowledge",
        headers=coord_headers,
        json={"acknowledgement_notes": "Continuity emergency ops center activated and on standby."},
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledgement_timestamp"] is not None
    assert len(ack_resp.json()["communication_references"]) >= 1


# =============================================================================
# Scenario 12: Alternative Operating Arrangement Tracking and Deactivation
# =============================================================================

def test_scenario_12_alternative_operating_arrangements(client: TestClient):
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Seed activation
    dis_id = client.post(
        "/api/v1/governance-continuity/disruptions",
        headers=headers,
        json={
            "category": "COMMUNICATION_FAILURE",
            "description": "Hospital PBX telephone lines severed.",
            "affected_capability_ids": ["GCC-01"],
            "detection_timestamp": "2026-11-21T09:00:00Z",
            "reported_impact": "No incoming risk calls.",
            "responsible_coordinator_id": "usr-lead-01",
        },
    ).json()["disruption_id"]

    act_id = client.post(
        "/api/v1/governance-continuity/activations",
        headers=headers,
        json={
            "triggering_disruption_id": dis_id,
            "affected_capability_ids": ["GCC-01"],
            "applicable_plan_id": "GCP-COMM-01",
            "responsible_coordinator_id": "usr-lead-01",
            "activation_rationale": "Lines severed.",
        },
    ).json()["activation_id"]

    # Create alternative operating arrangement
    arr_payload = {
        "activation_id": act_id,
        "affected_capability_id": "GCC-01",
        "description": "Emergency VHF handheld radio network distributed to ward charge nurses.",
        "authorized_procedure_reference": "SOP-ALT-VHF-RADIO-2026",
        "responsible_owner_id": "usr-lead-01",
        "expiry_or_review_time": "2026-11-21T18:00:00Z",
    }
    resp = client.post("/api/v1/governance-continuity/arrangements", headers=headers, json=arr_payload)
    assert resp.status_code == 201, resp.text
    arr_id = resp.json()["arrangement_id"]
    assert resp.json()["verification_status"] == "ACTIVE"

    # Deactivate arrangement
    deact_resp = client.post(
        f"/api/v1/governance-continuity/arrangements/{arr_id}/deactivate",
        headers=headers,
        json={
            "deactivation_reason": "PBX telephone system restored and verified.",
            "reconciliation_reference": "REC-RADIO-LOGS-RETURNED",
        },
    )
    assert deact_resp.status_code == 200
    assert deact_resp.json()["verification_status"] == "DEACTIVATED"


# =============================================================================
# Scenario 13: Temporary Decision Logging and Authoritative Reconciliation
# =============================================================================

def test_scenario_13_temporary_decision_reconciliation(client: TestClient):
    headers = {"X-User-Id": "usr-clinician-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    dis_id = client.post(
        "/api/v1/governance-continuity/disruptions",
        headers=headers,
        json={
            "category": "IDENTITY_AUTHENTICATION_FAILURE",
            "description": "SSO identity provider offline.",
            "affected_capability_ids": ["GCC-01"],
            "detection_timestamp": "2026-11-21T09:00:00Z",
            "reported_impact": "Cannot log in to sign clinical governance risk orders.",
            "responsible_coordinator_id": "usr-clinician-01",
        },
    ).json()["disruption_id"]

    act_id = client.post(
        "/api/v1/governance-continuity/activations",
        headers=headers,
        json={
            "triggering_disruption_id": dis_id,
            "affected_capability_ids": ["GCC-01"],
            "applicable_plan_id": "GCP-SSO-01",
            "responsible_coordinator_id": "usr-clinician-01",
            "activation_rationale": "SSO failure.",
        },
    ).json()["activation_id"]

    # Record decision made during disruption
    dec_payload = {
        "activation_id": act_id,
        "decision_title": "Emergency Escalation of Sepsis Risk Protocol in ICU",
        "decision_summary": "Authorized immediate ICU step-up for deteriorating surgical patient under paper continuity SOP.",
        "decision_authority_role": "Acting Emergency Clinical Safety Officer",
        "authorized_decision_maker_id": "usr-clinician-01",
        "decision_timestamp": "2026-11-21T09:30:00Z",
        "supporting_evidence_references": ["PAPER-CHART-ICU-BED-04"],
        "temporary_documentation_reference": "FORM-SAF-701-DOC-9821",
    }
    dec_resp = client.post("/api/v1/governance-continuity/temporary-decisions", headers=headers, json=dec_payload)
    assert dec_resp.status_code == 201, dec_resp.text
    dec_id = dec_resp.json()["temporary_decision_id"]
    assert dec_resp.json()["reconciliation_status"] == "PENDING"

    # Reconcile into Phase 72 authoritative management decision record
    rec_resp = client.post(
        f"/api/v1/governance-continuity/temporary-decisions/{dec_id}/reconcile",
        headers=headers,
        json={
            "receiving_authoritative_record_id": "DEC-P72-2026-ICU-STEPUP-01",
            "reconciliation_notes": "SSO restored. Manually entered into electronic governance logbook.",
        },
    )
    assert rec_resp.status_code == 200, rec_resp.text
    rec_data = rec_resp.json()
    assert rec_data["reconciliation_status"] == "RECONCILED"
    assert rec_data["receiving_authoritative_record_id"] == "DEC-P72-2026-ICU-STEPUP-01"
    assert rec_data["decision_timestamp"] == "2026-11-21T09:30:00Z"  # Original provenance preserved


# =============================================================================
# Scenario 14: Decision Reconciliation Conflict Detection and Resolution
# =============================================================================

def test_scenario_14_reconciliation_conflict_detection_and_resolution(client: TestClient):
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    dis_id = client.post(
        "/api/v1/governance-continuity/disruptions",
        headers=headers,
        json={
            "category": "DATA_AVAILABILITY_PROBLEM",
            "description": "Risk database lockup.",
            "affected_capability_ids": ["GCC-01"],
            "detection_timestamp": "2026-11-21T10:00:00Z",
            "reported_impact": "Database lockup.",
            "responsible_coordinator_id": "usr-lead-01",
        },
    ).json()["disruption_id"]

    act_id = client.post(
        "/api/v1/governance-continuity/activations",
        headers=headers,
        json={
            "triggering_disruption_id": dis_id,
            "affected_capability_ids": ["GCC-01"],
            "applicable_plan_id": "GCP-01",
            "responsible_coordinator_id": "usr-lead-01",
            "activation_rationale": "Lockup.",
        },
    ).json()["activation_id"]

    dec_id = client.post(
        "/api/v1/governance-continuity/temporary-decisions",
        headers=headers,
        json={
            "activation_id": act_id,
            "decision_title": "Temporary Clinical Safety Barrier Waiver",
            "decision_summary": "Waiver of automated pharmacy allergy cross-check.",
            "decision_authority_role": "Chief Pharmacist",
            "authorized_decision_maker_id": "usr-lead-01",
            "decision_timestamp": "2026-11-21T10:15:00Z",
            "temporary_documentation_reference": "DOC-WAIVER-PAPER-77",
        },
    ).json()["temporary_decision_id"]

    # Reconcile with conflict target string
    conflict_resp = client.post(
        f"/api/v1/governance-continuity/temporary-decisions/{dec_id}/reconcile",
        headers=headers,
        json={"receiving_authoritative_record_id": "DEC-CONFLICT-DETECTED-01"},
    )
    assert conflict_resp.status_code == 200
    assert conflict_resp.json()["reconciliation_status"] == "CONFLICT_DETECTED"
    assert conflict_resp.json()["conflict_description"] is not None

    # Resolve conflict
    res_resp = client.post(
        f"/api/v1/governance-continuity/temporary-decisions/{dec_id}/resolve-conflict",
        headers=headers,
        json={
            "resolution_disposition": "RECONCILED",
            "conflict_resolution_notes": "Dual clinician sign-off reconciled with authoritative record DEC-P63-FINAL-01.",
            "receiving_authoritative_record_id": "DEC-P63-FINAL-01",
        },
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["reconciliation_status"] == "RECONCILED"
    assert res_resp.json()["receiving_authoritative_record_id"] == "DEC-P63-FINAL-01"


# =============================================================================
# Scenario 15: Governance Recovery Coordination and Independent Verification
# =============================================================================

def test_scenario_15_recovery_restoration_verification(client: TestClient):
    headers = {"X-User-Id": "usr-coord-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    verifier_headers = {"X-User-Id": "usr-independent-verifier-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    dis_id = client.post(
        "/api/v1/governance-continuity/disruptions",
        headers=headers,
        json={
            "category": "FACILITY_DISRUPTION",
            "description": "Main hospital power outage impacting server rooms.",
            "affected_capability_ids": ["GCC-REC-01"],
            "detection_timestamp": "2026-11-21T07:00:00Z",
            "reported_impact": "Power loss.",
            "responsible_coordinator_id": "usr-coord-01",
        },
    ).json()["disruption_id"]

    cap_id = client.post(
        "/api/v1/governance-continuity/capabilities",
        headers=headers,
        json={
            "name": "Clinical Incident Surveillance Engine",
            "description": "Continuous safety surveillance engine.",
            "responsible_department": "Safety Informatics",
            "accountable_owner_id": "usr-coord-01",
            "related_workflow": "PHASE_49",
            "criticality": "TIER_1_CRITICAL",
            "minimum_operational_requirements": "Active surveillance engine.",
            "max_acceptable_interruption_hours": 2.0,
            "recovery_priority": 1,
            "review_date": "2026-12-31T00:00:00Z",
        },
    ).json()["capability_id"]

    # Initialize recovery tracking
    rec_resp = client.post(
        "/api/v1/governance-continuity/recoveries",
        headers=headers,
        json={
            "disruption_id": dis_id,
            "capability_id": cap_id,
            "pre_disruption_operating_state": "Continuous electronic surveillance.",
            "initial_milestone": "Emergency diesel generator running.",
        },
    )
    assert rec_resp.status_code == 201
    rec_id = rec_resp.json()["recovery_id"]
    assert rec_resp.json()["recovery_status"] == "IN_PROGRESS"

    # Progress to TECHNICALLY_RESTORED
    client.post(
        f"/api/v1/governance-continuity/recoveries/{rec_id}/update-status",
        headers=headers,
        json={
            "recovery_status": "TECHNICALLY_RESTORED",
            "milestone_description": "Server hardware rebooted and online.",
        },
    )

    # Progress to OPERATIONALLY_RESTORED
    client.post(
        f"/api/v1/governance-continuity/recoveries/{rec_id}/update-status",
        headers=headers,
        json={
            "recovery_status": "OPERATIONALLY_RESTORED",
            "milestone_description": "Clinical safety officers logged in and actively reviewing live incident queue.",
        },
    )

    # Disruption coordinator attempts to self-verify -> 403 Forbidden
    self_ver = client.post(
        f"/api/v1/governance-continuity/recoveries/{rec_id}/verify",
        headers=headers,
        json={
            "verification_evidence_reference": "SELF-VERIFICATION",
            "verification_notes": "Coordinator approves own recovery.",
        },
    )
    assert self_ver.status_code == 403
    assert self_ver.json()["error"]["code"] == "CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent verifier signs off
    good_ver = client.post(
        f"/api/v1/governance-continuity/recoveries/{rec_id}/verify",
        headers=verifier_headers,
        json={
            "verification_evidence_reference": "AUDIT-RESTORED-CONFIRMED-2026-101",
            "verification_notes": "Verified that all 14 clinical ward queues are operational and data synchronized.",
        },
    )
    assert good_ver.status_code == 200
    assert good_ver.json()["recovery_status"] == "VERIFIED"
    assert good_ver.json()["responsible_verifier_id"] == "usr-independent-verifier-02"


# =============================================================================
# Scenario 16: Continuity Exercise Management and Evaluation
# =============================================================================

def test_scenario_16_continuity_exercise_management(client: TestClient):
    headers = {"X-User-Id": "usr-drill-master-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    create_payload = {
        "title": "Hospital-Wide Sepsis Escalation Tabletop Exercise",
        "exercise_type": "TABLETOP_EXERCISE",
        "scope": "Emergency & ICU Governance Teams",
        "objectives": "Test paper-based incident escalation during simulated ransomware attack.",
        "applicable_plan_id": "GCP-CYBER-01",
        "plan_version": 1,
        "participating_departments": ["Emergency Medicine", "Intensive Care", "Clinical Safety"],
        "coordinator_id": "usr-drill-master-01",
        "planned_date": "2026-11-25T09:00:00Z",
        "scenario": "Simulated ransomware encrypts all hospital clinical servers.",
        "expected_results": "Staff switch to Form-SAF-701 within 15 minutes and radio check within 30 minutes.",
    }
    resp = client.post("/api/v1/governance-continuity/exercises", headers=headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    ex_id = resp.json()["exercise_id"]
    assert resp.json()["status"] == "PLANNED"

    # Record execution
    exec_resp = client.post(
        f"/api/v1/governance-continuity/exercises/{ex_id}/record-execution",
        headers=headers,
        json={
            "actual_date": "2026-11-25T11:30:00Z",
            "observed_results": "Form-SAF-701 deployed in 12 minutes. Radio batteries drained on 2 ward units.",
        },
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "COMPLETED"

    # Submit evaluation
    eval_resp = client.post(
        f"/api/v1/governance-continuity/exercises/{ex_id}/evaluate",
        headers=headers,
        json={
            "status": "FOLLOW_UP_REQUIRED",
            "identified_weaknesses": ["Ward 3 and Ward 5 emergency radios uncharged."],
            "corrective_action_references": ["CAPA-RADIO-BATTERY-MAINTENANCE-01"],
        },
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["status"] == "FOLLOW_UP_REQUIRED"
    assert "Ward 3 and Ward 5 emergency radios uncharged." in eval_resp.json()["identified_weaknesses"]


# =============================================================================
# Scenario 17: Continuity Gap Detection and Authoritative Corrective Action Routing
# =============================================================================

def test_scenario_17_continuity_gap_and_corrective_action_routing(client: TestClient):
    headers = {"X-User-Id": "usr-auditor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    create_payload = {
        "category": "SPOF_WITHOUT_ALTERNATIVE",
        "affected_capability_ids": ["GCC-BLOOD-01"],
        "detection_method": "Bi-Annual Governance Continuity Audit",
        "explanation": "Critical blood bank safety reviews rely entirely on one individual with no designated delegate.",
        "severity": "CRITICAL",
        "recommended_action": "Designate and cross-train 2 deputy clinical haematology safety officers.",
        "escalation_destination": "PHASE_54_CAPA",
    }
    resp = client.post("/api/v1/governance-continuity/gaps", headers=headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    gap_id = resp.json()["gap_id"]
    assert resp.json()["status"] == "DETECTED"

    # Review gap
    client.post(
        f"/api/v1/governance-continuity/gaps/{gap_id}/review",
        headers=headers,
        json={"status": "UNDER_REVIEW", "review_notes": "Reviewed and validated with Haematology Director."},
    )

    # Route to Phase 54 CAPA
    route_resp = client.post(
        f"/api/v1/governance-continuity/gaps/{gap_id}/refer-corrective-action",
        headers=headers,
        json={
            "escalation_destination": "PHASE_54_CAPA",
            "corrective_action_reference": "CAPA-P54-HAEM-DELEGATE-01",
            "routing_notes": "Formally referred to Phase 54 for immediate cross-training action execution.",
        },
    )
    assert route_resp.status_code == 200, route_resp.text
    assert route_resp.json()["status"] == "ACTION_REFERRED"
    assert route_resp.json()["corrective_action_reference"] == "CAPA-P54-HAEM-DELEGATE-01"


# =============================================================================
# Scenario 18: Assurance Reporting and Routine Maintenance Scan
# =============================================================================

def test_scenario_18_assurance_reporting_and_maintenance_scan(client: TestClient):
    headers = {"X-User-Id": "usr-dir-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Seed capability and plan
    client.post(
        "/api/v1/governance-continuity/capabilities",
        headers=headers,
        json={
            "name": "General Safety Triage",
            "description": "General triage.",
            "responsible_department": "Safety",
            "accountable_owner_id": "usr-dir-01",
            "related_workflow": "PHASE_49",
            "criticality": "TIER_1_CRITICAL",
            "minimum_operational_requirements": "Continuous triage.",
            "max_acceptable_interruption_hours": 4.0,
            "recovery_priority": 1,
            "review_date": "2026-12-31T00:00:00Z",
        },
    )

    # Fetch inventory summary
    inv_resp = client.get("/api/v1/governance-continuity/reports/capability-summary", headers=headers)
    assert inv_resp.status_code == 200
    assert inv_resp.json()["total_capabilities"] == 1
    assert inv_resp.json()["tier_1_critical_count"] == 1

    # Fetch plan coverage
    cov_resp = client.get("/api/v1/governance-continuity/reports/plan-coverage", headers=headers)
    assert cov_resp.status_code == 200
    assert "coverage_ratio" in cov_resp.json()

    # Fetch executive resilience assurance report
    resil_resp = client.get("/api/v1/governance-continuity/reports/resilience-assurance?reporting_period=Q4-2026", headers=headers)
    assert resil_resp.status_code == 200
    assert resil_resp.json()["total_critical_capabilities"] == 1

    # Execute background routine scan
    scan_resp = client.post("/api/v1/governance-continuity/maintenance/routine-scan", headers=headers)
    assert scan_resp.status_code == 200
    assert scan_resp.json()["status"] == "COMPLETED"
    assert scan_resp.json()["scanned_capabilities"] == 1


# =============================================================================
# Scenario 19: Multi-Tenant Boundary Isolation
# =============================================================================

def test_scenario_19_multitenant_boundary_isolation(client: TestClient):
    tenant_a_headers = {"X-User-Id": "usr-apollo-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    tenant_b_headers = {"X-User-Id": "usr-fortis-01", "X-User-Organization": "org-fortis-02", "X-User-Role": "ADMIN"}

    # Tenant A creates capability
    cap_a = client.post(
        "/api/v1/governance-continuity/capabilities",
        headers=tenant_a_headers,
        json={
            "name": "Apollo Pediatric Safety Triage",
            "description": "Apollo pediatric safety governance.",
            "responsible_department": "Pediatric Safety",
            "accountable_owner_id": "usr-apollo-01",
            "related_workflow": "PHASE_49",
            "criticality": "TIER_1_CRITICAL",
            "minimum_operational_requirements": "Pediatric clinician triage.",
            "max_acceptable_interruption_hours": 2.0,
            "recovery_priority": 1,
            "review_date": "2026-12-31T00:00:00Z",
        },
    ).json()["capability_id"]

    # Tenant B attempts to fetch Tenant A's capability -> 404
    resp_b_get = client.get(f"/api/v1/governance-continuity/capabilities/{cap_a}", headers=tenant_b_headers)
    assert resp_b_get.status_code == 404

    # Tenant B lists capabilities -> sees 0
    resp_b_list = client.get("/api/v1/governance-continuity/capabilities", headers=tenant_b_headers)
    assert resp_b_list.status_code == 200
    assert len(resp_b_list.json()) == 0


# =============================================================================
# Scenario 20: Patient Role Authorization Enforcement (403 Forbidden)
# =============================================================================

def test_scenario_20_patient_role_authorization_enforcement(client: TestClient):
    patient_headers = {"X-User-Id": "usr-patient-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "PATIENT"}

    endpoints_to_test = [
        ("GET", "/api/v1/governance-continuity/capabilities"),
        ("POST", "/api/v1/governance-continuity/capabilities"),
        ("GET", "/api/v1/governance-continuity/requirements"),
        ("POST", "/api/v1/governance-continuity/requirements"),
        ("GET", "/api/v1/governance-continuity/dependencies"),
        ("POST", "/api/v1/governance-continuity/dependencies"),
        ("GET", "/api/v1/governance-continuity/plans"),
        ("POST", "/api/v1/governance-continuity/plans"),
        ("GET", "/api/v1/governance-continuity/disruptions"),
        ("POST", "/api/v1/governance-continuity/disruptions"),
        ("GET", "/api/v1/governance-continuity/activations"),
        ("POST", "/api/v1/governance-continuity/activations"),
        ("GET", "/api/v1/governance-continuity/arrangements"),
        ("POST", "/api/v1/governance-continuity/arrangements"),
        ("GET", "/api/v1/governance-continuity/temporary-decisions"),
        ("POST", "/api/v1/governance-continuity/temporary-decisions"),
        ("GET", "/api/v1/governance-continuity/recoveries"),
        ("POST", "/api/v1/governance-continuity/recoveries"),
        ("GET", "/api/v1/governance-continuity/exercises"),
        ("POST", "/api/v1/governance-continuity/exercises"),
        ("GET", "/api/v1/governance-continuity/gaps"),
        ("POST", "/api/v1/governance-continuity/gaps"),
        ("GET", "/api/v1/governance-continuity/reports/capability-summary"),
        ("GET", "/api/v1/governance-continuity/reports/plan-coverage"),
        ("GET", "/api/v1/governance-continuity/reports/resilience-assurance"),
        ("POST", "/api/v1/governance-continuity/maintenance/routine-scan"),
    ]

    for method, path in endpoints_to_test:
        if method == "GET":
            resp = client.get(path, headers=patient_headers)
        else:
            resp = client.post(path, headers=patient_headers, json={})
        assert resp.status_code == 403, f"Endpoint {method} {path} returned {resp.status_code} instead of 403"
        assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

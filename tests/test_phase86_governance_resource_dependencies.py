"""Phase 86: Clinical Safety Governance Resilience Resource Dependency Mapping, Critical Resource Availability & Continuity Capacity Assurance Tests.

Comprehensive test suite verifying:
- Scenario 1: Critical Governance Resource Creation (ACTIVE state, disclaimer, categories)
- Scenario 2: Resource Update & Lifecycle Enforcement (Retired resource cannot be updated)
- Scenario 3: Resource Not Found (404 RESOURCE_NOT_FOUND)
- Scenario 4: Capability Dependency Mapping Creation in DRAFT state
- Scenario 5: Dependency Mapping Submission for Review (SUBMITTED state)
- Scenario 6: Dependency Mapping Self-Approval Rejection (Separation of duties violation -> 403)
- Scenario 7: Independent Dependency Mapping Approval (APPROVED state)
- Scenario 8: Availability Observation Ingestion & Data Freshness Calculation
- Scenario 9: Availability Summary — No Observations Yields UNKNOWN (Never inferred as AVAILABLE)
- Scenario 10: Stale Availability Detection (Observation > 24 hours flagged as STALE)
- Scenario 11: Alternative Resource Creation — Self-Reference Prohibited (400)
- Scenario 12: Fallback Readiness Assessment — Transition to READY_VERIFIED
- Scenario 13: Fallback Readiness Assessment — INSUFFICIENT_EVIDENCE
- Scenario 14: Capacity Requirement Creation & Shortfall Evaluation (CAPACITY_SHORTFALL_DETECTED)
- Scenario 15: Capacity Evaluation with Unverified Estimate Only (UNVERIFIED_ESTIMATE_ONLY)
- Scenario 16: Dependency Graph & SPOF Analysis — Single Shared Resource Supporting Multiple Capabilities
- Scenario 17: SPOF Analysis — Essential Resource Without Verified Fallback Identified
- Scenario 18: Resource Dependency Gap Lifecycle — Create, Assign, and Escalate
- Scenario 19: Gap Resolution — Rejection Without Evidence & Verified Resolution With Evidence
- Scenario 20: Executive Reports (5 reports) and Patient Access Rejection (403)
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
from app.repositories.governance_resource_dependency_repository import (
    get_governance_resource_dependency_repository,
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
    repo = get_governance_resource_dependency_repository()
    repo.clear()
    yield
    repo.clear()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Critical Governance Resource Creation
# =============================================================================

def test_scenario_01_create_critical_resource(client):
    payload = {
        "resource_name": "Clinical Safety Telemetry Bus",
        "category": "INFRASTRUCTURE_SERVICE",
        "description": "High-throughput asynchronous messaging cluster for real-time safety telemetry.",
        "owning_organization": "Apollo Health Organization",
        "responsible_department": "Clinical Safety Operations",
        "resource_owner_ref": "usr-arch-01",
        "criticality": "ESSENTIAL",
        "associated_governance_capability": "CAP-SAFETY-INCIDENT-ESCALATION",
        "availability_requirement_hours": 99.95,
        "review_cycle_days": 90,
    }
    resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json=payload,
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["resource_id"].startswith("res-")
    assert data["resource_name"] == "Clinical Safety Telemetry Bus"
    assert data["category"] == "INFRASTRUCTURE_SERVICE"
    assert data["lifecycle_status"] == "ACTIVE"
    assert "disclaimer" in data
    assert "administrative governance instruments" in data["disclaimer"]


# =============================================================================
# Scenario 2: Resource Update & Lifecycle Enforcement
# =============================================================================

def test_scenario_02_update_resource_lifecycle_enforcement(client):
    # Create resource
    create_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Legacy Incident Archive",
            "category": "DATA_STORAGE",
            "description": "Historical incident records repository.",
            "owning_organization": "Apollo Health Organization",
            "criticality": "SUPPORTING",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = create_resp.json()["resource_id"]

    # Retire the resource
    retire_resp = client.patch(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{res_id}",
        json={"lifecycle_status": "RETIRED"},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert retire_resp.status_code == 200
    assert retire_resp.json()["lifecycle_status"] == "RETIRED"

    # Attempt to update retired resource -> 400
    fail_resp = client.patch(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{res_id}",
        json={"description": "Should fail modification on retired asset"},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert fail_resp.status_code == 400
    assert fail_resp.json()["error"]["code"] == "INVALID_RESOURCE_STATE"


# =============================================================================
# Scenario 3: Resource Not Found
# =============================================================================

def test_scenario_03_resource_not_found(client):
    resp = client.get(
        "/api/v1/governance-resilience-resource-dependencies/resources/res-nonexistent-999",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# =============================================================================
# Scenario 4: Dependency Mapping Creation in DRAFT State
# =============================================================================

def test_scenario_04_create_dependency_mapping(client):
    # First create resource
    create_res = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Electronic Health Record Core",
            "category": "CLINICAL_INFORMATION_SYSTEM",
            "description": "Primary clinical EHR system.",
            "owning_organization": "Apollo Health Organization",
            "criticality": "ESSENTIAL",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = create_res.json()["resource_id"]

    mapping_payload = {
        "governance_capability_ref": "CAP-CLINICAL-AUDIT-QUORUM",
        "responsibility_ref": "RESP-CLINICAL-AUDIT-CHAIR",
        "resource_id": res_id,
        "resource_criticality": "ESSENTIAL",
        "dependency_type": "REQUIRED",
        "minimum_availability_pct": 99.9,
        "required_operating_capacity": "High concurrency clinical data access",
        "organizational_scope": "ORGANIZATION",
    }
    resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json=mapping_payload,
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["dependency_id"].startswith("dep-")
    assert data["status"] == "DRAFT"
    assert data["resource_id"] == res_id
    assert "disclaimer" in data


# =============================================================================
# Scenario 5: Dependency Mapping Submission for Review
# =============================================================================

def test_scenario_05_submit_dependency_mapping(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Emergency Paging System",
            "category": "COMMUNICATION_SERVICE",
            "description": "Critical emergency paging infrastructure.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    dep_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json={
            "governance_capability_ref": "CAP-RAPID-RESPONSE-ESCALATION",
            "resource_id": res_id,
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    dep_id = dep_resp.json()["dependency_id"]

    submit_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/submit",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "SUBMITTED"


# =============================================================================
# Scenario 6: Dependency Mapping Self-Approval Rejection (Separation of Duties)
# =============================================================================

def test_scenario_06_self_approval_separation_of_duties_violation(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Governance Workflow Portal",
            "category": "CRITICAL_APPLICATION",
            "description": "Portal for safety approvals.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    dep_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json={
            "governance_capability_ref": "CAP-SAFETY-COMMITTEE-WORKFLOW",
            "resource_id": res_id,
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    dep_id = dep_resp.json()["dependency_id"]

    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/submit",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )

    # Proposer usr-lead-01 attempts to approve own mapping -> 403
    fail_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/approve",
        json={"notes": "Attempting self approval"},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert fail_resp.status_code == 403
    assert fail_resp.json()["error"]["code"] == "RESOURCE_DEPENDENCY_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 7: Independent Dependency Mapping Approval
# =============================================================================

def test_scenario_07_independent_dependency_approval(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Clinical Registry Cluster",
            "category": "DATA_STORAGE",
            "description": "Registry storage cluster.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-proposer-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    dep_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json={
            "governance_capability_ref": "CAP-SAFETY-REPORTING",
            "resource_id": res_id,
        },
        headers={"X-User-Id": "usr-proposer-01", "X-User-Role": "ADMIN"},
    )
    dep_id = dep_resp.json()["dependency_id"]

    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/submit",
        headers={"X-User-Id": "usr-proposer-01", "X-User-Role": "ADMIN"},
    )

    # Independent approver usr-independent-approver
    approve_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/approve",
        json={"notes": "Independently verified and approved."},
        headers={"X-User-Id": "usr-independent-approver", "X-User-Role": "ADMIN"},
    )
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["status"] == "APPROVED"
    assert data["approved_by"] == "usr-independent-approver"
    assert data["approved_at"] is not None


# =============================================================================
# Scenario 8: Availability Observation Ingestion & Freshness
# =============================================================================

def test_scenario_08_availability_observation_ingestion(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Active Directory Auth Cluster",
            "category": "IDENTITY_AUTHENTICATION",
            "description": "Federated authentication identity provider.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    obs_payload = {
        "resource_id": res_id,
        "source_system": "Datadog Health Probe",
        "observed_status": "AVAILABLE_VERIFIED",
        "source_reliability": "HIGH",
        "evidence_ref": "ev-probe-log-20261123",
        "organizational_scope": "ORGANIZATION",
    }
    resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{res_id}/availability-observations",
        json=obs_payload,
        headers={"X-User-Id": "usr-monitor-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["observation_id"].startswith("obs-")
    assert data["observed_status"] == "AVAILABLE_VERIFIED"
    assert data["data_freshness_minutes"] is not None
    assert "disclaimer" in data


# =============================================================================
# Scenario 9: Availability Summary — No Observations Yields UNKNOWN
# =============================================================================

def test_scenario_09_availability_summary_no_observations_unknown(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Unmonitored Fallback Server",
            "category": "INFRASTRUCTURE_SERVICE",
            "description": "Standby server without active telemetry.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    # When no observations exist, latest_status MUST be UNKNOWN (never inferred as AVAILABLE)
    resp = client.get(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{res_id}/availability",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_status"] == "UNKNOWN"
    assert data["observation_count"] == 0
    assert data["is_stale"] is True


# =============================================================================
# Scenario 10: Stale Availability Detection
# =============================================================================

def test_scenario_10_stale_availability_detection(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Telemetry Node 4",
            "category": "INFRASTRUCTURE_SERVICE",
            "description": "Secondary telemetry node.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    # Submit observation with timestamp older than 24 hours
    old_time = (datetime.utcnow() - timedelta(hours=36)).isoformat()
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{res_id}/availability-observations",
        json={
            "resource_id": res_id,
            "source_system": "Legacy Snmp Collector",
            "observed_status": "AVAILABLE_VERIFIED",
            "observation_timestamp": old_time,
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )

    resp = client.get(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{res_id}/availability",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_stale"] is True
    assert data["latest_status"] == "STALE"


# =============================================================================
# Scenario 11: Alternative Resource Creation — Self-Reference Prohibited
# =============================================================================

def test_scenario_11_alternative_resource_self_reference_prohibited(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Primary Clinical Data Hub",
            "category": "DATA_STORAGE",
            "description": "Primary clinical repository.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    # Attempt to define resource as its own alternative -> 400
    fail_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{res_id}/alternatives",
        json={
            "primary_resource_id": res_id,
            "alternative_resource_id": res_id,
            "substitution_conditions": "Self fallback attempt.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert fail_resp.status_code == 400
    assert fail_resp.json()["error"]["code"] == "INVALID_ALTERNATIVE_RESOURCE_STATE"


# =============================================================================
# Scenario 12: Fallback Readiness Assessment — Transition to READY_VERIFIED
# =============================================================================

def test_scenario_12_assess_fallback_readiness_verified(client):
    # Primary
    p_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Primary Video Bridge",
            "category": "COMMUNICATION_SERVICE",
            "description": "Primary video consultation bridge.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    p_id = p_resp.json()["resource_id"]

    # Alternative
    a_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Secondary Telehealth Bridge",
            "category": "COMMUNICATION_SERVICE",
            "description": "Isolated secondary video platform.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    a_id = a_resp.json()["resource_id"]

    alt_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{p_id}/alternatives",
        json={
            "primary_resource_id": p_id,
            "alternative_resource_id": a_id,
            "substitution_conditions": "Primary bridge failure or WAN partition.",
            "dependency_compatibility": "Fully compatible WebRTC fallback.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert alt_resp.status_code == 201
    alt_id = alt_resp.json()["alternative_id"]
    assert alt_resp.json()["fallback_readiness"] == "NOT_ASSESSED"

    # Assess readiness to READY_VERIFIED
    assess_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/alternatives/{alt_id}/assess",
        json={
            "fallback_readiness": "READY_VERIFIED",
            "readiness_notes": "Live test completed successfully with zero packet loss.",
            "verification_evidence_ref": "ev-failover-drill-20261123",
            "last_successful_validation": datetime.utcnow().isoformat(),
        },
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    assert assess_resp.status_code == 200
    data = assess_resp.json()
    assert data["fallback_readiness"] == "READY_VERIFIED"
    assert data["readiness_assessed_by"] == "usr-assessor-01"


# =============================================================================
# Scenario 13: Fallback Readiness Assessment — INSUFFICIENT_EVIDENCE
# =============================================================================

def test_scenario_13_assess_fallback_readiness_insufficient_evidence(client):
    p_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Main Database Cluster",
            "category": "DATA_STORAGE",
            "description": "Primary relational cluster.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    p_id = p_resp.json()["resource_id"]

    a_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Offsite Replica",
            "category": "DATA_STORAGE",
            "description": "Warm replica in remote datacenter.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    a_id = a_resp.json()["resource_id"]

    alt_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{p_id}/alternatives",
        json={
            "primary_resource_id": p_id,
            "alternative_resource_id": a_id,
            "substitution_conditions": "Datacenter blackout.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    alt_id = alt_resp.json()["alternative_id"]

    assess_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/alternatives/{alt_id}/assess",
        json={
            "fallback_readiness": "INSUFFICIENT_EVIDENCE",
            "readiness_notes": "Replication lag exceeds clinical RPO threshold. Evidence missing.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert assess_resp.status_code == 200
    assert assess_resp.json()["fallback_readiness"] == "INSUFFICIENT_EVIDENCE"


# =============================================================================
# Scenario 14: Capacity Requirement & Shortfall Evaluation
# =============================================================================

def test_scenario_14_capacity_requirement_shortfall_evaluation(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Safety Event Gateway",
            "category": "INFRASTRUCTURE_SERVICE",
            "description": "Ingress gateway for clinical safety events.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    cap_req_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/capacity-requirements",
        json={
            "governance_capability_ref": "CAP-SAFETY-INGRESS",
            "resource_id": res_id,
            "minimum_availability_pct": 99.0,
            "max_acceptable_interruption_minutes": 30.0,
            "min_service_capacity_pct": 85.0,
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert cap_req_resp.status_code == 201
    req_id = cap_req_resp.json()["requirement_id"]

    # Evaluate with verified capacity of 70% (shortfall of 99 - 70 = 29%)
    eval_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/capacity-requirements/{req_id}/evaluate",
        json={
            "verified_capacity_pct": 70.0,
            "reported_capacity_pct": 95.0,
            "evidence_freshness_hours": 2.0,
            "applicable_scenario": "MASS_CASUALTY_STRESS",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert data["evaluation_status"] == "CAPACITY_SHORTFALL_DETECTED"
    assert data["capacity_shortfall_pct"] == 29.0
    assert "disclaimer" in data


# =============================================================================
# Scenario 15: Capacity Evaluation with Unverified Estimate Only
# =============================================================================

def test_scenario_15_capacity_evaluation_unverified_estimate_only(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Document Export Service",
            "category": "CRITICAL_APPLICATION",
            "description": "Generates PDF governance reports.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    req_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/capacity-requirements",
        json={
            "governance_capability_ref": "CAP-AUDIT-EXPORT",
            "resource_id": res_id,
            "minimum_availability_pct": 95.0,
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    req_id = req_resp.json()["requirement_id"]

    # Evaluate with reported_capacity_pct only, verified_capacity_pct=None
    eval_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/capacity-requirements/{req_id}/evaluate",
        json={
            "reported_capacity_pct": 98.0,
            "applicable_scenario": "NORMAL_OPERATIONS",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert data["evaluation_status"] == "UNVERIFIED_ESTIMATE_ONLY"
    assert data["capacity_shortfall_pct"] is None


# =============================================================================
# Scenario 16: SPOF Analysis — Single Shared Resource Supporting Multiple Capabilities
# =============================================================================

def test_scenario_16_spof_shared_resource_multiple_capabilities(client):
    # Create single shared resource
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Core IAM Authentication Service",
            "category": "IDENTITY_AUTHENTICATION",
            "description": "Single sign-on provider for clinical governance tools.",
            "owning_organization": "Apollo Health Organization",
            "criticality": "ESSENTIAL",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    # Map to 2 distinct capabilities and approve both
    d1 = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json={
            "governance_capability_ref": "CAP-INCIDENT-REVIEW-QUORUM",
            "resource_id": res_id,
            "dependency_type": "REQUIRED",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    d1_id = d1.json()["dependency_id"]
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{d1_id}/submit",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{d1_id}/approve",
        json={"notes": "Approved"},
        headers={"X-User-Id": "usr-approver-99", "X-User-Role": "ADMIN"},
    )

    d2 = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json={
            "governance_capability_ref": "CAP-EMERGENCY-SAFETY-DIRECTIVE",
            "resource_id": res_id,
            "dependency_type": "REQUIRED",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    d2_id = d2.json()["dependency_id"]
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{d2_id}/submit",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{d2_id}/approve",
        json={"notes": "Approved"},
        headers={"X-User-Id": "usr-approver-99", "X-User-Role": "ADMIN"},
    )

    # Run dependency analysis
    analysis_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependency-analysis/run",
        json={"analysis_scope": "ORGANIZATION"},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert analysis_resp.status_code == 201
    data = analysis_resp.json()
    assert data["total_resources_analyzed"] >= 1
    assert len(data["spof_findings"]) >= 1
    finding_types = [f["finding_type"] for f in data["spof_findings"]]
    assert "SHARED_RESOURCE_SINGLE_POINT_OF_FAILURE" in finding_types
    spof = next(f for f in data["spof_findings"] if f["finding_type"] == "SHARED_RESOURCE_SINGLE_POINT_OF_FAILURE")
    assert res_id in spof["affected_resource_refs"]
    assert len(spof["affected_capability_refs"]) == 2


# =============================================================================
# Scenario 17: SPOF Analysis — Essential Resource Without Fallback Identified
# =============================================================================

def test_scenario_17_spof_essential_resource_without_fallback(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Radiology Decision Engine",
            "category": "CLINICAL_INFORMATION_SYSTEM",
            "description": "AI safety cross-check for imaging.",
            "owning_organization": "Apollo Health Organization",
            "criticality": "ESSENTIAL",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    analysis_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependency-analysis/run",
        json={"analysis_scope": "ORGANIZATION"},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert analysis_resp.status_code == 201
    data = analysis_resp.json()
    assert res_id in data["resources_without_fallback"]


# =============================================================================
# Scenario 18: Resource Dependency Gap Lifecycle — Create, Assign, Escalate
# =============================================================================

def test_scenario_18_resource_gap_lifecycle(client):
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Outdated Lab Gateway",
            "category": "CLINICAL_INFORMATION_SYSTEM",
            "description": "Lab gateway lacking redundant network route.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    # 1. Create Gap
    gap_payload = {
        "governance_capability_ref": "CAP-LAB-SAFETY-MONITORING",
        "resource_id": res_id,
        "category": "SINGLE_POINT_OF_FAILURE",
        "severity": "CRITICAL",
        "title": "Lab gateway lacks secondary communication uplink",
        "description": "Single fiber line; cable cut would halt safety feeds.",
    }
    create_gap = client.post(
        "/api/v1/governance-resilience-resource-dependencies/gaps",
        json=gap_payload,
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert create_gap.status_code == 201
    gap_id = create_gap.json()["gap_id"]
    assert create_gap.json()["status"] == "IDENTIFIED"

    # 2. Assign Gap
    assign_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/gaps/{gap_id}/assign",
        json={
            "assigned_to": "usr-network-engineer-01",
            "remediation_proposal": "Provision dedicated 5G wireless backup tunnel.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "ASSIGNED"
    assert assign_resp.json()["assigned_to"] == "usr-network-engineer-01"

    # 3. Escalate Gap
    esc_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/gaps/{gap_id}/escalate",
        json={
            "escalated_to_phase": "PHASE_67",
            "escalation_reference_id": "esc-risk-67-001",
            "escalation_notes": "Budget approval required for secondary telecom link.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["status"] == "ESCALATED"
    assert esc_resp.json()["escalated_to_phase"] == "PHASE_67"


# =============================================================================
# Scenario 19: Gap Resolution — Evidence Required & Verified Resolution
# =============================================================================

def test_scenario_19_gap_resolution_lifecycle(client):
    gap_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/gaps",
        json={
            "category": "CAPACITY_SHORTFALL",
            "severity": "HIGH",
            "title": "Audit log buffer size constrained under peak load",
            "description": "Log buffer overflows during peak morning discharge cycle.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    gap_id = gap_resp.json()["gap_id"]

    # Resolution attempt WITHOUT evidence -> 400
    fail_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/gaps/{gap_id}/verify-resolution",
        json={
            "resolution_notes": "Buffer size was enlarged in config.",
            "resolution_evidence_ref": "",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert fail_resp.status_code == 400
    assert fail_resp.json()["error"]["code"] == "INVALID_RESOURCE_GAP_STATE"

    # Valid resolution WITH evidence -> 200
    resolve_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/gaps/{gap_id}/verify-resolution",
        json={
            "resolution_notes": "Buffer enlarged to 10GB and verified with stress test load.",
            "resolution_evidence_ref": "ev-load-test-pass-20261123",
        },
        headers={"X-User-Id": "usr-verifier-01", "X-User-Role": "ADMIN"},
    )
    assert resolve_resp.status_code == 200
    data = resolve_resp.json()
    assert data["status"] == "VERIFIED_RESOLVED"
    assert data["resolution_verified_by"] == "usr-verifier-01"
    assert data["resolution_evidence_ref"] == "ev-load-test-pass-20261123"


# =============================================================================
# Scenario 20: Executive Reports (5 Reports) & Patient Access Rejection
# =============================================================================

def test_scenario_20_executive_reports_and_patient_access_rejection(client):
    headers_admin = {"X-User-Id": "usr-exec-01", "X-User-Role": "ADMIN"}

    # 1. Coverage summary report
    r1 = client.get(
        "/api/v1/governance-resilience-resource-dependencies/reports/resource-coverage",
        headers=headers_admin,
    )
    assert r1.status_code == 200
    assert "total_critical_resources" in r1.json()
    assert "disclaimer" in r1.json()

    # 2. Dependency concentration report
    r2 = client.get(
        "/api/v1/governance-resilience-resource-dependencies/reports/dependency-concentration",
        headers=headers_admin,
    )
    assert r2.status_code == 200
    assert "total_spof_findings" in r2.json()
    assert "disclaimer" in r2.json()

    # 3. Fallback readiness report
    r3 = client.get(
        "/api/v1/governance-resilience-resource-dependencies/reports/fallback-readiness",
        headers=headers_admin,
    )
    assert r3.status_code == 200
    assert "total_alternatives_documented" in r3.json()
    assert "disclaimer" in r3.json()

    # 4. Resource availability status report
    r4 = client.get(
        "/api/v1/governance-resilience-resource-dependencies/reports/resource-availability",
        headers=headers_admin,
    )
    assert r4.status_code == 200
    assert "total_resources" in r4.json()
    assert "disclaimer" in r4.json()

    # 5. Resource gaps summary report
    r5 = client.get(
        "/api/v1/governance-resilience-resource-dependencies/reports/resource-gaps",
        headers=headers_admin,
    )
    assert r5.status_code == 200
    assert "total_gaps" in r5.json()
    assert "disclaimer" in r5.json()

    # 6. Patient access rejection (403 FORBIDDEN)
    headers_patient = {"X-User-Id": "usr-patient-01", "X-User-Role": "PATIENT"}
    p_resp = client.get(
        "/api/v1/governance-resilience-resource-dependencies/reports/resource-coverage",
        headers=headers_patient,
    )
    assert p_resp.status_code == 403
    assert p_resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

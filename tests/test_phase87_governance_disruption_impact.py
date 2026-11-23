"""Phase 87: Clinical Safety Governance Resilience Disruption Impact Analysis Tests.

Comprehensive test suite verifying:
- Scenario 1: Disruption Scenario Creation (DRAFT state, disclaimer, categories)
- Scenario 2: Disruption Scenario Update & Lifecycle Enforcement (ARCHIVED update prohibited -> 400)
- Scenario 3: Scenario Self-Approval Rejection (Separation of duties -> 403)
- Scenario 4: Independent Scenario Approval (APPROVED state)
- Scenario 5: Impact Assessment Creation linked to Scenario
- Scenario 6: Assessment Execution with Direct Capability Impact from Phase 86
- Scenario 7: Assessment Execution with Indirect Multi-Hop Dependency Propagation
- Scenario 8: Duration-Based Analysis & MTPD Threshold Exceeded Evaluation
- Scenario 9: Assessment Submission for Review (EVIDENCE_REVIEW_PENDING)
- Scenario 10: Assessment Self-Review Rejection (Separation of duties -> 403)
- Scenario 11: Independent Assessment Review and Approval (APPROVED state)
- Scenario 12: Assessment Challenge Workflow (CHALLENGED state)
- Scenario 13: Additional Evidence Request Workflow (ADDITIONAL_EVIDENCE_REQUESTED)
- Scenario 14: Cascading Failure Analysis — Multi-Level Propagation Paths
- Scenario 15: Cascading Failure Analysis — Common External Provider Risk Identification
- Scenario 16: Compound Disruption Scenario Creation & Simultaneous Resource Evaluation
- Scenario 17: Compound Disruption Non-Independent Fallback Discovery
- Scenario 18: Fallback Effectiveness Comparison (Baseline vs Verified vs Unverified)
- Scenario 19: Remediation Follow-up Lifecycle (Create -> Submit to Phase 63 -> Acknowledge)
- Scenario 20: Executive Reports (All 5 Reports) & Patient Access Rejection (403)
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
from app.repositories.governance_disruption_impact_repository import (
    get_governance_disruption_impact_repository,
)
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
    impact_repo = get_governance_disruption_impact_repository()
    resource_repo = get_governance_resource_dependency_repository()
    impact_repo.clear()
    resource_repo.clear()
    yield
    impact_repo.clear()
    resource_repo.clear()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Disruption Scenario Creation
# =============================================================================

def test_scenario_01_create_disruption_scenario(client):
    payload = {
        "scenario_name": "Regional Fiber Cut - Telehealth Corridor",
        "description": "Simulation of primary WAN trunk severed along eastern corridor.",
        "category": "NETWORK_DISRUPTION",
        "organizational_scope": "ORGANIZATION",
        "affected_resource_refs": ["res-net-backbone-01"],
        "affected_capability_refs": ["CAP-TELEHEALTH-GOVERNANCE"],
        "initial_disruption_conditions": "Zero network throughput on 10Gbps fiber link.",
        "duration_type": "EXTENDED_INTERRUPTION",
        "assumed_duration_hours": 3.5,
        "severity_assumption": "HIGH",
        "expected_operating_constraints": ["Voice failover only", "Video streams disabled"],
    }
    resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json=payload,
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_id"].startswith("scen-")
    assert data["scenario_name"] == "Regional Fiber Cut - Telehealth Corridor"
    assert data["review_status"] == "DRAFT"
    assert "disclaimer" in data
    assert "administrative governance instruments" in data["disclaimer"]


# =============================================================================
# Scenario 2: Disruption Scenario Update & Lifecycle Enforcement
# =============================================================================

def test_scenario_02_update_scenario_lifecycle_enforcement(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Deprecated Testing Scenario",
            "description": "Old scenario to be archived.",
            "category": "INFRASTRUCTURE_FAILURE",
            "initial_disruption_conditions": "Server ungraceful shutdown.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = create_resp.json()["scenario_id"]

    # Update to ARCHIVED
    archive_resp = client.patch(
        f"/api/v1/governance-resilience-impact-analysis/scenarios/{scen_id}",
        json={"review_status": "ARCHIVED"},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    # Note: Pydantic UpdateDisruptionScenarioRequest doesn't update review_status directly,
    # but we can set it in repository or test updating an archived scenario
    repo = get_governance_disruption_impact_repository()
    scen_rec = repo.get_scenario(scen_id, "org-apollo-01")
    scen_rec.review_status = "ARCHIVED"
    repo.save_scenario(scen_rec)

    # Attempt to update archived scenario -> 400
    fail_resp = client.patch(
        f"/api/v1/governance-resilience-impact-analysis/scenarios/{scen_id}",
        json={"description": "Attempting update on archived scenario."},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert fail_resp.status_code == 400
    assert fail_resp.json()["error"]["code"] == "INVALID_DISRUPTION_SCENARIO_STATE"


# =============================================================================
# Scenario 3: Scenario Self-Approval Rejection (Separation of Duties)
# =============================================================================

def test_scenario_03_scenario_self_approval_rejection(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "EHR Database Corrupt Partition",
            "description": "Simulation of primary DB corruption.",
            "category": "DATA_STORAGE_UNAVAILABILITY",
            "initial_disruption_conditions": "Table corruption in patient safety logs.",
        },
        headers={"X-User-Id": "usr-proposer-01", "X-User-Role": "ADMIN"},
    )
    scen_id = create_resp.json()["scenario_id"]

    client.post(
        f"/api/v1/governance-resilience-impact-analysis/scenarios/{scen_id}/submit",
        json={"submission_notes": "Ready for approval."},
        headers={"X-User-Id": "usr-proposer-01", "X-User-Role": "ADMIN"},
    )

    # Proposer usr-proposer-01 attempts to approve own scenario -> 403
    fail_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/scenarios/{scen_id}/approve",
        json={"approval_ref": "APR-SELF-01"},
        headers={"X-User-Id": "usr-proposer-01", "X-User-Role": "ADMIN"},
    )
    assert fail_resp.status_code == 403
    assert fail_resp.json()["error"]["code"] == "DISRUPTION_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 4: Independent Scenario Approval
# =============================================================================

def test_scenario_04_independent_scenario_approval(client):
    create_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Auth Gateway SSL Expiration",
            "description": "Gateway certificate expired unexpectedly.",
            "category": "IDENTITY_AUTHENTICATION_DISRUPTION",
            "initial_disruption_conditions": "Mutual TLS handshake failure.",
        },
        headers={"X-User-Id": "usr-creator-01", "X-User-Role": "ADMIN"},
    )
    scen_id = create_resp.json()["scenario_id"]

    client.post(
        f"/api/v1/governance-resilience-impact-analysis/scenarios/{scen_id}/submit",
        json={"submission_notes": "Submitted by creator."},
        headers={"X-User-Id": "usr-creator-01", "X-User-Role": "ADMIN"},
    )

    # Independent approver usr-governance-lead-99
    app_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/scenarios/{scen_id}/approve",
        json={"approval_ref": "APR-INDEP-20261123"},
        headers={"X-User-Id": "usr-governance-lead-99", "X-User-Role": "ADMIN"},
    )
    assert app_resp.status_code == 200
    data = app_resp.json()
    assert data["review_status"] == "APPROVED"
    assert data["approved_by"] == "usr-governance-lead-99"
    assert data["approval_ref"] == "APR-INDEP-20261123"


# =============================================================================
# Scenario 5: Impact Assessment Creation Linked to Scenario
# =============================================================================

def test_scenario_05_create_impact_assessment(client):
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Cloud Region Outage",
            "description": "Central cloud hosting facility offline.",
            "category": "CLOUD_INTERRUPTION",
            "initial_disruption_conditions": "Complete AZ unreachable.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "Central Cloud Region Outage Impact Evaluation",
            "dependency_graph_version": "1.2",
        },
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["assessment_id"].startswith("dia-")
    assert data["scenario_id"] == scen_id
    assert data["review_status"] == "DRAFT"
    assert data["assessment_version"] == 1


# =============================================================================
# Scenario 6: Assessment Execution with Direct Capability Impact from Phase 86
# =============================================================================

def test_scenario_06_assessment_run_direct_impact(client):
    # 1. Setup Phase 86 resource and approved mapping
    res_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Clinical Safety Messaging Broker",
            "category": "INFRASTRUCTURE_SERVICE",
            "description": "Primary messaging broker for safety alerts.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    res_id = res_resp.json()["resource_id"]

    dep_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json={
            "governance_capability_ref": "CAP-ALERT-BROADCAST",
            "responsibility_ref": "RESP-SAFETY-COMMUNICATION-OFFICER",
            "resource_id": res_id,
            "dependency_type": "REQUIRED",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    dep_id = dep_resp.json()["dependency_id"]
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/submit",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/approve",
        json={"notes": "Approved"},
        headers={"X-User-Id": "usr-approver-99", "X-User-Role": "ADMIN"},
    )

    # 2. Setup Scenario affecting this resource
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Broker Cluster Panic",
            "description": "Memory exhaustion crash on messaging broker.",
            "category": "APPLICATION_UNAVAILABILITY",
            "affected_resource_refs": [res_id],
            "initial_disruption_conditions": "Process exit code 137.",
            "assumed_duration_hours": 2.0,
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    # 3. Create & Run Assessment
    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "Broker Crash Impact Analysis",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    run_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/run",
        json={"include_indirect_dependencies": True},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert data["review_status"] == "AUTOMATED_ANALYSIS_COMPLETED"
    assert "CAP-ALERT-BROADCAST" in data["affected_capability_refs"]
    assert "RESP-SAFETY-COMMUNICATION-OFFICER" in data["affected_responsibility_refs"]
    assert len(data["direct_findings"]) >= 1
    assert data["direct_findings"][0]["resource_id"] == res_id


# =============================================================================
# Scenario 7: Assessment Execution with Indirect Multi-Hop Dependency Propagation
# =============================================================================

def test_scenario_07_assessment_run_indirect_propagation(client):
    # Upstream Resource
    up_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Internal DNS Authority",
            "category": "INFRASTRUCTURE_SERVICE",
            "description": "Core internal DNS cluster.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    up_id = up_resp.json()["resource_id"]

    # Downstream Resource depending on Upstream
    ds_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Lab Results Portal",
            "category": "CLINICAL_INFORMATION_SYSTEM",
            "description": "Portal for lab results.",
            "owning_organization": "Apollo Health Organization",
            "dependency_refs": [up_id],
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    ds_id = ds_resp.json()["resource_id"]

    # Map downstream to capability
    dep_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/dependencies",
        json={
            "governance_capability_ref": "CAP-LAB-CRITICAL-VALUE-AUDIT",
            "resource_id": ds_id,
            "dependency_type": "REQUIRED",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    dep_id = dep_resp.json()["dependency_id"]
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/submit",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/dependencies/{dep_id}/approve",
        json={"notes": "Approved"},
        headers={"X-User-Id": "usr-approver-99", "X-User-Role": "ADMIN"},
    )

    # Scenario disrupts ONLY internal DNS (up_id)
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Internal DNS Poisoning",
            "description": "DNS root authority records corrupted.",
            "category": "INFRASTRUCTURE_FAILURE",
            "affected_resource_refs": [up_id],
            "initial_disruption_conditions": "DNS resolution timeout.",
            "assumed_duration_hours": 1.5,
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "DNS Outage Cascading Impact",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    run_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/run",
        json={"include_indirect_dependencies": True},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert len(data["indirect_findings"]) >= 1
    ind = data["indirect_findings"][0]
    assert ind["root_resource_id"] == up_id
    assert ind["intermediate_resource_id"] == ds_id
    assert ind["affected_capability_ref"] == "CAP-LAB-CRITICAL-VALUE-AUDIT"


# =============================================================================
# Scenario 8: Duration-Based Analysis & MTPD Threshold Exceeded
# =============================================================================

def test_scenario_08_duration_analysis_mtpd_exceeded(client):
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Extended Datacenter Flooding",
            "description": "Severe storm floods basement generator room.",
            "category": "FACILITY_DISRUPTION",
            "initial_disruption_conditions": "Water level 4ft in power switchboard.",
            "assumed_duration_hours": 8.0,  # Exceeds 4.0h MTPD
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "Flooding Prolonged Outage Assessment",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    run_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/run",
        json={},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert data["mtpd_exceeded"] is True
    assert data["rto_exceeded"] is True
    assert data["overall_impact_severity"] == "CRITICAL"
    assert any("Maximum Tolerable Period of Disruption" in c for c in data["potential_operational_consequences"])


# =============================================================================
# Scenario 9: Assessment Submission for Review
# =============================================================================

def test_scenario_09_assessment_submission_for_review(client):
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Storage SAN Controller Failure",
            "description": "Dual controller failover lockup.",
            "category": "DATA_STORAGE_UNAVAILABILITY",
            "initial_disruption_conditions": "SAN IO paused.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "SAN Controller Review Assessment",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/run",
        json={},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )

    sub_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/submit-review",
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["review_status"] == "EVIDENCE_REVIEW_PENDING"


# =============================================================================
# Scenario 10: Assessment Self-Review Rejection (Separation of Duties)
# =============================================================================

def test_scenario_10_assessment_self_review_rejection(client):
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "API Gateway Denial of Service",
            "description": "Rate limiting bypass flood.",
            "category": "APPLICATION_UNAVAILABILITY",
            "initial_disruption_conditions": "HTTP 503 errors.",
        },
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "DoS Assessment",
        },
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/run",
        json={},
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/submit-review",
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )

    # Assessor usr-assessor-01 attempts to review own assessment -> 403
    fail_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/review",
        json={
            "review_status": "APPROVED",
            "review_notes": "Attempting self-approval of impact findings.",
        },
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    assert fail_resp.status_code == 403
    assert fail_resp.json()["error"]["code"] == "DISRUPTION_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 11: Independent Assessment Review and Approval
# =============================================================================

def test_scenario_11_independent_assessment_approval(client):
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Telemetry Node Disk Full",
            "description": "Log directory full.",
            "category": "INFRASTRUCTURE_FAILURE",
            "initial_disruption_conditions": "Disk utilization 100%.",
        },
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "Disk Full Assessment",
        },
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/run",
        json={},
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/submit-review",
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "ADMIN"},
    )

    # Independent reviewer usr-indep-reviewer-01
    rev_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/review",
        json={
            "review_status": "APPROVED",
            "review_notes": "Independently verified findings against current telemetry baseline.",
            "approval_ref": "APR-IMPACT-20261123",
        },
        headers={"X-User-Id": "usr-indep-reviewer-01", "X-User-Role": "ADMIN"},
    )
    assert rev_resp.status_code == 200
    data = rev_resp.json()
    assert data["review_status"] == "APPROVED"
    assert data["reviewed_by"] == "usr-indep-reviewer-01"
    assert data["reviewed_at"] is not None


# =============================================================================
# Scenario 12: Assessment Challenge Workflow
# =============================================================================

def test_scenario_12_assessment_challenge_workflow(client):
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Switch Reboot Scenario",
            "description": "Core switch reboot.",
            "category": "NETWORK_DISRUPTION",
            "initial_disruption_conditions": "Switch reload.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "Switch Reboot Impact",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    chal_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/challenge",
        json={
            "challenge_notes": "Assumed duration of 4h is excessive for a hot-swappable supervisor engine.",
            "evidence_refs": ["ev-switch-spec-2026"],
        },
        headers={"X-User-Id": "usr-engineer-01", "X-User-Role": "ADMIN"},
    )
    assert chal_resp.status_code == 200
    data = chal_resp.json()
    assert data["review_status"] == "CHALLENGED"
    assert data["challenged_by"] == "usr-engineer-01"
    assert "hot-swappable" in data["challenge_notes"]


# =============================================================================
# Scenario 13: Additional Evidence Request Workflow
# =============================================================================

def test_scenario_13_request_evidence_workflow(client):
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Remote PACS Disruption",
            "description": "Imaging archive inaccessible.",
            "category": "DATA_STORAGE_UNAVAILABILITY",
            "initial_disruption_conditions": "DICOM network timeout.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    scen_id = scen_resp.json()["scenario_id"]

    ass_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "PACS Impact Assessment",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    ass_id = ass_resp.json()["assessment_id"]

    req_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/request-evidence",
        json={
            "requested_evidence_description": "Need local caching storage validation logs.",
            "target_capabilities": ["CAP-IMAGING-SAFETY-REVIEW"],
        },
        headers={"X-User-Id": "usr-auditor-01", "X-User-Role": "ADMIN"},
    )
    assert req_resp.status_code == 200
    data = req_resp.json()
    assert data["review_status"] == "ADDITIONAL_EVIDENCE_REQUESTED"
    assert len(data["uncertainty_indicators"]) >= 1


# =============================================================================
# Scenario 14: Cascading Failure Analysis — Multi-Level Propagation Paths
# =============================================================================

def test_scenario_14_cascading_failure_analysis_run(client):
    # Setup 2-tier resource hierarchy
    r1_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Core Optical Transport",
            "category": "NETWORK_CONNECTIVITY",
            "description": "Optical fiber DWDM transport ring.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    r1_id = r1_resp.json()["resource_id"]

    r2_resp = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Clinical Vitals Gateway",
            "category": "CLINICAL_INFORMATION_SYSTEM",
            "description": "Vitals ingestion service.",
            "owning_organization": "Apollo Health Organization",
            "dependency_refs": [r1_id],
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    r2_id = r2_resp.json()["resource_id"]

    # Run cascading analysis
    casc_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/cascading-analysis/run",
        json={"max_depth": 3},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert casc_resp.status_code == 201
    data = casc_resp.json()
    assert data["analysis_id"].startswith("casc-an-")
    assert data["total_paths_identified"] >= 1
    assert data["max_depth_traversed"] >= 2
    assert "disclaimer" in data


# =============================================================================
# Scenario 15: Cascading Failure Analysis — Common External Provider Risk
# =============================================================================

def test_scenario_15_common_external_provider_risk(client):
    # 2 resources with identical external_provider_ref
    client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "External Lab Ingestion API",
            "category": "THIRD_PARTY_INTEGRATION",
            "description": "Vendor lab API feed.",
            "owning_organization": "Apollo Health Organization",
            "external_provider_ref": "PROV-AMAZON-AWS",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "External Radiology Archive Cloud",
            "category": "HOSTING_CLOUD",
            "description": "Vendor PACS hosting.",
            "owning_organization": "Apollo Health Organization",
            "external_provider_ref": "PROV-AMAZON-AWS",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )

    casc_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/cascading-analysis/run",
        json={},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert casc_resp.status_code == 201
    data = casc_resp.json()
    assert len(data["common_provider_risks"]) >= 1
    risk = data["common_provider_risks"][0]
    assert risk["provider_ref"] == "PROV-AMAZON-AWS"
    assert risk["resource_count"] >= 2


# =============================================================================
# Scenario 16: Compound Disruption Scenario Creation & Simultaneous Resource Evaluation
# =============================================================================

def test_scenario_16_compound_disruption_scenario(client):
    r1 = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Core PBX Voice System",
            "category": "COMMUNICATION_SERVICE",
            "description": "Hospital PBX telephony switch.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["resource_id"]

    r2 = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Clinical Mobile Messenger",
            "category": "COMMUNICATION_SERVICE",
            "description": "Clinical smartphone chat platform.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["resource_id"]

    # Compound scenario: Both communication channels down simultaneously
    create_cmp = client.post(
        "/api/v1/governance-resilience-impact-analysis/compound-scenarios",
        json={
            "scenario_name": "Total Communication Blackout",
            "description": "Simultaneous failure of PBX telephony and mobile messaging.",
            "simultaneous_resource_ids": [r1, r2],
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert create_cmp.status_code == 201
    cmp_id = create_cmp.json()["compound_scenario_id"]

    eval_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/compound-scenarios/{cmp_id}/evaluate",
        json={"include_personnel_constraints": True},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert data["evaluated_at"] is not None
    assert len(data["capacity_limitations"]) >= 1


# =============================================================================
# Scenario 17: Compound Disruption Non-Independent Fallback Discovery
# =============================================================================

def test_scenario_17_compound_non_independent_fallback(client):
    # Primary Resource
    p_id = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Primary Database",
            "category": "DATA_STORAGE",
            "description": "Primary database server.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["resource_id"]

    # Supposed Fallback that actually depends on the Shared SAN
    san_id = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Shared Enterprise SAN",
            "category": "DATA_STORAGE",
            "description": "Enterprise SAN storage rack.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["resource_id"]

    alt_id = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Standby Database Server",
            "category": "DATA_STORAGE",
            "description": "Standby database server mounting the same SAN.",
            "owning_organization": "Apollo Health Organization",
            "dependency_refs": [san_id],
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["resource_id"]

    # Register alternative
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{p_id}/alternatives",
        json={
            "primary_resource_id": p_id,
            "alternative_resource_id": alt_id,
            "substitution_conditions": "Failover when primary fails.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )

    # Compound scenario: Primary DB and Shared SAN fail simultaneously
    cmp_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/compound-scenarios",
        json={
            "scenario_name": "SAN Catastrophic Outage",
            "description": "Simultaneous crash of primary DB and backend SAN.",
            "simultaneous_resource_ids": [p_id, san_id],
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    cmp_id = cmp_resp.json()["compound_scenario_id"]

    eval_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/compound-scenarios/{cmp_id}/evaluate",
        json={},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert len(data["non_independent_fallbacks"]) >= 1
    assert any(alt_id in msg for msg in data["non_independent_fallbacks"])


# =============================================================================
# Scenario 18: Fallback Effectiveness Comparison
# =============================================================================

def test_scenario_18_fallback_effectiveness_comparison(client):
    # Primary Resource
    p_id = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Primary LIS Feed",
            "category": "CLINICAL_INFORMATION_SYSTEM",
            "description": "Primary laboratory information system feed.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["resource_id"]

    # Verified Alternative
    a_id = client.post(
        "/api/v1/governance-resilience-resource-dependencies/resources",
        json={
            "resource_name": "Secondary LIS Satellite Link",
            "category": "COMMUNICATION_SERVICE",
            "description": "Secondary satellite lab uplink.",
            "owning_organization": "Apollo Health Organization",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["resource_id"]

    alt_resp = client.post(
        f"/api/v1/governance-resilience-resource-dependencies/resources/{p_id}/alternatives",
        json={
            "primary_resource_id": p_id,
            "alternative_resource_id": a_id,
            "substitution_conditions": "Cable severance.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    alt_id = alt_resp.json()["alternative_id"]

    # Assess readiness to READY_VERIFIED
    client.post(
        f"/api/v1/governance-resilience-resource-dependencies/alternatives/{alt_id}/assess",
        json={
            "fallback_readiness": "READY_VERIFIED",
            "readiness_notes": "Live test passed.",
            "verification_evidence_ref": "ev-drill-pass-01",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )

    # Create assessment
    scen_resp = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "LIS Outage",
            "description": "Lab feed down.",
            "category": "APPLICATION_UNAVAILABILITY",
            "initial_disruption_conditions": "Feed offline.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert scen_resp.status_code == 201
    scen_id = scen_resp.json()["scenario_id"]

    ass_id = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "LIS Assessment",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["assessment_id"]

    # Run Fallback Comparison
    cmp_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/fallback-comparison",
        json={"resource_id": p_id},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert cmp_resp.status_code == 201
    data = cmp_resp.json()
    assert data["resource_id"] == p_id
    assert len(data["comparison_items"]) >= 2  # Baseline NO_FALLBACK + READY_VERIFIED
    tiers = [i["readiness_tier"] for i in data["comparison_items"]]
    assert "NO_FALLBACK" in tiers
    assert "READY_VERIFIED" in tiers
    assert data["optimal_fallback_id"] == alt_id


# =============================================================================
# Scenario 19: Remediation Follow-Up Lifecycle
# =============================================================================

def test_scenario_19_remediation_follow_up_lifecycle(client):
    scen_id = client.post(
        "/api/v1/governance-resilience-impact-analysis/scenarios",
        json={
            "scenario_name": "Power Grid Instability",
            "description": "Generator switchgear delay.",
            "category": "INFRASTRUCTURE_FAILURE",
            "initial_disruption_conditions": "Brownout.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["scenario_id"]

    ass_id = client.post(
        "/api/v1/governance-resilience-impact-analysis/assessments",
        json={
            "scenario_id": scen_id,
            "assessment_name": "Power Assessment",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    ).json()["assessment_id"]

    # 1. Create Follow-up
    create_fu = client.post(
        f"/api/v1/governance-resilience-impact-analysis/assessments/{ass_id}/follow-ups",
        json={
            "affected_capability_ref": "CAP-EMERGENCY-SURGERY-SAFETY",
            "responsible_owner_ref": "usr-facilities-dir",
            "destination_workflow": "PHASE_63_RISK_MANAGEMENT",
            "priority_severity": "HIGH",
            "proposal_description": "Add secondary UPS buffer for surgical theater governance consoles.",
        },
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert create_fu.status_code == 201
    fu_id = create_fu.json()["follow_up_id"]
    assert create_fu.json()["status"] == "PROPOSED"

    # 2. Submit Follow-up
    sub_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/follow-ups/{fu_id}/submit",
        json={"submission_notes": "Routing to Phase 63 Risk Committee."},
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"
    assert sub_resp.json()["handoff_timestamp"] is not None

    # 3. Acknowledge Follow-up
    ack_resp = client.post(
        f"/api/v1/governance-resilience-impact-analysis/follow-ups/{fu_id}/acknowledge",
        json={
            "external_workflow_reference_id": "RSK-PHASE63-ITEM-9021",
            "acknowledgement_notes": "Accepted onto Safety Risk Register.",
        },
        headers={"X-User-Id": "usr-risk-chair", "X-User-Role": "ADMIN"},
    )
    assert ack_resp.status_code == 200
    data = ack_resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["external_workflow_reference_id"] == "RSK-PHASE63-ITEM-9021"
    assert data["acknowledged_by"] == "usr-risk-chair"


# =============================================================================
# Scenario 20: Executive Reports (All 5) & Patient Access Rejection
# =============================================================================

def test_scenario_20_executive_reports_and_patient_access_rejection(client):
    headers_admin = {"X-User-Id": "usr-exec-01", "X-User-Role": "ADMIN"}

    # 1. Disruption Impact Summary Report
    r1 = client.get(
        "/api/v1/governance-resilience-impact-analysis/reports/impact-summary",
        headers=headers_admin,
    )
    assert r1.status_code == 200
    assert "total_scenarios_registered" in r1.json()
    assert "disclaimer" in r1.json()

    # 2. Cascading Dependencies Report
    r2 = client.get(
        "/api/v1/governance-resilience-impact-analysis/reports/cascading-dependencies",
        headers=headers_admin,
    )
    assert r2.status_code == 200
    assert "total_cascading_analyses" in r2.json()
    assert "disclaimer" in r2.json()

    # 3. Compound Disruptions Report
    r3 = client.get(
        "/api/v1/governance-resilience-impact-analysis/reports/compound-disruptions",
        headers=headers_admin,
    )
    assert r3.status_code == 200
    assert "total_compound_scenarios" in r3.json()
    assert "disclaimer" in r3.json()

    # 4. Fallback Comparison Report
    r4 = client.get(
        "/api/v1/governance-resilience-impact-analysis/reports/fallback-comparison",
        headers=headers_admin,
    )
    assert r4.status_code == 200
    assert "total_resources_compared" in r4.json()
    assert "disclaimer" in r4.json()

    # 5. Impact Assessment Coverage Report
    r5 = client.get(
        "/api/v1/governance-resilience-impact-analysis/reports/impact-assessment-coverage",
        headers=headers_admin,
    )
    assert r5.status_code == 200
    assert "total_critical_capabilities" in r5.json()
    assert "disclaimer" in r5.json()

    # 6. Patient Access Rejection (403 FORBIDDEN)
    headers_patient = {"X-User-Id": "usr-patient-01", "X-User-Role": "PATIENT"}
    p_resp = client.get(
        "/api/v1/governance-resilience-impact-analysis/reports/impact-summary",
        headers=headers_patient,
    )
    assert p_resp.status_code == 403
    assert p_resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

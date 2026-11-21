"""Phase 79: Strategic Execution Monitoring, Cross-Roadmap Coordination & Long-Term Strategy Adaptation Tests.

Comprehensive test suite verifying:
- Scenario 1: Strategic execution monitoring and source synchronization across Phase 78/75/73/74/76/77
- Scenario 2: Cross-roadmap dependency creation, review, and status tracking
- Scenario 3: Cross-roadmap circular dependency detection (HTTP 400 CROSS_ROADMAP_CYCLE_DETECTED)
- Scenario 4: Cross-roadmap dependency validation identifying sequencing conflicts
- Scenario 5: Strategic alignment analysis detecting orphan objectives and disconnected portfolios
- Scenario 6: Strategic planning assumption lifecycle (PROPOSED -> VALIDATED -> INVALIDATED)
- Scenario 7: Strategic change signal detection and escalation routing to Phase 63
- Scenario 8: Adaptation proposal lifecycle (DRAFT -> SUBMITTED -> ACCEPTED -> APPROVED_AUTHORITATIVE)
- Scenario 9: Adaptation proposal separation of duties (proposer cannot review own proposal -> 403)
- Scenario 10: Adaptation follow-through tracking across downstream execution references
- Scenario 11: Advisory scenario analysis execution and comparison with projection caveats
- Scenario 12: Strategic execution exception creation and authoritative escalation to Phase 67/63
- Scenario 13: Strategic execution exception resolution
- Scenario 14: Strategic review package generation and Phase 72 referral
- Scenario 15: Background routine maintenance scan job
- Scenario 16: Multi-tenant boundary isolation
- Scenario 17: Patient role authorization enforcement (HTTP 403 Forbidden)
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
from app.repositories.governance_strategy_execution_repository import (
    get_governance_strategy_execution_repository,
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
    repo = get_governance_strategy_execution_repository()
    repo.clear()
    yield
    repo.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Strategic Execution Monitoring & Source Synchronization
# =============================================================================

def test_scenario_1_strategic_execution_monitoring(client: TestClient):
    headers = {"X-User-Id": "usr-monitor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Create monitoring record for a Phase 78 roadmap milestone
    create_payload = {
        "roadmap_id": "RMAP-2026-01",
        "monitored_item_type": "PHASE_78_MILESTONE",
        "monitored_item_id": "MIL-001",
        "source_status": "IN_PROGRESS",
        "health_status": "ON_TRACK",
        "analytical_observation": "Initial execution tracking started.",
    }
    resp = client.post("/api/v1/governance-strategy-execution/monitoring", headers=headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    monitoring_id = data["monitoring_id"]
    assert data["health_status"] == "ON_TRACK"
    assert "advisory oversight and coordination tools" in data["disclaimer"]

    # Reconcile status with new health status
    reconcile_payload = {
        "source_status": "DELAYED",
        "health_status": "AT_RISK",
        "analytical_observation": "Milestone delivery delayed due to staff training bottleneck.",
        "detected_issue_count": 1,
    }
    rec_resp = client.post(
        f"/api/v1/governance-strategy-execution/monitoring/{monitoring_id}/reconcile",
        headers=headers,
        json=reconcile_payload,
    )
    assert rec_resp.status_code == 200, rec_resp.text
    updated = rec_resp.json()
    assert updated["health_status"] == "AT_RISK"
    assert updated["detected_issue_count"] == 1

    # List records
    list_resp = client.get("/api/v1/governance-strategy-execution/monitoring", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


# =============================================================================
# Scenario 2: Cross-Roadmap Dependency Creation, Review, and Status Tracking
# =============================================================================

def test_scenario_2_cross_roadmap_dependency_lifecycle(client: TestClient):
    author_headers = {"X-User-Id": "usr-owner-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    reviewer_headers = {"X-User-Id": "usr-lead-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Establish dependency: RMAP-A depends on RMAP-B
    create_payload = {
        "source_roadmap_id": "RMAP-ALPHA",
        "target_roadmap_id": "RMAP-BETA",
        "category": "SHARED_CAPABILITY",
        "rationale": "Alpha roadmap requires unified clinical decision support engine from Beta.",
        "planned_dependency_date": "2026-06-30T00:00:00Z",
        "responsible_owner_id": "usr-owner-01",
    }
    resp = client.post("/api/v1/governance-strategy-execution/cross-dependencies", headers=author_headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    dep_data = resp.json()
    dep_id = dep_data["dependency_id"]
    assert dep_data["status"] == "IDENTIFIED"

    # Review by independent reviewer
    review_payload = {
        "status": "CONFIRMED",
        "review_outcome": "Cross-roadmap dependency confirmed by steering committee.",
    }
    rev_resp = client.post(
        f"/api/v1/governance-strategy-execution/cross-dependencies/{dep_id}/review",
        headers=reviewer_headers,
        json=review_payload,
    )
    assert rev_resp.status_code == 200, rev_resp.text
    assert rev_resp.json()["status"] == "CONFIRMED"


# =============================================================================
# Scenario 3: Cross-Roadmap Circular Dependency Detection (400)
# =============================================================================

def test_scenario_3_cross_roadmap_circular_dependency_detection(client: TestClient):
    headers = {"X-User-Id": "usr-admin-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Dependency 1: RMAP-01 -> RMAP-02
    resp1 = client.post(
        "/api/v1/governance-strategy-execution/cross-dependencies",
        headers=headers,
        json={
            "source_roadmap_id": "RMAP-01",
            "target_roadmap_id": "RMAP-02",
            "category": "SHARED_TECHNOLOGY",
            "rationale": "RMAP-01 requires platform upgrades from RMAP-02.",
            "planned_dependency_date": "2026-05-01T00:00:00Z",
            "responsible_owner_id": "usr-admin-01",
        },
    )
    assert resp1.status_code == 201

    # Dependency 2: RMAP-02 -> RMAP-01 (Creates direct cycle)
    resp2 = client.post(
        "/api/v1/governance-strategy-execution/cross-dependencies",
        headers=headers,
        json={
            "source_roadmap_id": "RMAP-02",
            "target_roadmap_id": "RMAP-01",
            "category": "SHARED_CAPABILITY",
            "rationale": "RMAP-02 requires capabilities from RMAP-01.",
            "planned_dependency_date": "2026-06-01T00:00:00Z",
            "responsible_owner_id": "usr-admin-01",
        },
    )
    assert resp2.status_code == 400
    assert resp2.json()["error"]["code"] == "CROSS_ROADMAP_CYCLE_DETECTED"
    assert "Circular cross-roadmap dependency detected" in resp2.json()["error"]["message"]


# =============================================================================
# Scenario 4: Cross-Roadmap Dependency Validation
# =============================================================================

def test_scenario_4_cross_roadmap_validation(client: TestClient):
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rev_headers = {"X-User-Id": "usr-reviewer-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Create dependency
    resp = client.post(
        "/api/v1/governance-strategy-execution/cross-dependencies",
        headers=headers,
        json={
            "source_roadmap_id": "RMAP-CENTRAL",
            "target_roadmap_id": "RMAP-BRANCH",
            "category": "SHARED_WORKFORCE",
            "rationale": "Shared clinical nurse specialist training.",
            "planned_dependency_date": "2026-09-01T00:00:00Z",
            "responsible_owner_id": "usr-lead-01",
        },
    )
    assert resp.status_code == 201
    dep_id = resp.json()["dependency_id"]

    # Validate - initially valid
    val_resp1 = client.post("/api/v1/governance-strategy-execution/cross-dependencies/validate", headers=headers)
    assert val_resp1.status_code == 200
    assert val_resp1.json()["is_valid"] is True

    # Update dependency to CONFLICT_DETECTED
    client.post(
        f"/api/v1/governance-strategy-execution/cross-dependencies/{dep_id}/review",
        headers=rev_headers,
        json={
            "status": "CONFLICT_DETECTED",
            "review_outcome": "Schedule conflict detected.",
            "conflict_description": "Target delivery scheduled after source go-live.",
        },
    )

    # Validate again - now flagged
    val_resp2 = client.post("/api/v1/governance-strategy-execution/cross-dependencies/validate", headers=headers)
    assert val_resp2.status_code == 200
    val_data = val_resp2.json()
    assert val_data["is_valid"] is False
    assert len(val_data["date_conflicts"]) == 1


# =============================================================================
# Scenario 5: Strategic Alignment Analysis
# =============================================================================

def test_scenario_5_strategic_alignment_analysis(client: TestClient):
    headers = {"X-User-Id": "usr-eval-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rev_headers = {"X-User-Id": "usr-gov-lead-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Record alignment finding
    payload = {
        "category": "ORPHAN_OBJECTIVE",
        "affected_roadmap_ids": ["RMAP-2026-01"],
        "affected_record_references": ["OBJ-101"],
        "detection_method": "Automated roadmap structural audit",
        "explanation": "Strategic objective OBJ-101 has no assigned milestones or implementation portfolios.",
        "confidence_score": 0.95,
        "suggested_review_destination": "PHASE_72_MANAGEMENT_REVIEW",
    }
    resp = client.post("/api/v1/governance-strategy-execution/alignment-findings", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    finding_id = resp.json()["finding_id"]
    assert resp.json()["status"] == "DETECTED"

    # Review finding
    rev_resp = client.post(
        f"/api/v1/governance-strategy-execution/alignment-findings/{finding_id}/review",
        headers=rev_headers,
        json={
            "status": "ACCEPTED_FOR_ADAPTATION",
            "review_notes": "Accepted. Will propose adaptation in upcoming executive review.",
        },
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "ACCEPTED_FOR_ADAPTATION"
    assert rev_resp.json()["reviewed_by"] == "usr-gov-lead-02"


# =============================================================================
# Scenario 6: Strategic Planning Assumption Lifecycle
# =============================================================================

def test_scenario_6_strategic_assumption_lifecycle(client: TestClient):
    headers = {"X-User-Id": "usr-planner-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Register assumption
    create_payload = {
        "roadmap_id": "RMAP-2026-01",
        "category": "WORKFORCE_AVAILABILITY",
        "description": "Assumes availability of 15 certified clinical safety auditors across facilities.",
        "source_rationale": "HR staffing projection Q2 2026.",
        "owner_id": "usr-planner-01",
        "validation_method": "Quarterly HR audit headcount verification",
        "expected_review_date": "2026-06-30T00:00:00Z",
        "impact_if_invalidated": "Delays across independent clinical safety audit execution.",
    }
    resp = client.post("/api/v1/governance-strategy-execution/assumptions", headers=headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    assump_id = resp.json()["assumption_id"]
    assert resp.json()["status"] == "PROPOSED"

    # Validate assumption
    val_resp = client.post(
        f"/api/v1/governance-strategy-execution/assumptions/{assump_id}/validate",
        headers=headers,
        json={
            "status": "VALIDATED",
            "supporting_evidence_reference": "DOC-HR-Q2-VERIFIED",
            "validation_notes": "Headcount verified by HR safety director.",
        },
    )
    assert val_resp.status_code == 200
    assert val_resp.json()["status"] == "VALIDATED"

    # Later: staffing shortage invalidates assumption
    inval_resp = client.post(
        f"/api/v1/governance-strategy-execution/assumptions/{assump_id}/validate",
        headers=headers,
        json={
            "status": "INVALIDATED",
            "supporting_evidence_reference": "DOC-HR-SHORTAGE-REPORT",
            "validation_notes": "5 safety auditors resigned; hiring frozen.",
        },
    )
    assert inval_resp.status_code == 200
    assert inval_resp.json()["status"] == "INVALIDATED"


# =============================================================================
# Scenario 7: Strategic Change Signal Detection and Escalation to Phase 63
# =============================================================================

def test_scenario_7_strategic_signal_detection_and_escalation(client: TestClient):
    headers = {"X-User-Id": "usr-detector-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    lead_headers = {"X-User-Id": "usr-safety-lead-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Record signal
    sig_payload = {
        "category": "REPEATED_MILESTONE_DELAYS",
        "affected_roadmap_ids": ["RMAP-2026-01"],
        "detection_rule": "3 consecutive delayed delivery milestones on critical path",
        "observation_period": "Q1 2026 - Q2 2026",
        "severity": "HIGH",
        "strategic_implication": "Risk of clinical safety control deployment slippage in emergency ward.",
        "recommended_destination": "PHASE_63_RISK",
    }
    resp = client.post("/api/v1/governance-strategy-execution/signals", headers=headers, json=sig_payload)
    assert resp.status_code == 201, resp.text
    sig_id = resp.json()["signal_id"]
    assert resp.json()["disposition"] == "ACTIVE"

    # Escalate to Phase 63
    esc_resp = client.post(
        f"/api/v1/governance-strategy-execution/signals/{sig_id}/escalate-phase-63?risk_rationale=Critical safety controls delayed impacting patient triage",
        headers=lead_headers,
    )
    assert esc_resp.status_code == 200, esc_resp.text
    assert esc_resp.json()["disposition"] == "ESCALATED_PHASE_63"
    assert "Escalated to Phase 63" in esc_resp.json()["review_notes"]


# =============================================================================
# Scenario 8: Adaptation Proposal Lifecycle
# =============================================================================

def test_scenario_8_adaptation_proposal_lifecycle(client: TestClient):
    author_headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rev_headers = {"X-User-Id": "usr-reviewer-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Create proposal in DRAFT
    create_payload = {
        "source_roadmap_id": "RMAP-2026-01",
        "proposal_type": "REVISE_MILESTONE",
        "proposed_change_description": "Extend target date of medication safety automation milestone by 60 days.",
        "rationale": "Hardware integration delay from external vendor.",
        "expected_benefits": "Avoids rushing testing phase and prevents clinical safety defects.",
        "potential_negative_consequences": "Pushes downstream analytics pilot by 30 days.",
        "resource_implications": "Requires $15,000 contractor extension.",
    }
    resp = client.post("/api/v1/governance-strategy-execution/adaptation-proposals", headers=author_headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    prop_id = resp.json()["proposal_id"]
    assert resp.json()["status"] == "DRAFT"

    # Submit proposal
    sub_resp = client.post(
        f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/submit",
        headers=author_headers,
        json={"submission_notes": "Submitted for Q3 executive review."},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # Review proposal by independent reviewer
    rev_resp = client.post(
        f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/review",
        headers=rev_headers,
        json={
            "status": "ACCEPTED_FOR_CONSIDERATION",
            "review_notes": "Accepted for inclusion in Phase 72 management review agenda.",
        },
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "ACCEPTED_FOR_CONSIDERATION"

    # Link authoritative Phase 72/78 decision
    link_resp = client.post(
        f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/link-decision",
        headers=rev_headers,
        json={
            "phase72_decision_reference": "DEC-P72-2026-088",
            "phase78_revision_reference": "REV-P78-RMAP-01-V2",
            "phase73_implementation_reference": "IMP-P73-042",
            "status": "AUTHORIZED",
        },
    )
    assert link_resp.status_code == 200
    assert link_resp.json()["status"] == "APPROVED_AUTHORITATIVE"
    assert link_resp.json()["authoritative_decision_reference"] == "DEC-P72-2026-088"


# =============================================================================
# Scenario 9: Adaptation Proposal Separation of Duties (403)
# =============================================================================

def test_scenario_9_adaptation_proposal_separation_of_duties(client: TestClient):
    author_headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Create and submit
    resp = client.post(
        "/api/v1/governance-strategy-execution/adaptation-proposals",
        headers=author_headers,
        json={
            "source_roadmap_id": "RMAP-2026-01",
            "proposal_type": "REVISE_OBJECTIVE",
            "proposed_change_description": "Modify emergency triage target capability.",
            "rationale": "Evolving regulatory mandate.",
            "expected_benefits": "Alignment with national standards.",
            "potential_negative_consequences": "None.",
            "resource_implications": "Internal resource re-allocation.",
        },
    )
    assert resp.status_code == 201
    prop_id = resp.json()["proposal_id"]

    client.post(
        f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/submit",
        headers=author_headers,
        json={"submission_notes": "Submitted."},
    )

    # Author attempts to review own proposal -> 403 Forbidden
    self_review_resp = client.post(
        f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/review",
        headers=author_headers,
        json={
            "status": "ACCEPTED_FOR_CONSIDERATION",
            "review_notes": "Author approves own proposal.",
        },
    )
    assert self_review_resp.status_code == 403
    assert self_review_resp.json()["error"]["code"] == "STRATEGY_EXECUTION_SEPARATION_OF_DUTIES_VIOLATION"


# =============================================================================
# Scenario 10: Adaptation Follow-Through Tracking
# =============================================================================

def test_scenario_10_adaptation_follow_through_tracking(client: TestClient):
    author_headers = {"X-User-Id": "usr-owner-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rev_headers = {"X-User-Id": "usr-reviewer-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    create_payload = {
        "source_roadmap_id": "RMAP-2026-02",
        "proposal_type": "RESOLVE_CROSS_DEPENDENCY",
        "proposed_change_description": "Re-sequence digital order entry dependency.",
        "rationale": "Prerequisite clearance.",
        "expected_benefits": "Resolved conflict.",
        "potential_negative_consequences": "None.",
        "resource_implications": "Neutral.",
    }
    resp = client.post("/api/v1/governance-strategy-execution/adaptation-proposals", headers=author_headers, json=create_payload)
    prop_id = resp.json()["proposal_id"]

    client.post(f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/submit", headers=author_headers, json={})
    client.post(
        f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/review",
        headers=rev_headers,
        json={"status": "ACCEPTED_FOR_CONSIDERATION", "review_notes": "Accepted."},
    )

    # Link authoritative decision, creating follow-through
    client.post(
        f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/link-decision",
        headers=rev_headers,
        json={
            "phase72_decision_reference": "DEC-P72-2026-101",
            "phase78_revision_reference": "REV-P78-RMAP-02-V2",
            "phase73_implementation_reference": "IMP-P73-099",
            "status": "AUTHORIZED",
        },
    )

    # Fetch follow-through by proposal
    ft_resp = client.get(f"/api/v1/governance-strategy-execution/adaptation-proposals/{prop_id}/follow-through", headers=author_headers)
    assert ft_resp.status_code == 200, ft_resp.text
    ft_data = ft_resp.json()
    assert ft_data is not None
    assert ft_data["proposal_id"] == prop_id
    assert ft_data["phase72_decision_reference"] == "DEC-P72-2026-101"

    # List all follow-through records
    list_ft = client.get("/api/v1/governance-strategy-execution/adaptation-follow-through", headers=author_headers)
    assert list_ft.status_code == 200
    assert len(list_ft.json()) >= 1


# =============================================================================
# Scenario 11: Advisory Scenario Analysis Execution and Comparison
# =============================================================================

def test_scenario_11_advisory_scenario_analysis(client: TestClient):
    headers = {"X-User-Id": "usr-analyst-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Create scenario
    scenario_payload = {
        "title": "Severe Workforce Shortage Scenario",
        "scenario_type": "REDUCED_RESOURCES",
        "description": "Simulates 30% reduction in available clinical informatics support.",
        "input_roadmap_id": "RMAP-2026-01",
        "assumptions": ["Contractor replacement delayed by 90 days"],
    }
    resp = client.post("/api/v1/governance-strategy-execution/scenarios", headers=headers, json=scenario_payload)
    assert resp.status_code == 201, resp.text
    scen_id = resp.json()["scenario_id"]
    assert "advisory what-if" in resp.json()["limitations"].lower()

    # Execute simulation
    exec_resp = client.post(
        f"/api/v1/governance-strategy-execution/scenarios/{scen_id}/execute",
        headers=headers,
        json={"milestone_delays_days": 45, "budget_variance_pct": -20.0},
    )
    assert exec_resp.status_code == 200, exec_resp.text
    exec_data = exec_resp.json()
    assert len(exec_data["projected_milestone_impacts"]) == 1
    assert exec_data["projected_milestone_impacts"][0]["projected_status"] == "OFF_TRACK"

    # Compare scenarios
    comp_resp = client.post(
        f"/api/v1/governance-strategy-execution/scenarios/compare?scenario_ids={scen_id}&baseline_roadmap_id=RMAP-2026-01",
        headers=headers,
    )
    assert comp_resp.status_code == 200, comp_resp.text
    comp_data = comp_resp.json()
    assert len(comp_data["compared_scenarios"]) == 1
    assert "do NOT constitute operational commitments" in comp_data["comparative_summary"]


# =============================================================================
# Scenario 12: Strategic Execution Exception Creation and Authoritative Escalation
# =============================================================================

def test_scenario_12_strategic_execution_exception_escalation(client: TestClient):
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Log exception
    create_payload = {
        "category": "CROSS_ROADMAP_CONFLICT",
        "affected_roadmap_ids": ["RMAP-2026-01", "RMAP-2026-02"],
        "detection_source": "Automated Cross-Dependency Monitor",
        "impact_description": "Unresolved technology dependency halts medication reconciliation milestone.",
        "responsible_owner_id": "usr-lead-01",
    }
    resp = client.post("/api/v1/governance-strategy-execution/exceptions", headers=headers, json=create_payload)
    assert resp.status_code == 201, resp.text
    exc_id = resp.json()["exception_id"]
    assert resp.json()["status"] == "OPEN"

    # Escalate to Phase 67 Escalation Governance
    esc_resp = client.post(
        f"/api/v1/governance-strategy-execution/exceptions/{exc_id}/escalate",
        headers=headers,
        json={
            "escalation_destination": "PHASE_67_ESCALATION",
            "escalation_reference": "ESC-P67-2026-099",
            "notes": "Escalated for cross-workflow governance resolution.",
        },
    )
    assert esc_resp.status_code == 200, esc_resp.text
    assert esc_resp.json()["status"] == "ESCALATED_PHASE_67"
    assert esc_resp.json()["escalation_destination"] == "PHASE_67_ESCALATION"


# =============================================================================
# Scenario 13: Strategic Execution Exception Resolution
# =============================================================================

def test_scenario_13_strategic_execution_exception_resolution(client: TestClient):
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    create_payload = {
        "category": "INVALIDATED_ASSUMPTION",
        "affected_roadmap_ids": ["RMAP-2026-01"],
        "detection_source": "Assumption Validation Audit",
        "impact_description": "Assumed funding grant reduced by 25%.",
        "responsible_owner_id": "usr-lead-01",
    }
    resp = client.post("/api/v1/governance-strategy-execution/exceptions", headers=headers, json=create_payload)
    exc_id = resp.json()["exception_id"]

    # Resolve exception
    res_resp = client.post(
        f"/api/v1/governance-strategy-execution/exceptions/{exc_id}/resolve",
        headers=headers,
        json={"resolution_evidence": "Reallocated contingency funds approved in DEC-FIN-2026-044."},
    )
    assert res_resp.status_code == 200, res_resp.text
    assert res_resp.json()["status"] == "RESOLVED"
    assert "Reallocated contingency funds" in res_resp.json()["resolution_evidence"]


# =============================================================================
# Scenario 14: Strategic Review Package Generation and Phase 72 Referral
# =============================================================================

def test_scenario_14_strategic_review_package_generation_and_referral(client: TestClient):
    headers = {"X-User-Id": "usr-preparer-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Populate monitored item and assumption first
    client.post(
        "/api/v1/governance-strategy-execution/monitoring",
        headers=headers,
        json={
            "roadmap_id": "RMAP-2026-01",
            "monitored_item_type": "PHASE_78_ROADMAP",
            "monitored_item_id": "RMAP-2026-01",
            "source_status": "ACTIVE",
            "health_status": "ON_TRACK",
        },
    )

    # Generate review package
    pkg_payload = {
        "title": "Q3 2026 Clinical Safety Governance Strategic Execution Dossier",
        "reporting_period": "Q3 2026",
        "included_roadmap_ids": ["RMAP-2026-01"],
        "executive_summary": "Overall execution is 85% on track with 1 emerging cross-roadmap dependency risk.",
    }
    resp = client.post("/api/v1/governance-strategy-execution/review-packages", headers=headers, json=pkg_payload)
    assert resp.status_code == 201, resp.text
    pkg_id = resp.json()["package_id"]
    assert resp.json()["monitored_status_summary"]["ON_TRACK"] == 1

    # Refer to Phase 72 Management Review
    ref_resp = client.post(
        f"/api/v1/governance-strategy-execution/review-packages/{pkg_id}/refer-phase-72",
        headers=headers,
        json={"agenda_item_title": "Executive Review of Strategic Governance Roadmaps"},
    )
    assert ref_resp.status_code == 200, ref_resp.text
    assert ref_resp.json()["phase_72_referral_reference"] is not None
    assert ref_resp.json()["phase_72_referral_reference"].startswith("P72-REF-")


# =============================================================================
# Scenario 15: Background Routine Maintenance Scan Job
# =============================================================================

def test_scenario_15_background_routine_scan_job(client: TestClient):
    headers = {"X-User-Id": "usr-sys-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Seed monitored items: one on-track, one stale
    client.post(
        "/api/v1/governance-strategy-execution/monitoring",
        headers=headers,
        json={
            "roadmap_id": "RMAP-2026-01",
            "monitored_item_type": "PHASE_78_ROADMAP",
            "monitored_item_id": "RMAP-2026-01",
            "source_status": "ACTIVE",
            "health_status": "ON_TRACK",
        },
    )
    client.post(
        "/api/v1/governance-strategy-execution/monitoring",
        headers=headers,
        json={
            "roadmap_id": "RMAP-2026-01",
            "monitored_item_type": "PHASE_78_OBJECTIVE",
            "monitored_item_id": "OBJ-999",
            "source_status": "PENDING",
            "health_status": "STALE_EVIDENCE",
        },
    )

    # Execute routine scan
    scan_resp = client.post("/api/v1/governance-strategy-execution/maintenance/routine-scan", headers=headers)
    assert scan_resp.status_code == 200, scan_resp.text
    scan_data = scan_resp.json()
    assert scan_data["status"] == "COMPLETED"
    assert scan_data["scanned_roadmaps"] == 1
    assert scan_data["scanned_monitored_items"] == 2
    assert scan_data["stale_evidence_flagged"] == 1


# =============================================================================
# Scenario 16: Multi-Tenant Boundary Isolation
# =============================================================================

def test_scenario_16_multitenant_boundary_isolation(client: TestClient):
    tenant_a_headers = {"X-User-Id": "usr-apollo-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    tenant_b_headers = {"X-User-Id": "usr-fortis-01", "X-User-Organization": "org-fortis-02", "X-User-Role": "ADMIN"}

    # Tenant A creates monitoring record
    resp_a = client.post(
        "/api/v1/governance-strategy-execution/monitoring",
        headers=tenant_a_headers,
        json={
            "roadmap_id": "RMAP-APOLLO",
            "monitored_item_type": "PHASE_78_ROADMAP",
            "monitored_item_id": "RMAP-APOLLO",
            "source_status": "ACTIVE",
            "health_status": "ON_TRACK",
        },
    )
    assert resp_a.status_code == 201
    mon_id_a = resp_a.json()["monitoring_id"]

    # Tenant B attempts to fetch Tenant A's record -> 404
    resp_b_get = client.get(f"/api/v1/governance-strategy-execution/monitoring/{mon_id_a}", headers=tenant_b_headers)
    assert resp_b_get.status_code == 404

    # Tenant B lists records -> empty
    resp_b_list = client.get("/api/v1/governance-strategy-execution/monitoring", headers=tenant_b_headers)
    assert resp_b_list.status_code == 200
    assert len(resp_b_list.json()) == 0


# =============================================================================
# Scenario 17: Patient Role Authorization Enforcement (403 Forbidden)
# =============================================================================

def test_scenario_17_patient_role_authorization_enforcement(client: TestClient):
    patient_headers = {"X-User-Id": "usr-patient-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "PATIENT"}

    # Test all endpoint groups for 403 Forbidden rejection
    endpoints_to_test = [
        ("GET", "/api/v1/governance-strategy-execution/monitoring"),
        ("POST", "/api/v1/governance-strategy-execution/monitoring"),
        ("GET", "/api/v1/governance-strategy-execution/cross-dependencies"),
        ("POST", "/api/v1/governance-strategy-execution/cross-dependencies"),
        ("GET", "/api/v1/governance-strategy-execution/alignment-findings"),
        ("POST", "/api/v1/governance-strategy-execution/alignment-findings"),
        ("GET", "/api/v1/governance-strategy-execution/assumptions"),
        ("POST", "/api/v1/governance-strategy-execution/assumptions"),
        ("GET", "/api/v1/governance-strategy-execution/signals"),
        ("POST", "/api/v1/governance-strategy-execution/signals"),
        ("GET", "/api/v1/governance-strategy-execution/adaptation-proposals"),
        ("POST", "/api/v1/governance-strategy-execution/adaptation-proposals"),
        ("GET", "/api/v1/governance-strategy-execution/scenarios"),
        ("POST", "/api/v1/governance-strategy-execution/scenarios"),
        ("GET", "/api/v1/governance-strategy-execution/exceptions"),
        ("POST", "/api/v1/governance-strategy-execution/exceptions"),
        ("GET", "/api/v1/governance-strategy-execution/review-packages"),
        ("POST", "/api/v1/governance-strategy-execution/review-packages"),
        ("POST", "/api/v1/governance-strategy-execution/maintenance/routine-scan"),
    ]

    for method, path in endpoints_to_test:
        if method == "GET":
            resp = client.get(path, headers=patient_headers)
        else:
            resp = client.post(path, headers=patient_headers, json={})
        assert resp.status_code == 403, f"Endpoint {method} {path} returned {resp.status_code} instead of 403"
        assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

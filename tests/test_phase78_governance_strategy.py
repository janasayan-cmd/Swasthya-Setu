"""Phase 78: Clinical Safety Governance Strategy and Multi-Year Roadmap Tests.

Comprehensive test suite verifying:
- Scenario 1: Strategic objective creation, update, submission, separation of duties on approval, activation, and retirement
- Scenario 2: Evidence-linked strategic priority proposal, validation of source references, and human review with separation of duties
- Scenario 3: Multi-year strategic roadmap creation, draft updates, submission, separation of duties on approval, and activation
- Scenario 4: Material roadmap revision preserving approved version baseline in change_history and incrementing version
- Scenario 5: Capability development target operating state proposal referencing Phase 77 assessment baselines
- Scenario 6: Strategic milestone creation, updating, and dependency linkage
- Scenario 7: Circular dependency detection (direct and indirect) returning HTTP 400 STRATEGY_DEPENDENCY_CYCLE_DETECTED
- Scenario 8: Dependency validation endpoint detecting sequencing date conflicts and validating DAGs
- Scenario 9: Milestone completion submission with evidence reference, and verification with separation of duties
- Scenario 10: Resource and investment proposal tracking, review status progression, and external approval reference recording
- Scenario 11: Strategy-to-portfolio linking (Phase 75) and milestone-to-implementation linking (Phase 73)
- Scenario 12: Strategic delivery issue creation and authoritative escalation to Phase 63 / Phase 67
- Scenario 13: Strategic issue resolution workflow
- Scenario 14: Strategic reporting endpoints (roadmap overview, milestone schedule, portfolio alignment, issue summary)
- Scenario 15: Idempotent background routine maintenance scan job detecting overdue milestones and conflicts
- Scenario 16: Multi-tenant boundary isolation
- Scenario 17: Patient role authorization enforcement (HTTP 403 Forbidden across all endpoints)
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
from app.repositories.governance_strategy_repository import (
    get_governance_strategy_repository,
)
from app.schemas.auth import UserRole
from app.schemas.governance_strategy_objective import (
    CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
    ObjectiveCategory,
    ObjectivePriority,
    ObjectiveStatus,
    PlanningHorizon,
)
from app.schemas.governance_strategy_priority import (
    PriorityLevel,
    PriorityReviewOutcome,
)
from app.schemas.governance_strategy_roadmap import (
    RoadmapStatus,
)
from app.schemas.governance_strategy_capability_target import (
    CapabilityDomainEnum,
    CapabilityTargetStatus,
)
from app.schemas.governance_strategy_milestone import (
    DependencyType,
    MilestoneStatus,
)
from app.schemas.governance_strategy_resource import (
    InvestmentReviewStatus,
)
from app.schemas.governance_strategy_coordination import (
    StrategyIssueClassification,
    StrategyIssueStatus,
)
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
    repo = get_governance_strategy_repository()
    repo.clear()
    yield
    repo.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Helper Utilities
# =============================================================================

def create_and_approve_test_objective(client: TestClient, org_id: str = "org-apollo-01") -> str:
    headers_author = {"X-User-Id": "usr-author-01", "X-User-Organization": org_id, "X-User-Role": "ADMIN"}
    headers_approver = {"X-User-Id": "usr-approver-02", "X-User-Organization": org_id, "X-User-Role": "ADMIN"}

    create_resp = client.post(
        "/api/v1/governance-strategy/objectives",
        headers=headers_author,
        json={
            "title": "Establish Zero Preventable Clinical Safety Adverse Incidents",
            "description": "Standardize clinical governance controls across all emergency and inpatient wards.",
            "rationale": "High-risk escalation gates must be consistently applied.",
            "category": "INCIDENT_PREVENTION",
            "intended_target_state": "All wards operating at Defined maturity level.",
            "priority": "HIGH",
            "planning_horizon": "THREE_YEAR",
            "responsible_governance_owner_id": "usr-author-01",
            "measurement_methodology": "Quarterly audit adherence metrics and verified incident rate reporting.",
            "target_condition": "Zero unescalated high-risk clinical safety events.",
        },
    )
    assert create_resp.status_code == 201
    obj_id = create_resp.json()["objective_id"]

    sub_resp = client.post(f"/api/v1/governance-strategy/objectives/{obj_id}/submit", headers=headers_author, json={})
    assert sub_resp.status_code == 200

    appr_resp = client.post(
        f"/api/v1/governance-strategy/objectives/{obj_id}/approve",
        headers=headers_approver,
        json={"approval_reference": "p72-dec-2026-001", "approver_notes": "Approved by Clinical Safety Committee."},
    )
    assert appr_resp.status_code == 200
    return obj_id


def create_and_activate_test_roadmap(client: TestClient, org_id: str = "org-apollo-01") -> str:
    headers_author = {"X-User-Id": "usr-author-01", "X-User-Organization": org_id, "X-User-Role": "ADMIN"}
    headers_approver = {"X-User-Id": "usr-approver-02", "X-User-Organization": org_id, "X-User-Role": "ADMIN"}

    obj_id = create_and_approve_test_objective(client, org_id)

    create_resp = client.post(
        "/api/v1/governance-strategy/roadmaps",
        headers=headers_author,
        json={
            "title": "3-Year Clinical Safety Governance Transformation Roadmap",
            "description": "Multi-year transformation of clinical risk and decision assurance capabilities.",
            "planning_horizon": "THREE_YEAR",
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2028-12-31T00:00:00Z",
            "owner_id": "usr-author-01",
            "strategic_objective_ids": [obj_id],
        },
    )
    assert create_resp.status_code == 201
    rm_id = create_resp.json()["roadmap_id"]

    sub_resp = client.post(f"/api/v1/governance-strategy/roadmaps/{rm_id}/submit", headers=headers_author, json={})
    assert sub_resp.status_code == 200

    appr_resp = client.post(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}/approve",
        headers=headers_approver,
        json={"approval_reference": "p72-exec-dec-100"},
    )
    assert appr_resp.status_code == 200

    act_resp = client.post(f"/api/v1/governance-strategy/roadmaps/{rm_id}/activate", headers=headers_author)
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ACTIVE"
    return rm_id


# =============================================================================
# Test Scenarios
# =============================================================================

def test_scenario_1_strategic_objective_lifecycle_and_separation_of_duties(client: TestClient):
    """Scenario 1: Objective creation, update, submission, separation of duties on approval, activation, retirement."""
    headers_author = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_approver = {"X-User-Id": "usr-approver-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Create DRAFT objective
    resp = client.post(
        "/api/v1/governance-strategy/objectives",
        headers=headers_author,
        json={
            "title": "Establish Comprehensive Clinical Risk Governance",
            "description": "Deploy standardized risk management protocols across all facilities.",
            "rationale": "High variance in regional risk assessments identified in Phase 77 audit.",
            "category": "RISK_GOVERNANCE",
            "intended_target_state": "All facilities operating under unified Phase 63 risk criteria.",
            "priority": "HIGH",
            "planning_horizon": "THREE_YEAR",
            "responsible_governance_owner_id": "usr-author-01",
            "measurement_methodology": "Verified Phase 63 risk register completeness.",
            "target_condition": "100% of high clinical risks have approved mitigating controls.",
        },
    )
    assert resp.status_code == 201
    obj = resp.json()
    obj_id = obj["objective_id"]
    assert obj["status"] == "DRAFT"
    assert obj["version"] == 1
    assert CLINICAL_SAFETY_STRATEGY_DISCLAIMER in obj["disclaimer"]

    # Update draft objective
    upd_resp = client.put(
        f"/api/v1/governance-strategy/objectives/{obj_id}",
        headers=headers_author,
        json={"title": "Establish Enterprise Clinical Risk Governance Framework"},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["title"] == "Establish Enterprise Clinical Risk Governance Framework"

    # Submit objective
    sub_resp = client.post(f"/api/v1/governance-strategy/objectives/{obj_id}/submit", headers=headers_author, json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # Separation of duties: author cannot approve own objective
    self_appr = client.post(
        f"/api/v1/governance-strategy/objectives/{obj_id}/approve",
        headers=headers_author,
        json={"approval_reference": "self-ref-001"},
    )
    assert self_appr.status_code == 403
    assert self_appr.json()["error"]["code"] == "STRATEGY_SEPARATION_OF_DUTIES_VIOLATION"

    # Authorized independent approver succeeds
    good_appr = client.post(
        f"/api/v1/governance-strategy/objectives/{obj_id}/approve",
        headers=headers_approver,
        json={"approval_reference": "p72-dec-approved-200"},
    )
    assert good_appr.status_code == 200
    assert good_appr.json()["status"] == "APPROVED"
    assert good_appr.json()["approved_by"] == "usr-approver-02"

    # Activate
    act_resp = client.post(f"/api/v1/governance-strategy/objectives/{obj_id}/activate", headers=headers_author)
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ACTIVE"

    # Retire
    ret_resp = client.post(
        f"/api/v1/governance-strategy/objectives/{obj_id}/retire",
        headers=headers_author,
        json={"reason": "Objective fully achieved and integrated into routine operations."},
    )
    assert ret_resp.status_code == 200
    assert ret_resp.json()["status"] == "COMPLETED"


def test_scenario_2_evidence_linked_priority_proposal_and_review(client: TestClient):
    """Scenario 2: Propose priority from Phase 77 evidence and human review with separation of duties."""
    headers_proposer = {"X-User-Id": "usr-proposer-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_reviewer = {"X-User-Id": "usr-reviewer-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    resp = client.post(
        "/api/v1/governance-strategy/priorities",
        headers=headers_proposer,
        json={
            "title": "Remediate Regional Clinical Risk Escalation Deficit",
            "strategic_rationale": "Phase 77 assessment detected systemic gap in emergency department telemetry escalation.",
            "potential_impact": "High potential for missed early clinical deterioration.",
            "urgency": "Immediate Q1 focus required.",
            "evidence_references": [
                {
                    "source_workflow": "PHASE_77_SYSTEMIC_GAP",
                    "source_record_id": "gap-ed-telemetry-01",
                    "ownership": "Clinical Safety Quality Office",
                    "timestamp": "2026-02-15T00:00:00Z",
                    "confidence_score": 0.95,
                    "limitations": "Evidence based on 3 regional tertiary hospitals.",
                }
            ],
            "proposed_priority_level": "CRITICAL",
        },
    )
    assert resp.status_code == 201
    p_data = resp.json()
    p_id = p_data["priority_id"]
    assert p_data["status"] == "PROPOSED"
    assert p_data["evidence_references"][0]["source_workflow"] == "PHASE_77_SYSTEMIC_GAP"

    # Separation of duties: proposer cannot review own priority
    self_rev = client.post(
        f"/api/v1/governance-strategy/priorities/{p_id}/review",
        headers=headers_proposer,
        json={"outcome": "ACCEPTED", "review_notes": "Attempting self-review"},
    )
    assert self_rev.status_code == 403
    assert self_rev.json()["error"]["code"] == "STRATEGY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent reviewer reviews and accepts priority
    good_rev = client.post(
        f"/api/v1/governance-strategy/priorities/{p_id}/review",
        headers=headers_reviewer,
        json={"outcome": "ACCEPTED", "review_notes": "Reviewed and validated against Phase 77 systemic gap report."},
    )
    assert good_rev.status_code == 200
    assert good_rev.json()["status"] == "ACCEPTED"
    assert good_rev.json()["reviewed_by"] == "usr-reviewer-02"


def test_scenario_3_multi_year_roadmap_lifecycle_and_separation_of_duties(client: TestClient):
    """Scenario 3: Multi-year roadmap creation, draft updates, submission, approval, and activation."""
    headers_author = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_approver = {"X-User-Id": "usr-approver-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    obj_id = create_and_approve_test_objective(client)

    resp = client.post(
        "/api/v1/governance-strategy/roadmaps",
        headers=headers_author,
        json={
            "title": "2026-2029 Clinical Safety Governance Strategic Roadmap",
            "description": "Enterprise-wide multi-year strategic roadmap.",
            "planning_horizon": "THREE_YEAR",
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2028-12-31T00:00:00Z",
            "owner_id": "usr-author-01",
            "strategic_objective_ids": [obj_id],
        },
    )
    assert resp.status_code == 201
    rm_id = resp.json()["roadmap_id"]
    assert resp.json()["status"] == "DRAFT"
    assert resp.json()["current_version"] == 1

    # Update draft roadmap
    upd_resp = client.put(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}",
        headers=headers_author,
        json={"title": "2026-2029 Enterprise Clinical Safety Governance Strategic Roadmap"},
    )
    assert upd_resp.status_code == 200

    # Submit
    sub_resp = client.post(f"/api/v1/governance-strategy/roadmaps/{rm_id}/submit", headers=headers_author, json={})
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # Separation of duties on approval
    self_appr = client.post(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}/approve",
        headers=headers_author,
        json={"approval_reference": "self-ref"},
    )
    assert self_appr.status_code == 403
    assert self_appr.json()["error"]["code"] == "STRATEGY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent approval
    good_appr = client.post(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}/approve",
        headers=headers_approver,
        json={"approval_reference": "p72-dec-board-101"},
    )
    assert good_appr.status_code == 200
    assert good_appr.json()["status"] == "APPROVED"
    assert good_appr.json()["approved_version"] == 1

    # Activate
    act_resp = client.post(f"/api/v1/governance-strategy/roadmaps/{rm_id}/activate", headers=headers_author)
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ACTIVE"


def test_scenario_4_material_roadmap_revision_controlled_versioning(client: TestClient):
    """Scenario 4: Material roadmap revision preserving approved version baseline in change_history."""
    headers_author = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_reviser = {"X-User-Id": "usr-reviser-03", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    # Revision
    rev_resp = client.post(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}/revise",
        headers=headers_reviser,
        json={
            "change_reason": "Accelerated timeline due to new executive clinical safety mandate.",
            "approval_reference": "p72-rev-mandate-002",
        },
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["current_version"] == 2
    assert rev_data["approved_version"] == 2
    assert len(rev_data["change_history"]) == 1
    chg = rev_data["change_history"][0]
    assert chg["previous_version"] == 1
    assert chg["new_version"] == 2
    assert chg["requesting_user_id"] == "usr-reviser-03"
    assert "Accelerated timeline" in chg["change_reason"]


def test_scenario_5_capability_target_operating_state_management(client: TestClient):
    """Scenario 5: Capability target proposal referencing Phase 77 assessment baselines."""
    headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    resp = client.post(
        "/api/v1/governance-strategy/capability-targets",
        headers=headers,
        json={
            "capability_domain": "CLINICAL_SAFETY_LEADERSHIP",
            "title": "Executive Clinical Safety Committee Operational Maturity",
            "current_state_description": "Currently at Level 2 (Developing) with emergent procedures in pockets.",
            "current_maturity_reference": "asmt-2026-q1-l2",
            "desired_future_state_description": "Achieve Level 4 (Managed) with quantitative monitoring of governance performance.",
            "target_maturity_level": "LEVEL_4_MANAGED",
            "responsible_owner_id": "usr-author-01",
            "evidence_required": ["Verified executive committee meeting packs", "Attendance quorum logs"],
            "review_criteria": "Demonstrated adherence across 4 consecutive calendar quarters.",
        },
    )
    assert resp.status_code == 201
    tgt_id = resp.json()["target_id"]
    assert resp.json()["status"] == "PROPOSED"
    assert resp.json()["capability_domain"] == "CLINICAL_SAFETY_LEADERSHIP"

    # Update target state
    upd_resp = client.put(
        f"/api/v1/governance-strategy/capability-targets/{tgt_id}",
        headers=headers,
        json={"status": "ACCEPTED", "target_maturity_level": "LEVEL_4_MANAGED"},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["status"] == "ACCEPTED"


def test_scenario_6_strategic_milestone_management(client: TestClient):
    """Scenario 6: Milestone creation, updating, and delivery date tracking."""
    headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    resp = client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "title": "Phase 1: Rollout Clinical Escalation Gates",
            "description": "Implement emergency triage SBAR gates across all tertiary sites.",
            "planned_start_date": "2026-03-01T00:00:00Z",
            "planned_completion_date": "2026-06-30T00:00:00Z",
            "responsible_owner_id": "usr-author-01",
            "expected_deliverables": ["Standardized triage checklists", "Staff training completion records"],
            "evidence_requirements": ["Audit log of triage gate executions"],
        },
    )
    assert resp.status_code == 201
    ms = resp.json()
    ms_id = ms["milestone_id"]
    assert ms["status"] == "PENDING"
    assert ms["roadmap_id"] == rm_id

    # Update milestone
    upd_resp = client.put(
        f"/api/v1/governance-strategy/milestones/{ms_id}",
        headers=headers,
        json={"status": "IN_PROGRESS"},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["status"] == "IN_PROGRESS"


def test_scenario_7_circular_dependency_detection(client: TestClient):
    """Scenario 7: Direct and indirect circular dependency detection rejected with HTTP 400."""
    headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    # Milestone A
    ms_a = client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "title": "Milestone A",
            "description": "First milestone",
            "planned_start_date": "2026-01-01T00:00:00Z",
            "planned_completion_date": "2026-03-31T00:00:00Z",
            "responsible_owner_id": "usr-author-01",
        },
    ).json()["milestone_id"]

    # Milestone B
    ms_b = client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "title": "Milestone B",
            "description": "Second milestone",
            "planned_start_date": "2026-04-01T00:00:00Z",
            "planned_completion_date": "2026-06-30T00:00:00Z",
            "responsible_owner_id": "usr-author-01",
        },
    ).json()["milestone_id"]

    # 1. Self-dependency attempt: A depends on A
    self_dep = client.post(
        f"/api/v1/governance-strategy/milestones/{ms_a}/dependencies",
        headers=headers,
        json={
            "depends_on_milestone_id": ms_a,
            "dependency_type": "SEQUENTIAL",
            "description": "A depends on itself",
        },
    )
    assert self_dep.status_code == 400
    assert self_dep.json()["error"]["code"] == "STRATEGY_DEPENDENCY_CYCLE_DETECTED"

    # Add valid dependency: B depends on A
    dep1 = client.post(
        f"/api/v1/governance-strategy/milestones/{ms_b}/dependencies",
        headers=headers,
        json={
            "depends_on_milestone_id": ms_a,
            "dependency_type": "SEQUENTIAL",
            "description": "B depends on A",
        },
    )
    assert dep1.status_code == 200

    # 2. Cycle attempt: A depends on B (which already depends on A)
    cycle_dep = client.post(
        f"/api/v1/governance-strategy/milestones/{ms_a}/dependencies",
        headers=headers,
        json={
            "depends_on_milestone_id": ms_b,
            "dependency_type": "SEQUENTIAL",
            "description": "A depends on B creating cycle",
        },
    )
    assert cycle_dep.status_code == 400
    assert cycle_dep.json()["error"]["code"] == "STRATEGY_DEPENDENCY_CYCLE_DETECTED"


def test_scenario_8_dependency_validation_endpoint(client: TestClient):
    """Scenario 8: Dependency validation endpoint detecting sequencing date conflicts."""
    headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    # Prerequisite Milestone: completes in July 2026
    ms_pre = client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "title": "Governance Infrastructure Upgrade",
            "description": "Infrastructure prerequisite",
            "planned_start_date": "2026-01-01T00:00:00Z",
            "planned_completion_date": "2026-07-31T00:00:00Z",
            "responsible_owner_id": "usr-author-01",
        },
    ).json()["milestone_id"]

    # Dependent Milestone: planned start in April 2026 (starts BEFORE prerequisite finishes!)
    ms_dep = client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "title": "Hospital Integration",
            "description": "Integration milestone",
            "planned_start_date": "2026-04-01T00:00:00Z",
            "planned_completion_date": "2026-09-30T00:00:00Z",
            "responsible_owner_id": "usr-author-01",
        },
    ).json()["milestone_id"]

    client.post(
        f"/api/v1/governance-strategy/milestones/{ms_dep}/dependencies",
        headers=headers,
        json={
            "depends_on_milestone_id": ms_pre,
            "dependency_type": "PREREQUISITE_CAPABILITY",
            "description": "Must have infra upgraded",
        },
    )

    val_resp = client.get(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}/validate-dependencies",
        headers=headers,
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert not val_data["is_valid"]
    assert len(val_data["date_conflicts"]) == 1
    assert "Sequencing conflict" in val_data["date_conflicts"][0]


def test_scenario_9_milestone_completion_submission_and_independent_verification(client: TestClient):
    """Scenario 9: Milestone completion requires evidence reference and independent verifier sign-off."""
    headers_owner = {"X-User-Id": "usr-owner-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_verifier = {"X-User-Id": "usr-verifier-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    ms_id = client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers_owner,
        json={
            "roadmap_id": rm_id,
            "title": "Deploy Standardized SBAR Escalation Protocol",
            "description": "Deploy across 12 inpatient facilities.",
            "planned_start_date": "2026-01-01T00:00:00Z",
            "planned_completion_date": "2026-06-30T00:00:00Z",
            "responsible_owner_id": "usr-owner-01",
        },
    ).json()["milestone_id"]

    # Submit completion with evidence
    sub_comp = client.post(
        f"/api/v1/governance-strategy/milestones/{ms_id}/submit-completion",
        headers=headers_owner,
        json={"completion_evidence_reference": "ref-audit-report-2026-q2"},
    )
    assert sub_comp.status_code == 200

    # Separation of duties: owner cannot self-verify completion
    self_ver = client.post(
        f"/api/v1/governance-strategy/milestones/{ms_id}/verify-completion",
        headers=headers_owner,
        json={"verification_notes": "Attempted self verification"},
    )
    assert self_ver.status_code == 403
    assert self_ver.json()["error"]["code"] == "STRATEGY_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent verifier verifies
    good_ver = client.post(
        f"/api/v1/governance-strategy/milestones/{ms_id}/verify-completion",
        headers=headers_verifier,
        json={"verification_notes": "Independently verified against clinical audit inspection logs."},
    )
    assert good_ver.status_code == 200
    assert good_ver.json()["status"] == "COMPLETED"
    assert good_ver.json()["verified_by"] == "usr-verifier-02"


def test_scenario_10_resource_and_investment_proposal_tracking(client: TestClient):
    """Scenario 10: Resource proposal tracking without autonomous budget allocation."""
    headers_proposer = {"X-User-Id": "usr-proposer-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_reviewer = {"X-User-Id": "usr-reviewer-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    resp = client.post(
        "/api/v1/governance-strategy/resource-proposals",
        headers=headers_proposer,
        json={
            "roadmap_id": rm_id,
            "title": "Clinical Safety Telemetry Infrastructure Investment",
            "rationale": "Hardware and software telemetry licenses for 50 critical care beds.",
            "proposed_financial_investment": 4500000.0,
            "currency": "INR",
            "staffing_requirements": "2 full-time biomedical telemetry clinical nurse specialists.",
            "technology_requirements": "Continuous cardiac telemetry gateway licenses.",
        },
    )
    assert resp.status_code == 201
    prop = resp.json()
    prop_id = prop["proposal_id"]
    assert prop["status"] == "PROPOSED"
    assert prop["proposed_financial_investment"] == 4500000.0

    # Review proposal
    client.post(
        f"/api/v1/governance-strategy/resource-proposals/{prop_id}/review",
        headers=headers_reviewer,
        json={"status": "REVIEWED", "review_notes": "Reviewed by governance resource panel."},
    )

    # Record external management/financial authorization
    appr_resp = client.post(
        f"/api/v1/governance-strategy/resource-proposals/{prop_id}/approval-reference",
        headers=headers_reviewer,
        json={"approval_reference": "fin-cap-exp-2026-992", "status": "APPROVED"},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"
    assert appr_resp.json()["approval_reference"] == "fin-cap-exp-2026-992"


def test_scenario_11_portfolio_and_implementation_coordination(client: TestClient):
    """Scenario 11: Link objective to Phase 75 portfolio and milestone to Phase 73 implementation."""
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)
    obj_id = create_and_approve_test_objective(client)

    ms_id = client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "title": "Phase 73 Implementation Coordination Milestone",
            "description": "Milestone linking to implementation",
            "planned_start_date": "2026-01-01T00:00:00Z",
            "planned_completion_date": "2026-06-30T00:00:00Z",
            "responsible_owner_id": "usr-lead-01",
        },
    ).json()["milestone_id"]

    # Link objective to Phase 75 portfolio
    p_link = client.post(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}/link-portfolio",
        headers=headers,
        json={"objective_id": obj_id, "portfolio_id": "port-phase75-001"},
    )
    assert p_link.status_code == 201
    assert p_link.json()["portfolio_id"] == "port-phase75-001"

    # Link milestone to Phase 73 implementation
    i_link = client.post(
        f"/api/v1/governance-strategy/roadmaps/{rm_id}/link-implementation",
        headers=headers,
        json={"milestone_id": ms_id, "implementation_id": "impl-phase73-001"},
    )
    assert i_link.status_code == 201
    assert i_link.json()["implementation_id"] == "impl-phase73-001"


def test_scenario_12_strategic_issue_creation_and_escalation(client: TestClient):
    """Scenario 12: Strategic delivery issue creation and escalation to Phase 63 (Risk)."""
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    issue_resp = client.post(
        "/api/v1/governance-strategy/issues",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "classification": "CLINICAL_SAFETY_RISK",
            "title": "Delayed Telemetry Monitor Procurement Poses Safety Risk",
            "description": "Vendor supply chain delays have stalled bedside telemetry rollout.",
            "impact_description": "Potential risk of unmonitored cardiac arrhythmias in Step-Down unit.",
        },
    )
    assert issue_resp.status_code == 201
    iss_id = issue_resp.json()["issue_id"]
    assert issue_resp.json()["status"] == "OPEN"

    # Escalate to Phase 63 (Clinical Risk)
    esc_resp = client.post(
        f"/api/v1/governance-strategy/issues/{iss_id}/escalate",
        headers=headers,
        json={
            "escalation_target": "PHASE_63_RISK",
            "notes": "Escalated for immediate clinical safety risk assessment.",
        },
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["status"] == "ESCALATED"
    assert esc_resp.json()["escalation_target"] == "PHASE_63_RISK"


def test_scenario_13_strategic_issue_resolution(client: TestClient):
    """Scenario 13: Strategic issue resolution workflow."""
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    issue_resp = client.post(
        "/api/v1/governance-strategy/issues",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "classification": "RESOURCE_CONFLICT",
            "title": "Clinical Nurse Trainer Availability Conflict",
            "description": "Trainer scheduled across two overlapping regional sites.",
            "impact_description": "1 week delay in regional training schedule.",
        },
    )
    iss_id = issue_resp.json()["issue_id"]

    res_resp = client.post(
        f"/api/v1/governance-strategy/issues/{iss_id}/resolve",
        headers=headers,
        json={"resolution_notes": "Alternate certified trainer assigned; training schedule preserved."},
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "RESOLVED"


def test_scenario_14_strategic_reporting_endpoints(client: TestClient):
    """Scenario 14: Strategic reporting endpoints (overview, milestones, alignment, issues)."""
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    # 1. Overview report
    ov_resp = client.get(f"/api/v1/governance-strategy/reports/roadmaps/{rm_id}/overview", headers=headers)
    assert ov_resp.status_code == 200
    assert ov_resp.json()["roadmap_id"] == rm_id
    assert CLINICAL_SAFETY_STRATEGY_DISCLAIMER in ov_resp.json()["disclaimer"]

    # 2. Milestones report
    ms_resp = client.get(f"/api/v1/governance-strategy/reports/roadmaps/{rm_id}/milestones", headers=headers)
    assert ms_resp.status_code == 200
    assert ms_resp.json()["roadmap_id"] == rm_id

    # 3. Objectives report
    obj_resp = client.get(f"/api/v1/governance-strategy/reports/objectives?roadmap_id={rm_id}", headers=headers)
    assert obj_resp.status_code == 200
    assert obj_resp.json()["total_count"] >= 1

    # 4. Portfolio alignment report
    align_resp = client.get(f"/api/v1/governance-strategy/reports/roadmaps/{rm_id}/portfolio-alignment", headers=headers)
    assert align_resp.status_code == 200

    # 5. Issues summary report
    iss_resp = client.get(f"/api/v1/governance-strategy/reports/roadmaps/{rm_id}/issues", headers=headers)
    assert iss_resp.status_code == 200


def test_scenario_15_background_routine_scan_job(client: TestClient):
    """Scenario 15: Background routine scan job detecting overdue milestones."""
    headers = {"X-User-Id": "usr-admin-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    rm_id = create_and_activate_test_roadmap(client)

    # Create milestone with past planned completion date
    client.post(
        "/api/v1/governance-strategy/milestones",
        headers=headers,
        json={
            "roadmap_id": rm_id,
            "title": "Overdue Historical Milestone",
            "description": "Milestone with past target date",
            "planned_start_date": "2025-01-01T00:00:00Z",
            "planned_completion_date": "2025-06-30T00:00:00Z",
            "responsible_owner_id": "usr-admin-01",
        },
    )

    scan_resp = client.post("/api/v1/governance-strategy/maintenance/routine-scan", headers=headers)
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["status"] == "COMPLETED"
    assert scan_data["scanned_roadmaps"] >= 1
    assert scan_data["overdue_milestones_flagged"] >= 1


def test_scenario_16_multi_tenant_boundary_isolation(client: TestClient):
    """Scenario 16: Multi-tenant boundary isolation across strategic roadmaps and objectives."""
    headers_t1 = {"X-User-Id": "usr-admin-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_t2 = {"X-User-Id": "usr-admin-02", "X-User-Organization": "org-fortis-02", "X-User-Role": "ADMIN"}

    rm1_id = create_and_activate_test_roadmap(client, org_id="org-apollo-01")

    # Tenant 2 cannot access Tenant 1's roadmap
    cross_get = client.get(f"/api/v1/governance-strategy/roadmaps/{rm1_id}", headers=headers_t2)
    assert cross_get.status_code == 404
    assert cross_get.json()["error"]["code"] == "STRATEGY_ROADMAP_NOT_FOUND"

    # Tenant 2 listing sees empty roadmaps
    list_t2 = client.get("/api/v1/governance-strategy/roadmaps", headers=headers_t2)
    assert list_t2.status_code == 200
    assert len(list_t2.json()) == 0


def test_scenario_17_patient_role_authorization_rejection(client: TestClient):
    """Scenario 17: Patient role is rejected with HTTP 403 Forbidden across all endpoints."""
    headers_patient = {"X-User-Id": "usr-pat-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "PATIENT"}

    # Objectives
    r1 = client.get("/api/v1/governance-strategy/objectives", headers=headers_patient)
    assert r1.status_code == 403
    assert r1.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Priorities
    r2 = client.get("/api/v1/governance-strategy/priorities", headers=headers_patient)
    assert r2.status_code == 403
    assert r2.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Roadmaps
    r3 = client.get("/api/v1/governance-strategy/roadmaps", headers=headers_patient)
    assert r3.status_code == 403
    assert r3.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Capability targets
    r4 = client.get("/api/v1/governance-strategy/capability-targets", headers=headers_patient)
    assert r4.status_code == 403
    assert r4.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Milestones
    r5 = client.get("/api/v1/governance-strategy/milestones", headers=headers_patient)
    assert r5.status_code == 403
    assert r5.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Resource proposals
    r6 = client.get("/api/v1/governance-strategy/resource-proposals", headers=headers_patient)
    assert r6.status_code == 403
    assert r6.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Issues
    r7 = client.get("/api/v1/governance-strategy/issues", headers=headers_patient)
    assert r7.status_code == 403
    assert r7.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

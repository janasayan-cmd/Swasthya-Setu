"""
Phase 88: Clinical Safety Governance Resilience Response Strategy Optimization, Recovery Option Evaluation & Continuity Decision Support Tests.

Comprehensive test suite verifying:
- Scenario 1: Strategy Creation (DRAFT state, disclaimer, categories)
- Scenario 2: Strategy Update & Lifecycle Enforcement (ARCHIVED update prohibited -> 400)
- Scenario 3: Strategy Self-Approval Rejection (Separation of duties -> 403)
- Scenario 4: Independent Strategy Approval (APPROVED state)
- Scenario 5: Candidate Recovery Option Generation from Scenario & Strategy
- Scenario 6: Feasibility Assessment Execution with Verified Evidence (FEASIBLE_VERIFIED)
- Scenario 7: Feasibility Assessment with Missing Fallback Evidence (INSUFFICIENT_EVIDENCE)
- Scenario 8: Recovery Priority Evaluation Across Capability Tiers (TIER_1_ESSENTIAL prioritized)
- Scenario 9: Recovery Sequencing with Milestone Targets & Bottlenecks
- Scenario 10: Recovery Option Comparison & Trade-off Analysis
- Scenario 11: Recovery Resource Planning without Autonomous Allocation
- Scenario 12: Recommendation Package Creation & Review Submission
- Scenario 13: Recommendation Self-Decision Rejection (Separation of duties -> 403)
- Scenario 14: Recommendation Challenge Workflow (CHALLENGED state)
- Scenario 15: Management Decision Handoff to Phase 72 (APPROVED state)
- Scenario 16: Continuity Handoff Creation & Submission to Phase 80
- Scenario 17: Continuity Handoff Acknowledgement by Receiving Workflow
- Scenario 18: Recovery Execution Tracking Progress & Milestones Updates
- Scenario 19: Recovery Execution Deviation Reporting & Restoration Verification
- Scenario 20: Executive Reports (All 6 Reports) & Patient Access Rejection (403)
"""
import os
from datetime import datetime, timezone

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_response_strategy_repository import (
    get_governance_response_strategy_repository,
)
from app.repositories.governance_resource_dependency_repository import (
    get_governance_resource_dependency_repository,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_resource_alternative import (
    AlternativeResourceRecord,
)
from app.schemas.governance_resource_common import (
    FallbackReadinessOutcome,
)


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
    resp_repo = get_governance_response_strategy_repository()
    res_repo = get_governance_resource_dependency_repository()
    resp_repo.clear()
    res_repo.clear()
    yield
    resp_repo.clear()
    res_repo.clear()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Scenario 1: Strategy Creation (DRAFT state, disclaimer, categories)
# =============================================================================

def test_scenario_01_create_response_strategy(client):
    payload = {
        "strategy_name": "Emergency Secondary EHR Hot Standby Switchover",
        "description": "Controlled activation of geographically redundant secondary EHR infrastructure.",
        "category": "OPERATE_VIA_ALTERNATIVE_RESOURCES",
        "applicable_scenario_ids": ["scen-ehr-outage-001"],
        "affected_capability_refs": ["CAP-CLIN-DECISION-01", "CAP-PATIENT-SAFETY-01"],
        "operational_constraints": ["Synchronous replication latency max 15s"],
    }
    resp = client.post("/api/v1/governance-resilience-response-strategies", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["strategy_id"].startswith("strat-")
    assert data["review_status"] == "DRAFT"
    assert data["category"] == "OPERATE_VIA_ALTERNATIVE_RESOURCES"
    assert "Response strategy evaluation" in data["disclaimer"]
    assert data["created_by"] == "usr-lead-01"


# =============================================================================
# Scenario 2: Strategy Update & Lifecycle Enforcement
# =============================================================================

def test_scenario_02_update_response_strategy_and_lifecycle(client):
    payload = {
        "strategy_name": "Temporary Degraded Operating Protocol",
        "description": "Initial draft of degraded operating protocol.",
        "category": "TEMPORARY_REDUCTION_NONESSENTIAL",
        "applicable_scenario_ids": ["scen-wan-cut-002"],
        "affected_capability_refs": ["CAP-TELEHEALTH-01"],
    }
    create_resp = client.post("/api/v1/governance-resilience-response-strategies", json=payload)
    assert create_resp.status_code == 201
    strat_id = create_resp.json()["strategy_id"]

    # Update draft
    update_payload = {
        "strategy_name": "Temporary Degraded Operating Protocol v2",
        "description": "Updated draft with triage inclusion.",
        "category": "TEMPORARY_REDUCTION_NONESSENTIAL",
        "affected_capability_refs": ["CAP-TELEHEALTH-01", "CAP-TRIAGE-02"],
    }
    put_resp = client.put(f"/api/v1/governance-resilience-response-strategies/{strat_id}", json=update_payload)
    assert put_resp.status_code == 200
    assert put_resp.json()["strategy_name"] == "Temporary Degraded Operating Protocol v2"

    # Archive strategy
    arch_resp = client.post(f"/api/v1/governance-resilience-response-strategies/{strat_id}/archive")
    assert arch_resp.status_code == 200
    assert arch_resp.json()["review_status"] == "ARCHIVED"

    # Updating archived strategy must fail
    fail_update = client.put(f"/api/v1/governance-resilience-response-strategies/{strat_id}", json=update_payload)
    assert fail_update.status_code == 400


# =============================================================================
# Scenario 3: Strategy Self-Approval Rejection (Separation of duties -> 403)
# =============================================================================

def test_scenario_03_strategy_self_approval_rejection_sod(client):
    payload = {
        "strategy_name": "Contingency Communication Reroute",
        "description": "Failover to secondary communication channel.",
        "category": "SWITCH_COMMUNICATION_CHANNEL",
        "applicable_scenario_ids": ["scen-dc-flood-003"],
        "affected_capability_refs": ["CAP-CORE-01"],
    }
    create_resp = client.post(
        "/api/v1/governance-resilience-response-strategies",
        json=payload,
        headers={"X-User-Id": "usr-proposer-99"},
    )
    strat_id = create_resp.json()["strategy_id"]

    # Submit strategy
    sub_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/{strat_id}/submit",
        json={"submission_notes": "Ready for governance review"},
        headers={"X-User-Id": "usr-proposer-99"},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["review_status"] == "SUBMITTED"

    # Self-approval attempt by same user
    appr_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/{strat_id}/approve",
        json={"approval_ref": "appr-001", "approval_notes": "Attempting self approval"},
        headers={"X-User-Id": "usr-proposer-99"},
    )
    assert appr_resp.status_code == 403
    assert "Separation of duties violation" in appr_resp.text


# =============================================================================
# Scenario 4: Independent Strategy Approval (APPROVED state)
# =============================================================================

def test_scenario_04_independent_strategy_approval(client):
    payload = {
        "strategy_name": "Provider Redirection Protocol",
        "description": "Redirect automated lab orders to secondary diagnostic partner.",
        "category": "EXTERNAL_SERVICE_ALTERNATIVE",
        "applicable_scenario_ids": ["scen-lab-outage-004"],
        "affected_capability_refs": ["CAP-LAB-ORDERS-01"],
    }
    create_resp = client.post(
        "/api/v1/governance-resilience-response-strategies",
        json=payload,
        headers={"X-User-Id": "usr-proposer-01"},
    )
    strat_id = create_resp.json()["strategy_id"]

    # Submit
    client.post(
        f"/api/v1/governance-resilience-response-strategies/{strat_id}/submit",
        json={"submission_notes": "Submitted"},
        headers={"X-User-Id": "usr-proposer-01"},
    )

    # Approve with independent user
    appr_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/{strat_id}/approve",
        json={"approval_ref": "appr-cso-004", "approval_notes": "Approved by Clinical Safety Officer"},
        headers={"X-User-Id": "usr-safety-officer-88"},
    )
    assert appr_resp.status_code == 200
    data = appr_resp.json()
    assert data["review_status"] == "APPROVED"
    assert data["approved_by"] == "usr-safety-officer-88"
    assert data["approval_ref"] == "appr-cso-004"


# =============================================================================
# Scenario 5: Candidate Recovery Option Generation
# =============================================================================

def test_scenario_05_candidate_recovery_option_generation(client):
    req_payload = {
        "scenario_id": "scen-ehr-outage-001",
        "target_capability_refs": ["CAP-CLIN-DECISION-01"],
    }
    resp = client.post("/api/v1/governance-resilience-response-strategies/recovery-options/generate", json=req_payload)
    assert resp.status_code == 201
    options = resp.json()
    assert len(options) == 2
    assert options[0]["category"] in ["OPERATE_VIA_ALTERNATIVE_RESOURCES", "TEMPORARY_REDUCTION_NONESSENTIAL"]
    assert "Response strategy evaluation" in options[0]["disclaimer"]


# =============================================================================
# Scenario 6: Feasibility Assessment Execution with Verified Evidence
# =============================================================================

def test_scenario_06_feasibility_assessment_verified_evidence(client):
    # Setup Phase 86 fallback readiness record
    res_repo = get_governance_resource_dependency_repository()
    alt_record = AlternativeResourceRecord(
        alternative_id="alt-test-01",
        tenant_id="org-apollo-01",
        primary_resource_id="res-compute-001",
        alternative_resource_id="res-standby-002",
        substitution_conditions="Automatic hot failover within 60 seconds",
        fallback_readiness=FallbackReadinessOutcome.READY_VERIFIED,
        verification_evidence_ref="ev-dr-exercise-phase81-001",
        created_by="usr-infra-lead",
    )
    res_repo.save_alternative(alt_record)

    # Generate option
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={
            "scenario_id": "scen-ehr-outage-001",
            "target_capability_refs": ["CAP-CLIN-DECISION-01"],
        },
    )
    opt_id = gen_resp.json()[0]["option_id"]

    # Evaluate feasibility with evidence
    eval_payload = {
        "notes": "Verified readiness in Phase 86",
    }
    feas_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-options/{opt_id}/feasibility",
        json=eval_payload,
    )
    assert feas_resp.status_code == 201
    feas_data = feas_resp.json()
    assert feas_data["feasibility_outcome"] == "FEASIBLE_VERIFIED"
    assert feas_data["fallback_readiness_verified"] is True
    assert feas_data["resource_availability_verified"] is True


# =============================================================================
# Scenario 7: Feasibility Assessment with Missing Fallback Evidence
# =============================================================================

def test_scenario_07_feasibility_assessment_insufficient_evidence(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={
            "scenario_id": "scen-unverified-007",
            "target_capability_refs": ["CAP-CLIN-DECISION-01"],
        },
    )
    opt_id = gen_resp.json()[0]["option_id"]

    eval_payload = {
        "notes": "No alternative configured",
    }
    feas_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-options/{opt_id}/feasibility",
        json=eval_payload,
    )
    assert feas_resp.status_code == 201
    feas_data = feas_resp.json()
    assert feas_data["feasibility_outcome"] == "INSUFFICIENT_EVIDENCE"
    assert feas_data["resource_availability_verified"] is False


# =============================================================================
# Scenario 8: Recovery Priority Evaluation Across Capability Tiers
# =============================================================================

def test_scenario_08_recovery_priority_evaluation_criticality_tiers(client):
    payload = {
        "scenario_id": "scen-multi-system-outage-008",
        "capability_refs": ["CAP-ADMIN-BILLING-04", "CAP-LIFE-SAFETY-MONITOR-01", "CAP-CLINICAL-MEDS-02"],
    }
    resp = client.post("/api/v1/governance-resilience-response-strategies/recovery-priorities/evaluate", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    priorities = data["prioritized_capabilities"]
    assert len(priorities) == 3
    # Check rank order
    assert priorities[0]["priority_rank"] == 1
    assert priorities[0]["priority_tier"] in ["TIER_1_ESSENTIAL", "TIER_2_CRITICAL"]


# =============================================================================
# Scenario 9: Recovery Sequencing with Milestone Targets & Bottlenecks
# =============================================================================

def test_scenario_09_recovery_sequencing_milestones_bottlenecks(client):
    prio_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-priorities/evaluate",
        json={
            "scenario_id": "scen-power-cut-009",
            "capability_refs": ["CAP-LIFE-SAFETY-01", "CAP-EHR-02"],
        },
    )
    eval_id = prio_resp.json()["priority_evaluation_id"]

    seq_payload = {
        "priority_evaluation_id": eval_id,
        "sequence_name": "Phased Restoration of ICU Systems",
        "milestone_targets": ["T+30m: Generators Synced", "T+90m: DB Warm", "T+120m: Full Resumption"],
    }
    seq_resp = client.post("/api/v1/governance-resilience-response-strategies/recovery-sequences", json=seq_payload)
    assert seq_resp.status_code == 201
    seq_data = seq_resp.json()
    assert len(seq_data["critical_dependency_bottlenecks"]) >= 1
    assert seq_data["estimated_total_duration_hours"] > 0


# =============================================================================
# Scenario 10: Recovery Option Comparison & Trade-off Analysis
# =============================================================================

def test_scenario_10_recovery_option_comparison_and_trade_offs(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={
            "scenario_id": "scen-wan-cut-010",
            "target_capability_refs": ["CAP-PATIENT-CARE-01"],
        },
    )
    opts = gen_resp.json()
    opt_ids = [o["option_id"] for o in opts]

    comp_payload = {
        "comparison_name": "Fallback vs Degraded Operation Trade-Off",
        "candidate_option_ids": opt_ids,
    }
    comp_resp = client.post("/api/v1/governance-resilience-response-strategies/recovery-comparisons", json=comp_payload)
    assert comp_resp.status_code == 201
    comp_data = comp_resp.json()
    assert len(comp_data["compared_options"]) == 2
    assert len(comp_data["trade_offs_identified"]) >= 2
    assert comp_data["top_recommended_option_id"] in opt_ids


# =============================================================================
# Scenario 11: Recovery Resource Planning without Autonomous Allocation
# =============================================================================

def test_scenario_11_recovery_resource_planning_non_autonomous(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={"scenario_id": "scen-db-011"},
    )
    opt_id = gen_resp.json()[0]["option_id"]

    plan_payload = {
        "option_id": opt_id,
        "requirements": [
            {
                "resource_id": "res-blade-server-01",
                "resource_name": "Standby Blade Server",
                "resource_category": "INFRASTRUCTURE",
                "required_capacity_note": "100% capacity",
                "availability_status": "AVAILABLE_VERIFIED",
                "competing_demands": ["dep-concurrent-01"],
                "allocation_constraints": [],
                "responsible_owner_ref": "usr-infra-lead",
            },
        ],
    }
    resp = client.post("/api/v1/governance-resilience-response-strategies/recovery-resource-plans", json=plan_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["competing_demands_count"] == 1
    assert data["planning_status"] == "PROPOSAL"


# =============================================================================
# Scenario 12: Recommendation Package Creation & Review Submission
# =============================================================================

def test_scenario_12_recommendation_creation_and_review_submission(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={"scenario_id": "scen-012"},
    )
    opts = gen_resp.json()

    rec_payload = {
        "recommendation_name": "Activate Secondary EHR Standby Cluster",
        "recommended_option_id": opts[0]["option_id"],
        "alternative_option_ids": [opts[1]["option_id"]],
        "executive_summary": "Maintains patient medication charting without interruption.",
    }
    rec_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-recommendations",
        json=rec_payload,
        headers={"X-User-Id": "usr-rec-preparer-01"},
    )
    assert rec_resp.status_code == 201
    rec_id = rec_resp.json()["recommendation_id"]
    assert rec_resp.json()["lifecycle_status"] == "RECOMMENDATION_PREPARED"

    # Submit for decision
    sub_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/submit-review",
        json={"submission_notes": "Submitted for executive decision"},
        headers={"X-User-Id": "usr-rec-preparer-01"},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["lifecycle_status"] == "SUBMITTED_FOR_DECISION"


# =============================================================================
# Scenario 13: Recommendation Self-Decision Rejection (Separation of duties -> 403)
# =============================================================================

def test_scenario_13_recommendation_self_decision_rejection_sod(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={"scenario_id": "scen-013"},
    )
    opt_id = gen_resp.json()[0]["option_id"]

    rec_payload = {
        "recommendation_name": "Switchover Recommendation",
        "recommended_option_id": opt_id,
        "alternative_option_ids": [],
        "executive_summary": "Zero data loss expected.",
    }
    rec_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-recommendations",
        json=rec_payload,
        headers={"X-User-Id": "usr-preparer-13"},
    )
    rec_id = rec_resp.json()["recommendation_id"]

    # Preparer tries to decide their own recommendation
    dec_payload = {
        "management_review_cycle_ref": "mrc-phase72-001",
        "notes": "I self-approve this",
    }
    dec_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/decision",
        json=dec_payload,
        headers={"X-User-Id": "usr-preparer-13"},
    )
    assert dec_resp.status_code == 403
    assert "Separation of duties violation" in dec_resp.text


# =============================================================================
# Scenario 14: Recommendation Challenge Workflow
# =============================================================================

def test_scenario_14_recommendation_challenge_workflow(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={"scenario_id": "scen-014"},
    )
    opt_id = gen_resp.json()[0]["option_id"]

    rec_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-recommendations",
        json={
            "recommendation_name": "Contested Recommendation",
            "recommended_option_id": opt_id,
            "alternative_option_ids": [],
            "executive_summary": "Adequate safety profile.",
        },
    )
    rec_id = rec_resp.json()["recommendation_id"]

    # Submit challenge
    chal_payload = {
        "challenge_notes": "Standby cluster synchronization has not been verified within last 30 days.",
        "evidence_refs": ["ev-old-sync-01"],
    }
    chal_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/challenge",
        json=chal_payload,
        headers={"X-User-Id": "usr-challenger-44"},
    )
    assert chal_resp.status_code == 200
    data = chal_resp.json()
    assert data["lifecycle_status"] == "CHALLENGED"
    assert data["challenged_by"] == "usr-challenger-44"


# =============================================================================
# Scenario 15: Management Decision Handoff to Phase 72 (APPROVED state)
# =============================================================================

def test_scenario_15_management_decision_approval(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={"scenario_id": "scen-015"},
    )
    opt_id = gen_resp.json()[0]["option_id"]

    rec_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-recommendations",
        json={
            "recommendation_name": "Validated Recommendation",
            "recommended_option_id": opt_id,
            "alternative_option_ids": [],
            "executive_summary": "Full safety verification confirmed.",
        },
        headers={"X-User-Id": "usr-author-15"},
    )
    rec_id = rec_resp.json()["recommendation_id"]

    # Decision by independent management reviewer
    dec_payload = {
        "management_review_cycle_ref": "mrc-phase72-cycle-99",
        "notes": "Approved by clinical safety committee",
    }
    dec_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/decision",
        json=dec_payload,
        headers={"X-User-Id": "usr-clinical-director-01"},
    )
    assert dec_resp.status_code == 200
    data = dec_resp.json()
    assert data["lifecycle_status"] == "APPROVED"
    assert data["management_decision"]["decision_maker_ref"] == "usr-clinical-director-01"


# =============================================================================
# Scenario 16: Continuity Handoff Creation & Submission to Phase 80
# =============================================================================

def test_scenario_16_continuity_handoff_creation(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={"scenario_id": "scen-016"},
    )
    opt_id = gen_resp.json()[0]["option_id"]

    rec_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-recommendations",
        json={
            "recommendation_name": "Approved Recovery Package",
            "recommended_option_id": opt_id,
            "alternative_option_ids": [],
            "executive_summary": "Approved profile.",
        },
        headers={"X-User-Id": "usr-prep-16"},
    )
    rec_id = rec_resp.json()["recommendation_id"]

    client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/decision",
        json={"management_review_cycle_ref": "mrc-phase72-016", "notes": "Approved"},
        headers={"X-User-Id": "usr-board-16"},
    )

    # Create continuity handoff
    hoff_payload = {
        "recommendation_id": rec_id,
        "approved_decision_ref": "dec-016",
        "selected_strategy_id": "strat-016",
    }
    hoff_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/continuity-handoff",
        json=hoff_payload,
    )
    assert hoff_resp.status_code == 201
    data = hoff_resp.json()
    assert data["status"] == "HANDED_OFF"
    assert data["selected_strategy_id"] == "strat-016"


# =============================================================================
# Scenario 17: Continuity Handoff Acknowledgement by Receiving Workflow
# =============================================================================

def test_scenario_17_continuity_handoff_acknowledgement(client):
    gen_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-options/generate",
        json={"scenario_id": "scen-017"},
    )
    opt_id = gen_resp.json()[0]["option_id"]

    rec_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-recommendations",
        json={
            "recommendation_name": "Handoff Test Package",
            "recommended_option_id": opt_id,
            "alternative_option_ids": [],
            "executive_summary": "Approved.",
        },
        headers={"X-User-Id": "usr-prep-17"},
    )
    rec_id = rec_resp.json()["recommendation_id"]

    client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/decision",
        json={"management_review_cycle_ref": "mrc-phase72-017", "notes": "Approved"},
        headers={"X-User-Id": "usr-dec-17"},
    )

    hoff_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-recommendations/{rec_id}/continuity-handoff",
        json={"recommendation_id": rec_id, "approved_decision_ref": "dec-017", "selected_strategy_id": "strat-017"},
    )
    hoff_id = hoff_resp.json()["handoff_id"]

    # Acknowledge handoff
    ack_payload = {
        "receiving_continuity_workflow_ref": "wf-continuity-phase80-001",
        "acknowledgement_notes": "Acknowledged and running",
    }
    ack_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/continuity-handoffs/{hoff_id}/acknowledge",
        json=ack_payload,
        headers={"X-User-Id": "usr-continuity-lead-77"},
    )
    assert ack_resp.status_code == 200
    data = ack_resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["acknowledged_by"] == "usr-continuity-lead-77"
    assert data["receiving_continuity_workflow_ref"] == "wf-continuity-phase80-001"


# =============================================================================
# Scenario 18: Recovery Execution Tracking Progress & Milestones Updates
# =============================================================================

def test_scenario_18_recovery_execution_tracking_milestones(client):
    track_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-execution-trackings?handoff_id=hoff-018&strategy_id=strat-018"
    )
    assert track_resp.status_code == 201
    track_id = track_resp.json()["execution_id"]
    assert track_resp.json()["status"] == "PLANNED"

    # Update progress
    prog_payload = {
        "progress_pct": 50.0,
        "notes": "Initiation complete",
    }
    prog_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-execution-trackings/{track_id}/progress",
        json=prog_payload,
    )
    assert prog_resp.status_code == 200
    data = prog_resp.json()
    assert data["status"] == "IN_PROGRESS"
    assert data["progress_pct"] == 50.0


# =============================================================================
# Scenario 19: Recovery Execution Deviation Reporting & Restoration Verification
# =============================================================================

def test_scenario_19_recovery_execution_deviation_and_restoration_verification(client):
    track_resp = client.post(
        "/api/v1/governance-resilience-response-strategies/recovery-execution-trackings?handoff_id=hoff-019&strategy_id=strat-019"
    )
    track_id = track_resp.json()["execution_id"]

    # Report deviation
    dev_payload = {
        "deviation_description": "Network latency spike observed during standby sync.",
        "root_cause_explanation": "Marginal delay in terminal responsiveness.",
        "compensating_safeguards": "Reroute non-critical logging traffic to secondary pipe",
    }
    dev_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-execution-trackings/{track_id}/deviation",
        json=dev_payload,
    )
    assert dev_resp.status_code == 200
    dev_data = dev_resp.json()
    assert dev_data["status"] == "DEVIATION_REPORTED"
    assert len(dev_data["reported_deviations"]) == 1

    # Restoration verification
    ver_payload = {
        "restoration_evidence_ref": "ev-verification-clin-audit-phase81-099",
        "verification_notes": "Clinical operations validated and fully operational.",
    }
    ver_resp = client.post(
        f"/api/v1/governance-resilience-response-strategies/recovery-execution-trackings/{track_id}/verify-restoration",
        json=ver_payload,
        headers={"X-User-Id": "usr-cso-verifier-99"},
    )
    assert ver_resp.status_code == 200
    ver_data = ver_resp.json()
    assert ver_data["status"] == "VERIFIED_RESTORED"
    assert ver_data["capability_restoration_evidence_ref"] == "ev-verification-clin-audit-phase81-099"
    assert ver_data["progress_pct"] == 100.0


# =============================================================================
# Scenario 20: Executive Reports (All 6) & Patient Access Rejection (403)
# =============================================================================

def test_scenario_20_executive_reports_and_patient_access_rejection(client):
    # 1. Recovery options summary
    r1 = client.get("/api/v1/governance-resilience-response-strategies/reports/recovery-options-summary")
    assert r1.status_code == 200
    assert "total_strategies_registered" in r1.json()

    # 2. Strategy feasibility report
    r2 = client.get("/api/v1/governance-resilience-response-strategies/reports/strategy-feasibility")
    assert r2.status_code == 200
    assert "total_feasibility_assessments" in r2.json()

    # 3. Recovery priorities report
    r3 = client.get("/api/v1/governance-resilience-response-strategies/reports/recovery-priorities")
    assert r3.status_code == 200
    assert "total_prioritized_capabilities" in r3.json()

    # 4. Recovery comparisons report
    r4 = client.get("/api/v1/governance-resilience-response-strategies/reports/recovery-comparisons")
    assert r4.status_code == 200
    assert "total_comparisons_conducted" in r4.json()

    # 5. Recovery execution tracking report
    r5 = client.get("/api/v1/governance-resilience-response-strategies/reports/recovery-execution-tracking")
    assert r5.status_code == 200
    assert "total_active_executions" in r5.json()

    # 6. Strategy deviations report
    r6 = client.get("/api/v1/governance-resilience-response-strategies/reports/strategy-deviations")
    assert r6.status_code == 200
    assert "total_executions_with_deviations" in r6.json()

    # Verify Patient access rejection (403)
    patient_headers = {"X-User-Role": "PATIENT", "X-User-Id": "pat-001"}
    r_pat = client.get(
        "/api/v1/governance-resilience-response-strategies/reports/recovery-options-summary",
        headers=patient_headers,
    )
    assert r_pat.status_code == 403
    assert "Patients are not permitted" in r_pat.text

"""Phase 77: Clinical Safety Governance Strategic Assurance Tests.

Comprehensive test suite verifying:
- Scenario 1: Framework creation, versioning, and activation lifecycle
- Scenario 2: Maturity criteria and dimension configuration
- Scenario 3: Assessment scoping and lifecycle across organizational scopes
- Scenario 4: Evidence intake, positive verification, rejection, and freshness checks
- Scenario 5: Assessment engine criteria evaluation without missing data defaulting
- Scenario 6: Organizational maturity aggregation without double counting or invalid extrapolation
- Scenario 7: Systemic governance gap identification, human review, and confirmation
- Scenario 8: Longitudinal trend analysis preserving methodology/framework version comparability
- Scenario 9: Governance capability improvement plan lifecycle and milestone tracking
- Scenario 10: Strategic improvement action routing to authoritative workflows (Phases 54, 63, 72, 73, 75)
- Scenario 11: Assurance coverage analysis (distinguishing availability from adequacy)
- Scenario 12: Independent assessment review with conflict-of-interest and separation of duties checks
- Scenario 13: Strategic management review packaging and referral to Phase 72 Management Review
- Scenario 14: Reporting APIs and background assurance routine scan
- Scenario 15: Multi-tenant boundary isolation
- Scenario 16: Patient role authorization enforcement (403 Forbidden)
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
from app.repositories.governance_strategic_assurance_repository import (
    get_strategic_assurance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    FrameworkStatus,
    MaturityDimensionEnum,
    MaturityLevelEnum,
    ScopeTypeEnum,
)
from app.schemas.governance_maturity_assessment import AssessmentStatus
from app.schemas.governance_assurance_evidence import (
    EvidenceSourceWorkflow,
    EvidenceVerificationStatus,
)
from app.schemas.governance_systemic_gaps import GapClassification, GapStatus
from app.schemas.governance_improvement_plan import (
    ImprovementMilestoneStatus,
    ImprovementPlanStatus,
)
from app.schemas.governance_assurance_review import AssuranceReviewStatus
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
    repo = get_strategic_assurance_repository()
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

def create_and_activate_test_framework(client: TestClient, org_id: str = "org-apollo-01") -> str:
    headers_author = {"X-User-Id": "usr-author-01", "X-User-Organization": org_id, "X-User-Role": "ADMIN"}
    headers_approver = {"X-User-Id": "usr-approver-02", "X-User-Organization": org_id, "X-User-Role": "ADMIN"}

    fw_resp = client.post(
        "/api/v1/governance-strategic-assurance/frameworks",
        headers=headers_author,
        json={
            "framework_code": "CS-GMF",
            "name": "Clinical Safety Governance Maturity Framework",
            "version": "1.0",
            "description": "Organizational clinical safety governance maturity assessment standard.",
        },
    )
    assert fw_resp.status_code == 201
    fw_id = fw_resp.json()["framework_id"]

    sub_resp = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/submit",
        headers=headers_author,
    )
    assert sub_resp.status_code == 200

    appr_resp = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/approve",
        headers=headers_approver,
        json={"approver_notes": "Governance review approved."},
    )
    assert appr_resp.status_code == 200

    act_resp = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/activate",
        headers=headers_author,
        json={"activation_notes": "Activated for active enterprise monitoring."},
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ACTIVE"
    return fw_id


# =============================================================================
# Test Scenarios
# =============================================================================

def test_scenario_1_framework_creation_versioning_and_activation(client: TestClient):
    """Scenario 1: Framework creation, versioning, separation of duties on approval, and activation."""
    headers_author = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_approver = {"X-User-Id": "usr-approver-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    resp = client.post(
        "/api/v1/governance-strategic-assurance/frameworks",
        headers=headers_author,
        json={
            "framework_code": "CS-GMF",
            "name": "Clinical Safety Governance Maturity Framework",
            "version": "1.0",
            "description": "Standardized maturity framework.",
        },
    )
    assert resp.status_code == 201
    fw_data = resp.json()
    fw_id = fw_data["framework_id"]
    assert fw_data["status"] == "DRAFT"
    assert len(fw_data["dimensions"]) == 8
    assert CLINICAL_SAFETY_DISCLAIMER in fw_data["disclaimer"]

    # Prevent duplicate version
    dup_resp = client.post(
        "/api/v1/governance-strategic-assurance/frameworks",
        headers=headers_author,
        json={
            "framework_code": "CS-GMF",
            "name": "Clinical Safety Governance Maturity Framework",
            "version": "1.0",
            "description": "Duplicate version.",
        },
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "INVALID_ASSURANCE_FRAMEWORK_STATE"

    # Submit framework
    sub_resp = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/submit",
        headers=headers_author,
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # Separation of duties violation: Author cannot approve their own framework
    bad_appr = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/approve",
        headers=headers_author,
        json={"approver_notes": "Self approval attempt"},
    )
    assert bad_appr.status_code == 403
    assert bad_appr.json()["error"]["code"] == "ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent approver succeeds
    good_appr = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/approve",
        headers=headers_approver,
        json={"approver_notes": "Independent approval completed."},
    )
    assert good_appr.status_code == 200
    assert good_appr.json()["status"] == "APPROVED"

    # Activate
    act_resp = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/activate",
        headers=headers_author,
        json={"activation_notes": "Activating v1.0"},
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ACTIVE"


def test_scenario_2_maturity_criteria_and_dimension_configuration(client: TestClient):
    """Scenario 2: Adding custom dimensions and criteria to draft framework."""
    headers = {"X-User-Id": "usr-author-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    resp = client.post(
        "/api/v1/governance-strategic-assurance/frameworks",
        headers=headers,
        json={
            "framework_code": "CUSTOM-GMF",
            "name": "Custom Governance Maturity Framework",
            "version": "1.0",
            "description": "Custom framework with extensible dimensions.",
            "dimensions": [],
        },
    )
    assert resp.status_code == 201
    fw_id = resp.json()["framework_id"]

    # Add custom dimension
    dim_resp = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/dimensions",
        headers=headers,
        json={
            "dimension": "CLINICAL_RISK_MANAGEMENT",
            "title": "Clinical Risk Management",
            "description": "Rigorous risk evaluation and mitigations.",
            "weight": 1.5,
        },
    )
    assert dim_resp.status_code == 200
    assert len(dim_resp.json()["dimensions"]) == 1

    # Add criterion to dimension
    crit_resp = client.post(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw_id}/criteria",
        headers=headers,
        json={
            "criterion_id": "crm_crit_01",
            "dimension": "CLINICAL_RISK_MANAGEMENT",
            "target_level": "LEVEL_1_INITIAL",
            "title": "Initial Risk Registry",
            "description": "Maintain active register of clinical risks.",
            "required_evidence_types": ["PHASE_63_RISK"],
            "verification_requirements": "Positive verification by clinical safety officer.",
            "mandatory": True,
            "threshold_percentage": 100.0,
        },
    )
    assert crit_resp.status_code == 200
    dims = crit_resp.json()["dimensions"]
    assert len(dims[0]["criteria"]) == 1
    assert dims[0]["criteria"][0]["criterion_id"] == "crm_crit_01"


def test_scenario_3_assessment_scoping_and_lifecycle(client: TestClient):
    """Scenario 3: Assessment scoping across organizational boundaries and lifecycle."""
    headers = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw_id,
            "scope": {
                "scope_type": "FACILITY",
                "scope_id": "fac-delhi-01",
                "scope_name": "Apollo Delhi Main Hospital",
                "parent_scope_id": "org-apollo-01",
            },
            "summary_findings": "Baseline Q4 governance maturity appraisal.",
        },
    )
    assert resp.status_code == 201
    asmt = resp.json()
    assert asmt["status"] == "DRAFT"
    assert asmt["overall_maturity_level"] == "NOT_ASSESSED"
    assert asmt["scope"]["scope_id"] == "fac-delhi-01"
    assert CLINICAL_SAFETY_DISCLAIMER in asmt["disclaimer"]


def test_scenario_4_evidence_intake_verification_and_freshness(client: TestClient):
    """Scenario 4: Evidence intake, positive verification, rejection, and freshness detection."""
    headers_assessor = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_verifier = {"X-User-Id": "usr-verifier-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    asmt_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers_assessor,
        json={
            "framework_id": fw_id,
            "scope": {
                "scope_type": "DEPARTMENT",
                "scope_id": "dept-emergency-01",
                "scope_name": "Emergency Department",
                "parent_scope_id": "fac-delhi-01",
            },
        },
    )
    asmt_id = asmt_resp.json()["assessment_id"]

    # Submit evidence item
    ev_resp = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evidence",
        headers=headers_assessor,
        json={
            "dimension": "INCIDENT_LEARNING",
            "criterion_id": "inci_c1",
            "source_workflow": "PHASE_49_INCIDENT",
            "source_record_id": "inc-2026-001",
            "title": "ED Incident Learning Record",
            "description": "Investigated near-miss medication incident with root cause analysis.",
        },
    )
    assert ev_resp.status_code == 201
    ev_id = ev_resp.json()["evidence_id"]
    assert ev_resp.json()["verification_status"] == "PENDING_VERIFICATION"
    assert not ev_resp.json()["is_stale"]

    # Positive verification
    ver_resp = client.post(
        f"/api/v1/governance-strategic-assurance/evidence/{ev_id}/verify",
        headers=headers_verifier,
        json={"verification_notes": "Verified against authoritative incident repository."},
    )
    assert ver_resp.status_code == 200
    assert ver_resp.json()["verification_status"] == "VERIFIED"
    assert ver_resp.json()["verified_by"] == "usr-verifier-02"

    # Submit second evidence item and reject it
    ev2_resp = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evidence",
        headers=headers_assessor,
        json={
            "dimension": "INCIDENT_LEARNING",
            "criterion_id": "inci_c2",
            "source_workflow": "DIRECT_OBSERVATION",
            "source_record_id": "obs-001",
            "title": "Verbal Report",
            "description": "Informal verbal report lacking documentation.",
        },
    )
    ev2_id = ev2_resp.json()["evidence_id"]

    rej_resp = client.post(
        f"/api/v1/governance-strategic-assurance/evidence/{ev2_id}/reject",
        headers=headers_verifier,
        json={"rejection_reason": "Undocumented verbal statement does not meet verification requirements."},
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["verification_status"] == "REJECTED"


def test_scenario_5_assessment_engine_evaluation_no_missing_data_defaulting(client: TestClient):
    """Scenario 5: Criteria evaluation strictly against verified evidence; no missing data defaulting."""
    headers_assessor = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_verifier = {"X-User-Id": "usr-verifier-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    asmt_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers_assessor,
        json={
            "framework_id": fw_id,
            "scope": {
                "scope_type": "FACILITY",
                "scope_id": "fac-delhi-01",
                "scope_name": "Apollo Delhi Main Hospital",
            },
        },
    )
    asmt_id = asmt_resp.json()["assessment_id"]

    # Evaluate dimension with ZERO evidence submitted
    eval_zero = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evaluate-dimension",
        headers=headers_assessor,
        json={"dimension": "CLINICAL_RISK_MANAGEMENT"},
    )
    assert eval_zero.status_code == 200
    res_zero = eval_zero.json()["dimension_results"]["CLINICAL_RISK_MANAGEMENT"]
    # Missing data cannot default to compliant: must be INSUFFICIENT_EVIDENCE
    assert res_zero["achieved_level"] == "INSUFFICIENT_EVIDENCE"
    assert res_zero["confidence_score"] == 0.0
    for crit_res in res_zero["criteria_results"]:
        assert not crit_res["is_met"]
        assert "Missing verified assurance evidence" in crit_res["missing_evidence_reasons"][0]

    # Submit and verify Level 1 evidence for CLINICAL_RISK_MANAGEMENT
    ev_resp = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evidence",
        headers=headers_assessor,
        json={
            "dimension": "CLINICAL_RISK_MANAGEMENT",
            "criterion_id": "clin_c1",
            "source_workflow": "ORGANIZATIONAL_POLICY",
            "source_record_id": "pol-risk-01",
            "title": "Hospital Clinical Risk Policy",
            "description": "Formally published risk management policy.",
        },
    )
    ev_id = ev_resp.json()["evidence_id"]

    client.post(
        f"/api/v1/governance-strategic-assurance/evidence/{ev_id}/verify",
        headers=headers_verifier,
        json={"verification_notes": "Policy verified in institutional policy portal."},
    )

    # Re-evaluate dimension: Level 1 criterion is now met
    eval_l1 = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evaluate-dimension",
        headers=headers_assessor,
        json={"dimension": "CLINICAL_RISK_MANAGEMENT"},
    )
    assert eval_l1.status_code == 200
    res_l1 = eval_l1.json()["dimension_results"]["CLINICAL_RISK_MANAGEMENT"]
    assert res_l1["achieved_level"] == "LEVEL_1_INITIAL"
    assert res_l1["confidence_score"] > 0.0


def test_scenario_6_controlled_organizational_maturity_aggregation(client: TestClient):
    """Scenario 6: Controlled maturity aggregation across child facilities without double counting."""
    headers = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_verifier = {"X-User-Id": "usr-verifier-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    # Child Assessment 1: Delhi Hospital
    asmt1_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw_id,
            "scope": {"scope_type": "FACILITY", "scope_id": "fac-delhi-01", "scope_name": "Apollo Delhi"},
        },
    )
    asmt1_id = asmt1_resp.json()["assessment_id"]

    # Child Assessment 2: Mumbai Hospital
    asmt2_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw_id,
            "scope": {"scope_type": "FACILITY", "scope_id": "fac-mumbai-01", "scope_name": "Apollo Mumbai"},
        },
    )
    asmt2_id = asmt2_resp.json()["assessment_id"]

    # Add Level 1 verified evidence to Delhi
    ev1 = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt1_id}/evidence",
        headers=headers,
        json={
            "dimension": "LEADERSHIP_ACCOUNTABILITY",
            "criterion_id": "lead_c1",
            "source_workflow": "ORGANIZATIONAL_POLICY",
            "source_record_id": "charter-01",
            "title": "Governance Charter",
            "description": "Executive committee charter.",
        },
    ).json()["evidence_id"]
    client.post(f"/api/v1/governance-strategic-assurance/evidence/{ev1}/verify", headers=headers_verifier, json={})
    client.post(f"/api/v1/governance-strategic-assurance/assessments/{asmt1_id}/evaluate-dimension", headers=headers, json={"dimension": "LEADERSHIP_ACCOUNTABILITY"})

    # Evaluate Mumbai with zero evidence (insufficient)
    client.post(f"/api/v1/governance-strategic-assurance/assessments/{asmt2_id}/evaluate-dimension", headers=headers, json={"dimension": "LEADERSHIP_ACCOUNTABILITY"})

    # Aggregate across Delhi and Mumbai under Parent Organization
    agg_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments/aggregate",
        headers=headers,
        json={
            "framework_id": fw_id,
            "parent_scope": {
                "scope_type": "ORGANIZATION",
                "scope_id": "org-apollo-01",
                "scope_name": "Apollo Health Enterprise",
            },
            "child_assessment_ids": [asmt1_id, asmt2_id],
        },
    )
    assert agg_resp.status_code == 200
    agg_data = agg_resp.json()
    assert agg_data["child_assessments_counted"] == 2
    # Conservative weakest-link: since Mumbai has INSUFFICIENT_EVIDENCE, aggregated is INSUFFICIENT_EVIDENCE
    assert agg_data["dimension_levels"]["LEADERSHIP_ACCOUNTABILITY"] == "INSUFFICIENT_EVIDENCE"
    assert agg_data["aggregated_level"] == "INSUFFICIENT_EVIDENCE"


def test_scenario_7_systemic_governance_gap_identification_and_confirmation(client: TestClient):
    """Scenario 7: Identifying a potential systemic gap and human confirmation."""
    headers_lead = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_reviewer = {"X-User-Id": "usr-reviewer-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    resp = client.post(
        "/api/v1/governance-strategic-assurance/systemic-gaps",
        headers=headers_lead,
        json={
            "title": "Inconsistent Clinical Risk Escalation Across Regional Sites",
            "description": "Multiple regional sites lack verified clinical risk escalation gates.",
            "classification": "COVERAGE_DEFICIT",
            "impacted_dimensions": ["CLINICAL_RISK_MANAGEMENT", "DECISION_ASSURANCE"],
        },
    )
    assert resp.status_code == 201
    gap_id = resp.json()["gap_id"]
    assert resp.json()["status"] == "POTENTIAL_GAP"

    # Human confirmation
    conf_resp = client.post(
        f"/api/v1/governance-strategic-assurance/systemic-gaps/{gap_id}/confirm",
        headers=headers_reviewer,
        json={"confirmation_notes": "Confirmed across Delhi and Mumbai regional site audits."},
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "CONFIRMED_GAP"
    assert conf_resp.json()["confirmed_by"] == "usr-reviewer-02"


def test_scenario_8_longitudinal_trend_preserves_version_comparability(client: TestClient):
    """Scenario 8: Longitudinal trend tracking with version transition caveat detection."""
    headers = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_approver = {"X-User-Id": "usr-approver-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    # Framework v1.0
    fw1_id = create_and_activate_test_framework(client)

    # Assessment 1 under v1.0 (while v1.0 is active)
    asmt1_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw1_id,
            "scope": {"scope_type": "FACILITY", "scope_id": "fac-delhi-01", "scope_name": "Apollo Delhi"},
            "assessment_date": "2026-01-15T00:00:00Z",
        },
    )
    assert asmt1_resp.status_code == 201

    # Framework v2.0
    fw2_resp = client.post(
        "/api/v1/governance-strategic-assurance/frameworks",
        headers=headers,
        json={
            "framework_code": "CS-GMF",
            "name": "Clinical Safety Governance Maturity Framework",
            "version": "2.0",
            "description": "Next generation framework standard.",
        },
    )
    fw2_id = fw2_resp.json()["framework_id"]
    client.post(f"/api/v1/governance-strategic-assurance/frameworks/{fw2_id}/submit", headers=headers)
    client.post(f"/api/v1/governance-strategic-assurance/frameworks/{fw2_id}/approve", headers=headers_approver, json={})
    client.post(f"/api/v1/governance-strategic-assurance/frameworks/{fw2_id}/activate", headers=headers, json={})

    # Assessment 2 under v2.0
    asmt2_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw2_id,
            "scope": {"scope_type": "FACILITY", "scope_id": "fac-delhi-01", "scope_name": "Apollo Delhi"},
            "assessment_date": "2026-06-15T00:00:00Z",
        },
    )
    assert asmt2_resp.status_code == 201

    trend_resp = client.get(
        "/api/v1/governance-strategic-assurance/reports/longitudinal-trend/fac-delhi-01",
        headers=headers,
    )
    assert trend_resp.status_code == 200
    trend_data = trend_resp.json()
    assert len(trend_data["data_points"]) == 2
    assert trend_data["version_transition_detected"]
    assert trend_data["data_points"][1]["comparability_caveat"] is not None
    assert "methodology transitioned" in trend_data["data_points"][1]["comparability_caveat"]


def test_scenario_9_governance_improvement_plan_and_milestones(client: TestClient):
    """Scenario 9: Governance capability improvement plan lifecycle and milestone tracking."""
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    plan_resp = client.post(
        "/api/v1/governance-strategic-assurance/improvement-plans",
        headers=headers,
        json={
            "title": "Hospital-Wide Incident Response Standardization",
            "description": "Standardize incident learning to achieve Managed maturity level.",
            "target_dimensions": ["INCIDENT_LEARNING"],
            "baseline_level": "LEVEL_2_DEVELOPING",
            "target_level": "LEVEL_4_MANAGED",
            "accountable_owner_id": "usr-lead-01",
            "target_completion_date": "2026-12-31T00:00:00Z",
            "milestones": [
                {
                    "milestone_id": "ms-01",
                    "title": "Deploy Phase 49 investigation workflows across all wards",
                    "target_date": "2026-09-30T00:00:00Z",
                    "status": "PENDING",
                }
            ],
        },
    )
    assert plan_resp.status_code == 201
    plan_data = plan_resp.json()
    plan_id = plan_data["plan_id"]
    assert plan_data["status"] == "ACTIVE"

    # Update milestone progress
    ms_resp = client.post(
        f"/api/v1/governance-strategic-assurance/improvement-plans/{plan_id}/milestones/ms-01",
        headers=headers,
        json={
            "status": "ACHIEVED",
            "completion_evidence": "All 14 ward clinical nurse supervisors certified on Phase 49 workflows.",
            "notes": "Verified by clinical governance committee.",
        },
    )
    assert ms_resp.status_code == 200
    updated_ms = ms_resp.json()["milestones"][0]
    assert updated_ms["status"] == "ACHIEVED"


def test_scenario_10_strategic_improvement_action_routing(client: TestClient):
    """Scenario 10: Routing strategic improvement actions to authoritative downstream workflows."""
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}

    plan_resp = client.post(
        "/api/v1/governance-strategic-assurance/improvement-plans",
        headers=headers,
        json={
            "title": "Enterprise Governance Risk Harmonization",
            "description": "Harmonize clinical safety risk evaluation with Phase 63.",
            "target_dimensions": ["CLINICAL_RISK_MANAGEMENT"],
            "baseline_level": "LEVEL_2_DEVELOPING",
            "target_level": "LEVEL_3_DEFINED",
            "accountable_owner_id": "usr-lead-01",
            "target_completion_date": "2026-10-31T00:00:00Z",
        },
    )
    plan_id = plan_resp.json()["plan_id"]

    # Route action to Phase 63 (Risk)
    route_resp = client.post(
        f"/api/v1/governance-strategic-assurance/improvement-plans/{plan_id}/route-action",
        headers=headers,
        json={
            "target_workflow": "PHASE_63_RISK",
            "action_title": "Register Enterprise Governance Clinical Risk",
            "action_description": "Initiate comprehensive risk assessment in Phase 63 for emergency department telemetry.",
            "assigned_lead_id": "usr-risk-lead-01",
            "target_date": "2026-08-31T00:00:00Z",
        },
    )
    assert route_resp.status_code == 200
    handoffs = route_resp.json()["external_handoffs"]
    assert len(handoffs) == 1
    assert handoffs[0]["target_workflow"] == "PHASE_63_RISK"
    assert handoffs[0]["action_title"] == "Register Enterprise Governance Clinical Risk"


def test_scenario_11_assurance_coverage_availability_vs_adequacy(client: TestClient):
    """Scenario 11: Assurance coverage evaluation distinguishing availability from adequacy."""
    headers = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_verifier = {"X-User-Id": "usr-verifier-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    asmt_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw_id,
            "scope": {"scope_type": "FACILITY", "scope_id": "fac-delhi-01", "scope_name": "Apollo Delhi"},
        },
    )
    asmt_id = asmt_resp.json()["assessment_id"]

    # Submit 2 evidence items (availability = 2)
    ev1 = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evidence",
        headers=headers,
        json={
            "dimension": "INCIDENT_LEARNING",
            "criterion_id": "inci_c1",
            "source_workflow": "PHASE_49_INCIDENT",
            "source_record_id": "inc-01",
            "title": "Incident 01",
            "description": "Investigated incident.",
        },
    ).json()["evidence_id"]

    client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evidence",
        headers=headers,
        json={
            "dimension": "INCIDENT_LEARNING",
            "criterion_id": "inci_c2",
            "source_workflow": "PHASE_49_INCIDENT",
            "source_record_id": "inc-02",
            "title": "Incident 02",
            "description": "Pending incident.",
        },
    )

    # Verify only ev1 (adequacy = 1)
    client.post(f"/api/v1/governance-strategic-assurance/evidence/{ev1}/verify", headers=headers_verifier, json={})

    cov_resp = client.get(
        "/api/v1/governance-strategic-assurance/reports/coverage",
        headers=headers,
    )
    assert cov_resp.status_code == 200
    cov_data = cov_resp.json()
    assert cov_data["evidence_availability_count"] == 2
    assert cov_data["evidence_adequacy_count"] == 1
    assert cov_data["scopes_assessed"] == 1


def test_scenario_12_independent_review_and_separation_of_duties(client: TestClient):
    """Scenario 12: Independent assessment review with conflict of interest and separation of duties enforcement."""
    headers_assessor = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_reviewer = {"X-User-Id": "usr-reviewer-02", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_other = {"X-User-Id": "usr-other-03", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    asmt_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers_assessor,
        json={
            "framework_id": fw_id,
            "scope": {"scope_type": "FACILITY", "scope_id": "fac-delhi-01", "scope_name": "Apollo Delhi"},
        },
    )
    asmt_id = asmt_resp.json()["assessment_id"]

    # 1. Separation of duties violation: Assessor cannot review own assessment
    self_rev = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/assign-reviewer",
        headers=headers_assessor,
        json={"reviewer_id": "usr-assessor-01", "conflict_of_interest_cleared": True},
    )
    assert self_rev.status_code == 403
    assert self_rev.json()["error"]["code"] == "ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"

    # 2. Conflict of interest not cleared
    bad_coi = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/assign-reviewer",
        headers=headers_assessor,
        json={"reviewer_id": "usr-reviewer-02", "conflict_of_interest_cleared": False},
    )
    assert bad_coi.status_code == 403
    assert bad_coi.json()["error"]["code"] == "ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"

    # 3. Valid assignment
    assign_resp = client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/assign-reviewer",
        headers=headers_assessor,
        json={"reviewer_id": "usr-reviewer-02", "conflict_of_interest_cleared": True},
    )
    assert assign_resp.status_code == 201
    rev_id = assign_resp.json()["review_id"]

    # 4. Unauthorized reviewer decision submission
    unauth_dec = client.post(
        f"/api/v1/governance-strategic-assurance/reviews/{rev_id}/decision",
        headers=headers_other,
        json={"decision": "ACCEPTED", "review_notes": "Attempted by wrong user"},
    )
    assert unauth_dec.status_code == 403
    assert unauth_dec.json()["error"]["code"] == "ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"

    # 5. Assigned reviewer submits decision
    auth_dec = client.post(
        f"/api/v1/governance-strategic-assurance/reviews/{rev_id}/decision",
        headers=headers_reviewer,
        json={"decision": "ACCEPTED", "review_notes": "Assessment reviewed and validated against audit evidence."},
    )
    assert auth_dec.status_code == 200
    assert auth_dec.json()["status"] == "ACCEPTED"

    # Verify assessment status transitioned to APPROVED
    asmt_check = client.get(f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}", headers=headers_assessor)
    assert asmt_check.json()["status"] == "APPROVED"


def test_scenario_13_strategic_management_review_packaging_and_phase72_referral(client: TestClient):
    """Scenario 13: Assembling review dossier and referring to Phase 72 Management Review."""
    headers = {"X-User-Id": "usr-lead-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    asmt_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw_id,
            "scope": {"scope_type": "ORGANIZATION", "scope_id": "org-apollo-01", "scope_name": "Apollo Enterprise"},
        },
    )
    asmt_id = asmt_resp.json()["assessment_id"]

    # Prepare package
    pkg_resp = client.post(
        "/api/v1/governance-strategic-assurance/review-packages",
        headers=headers,
        json={
            "title": "Annual Executive Clinical Safety Governance Assurance Dossier",
            "reporting_period": "FY2026",
            "executive_summary": "Comprehensive appraisal of enterprise governance maturity and systemic capability gaps.",
            "included_assessment_ids": [asmt_id],
        },
    )
    assert pkg_resp.status_code == 201
    pkg_id = pkg_resp.json()["package_id"]
    assert CLINICAL_SAFETY_DISCLAIMER in pkg_resp.json()["disclaimer"]

    # Refer to Phase 72
    ref_resp = client.post(
        f"/api/v1/governance-strategic-assurance/review-packages/{pkg_id}/refer-phase-72",
        headers=headers,
        json={
            "agenda_item_title": "Strategic Governance Assurance & Capability Review",
            "phase_72_meeting_id": "p72-mtg-2026-q4",
            "referral_notes": "Executive committee formal review and budget commitment agenda item.",
        },
    )
    assert ref_resp.status_code == 200
    assert ref_resp.json()["phase_72_referral_id"] == "p72-mtg-2026-q4"


def test_scenario_14_reporting_apis_and_background_scan(client: TestClient):
    """Scenario 14: Maturity radar report and background routine scan job."""
    headers = {"X-User-Id": "usr-assessor-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    fw_id = create_and_activate_test_framework(client)

    asmt_resp = client.post(
        "/api/v1/governance-strategic-assurance/assessments",
        headers=headers,
        json={
            "framework_id": fw_id,
            "scope": {"scope_type": "FACILITY", "scope_id": "fac-delhi-01", "scope_name": "Apollo Delhi"},
        },
    )
    asmt_id = asmt_resp.json()["assessment_id"]

    # Evaluate dimension to generate report data
    client.post(
        f"/api/v1/governance-strategic-assurance/assessments/{asmt_id}/evaluate-dimension",
        headers=headers,
        json={"dimension": "INCIDENT_LEARNING"},
    )

    # Fetch maturity report
    report_resp = client.get(
        f"/api/v1/governance-strategic-assurance/reports/maturity/{asmt_id}",
        headers=headers,
    )
    assert report_resp.status_code == 200
    rep_data = report_resp.json()
    assert rep_data["scope_name"] == "Apollo Delhi"
    assert len(rep_data["dimension_scores"]) == 1
    assert rep_data["dimension_scores"][0]["dimension"] == "INCIDENT_LEARNING"
    assert CLINICAL_SAFETY_DISCLAIMER in rep_data["disclaimer"]

    # Run routine background maintenance scan
    scan_resp = client.post(
        "/api/v1/governance-strategic-assurance/maintenance/routine-scan",
        headers=headers,
    )
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["status"] == "COMPLETED"
    assert scan_data["scanned_assessments"] >= 1


def test_scenario_15_multi_tenant_boundary_isolation(client: TestClient):
    """Scenario 15: Cross-tenant data isolation enforcement."""
    headers_t1 = {"X-User-Id": "usr-admin-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "ADMIN"}
    headers_t2 = {"X-User-Id": "usr-admin-02", "X-User-Organization": "org-fortis-02", "X-User-Role": "ADMIN"}

    # Create framework in Tenant 1
    fw1_id = create_and_activate_test_framework(client, org_id="org-apollo-01")

    # Tenant 2 cannot access Tenant 1's framework
    cross_get = client.get(
        f"/api/v1/governance-strategic-assurance/frameworks/{fw1_id}",
        headers=headers_t2,
    )
    assert cross_get.status_code == 404
    assert cross_get.json()["error"]["code"] == "ASSURANCE_FRAMEWORK_NOT_FOUND"

    # Tenant 2 listing sees empty frameworks
    list_t2 = client.get(
        "/api/v1/governance-strategic-assurance/frameworks",
        headers=headers_t2,
    )
    assert list_t2.status_code == 200
    assert len(list_t2.json()) == 0


def test_scenario_16_patient_role_authorization_rejection(client: TestClient):
    """Scenario 16: Patient role is rejected with HTTP 403 Forbidden across endpoints."""
    headers_patient = {"X-User-Id": "usr-pat-01", "X-User-Organization": "org-apollo-01", "X-User-Role": "PATIENT"}

    # Frameworks
    resp1 = client.get("/api/v1/governance-strategic-assurance/frameworks", headers=headers_patient)
    assert resp1.status_code == 403
    assert resp1.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Assessments
    resp2 = client.get("/api/v1/governance-strategic-assurance/assessments", headers=headers_patient)
    assert resp2.status_code == 403
    assert resp2.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Gaps
    resp3 = client.get("/api/v1/governance-strategic-assurance/systemic-gaps", headers=headers_patient)
    assert resp3.status_code == 403
    assert resp3.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Plans
    resp4 = client.get("/api/v1/governance-strategic-assurance/improvement-plans", headers=headers_patient)
    assert resp4.status_code == 403
    assert resp4.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Review packages
    resp5 = client.get("/api/v1/governance-strategic-assurance/review-packages", headers=headers_patient)
    assert resp5.status_code == 403
    assert resp5.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

"""Phase 81: Clinical Safety Governance Continuity Assurance Tests.

Comprehensive test suite verifying:
- Scenario 1: Continuity Assurance Framework lifecycle (Draft -> Submit -> Approve)
- Scenario 2: Framework approval separation of duties (creator cannot approve -> 400)
- Scenario 3: Plan validation request creation, 16 criteria completeness check, and outcome
- Scenario 4: Plan validation separation of duties (evaluator cannot review own validation -> 400)
- Scenario 5: Plan validation review completion
- Scenario 6: Capability coverage assurance scan across Phase 80 capability inventory
- Scenario 7: Exercise assurance evaluation creation across criteria outcomes
- Scenario 8: Exercise assurance separation of duties (exercise coordinator cannot evaluate -> 400)
- Scenario 9: Advisory scenario assessment creation and evaluation across disruption scenarios
- Scenario 10: Scenario evaluation separation of duties (author cannot evaluate -> 400)
- Scenario 11: Personnel readiness assessment for critical governance role
- Scenario 12: Delegated authority verification against system (VERIFIED_READY)
- Scenario 13: Delegated authority verification separation of duties (owner cannot verify self -> 400)
- Scenario 14: Dependency resilience assessment and Single Point of Failure (SPOF) detection
- Scenario 15: Dependency resilience assessment with stale evidence (> 365 days)
- Scenario 16: Recovery performance evaluation vs RTO/MTPD and stage distinction
- Scenario 17: Reconciliation assurance evaluation with conflict detection
- Scenario 18: Independent validation programme, conflict-of-interest detection, and approval
- Scenario 19: Continuity finding lifecycle, referral to Phase 54 CAPA, and closure with Phase 55
- Scenario 20: Strategic resilience reporting, routine scan, and patient role rejection (HTTP 403)
"""

from datetime import datetime, timezone, timedelta
import os

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi import Request
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.repositories.governance_continuity_assurance_repository import (
    get_governance_continuity_assurance_repository,
)
from app.repositories.governance_continuity_repository import (
    get_governance_continuity_repository,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

# Schemas for seeding Phase 80 records
from app.schemas.governance_continuity_capability import (
    CapabilityCriticalityTier,
    CapabilityInventoryStatus,
    ClinicalSafetyGovernanceCapabilityRecord,
)
from app.schemas.governance_continuity_plan import (
    ContinuityPlanStatus,
    GovernanceContinuityPlanRecord,
)
from app.schemas.governance_continuity_exercises import (
    ContinuityExerciseRecord,
    ContinuityExerciseStatus,
    ContinuityExerciseType,
)
from app.schemas.governance_continuity_recovery import (
    GovernanceRecoveryRecord,
    RecoveryStatus,
)


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
    repo81 = get_governance_continuity_assurance_repository()
    repo80 = get_governance_continuity_repository()
    repo81.clear()
    repo80.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    repo81.clear()
    repo80.clear()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =========================================================================
# Scenario 1 & 2: Framework Lifecycle & Separation of Duties
# =========================================================================

def test_scenario_01_framework_lifecycle(client):
    """Creates, updates, submits, and approves a continuity assurance framework."""
    payload = {
        "framework_name": "Clinical Governance Continuity Assurance Framework 2026",
        "description": "Standardized multi-dimension resilience validation framework.",
        "organizational_scope": "GLOBAL",
        "scoring_method": "QUALITATIVE_TIERED",
    }
    # 1. Create
    resp = client.post(
        "/api/v1/governance-continuity-assurance/frameworks",
        json=payload,
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    framework_id = data["framework_id"]
    assert data["status"] == "DRAFT"
    assert len(data["dimensions"]) == 15  # All 15 core dimensions seeded

    # 2. Update
    resp = client.patch(
        f"/api/v1/governance-continuity-assurance/frameworks/{framework_id}",
        json={"description": "Updated multi-dimension resilience validation framework."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 200
    assert "Updated" in resp.json()["description"]

    # 3. Submit
    resp = client.post(
        f"/api/v1/governance-continuity-assurance/frameworks/{framework_id}/submit",
        json={"submission_notes": "Ready for governance committee review."},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUBMITTED"

    # 4. Approve by independent director
    resp = client.post(
        f"/api/v1/governance-continuity-assurance/frameworks/{framework_id}/approve",
        json={"approval_notes": "Approved for enterprise clinical resilience validation."},
        headers={"X-User-Id": "usr-director-01", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"


def test_scenario_02_framework_approval_separation_of_duties(client):
    """Ensures creator/submitter cannot approve their own framework."""
    payload = {
        "framework_name": "Self Review Framework",
        "description": "Testing separation of duties.",
        "organizational_scope": "GLOBAL",
    }
    create_resp = client.post(
        "/api/v1/governance-continuity-assurance/frameworks",
        json=payload,
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "SAFETY_LEAD"},
    )
    framework_id = create_resp.json()["framework_id"]

    client.post(
        f"/api/v1/governance-continuity-assurance/frameworks/{framework_id}/submit",
        json={},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "SAFETY_LEAD"},
    )

    # Creator attempts self-approval
    resp = client.post(
        f"/api/v1/governance-continuity-assurance/frameworks/{framework_id}/approve",
        json={"approval_notes": "Self approval attempt"},
        headers={"X-User-Id": "usr-author-01", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"


# =========================================================================
# Scenario 3, 4, 5: Plan Validation & Separation of Duties
# =========================================================================

def test_scenario_03_plan_validation_creation(client):
    """Validates an approved Phase 80 continuity plan against 16 completeness criteria."""
    repo80 = get_governance_continuity_repository()
    now_str = datetime.now(timezone.utc).isoformat()
    plan_rec = GovernanceContinuityPlanRecord(
        plan_id="CP-2026-001",
        tenant_id="org-apollo-01",
        title="Emergency Escalation Continuity Plan",
        organizational_scope={},
        covered_capability_ids=["CAP-ESC-01"],
        plan_owner_id="usr-owner-01",
        authorized_approver_id="usr-approver-01",
        activation_conditions="System outage > 15m or primary auth failure",
        disruption_categories=["TECHNOLOGY_OUTAGE"],
        escalation_procedures="Notify Lead then Convene Committee",
        communication_arrangements="Manual paper log and voice phone bridge",
        alternative_operating_procedures="Fallback to paper triage register",
        delegation_arrangements="Deputy triage lead acts in absence",
        required_resources="Paper triage templates and dedicated mobile phones",
        recovery_priorities="P1 Triage Restoration within 30m",
        restoration_criteria="Primary database connectivity and API health check 200",
        verification_requirements="Independent clinical lead verification signature",
        testing_schedule="Quarterly simulation drill",
        review_schedule="Annual governance review",
        status=ContinuityPlanStatus.APPROVED,
        version=1,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_plan(plan_rec)

    # Create validation request by independent evaluator
    val_payload = {
        "plan_id": "CP-2026-001",
        "plan_version": 1,
        "framework_version": 1,
        "review_scope": "FULL_PLAN_COMPLETENESS",
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/plan-validations",
        json=val_payload,
        headers={"X-User-Id": "usr-evaluator-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["plan_id"] == "CP-2026-001"
    assert data["validation_outcome"] in ("VALIDATED", "VALIDATED_WITH_OBSERVATIONS")
    assert len(data["evaluated_criteria"]) == 16


def test_scenario_04_plan_validation_separation_of_duties(client):
    """Ensures plan owner cannot validate their own plan."""
    repo80 = get_governance_continuity_repository()
    now_str = datetime.now(timezone.utc).isoformat()
    plan_rec = GovernanceContinuityPlanRecord(
        plan_id="CP-2026-002",
        tenant_id="org-apollo-01",
        title="Triage Continuity Plan",
        organizational_scope={},
        covered_capability_ids=["CAP-TRI-01"],
        plan_owner_id="usr-creator-01",
        activation_conditions="Service down > 10m",
        disruption_categories=["TECHNOLOGY_OUTAGE"],
        escalation_procedures="Notify Lead",
        communication_arrangements="Phone bridge",
        alternative_operating_procedures="Paper register",
        delegation_arrangements="Deputy triage lead",
        required_resources="Paper",
        recovery_priorities="Immediate",
        restoration_criteria="HTTP 200",
        verification_requirements="Audit signoff",
        testing_schedule="Quarterly",
        review_schedule="Annual",
        status=ContinuityPlanStatus.APPROVED,
        version=1,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_plan(plan_rec)

    val_payload = {
        "plan_id": "CP-2026-002",
        "plan_version": 1,
        "framework_version": 1,
        "review_scope": "FULL_PLAN_COMPLETENESS",
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/plan-validations",
        json=val_payload,
        headers={"X-User-Id": "usr-creator-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"


def test_scenario_05_plan_validation_review(client):
    """Reviews and finalizes a plan validation with remediation observations."""
    repo80 = get_governance_continuity_repository()
    now_str = datetime.now(timezone.utc).isoformat()
    plan_rec = GovernanceContinuityPlanRecord(
        plan_id="CP-2026-003",
        tenant_id="org-apollo-01",
        title="Audit Continuity Plan",
        organizational_scope={},
        covered_capability_ids=["CAP-AUD-01"],
        plan_owner_id="usr-creator-02",
        activation_conditions="Audit system down",
        disruption_categories=["TECHNOLOGY_OUTAGE"],
        escalation_procedures="Notify Lead",
        communication_arrangements="Phone bridge",
        alternative_operating_procedures="Paper register",
        delegation_arrangements="Deputy lead",
        required_resources="Paper",
        recovery_priorities="Immediate",
        restoration_criteria="HTTP 200",
        verification_requirements="Audit signoff",
        testing_schedule="Quarterly",
        review_schedule="Annual",
        status=ContinuityPlanStatus.APPROVED,
        version=1,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_plan(plan_rec)

    create_resp = client.post(
        "/api/v1/governance-continuity-assurance/plan-validations",
        json={"plan_id": "CP-2026-003"},
        headers={"X-User-Id": "usr-evaluator-01", "X-User-Role": "SAFETY_LEAD"},
    )
    validation_id = create_resp.json()["validation_id"]

    # Review by independent reviewer
    review_payload = {
        "validation_outcome": "VALIDATED_WITH_OBSERVATIONS",
        "observations": ["Manual workaround requires updated phone directory."],
        "remediation_recommendations": ["Update phone contact tree quarterly."],
    }
    resp = client.post(
        f"/api/v1/governance-continuity-assurance/plan-validations/{validation_id}/review",
        json=review_payload,
        headers={"X-User-Id": "usr-reviewer-01", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "COMPLETED"
    assert resp.json()["validation_outcome"] == "VALIDATED_WITH_OBSERVATIONS"


# =========================================================================
# Scenario 6: Capability Coverage Assurance Scan
# =========================================================================

def test_scenario_06_coverage_assurance_scan(client):
    """Scans capability inventory to identify covered and uncovered capabilities."""
    repo80 = get_governance_continuity_repository()
    now_str = datetime.now(timezone.utc).isoformat()
    cap1 = ClinicalSafetyGovernanceCapabilityRecord(
        capability_id="CAP-001",
        tenant_id="org-apollo-01",
        name="Critical Safety Triage",
        description="Immediate risk triage",
        organizational_scope={},
        responsible_department="Emergency Medicine",
        accountable_owner_id="usr-owner-01",
        supporting_roles=["Triage Nurse", "Safety Officer"],
        related_workflow="Phase 8 Clinical Triage",
        criticality=CapabilityCriticalityTier.TIER_1_CRITICAL,
        continuity_requirement_id=None,
        required_supporting_systems=["EHR", "LIS"],
        required_integrations=["SMS Gateway"],
        required_information_sources=["Patient Identity Database"],
        minimum_operational_requirements="Manual paper fallback triage register",
        max_acceptable_interruption_hours=1.0,
        recovery_priority=1,
        status=CapabilityInventoryStatus.APPROVED,
        approved_by="usr-director-01",
        review_date=now_str,
        created_at=now_str,
        updated_at=now_str,
    )
    cap2 = ClinicalSafetyGovernanceCapabilityRecord(
        capability_id="CAP-002",
        tenant_id="org-apollo-01",
        name="Long Term Strategy",
        description="Multi-year strategy planning",
        organizational_scope={},
        responsible_department="Governance Office",
        accountable_owner_id="usr-owner-02",
        supporting_roles=["Strategy Analyst"],
        related_workflow="Phase 78 Strategy",
        criticality=CapabilityCriticalityTier.TIER_4_SUPPORTING,
        continuity_requirement_id=None,
        required_supporting_systems=["Strategy Portal"],
        required_integrations=[],
        required_information_sources=["Roadmap Database"],
        minimum_operational_requirements="Offline documentation",
        max_acceptable_interruption_hours=72.0,
        recovery_priority=10,
        status=CapabilityInventoryStatus.APPROVED,
        approved_by="usr-director-01",
        review_date=now_str,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_capability(cap1)
    repo80.save_capability(cap2)

    # CAP-001 has an approved plan; CAP-002 has no plan
    plan1 = GovernanceContinuityPlanRecord(
        plan_id="CP-001",
        tenant_id="org-apollo-01",
        title="Triage Continuity Plan",
        organizational_scope={},
        covered_capability_ids=["CAP-001"],
        plan_owner_id="usr-owner-01",
        activation_conditions="System outage > 15m",
        disruption_categories=["TECHNOLOGY_OUTAGE"],
        escalation_procedures="Notify Lead",
        communication_arrangements="Phone bridge",
        alternative_operating_procedures="Paper register",
        delegation_arrangements="Deputy triage lead",
        required_resources="Paper",
        recovery_priorities="Immediate",
        restoration_criteria="HTTP 200",
        verification_requirements="Audit signoff",
        testing_schedule="Quarterly",
        review_schedule="Annual",
        status=ContinuityPlanStatus.APPROVED,
        version=1,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_plan(plan1)

    # Run coverage assessment
    resp = client.post(
        "/api/v1/governance-continuity-assurance/coverage-assessments",
        json={"scope_level": "GLOBAL"},
        headers={"X-User-Id": "usr-auditor-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_critical_capabilities"] == 2
    assert data["covered_capabilities_count"] == 1
    assert data["uncovered_capabilities_count"] == 1
    assert data["coverage_percentage"] == 50.0


# =========================================================================
# Scenario 7 & 8: Exercise Assurance & Separation of Duties
# =========================================================================

def test_scenario_07_exercise_assurance_evaluation(client):
    """Evaluates Phase 80 continuity exercise criteria and review outcome."""
    repo80 = get_governance_continuity_repository()
    now_str = datetime.now(timezone.utc).isoformat()
    ex_rec = ContinuityExerciseRecord(
        exercise_id="EX-2026-001",
        tenant_id="org-apollo-01",
        title="Tabletop Failure Drill",
        exercise_type=ContinuityExerciseType.TABLETOP_EXERCISE,
        scope="Clinical triage operations",
        objectives="Verify manual fallback procedure execution",
        applicable_plan_id="CP-001",
        plan_version=1,
        participating_departments=["Emergency", "Clinical Safety"],
        coordinator_id="usr-drill-lead-01",
        planned_date="2026-12-01",
        actual_date="2026-12-01",
        scenario="Total EHR outage during peak hours",
        expected_results="All triage handovers completed manually within target",
        observed_results="Completed in 4m",
        status=ContinuityExerciseStatus.COMPLETED,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_exercise(ex_rec)

    eval_payload = {
        "exercise_id": "EX-2026-001",
        "exercise_type": "TABLETOP",
        "plan_id": "CP-001",
        "plan_version": 1,
        "evaluator_role": "Independent Safety Assurance Reviewer",
        "criteria_evaluations": [
            {
                "criterion_id": "CRIT-COMM-1",
                "criterion_name": "Emergency notification activation within 10m",
                "outcome": "PASSED",
                "observed_evidence": "All members notified in 4m",
            },
            {
                "criterion_id": "CRIT-PAPER-1",
                "criterion_name": "Manual log reconciliation",
                "outcome": "PARTIALLY_DEMONSTRATED",
                "observed_evidence": "Minor formatting discrepancy in paper logs",
            },
        ],
        "review_outcome": "DEMONSTRATED_EFFECTIVE",
        "deviations": ["Manual logs lacked standardized timestamps"],
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/exercise-evaluations",
        json=eval_payload,
        headers={"X-User-Id": "usr-independent-eval-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["passed_count"] == 1
    assert data["partially_demonstrated_count"] == 1
    assert data["review_outcome"] == "DEMONSTRATED_EFFECTIVE"


def test_scenario_08_exercise_assurance_separation_of_duties(client):
    """Ensures exercise coordinator cannot evaluate exercise effectiveness."""
    repo80 = get_governance_continuity_repository()
    now_str = datetime.now(timezone.utc).isoformat()
    ex_rec = ContinuityExerciseRecord(
        exercise_id="EX-2026-002",
        tenant_id="org-apollo-01",
        title="Communication Drill",
        exercise_type=ContinuityExerciseType.COMMUNICATION_TEST,
        scope="Clinical triage operations",
        objectives="Verify notification speed",
        applicable_plan_id="CP-001",
        plan_version=1,
        participating_departments=["Emergency"],
        coordinator_id="usr-drill-lead-02",
        planned_date="2026-12-01",
        scenario="SMS outage",
        expected_results="All notified in 10m",
        status=ContinuityExerciseStatus.COMPLETED,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_exercise(ex_rec)

    eval_payload = {
        "exercise_id": "EX-2026-002",
        "exercise_type": "COMMUNICATION",
        "plan_id": "CP-001",
        "plan_version": 1,
        "evaluator_role": "Self Evaluator",
        "review_outcome": "DEMONSTRATED_EFFECTIVE",
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/exercise-evaluations",
        json=eval_payload,
        headers={"X-User-Id": "usr-drill-lead-02", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"


# =========================================================================
# Scenario 9 & 10: Scenario Coverage & Stress Validation
# =========================================================================

def test_scenario_09_scenario_assessment_and_evaluation(client):
    """Creates an advisory scenario stress definition and evaluates resilience."""
    payload = {
        "scenario_type": "PRIMARY_SYSTEM_OUTAGE",
        "scenario_title": "Core EHR API Cluster Outage",
        "scenario_description": "Total disruption of primary EHR API services for > 4 hours.",
        "severity_level": "CRITICAL",
        "affected_capability_ids": ["CAP-001"],
        "required_dependencies": ["Primary PostgreSQL DB", "Redis Cache"],
        "assumptions": ["Network backbone remains functional"],
        "expected_continuity_response": "Transition to offline triage logs within 15 minutes.",
        "expected_recovery_sequence": ["Isolate DB", "Failover to replica", "Reconcile offline logs"],
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/scenario-assessments",
        json=payload,
        headers={"X-User-Id": "usr-planner-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    scenario_id = resp.json()["scenario_id"]
    assert resp.json()["is_advisory_only"] is True

    # Evaluate by independent evaluator
    eval_resp = client.post(
        f"/api/v1/governance-continuity-assurance/scenario-assessments/{scenario_id}/evaluate",
        json={
            "evaluation_outcome": "ADEQUATELY_ADDRESSED",
            "identified_weaknesses": ["Offline log sync bandwidth limitation"],
            "recommended_mitigations": ["Upgrade secondary uplink capacity"],
        },
        headers={"X-User-Id": "usr-evaluator-02", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["evaluation_outcome"] == "ADEQUATELY_ADDRESSED"


def test_scenario_10_scenario_evaluation_separation_of_duties(client):
    """Ensures scenario author cannot self-evaluate scenario stress resilience."""
    resp = client.post(
        "/api/v1/governance-continuity-assurance/scenario-assessments",
        json={
            "scenario_type": "FACILITY_DISRUPTION",
            "scenario_title": "Facility Power Loss",
            "scenario_description": "Grid power loss at main hospital facility.",
            "expected_continuity_response": "Generator backup active in 30s.",
        },
        headers={"X-User-Id": "usr-planner-01", "X-User-Role": "SAFETY_LEAD"},
    )
    scenario_id = resp.json()["scenario_id"]

    eval_resp = client.post(
        f"/api/v1/governance-continuity-assurance/scenario-assessments/{scenario_id}/evaluate",
        json={"evaluation_outcome": "ADEQUATELY_ADDRESSED"},
        headers={"X-User-Id": "usr-planner-01", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert eval_resp.status_code == 400
    assert eval_resp.json()["error"]["code"] == "CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"


# =========================================================================
# Scenario 11, 12, 13: Personnel Readiness & Delegated Authority
# =========================================================================

def test_scenario_11_and_12_personnel_readiness_lifecycle(client):
    """Assesses role readiness and verifies delegated authority against authorization rules."""
    req_payload = {
        "role_key": "CLINICAL_SAFETY_OFFICER",
        "role_name": "Chief Clinical Safety Officer",
        "primary_owner_id": "usr-doc-primary-01",
        "approved_substitute_id": "usr-doc-substitute-01",
        "organizational_scope": "GLOBAL",
        "authority_source_doc_ref": "DOC-AUTH-DELEGATION-2026-A",
        "competency_evidence_ref": "CERT-SAFETY-GOV-2025-V2",
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/personnel-readiness",
        json=req_payload,
        headers={"X-User-Id": "usr-hr-governance-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    readiness_id = data["readiness_id"]
    assert data["readiness_status"] == "UNVERIFIED_AUTHORITY"
    assert data["authority_verified_valid"] is False

    # Verify authority by independent authority verification officer
    verify_payload = {
        "verified_valid": True,
        "delegation_expiration_date": (datetime.now(timezone.utc) + timedelta(days=180)).isoformat(),
        "separation_of_duties_verified": True,
        "verification_notes": "Delegation instrument verified with Medical Directorate.",
    }
    v_resp = client.post(
        f"/api/v1/governance-continuity-assurance/personnel-readiness/{readiness_id}/verify-authority",
        json=verify_payload,
        headers={"X-User-Id": "usr-director-02", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert v_resp.status_code == 200
    v_data = v_resp.json()
    assert v_data["readiness_status"] == "VERIFIED_READY"
    assert v_data["authority_verified_valid"] is True
    assert v_data["separation_of_duties_verified"] is True


def test_scenario_13_personnel_authority_verification_separation_of_duties(client):
    """Ensures substitute cannot verify their own delegated authority."""
    req_payload = {
        "role_key": "TRIAGE_LEAD",
        "role_name": "Triage Lead",
        "primary_owner_id": "usr-doc-01",
        "approved_substitute_id": "usr-doc-02",
        "authority_source_doc_ref": "DOC-REF-01",
        "competency_evidence_ref": "CERT-REF-01",
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/personnel-readiness",
        json=req_payload,
        headers={"X-User-Id": "usr-hr-01", "X-User-Role": "SAFETY_LEAD"},
    )
    readiness_id = resp.json()["readiness_id"]

    # Substitute attempts to verify themselves
    v_resp = client.post(
        f"/api/v1/governance-continuity-assurance/personnel-readiness/{readiness_id}/verify-authority",
        json={"verified_valid": True, "separation_of_duties_verified": True},
        headers={"X-User-Id": "usr-doc-02", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert v_resp.status_code == 400
    assert v_resp.json()["error"]["code"] == "CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"


# =========================================================================
# Scenario 14 & 15: Critical Dependency Resilience & SPOF Detection
# =========================================================================

def test_scenario_14_dependency_spof_detection(client):
    """Detects Single Point of Failure (SPOF) when no alternative is documented."""
    payload = {
        "dependency_id": "DEP-SMS-01",
        "source_capability_id": "CAP-001",
        "dependency_type": "EXTERNAL_PARTNER",
        "criticality": "CRITICAL",
        "has_alternative": False,
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/dependency-assessments",
        json=payload,
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_spof"] is True
    assert data["resilience_evaluation"] == "SINGLE_POINT_OF_FAILURE"


def test_scenario_15_dependency_stale_evidence_detection(client):
    """Detects stale testing evidence older than 365 days."""
    stale_date = datetime.now(timezone.utc) - timedelta(days=400)
    payload = {
        "dependency_id": "DEP-AUTH-01",
        "source_capability_id": "CAP-001",
        "dependency_type": "SYSTEM",
        "criticality": "CRITICAL",
        "has_alternative": True,
        "alternative_arrangement_ref": "ARR-LDAP-FALLBACK",
        "testing_evidence_ref": "TEST-REPORT-2024",
        "evidence_timestamp": stale_date.isoformat(),
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/dependency-assessments",
        json=payload,
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_spof"] is False
    assert data["resilience_evaluation"] == "EVIDENCE_STALE"


# =========================================================================
# Scenario 16: Recovery Performance Assurance vs Targets
# =========================================================================

def test_scenario_16_recovery_performance_evaluation(client):
    """Evaluates actual recovery timestamps against approved RTO/MTPD targets."""
    repo80 = get_governance_continuity_repository()
    now_str = datetime.now(timezone.utc).isoformat()
    rec_record = GovernanceRecoveryRecord(
        recovery_id="REC-2026-001",
        tenant_id="org-apollo-01",
        disruption_id="DIS-001",
        capability_id="CAP-001",
        pre_disruption_operating_state="Active 24x7 Triage Operations",
        recovery_start_time=now_str,
        recovery_milestones=[],
        recovery_status=RecoveryStatus.OPERATIONALLY_RESTORED,
        evidence_of_restored_functionality="Restoration completed and verified",
        responsible_verifier_id="usr-verifier-01",
        verification_timestamp=now_str,
        created_at=now_str,
        updated_at=now_str,
    )
    repo80.save_recovery(rec_record)

    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    t_req = t0 + timedelta(minutes=10)
    t_app = t_req + timedelta(minutes=5)
    t_arr = t_app + timedelta(minutes=15)
    t_tech = t0 + timedelta(minutes=60)
    t_oper = t0 + timedelta(minutes=90)
    t_gov = t0 + timedelta(minutes=105)

    payload = {
        "recovery_id": "REC-2026-001",
        "capability_id": "CAP-001",
        "disruption_detected_at": t0.isoformat(),
        "activation_requested_at": t_req.isoformat(),
        "activation_approved_at": t_app.isoformat(),
        "arrangements_established_at": t_arr.isoformat(),
        "technical_restored_at": t_tech.isoformat(),
        "operational_restored_at": t_oper.isoformat(),
        "governance_verified_at": t_gov.isoformat(),
        "approved_rto_minutes": 120,  # Met within target (90m <= 120m)
        "approved_mtpd_minutes": 240,  # Met within target (105m <= 240m)
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/recovery-assessments",
        json=payload,
        headers={"X-User-Id": "usr-assessor-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rto_outcome"] == "MET_WITHIN_TARGET"
    assert data["mtpd_outcome"] == "MET_WITHIN_TARGET"
    assert data["current_restoration_stage"] == "VERIFIED_GOVERNANCE_RESTORATION"
    assert data["is_governance_verified"] is True


# =========================================================================
# Scenario 17: Reconciliation Assurance & Conflict Detection
# =========================================================================

def test_scenario_17_reconciliation_assurance(client):
    """Assesses temporary decision reconciliation integrity and detects conflicts."""
    payload = {
        "reconciliation_batch_id": "BATCH-REC-2026-01",
        "activation_id": "ACT-2026-001",
        "total_temporary_decisions_recorded": 10,
        "total_decisions_reconciled": 8,
        "unresolved_conflict_ids": ["TEMP-DEC-004", "TEMP-DEC-007"],
        "has_full_provenance": True,
        "receiving_workflow_references": ["Phase72_Review_001", "Phase63_Risk_002"],
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/reconciliation-assessments",
        json=payload,
        headers={"X-User-Id": "usr-audit-lead-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["integrity_status"] == "UNRESOLVED_CONFLICT_DETECTED"
    assert data["unresolved_conflicts_count"] == 2
    assert len(data["findings_generated"]) > 0


# =========================================================================
# Scenario 18: Independent Validation Programme & Conflict of Interest
# =========================================================================

def test_scenario_18_independent_validation_programme(client):
    """Manages independent validation programme with evaluator assignment and conflict checks."""
    p_payload = {
        "programme_name": "Annual Clinical Governance Resilience Review 2026",
        "scope_description": "Independent validation of Tier 1 critical capability continuity arrangements.",
        "objectives": ["Validate completeness", "Verify exercise realism"],
        "scheduled_start_date": datetime.now(timezone.utc).isoformat(),
        "scheduled_end_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/validation-programmes",
        json=p_payload,
        headers={"X-User-Id": "usr-officer-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    programme_id = resp.json()["programme_id"]

    # Assign evaluator
    client.post(
        f"/api/v1/governance-continuity-assurance/validation-programmes/{programme_id}/evaluators",
        json={
            "evaluator_id": "usr-ext-auditor-01",
            "evaluator_name": "Dr. Sarah Mitchell",
            "evaluator_organization": "Healthcare Accreditation International",
            "is_external_or_independent": True,
        },
        headers={"X-User-Id": "usr-officer-01", "X-User-Role": "SAFETY_LEAD"},
    )

    # Record conflict of interest
    client.post(
        f"/api/v1/governance-continuity-assurance/validation-programmes/{programme_id}/independence-declarations",
        json={
            "evaluator_id": "usr-ext-auditor-01",
            "declaration_statement": "I have previously consulted on this capability.",
            "has_conflict_of_interest": True,
            "conflict_details": "Consultancy fee received in 2024.",
        },
        headers={"X-User-Id": "usr-ext-auditor-01", "X-User-Role": "SAFETY_LEAD"},
    )

    # Attempting to submit evidence under programme with conflict of interest fails
    ev_resp = client.post(
        f"/api/v1/governance-continuity-assurance/validation-programmes/{programme_id}/evidence-requests",
        json={
            "target_capability_or_plan_id": "CAP-001",
            "evidence_description": "Exercise logs",
            "evidence_document_ref": "DOC-EX-LOGS",
        },
        headers={"X-User-Id": "usr-ext-auditor-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert ev_resp.status_code == 400
    assert ev_resp.json()["error"]["code"] == "CONFLICT_OF_INTEREST_DETECTED"


# =========================================================================
# Scenario 19: Continuity Finding Management & Phase 55 Integration
# =========================================================================

def test_scenario_19_finding_management_and_closure(client):
    """Creates a finding, refers it to Phase 54 CAPA, and closes it with Phase 55 effectiveness."""
    f_payload = {
        "category": "INADEQUATE_DEPENDENCY_ALTERNATIVES",
        "severity": "HIGH",
        "title": "Single point of failure on primary identity provider",
        "description": "No automated fallback when Active Directory becomes unreachable.",
        "affected_capability_id": "CAP-001",
        "source_evidence_ref": "EVAL-DRA-001",
        "validation_criteria_ref": "CRIT-DEP-1",
        "detection_method": "INDEPENDENT_VALIDATION",
        "impact_description": "Clinical staff locked out during ID provider outage.",
        "assigned_owner": "usr-infra-lead-01",
        "recommended_action": "Deploy read-only cached identity replica.",
    }
    resp = client.post(
        "/api/v1/governance-continuity-assurance/findings",
        json=f_payload,
        headers={"X-User-Id": "usr-evaluator-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert resp.status_code == 201
    finding_id = resp.json()["finding_id"]
    assert resp.json()["status"] == "IDENTIFIED"

    # Refer finding to Phase 54 CAPA
    refer_resp = client.post(
        f"/api/v1/governance-continuity-assurance/findings/{finding_id}/refer",
        json={
            "destination_workflow": "CAPA_PHASE54",
            "referral_reference_id": "CAPA-2026-881",
            "referral_notes": "Corrective action initiated to deploy local directory cache.",
        },
        headers={"X-User-Id": "usr-evaluator-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert refer_resp.status_code == 200
    assert refer_resp.json()["status"] == "REFERRED_TO_CAPA"

    # Action owner attempts self-closure (fails separation of duties)
    close_attempt = client.post(
        f"/api/v1/governance-continuity-assurance/findings/{finding_id}/close",
        json={"closure_rationale": "I fixed it."},
        headers={"X-User-Id": "usr-infra-lead-01", "X-User-Role": "SAFETY_LEAD"},
    )
    assert close_attempt.status_code == 400
    assert close_attempt.json()["error"]["code"] == "CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION"

    # Independent auditor closes with Phase 55 verified effectiveness reference
    close_resp = client.post(
        f"/api/v1/governance-continuity-assurance/findings/{finding_id}/close",
        json={
            "phase55_effectiveness_ref": "EFF-EVAL-PHASE55-901",
            "closure_rationale": "Verified effective through simulated AD cutoff drill.",
        },
        headers={"X-User-Id": "usr-auditor-02", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "VERIFIED_EFFECTIVE_BY_PHASE55"


# =========================================================================
# Scenario 20: Strategic Resilience Reporting & Patient Rejection
# =========================================================================

def test_scenario_20_reports_scan_and_patient_rejection(client):
    """Generates strategic reports, runs maintenance scan, and enforces patient role rejection."""
    # 1. Generate Report
    rep_resp = client.post(
        "/api/v1/governance-continuity-assurance/reports/generate",
        json={
            "report_type": "ORGANIZATIONAL_RESILIENCE_ASSURANCE",
            "organizational_scope": "GLOBAL",
            "reporting_period": "Q1-2026",
            "framework_version": 1,
        },
        headers={"X-User-Id": "usr-director-01", "X-User-Role": "CLINICAL_DIRECTOR"},
    )
    assert rep_resp.status_code == 200
    assert rep_resp.json()["overall_outcome"] in ("SATISFACTORY", "INSUFFICIENT_EVIDENCE")

    # 2. Run Routine Maintenance Scan
    scan_resp = client.post(
        "/api/v1/governance-continuity-assurance/maintenance/scan",
        headers={"X-User-Id": "usr-director-01", "X-User-Role": "ADMIN"},
    )
    assert scan_resp.status_code == 200
    assert "Automated background scan completed" in scan_resp.json()["scan_notes"]

    # 3. Patient Role Rejection (HTTP 403)
    patient_resp = client.get(
        "/api/v1/governance-continuity-assurance/frameworks",
        headers={"X-User-Id": "usr-patient-01", "X-User-Role": "PATIENT"},
    )
    assert patient_resp.status_code == 403
    assert patient_resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

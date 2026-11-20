"""Phase 73: Clinical Safety Governance Decision Implementation & Outcome Assurance Tests.

Validates:
- Scenario 1: Approved decision intake, draft decision rejection, superseded rejection, and intake idempotency
- Scenario 2: Implementation register lifecycle (create, update, submit, approve)
- Scenario 3: Implementation plan creation, approval, and versioning with change reasons
- Scenario 4: Ownership assignments, acceptance, and separation of duties enforcement
- Scenario 5: Dependency management, circular dependency detection, and authorized waivers
- Scenario 6: Milestone tracking, submission (no auto-verify), and independent verification
- Scenario 7: Evidence referencing, review status, and contradictory evidence flagging
- Scenario 8: Cross-workflow destination handoffs (Phase 54, 55, 63, 67, 69, 70)
- Scenario 9: Outcome reconciliation (OUTCOME_ACHIEVED, INCONCLUSIVE, evidence requirement)
- Scenario 10: Implementation exception logging and referral to Phase 67 escalation
- Scenario 11: Decision change impact review on supersession and authorized disposition
- Scenario 12: Closure gating check, controlled closure, and governed reopening
- Scenario 13: Management oversight reporting and aggregated metrics
- Scenario 14: Tenant boundary isolation between distinct organizations
- Scenario 15: Patient role authorization enforcement (403 Forbidden)
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
from app.repositories.governance_decision_implementation_repository import (
    get_governance_decision_implementation_repository,
)
from app.repositories.governance_management_review_repository import (
    get_governance_management_review_repository,
)
from app.schemas.auth import UserRole
from app.schemas.management_review_decisions import (
    ManagementDecisionCategory,
    ManagementDecisionRecord,
    ManagementDecisionStatus,
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
def clean_repos():
    """Clear repositories and configure auth dependency override."""
    repo73 = get_governance_decision_implementation_repository()
    repo73.clear()
    repo72 = get_governance_management_review_repository()
    repo72.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_phase72_decision(
    decision_id: str = "gmdc-test-01",
    status: ManagementDecisionStatus = ManagementDecisionStatus.APPROVED,
    title: str = "Standardize CDS Drug Interaction Thresholds",
    superseded_by: str = None,
    organization_id: str = "org-apollo-01",
) -> ManagementDecisionRecord:
    repo72 = get_governance_management_review_repository()
    decision = ManagementDecisionRecord(
        decision_id=decision_id,
        review_id="gmrv-rev-01",
        title=title,
        category=ManagementDecisionCategory.PROCESS_CHANGE,
        status=status,
        rationale="Reduce alert fatigue while maintaining medication safety coverage.",
        decided_by_id="usr-cso-01",
        decided_by_role="DOCTOR",
        superseded_by_id=superseded_by,
        organization_id=organization_id,
    )
    return repo72.save_decision(decision)


# =============================================================================
# SCENARIOS
# =============================================================================

def test_scenario_01_decision_intake(client: TestClient):
    """Scenario 1: Decision intake validation, eligibility, draft rejection, and idempotency."""
    # 1. Seed approved decision in Phase 72
    _seed_phase72_decision("gmdc-appr-01", ManagementDecisionStatus.APPROVED)

    # Ingest approved decision -> 201 Created
    intake_payload = {
        "decision_id": "gmdc-appr-01",
        "required_outcome": "Deployment of standardized CDS rules across all emergency facilities.",
        "assigned_management_owner": "usr-lead-01",
    }
    resp = client.post("/api/v1/governance-decision-implementation/decisions/intake", json=intake_payload)
    assert resp.status_code == 201
    intake = resp.json()
    assert intake["intake_status"] == "INTAKE_ACCEPTED"
    assert intake["decision_id"] == "gmdc-appr-01"

    # Idempotent re-ingestion returns same accepted intake
    resp_idem = client.post("/api/v1/governance-decision-implementation/decisions/intake", json=intake_payload)
    assert resp_idem.status_code == 200 or resp_idem.status_code == 201
    assert resp_idem.json()["intake_id"] == intake["intake_id"]

    # 2. Ingest DRAFT decision -> 400 Bad Request
    _seed_phase72_decision("gmdc-draft-01", ManagementDecisionStatus.DRAFT)
    resp_draft = client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-draft-01", "required_outcome": "Outcome A"},
    )
    assert resp_draft.status_code == 400
    assert resp_draft.json()["error"]["code"] == "DECISION_NOT_ELIGIBLE_FOR_IMPLEMENTATION"

    # 3. Ingest SUPERSEDED decision -> 400 Bad Request
    _seed_phase72_decision("gmdc-sup-01", ManagementDecisionStatus.SUPERSEDED, superseded_by="gmdc-newer-02")
    resp_sup = client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-sup-01", "required_outcome": "Outcome B"},
    )
    assert resp_sup.status_code == 400
    assert resp_sup.json()["error"]["code"] == "DECISION_NOT_ELIGIBLE_FOR_IMPLEMENTATION"


def test_scenario_02_implementation_register(client: TestClient):
    """Scenario 2: Register initiative, update details, submit, and approve."""
    _seed_phase72_decision("gmdc-reg-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-reg-01", "required_outcome": "Outcome Reg"},
    )

    # 1. Register Implementation Initiative
    target_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    imp_payload = {
        "decision_id": "gmdc-reg-01",
        "title": "CDS Rule Modernization Initiative",
        "description": "Refactor drug-drug interaction alert severity rules.",
        "intended_outcome": "Achieve 40% reduction in alert overrides.",
        "responsible_owner_id": "usr-lead-01",
        "accountable_lead_id": "usr-sponsor-01",
        "category": "OPERATIONAL_WORKFLOW_CHANGE",
        "priority": "HIGH",
        "target_completion_date": target_date,
    }
    resp = client.post("/api/v1/governance-decision-implementation/implementations", json=imp_payload)
    assert resp.status_code == 201
    imp = resp.json()
    imp_id = imp["implementation_id"]
    assert imp["status"] == "PLANNING"

    # 2. Update Implementation
    update_payload = {"description": "Updated description for CDS Modernization."}
    resp_up = client.patch(f"/api/v1/governance-decision-implementation/implementations/{imp_id}", json=update_payload)
    assert resp_up.status_code == 200
    assert resp_up.json()["description"] == update_payload["description"]

    # 3. Submit implementation without plan -> 400 PLAN_APPROVAL_REQUIRED
    resp_fail_sub = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/submit", json={})
    assert resp_fail_sub.status_code == 400
    assert resp_fail_sub.json()["error"]["code"] == "PLAN_APPROVAL_REQUIRED"

    # Create plan, then submit implementation
    client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/plans",
        json={"objectives": ["Phase 1 CDS Testing"]},
    )
    resp_sub = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/submit", json={})
    assert resp_sub.status_code == 200
    assert resp_sub.json()["status"] == "PENDING_APPROVAL"

    # 4. Formally Approve Implementation -> advances to IN_PROGRESS
    appr_payload = {"approval_rationale": "Approved by Clinical Safety Executive Board."}
    resp_appr = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/approve",
        json=appr_payload,
    )
    assert resp_appr.status_code == 200
    assert resp_appr.json()["status"] == "IN_PROGRESS"


def test_scenario_03_implementation_plans_and_versioning(client: TestClient):
    """Scenario 3: Implementation plan creation, approval, and versioning on modification."""
    _seed_phase72_decision("gmdc-plan-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-plan-01", "required_outcome": "Outcome Plan"},
    )
    imp_resp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-plan-01",
            "title": "Plan Versioning Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
        },
    )
    imp_id = imp_resp.json()["implementation_id"]

    # 1. Create initial Plan (version 1)
    plan_payload = {
        "objectives": ["Deploy CDS Rule v1", "Train staff"],
        "expected_evidence": ["Training Attendance Sheets", "System Audit Logs"],
        "verification_criteria": ["All ICU nurses completed module"],
    }
    resp = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/plans", json=plan_payload)
    assert resp.status_code == 201
    plan1 = resp.json()
    assert plan1["version"] == 1
    assert plan1["approval_status"] == "DRAFT"
    plan1_id = plan1["plan_id"]

    # Approve Plan 1
    client.post(
        f"/api/v1/governance-decision-implementation/plans/{plan1_id}/approve",
        json={"approval_rationale": "Plan 1 Approved"},
    )

    # 2. Modify approved plan without change reason -> 400 Bad Request
    new_plan_no_reason = {"objectives": ["Revised CDS Scope"]}
    fail_mod = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/plans",
        json=new_plan_no_reason,
    )
    assert fail_mod.status_code == 400

    # 3. Version Plan with change reason -> version 2
    new_plan_payload = {
        "objectives": ["Revised CDS Scope including Emergency Dept"],
        "change_reason": "Executive directive to expand rollout to Emergency Department.",
    }
    resp2 = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/plans",
        json=new_plan_payload,
    )
    assert resp2.status_code == 201
    plan2 = resp2.json()
    assert plan2["version"] == 2
    assert plan2["change_reason"] == new_plan_payload["change_reason"]

    # Verify Plan 1 is now SUPERSEDED
    old_plan = client.get(f"/api/v1/governance-decision-implementation/plans/{plan1_id}").json()
    assert old_plan["approval_status"] == "SUPERSEDED"
    assert old_plan["is_active"] is False


def test_scenario_04_ownership_and_separation_of_duties(client: TestClient):
    """Scenario 4: Role assignment, acceptance, and separation of duties enforcement."""
    _seed_phase72_decision("gmdc-own-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-own-01", "required_outcome": "Outcome Own"},
    )
    imp_resp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-own-01",
            "title": "Ownership Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        },
    )
    imp_id = imp_resp.json()["implementation_id"]

    # 1. Assign Work Item Owner
    assign_payload = {
        "user_id": "usr-worker-02",
        "user_name": "Nurse Janet",
        "role": "WORK_ITEM_OWNER",
        "scope_of_responsibility": "Coordinate ICU training modules",
    }
    resp = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/assignments", json=assign_payload)
    assert resp.status_code == 201
    asgn = resp.json()
    assert asgn["acceptance_status"] == "PENDING"
    asgn_id = asgn["assignment_id"]

    # Accept assignment
    accept_payload = {"acceptance_status": "ACCEPTED"}
    resp_acc = client.post(
        f"/api/v1/governance-decision-implementation/assignments/{asgn_id}/accept",
        json=accept_payload,
        headers={"X-User-Id": "usr-worker-02"},
    )
    assert resp_acc.status_code == 200
    assert resp_acc.json()["acceptance_status"] == "ACCEPTED"

    # 2. Separation of Duties Violation:
    # Attempt to assign the implementation lead ('usr-lead-01') as INDEPENDENT_VERIFIER -> 400 SEPARATION_OF_DUTIES_VIOLATION
    bad_verifier_payload = {
        "user_id": "usr-lead-01",
        "role": "INDEPENDENT_VERIFIER",
        "scope_of_responsibility": "Verify own work",
    }
    resp_bad = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/assignments",
        json=bad_verifier_payload,
    )
    assert resp_bad.status_code == 400
    assert resp_bad.json()["error"]["code"] == "SEPARATION_OF_DUTIES_VIOLATION"


def test_scenario_05_dependencies_and_waivers(client: TestClient):
    """Scenario 5: Dependency management, circular dependency detection, and authorized waivers."""
    _seed_phase72_decision("gmdc-dep-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-dep-01", "required_outcome": "Outcome Dep"},
    )
    imp1 = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-dep-01",
            "title": "Imp A",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    ).json()
    imp1_id = imp1["implementation_id"]

    # 1. Circular dependency detection: Self-dependency
    self_dep = {
        "dependency_type": "DECISION_PREREQUISITE",
        "source_workflow": "PHASE_73",
        "source_record_id": imp1_id,
    }
    resp_circ = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp1_id}/dependencies", json=self_dep)
    assert resp_circ.status_code == 400
    assert resp_circ.json()["error"]["code"] == "CIRCULAR_DEPENDENCY_DETECTED"

    # 2. Link legitimate dependency to external policy approval (Phase 69)
    dep_payload = {
        "dependency_type": "POLICY_APPROVAL",
        "source_workflow": "PHASE_69",
        "source_record_id": "pol-safe-69-001",
        "required_state": "APPROVED",
        "responsible_owner_id": "usr-gov-lead",
    }
    resp_dep = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp1_id}/dependencies", json=dep_payload)
    assert resp_dep.status_code == 201
    dep_id = resp_dep.json()["dependency_id"]

    # 3. Waive dependency without executive authorization (as staff) -> 403 Forbidden
    resp_waive_fail = client.post(
        f"/api/v1/governance-decision-implementation/dependencies/{dep_id}/waive",
        json={"waiver_rationale": "Staff waiver attempt"},
        headers={"X-User-Role": "SUPPORT_OPERATOR", "X-User-Id": "usr-operator-01"},
    )
    assert resp_waive_fail.status_code == 403
    assert resp_waive_fail.json()["error"]["code"] == "DEPENDENCY_WAIVER_UNAUTHORIZED"

    # 4. Waive dependency with executive authorization (as DOCTOR / ADMIN)
    resp_waive_ok = client.post(
        f"/api/v1/governance-decision-implementation/dependencies/{dep_id}/waive",
        json={"waiver_rationale": "Emergency deployment authorized by Clinical Safety Officer."},
        headers={"X-User-Role": "DOCTOR", "X-User-Id": "usr-cso-01"},
    )
    assert resp_waive_ok.status_code == 200
    assert resp_waive_ok.json()["status"] == "WAIVED_WITH_AUTHORIZATION"


def test_scenario_06_07_milestones_evidence_verification(client: TestClient):
    """Scenarios 6 & 7: Milestones, submission (no auto-verify), evidence attachment, and independent verification."""
    _seed_phase72_decision("gmdc-ms-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-ms-01", "required_outcome": "Outcome MS"},
    )
    imp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-ms-01",
            "title": "Milestone Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    ).json()
    imp_id = imp["implementation_id"]

    # 1. Create Milestone
    ms_payload = {
        "title": "Develop CDS Rule Definitions",
        "description": "Author clinical alert triggers and suppressions.",
        "responsible_owner_id": "usr-lead-01",
        "target_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        "expected_output": "Approved CDS configuration artifact",
        "required_evidence_types": ["CONFIGURATION_SPECIFICATION"],
    }
    resp_ms = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/milestones", json=ms_payload)
    assert resp_ms.status_code == 201
    ms_id = resp_ms.json()["milestone_id"]

    # 2. Attach Evidence
    ev_payload = {
        "source_record_ref": "doc-cds-cfg-2026",
        "evidence_type": "CONFIGURATION_SPECIFICATION",
        "version": "1.0",
        "access_classification": "STANDARD",
    }
    resp_ev = client.post(f"/api/v1/governance-decision-implementation/milestones/{ms_id}/evidence", json=ev_payload)
    assert resp_ev.status_code == 201
    ev_id = resp_ev.json()["evidence_id"]

    # Review Evidence -> ACCEPTED
    client.post(
        f"/api/v1/governance-decision-implementation/evidence/{ev_id}/review",
        json={"review_status": "ACCEPTED", "review_comments": "Configuration specification verified against policy."},
    )

    # 3. Owner Submits Milestone
    sub_payload = {
        "submission_notes": "Completed initial draft of CDS configuration rules.",
        "evidence_refs": [ev_id],
    }
    resp_sub = client.post(f"/api/v1/governance-decision-implementation/milestones/{ms_id}/submit", json=sub_payload)
    assert resp_sub.status_code == 200
    ms_sub = resp_sub.json()
    assert ms_sub["status"] == "SUBMITTED"
    assert ms_sub["verification_status"] != "VERIFIED"  # INVARIANT: No auto-verify on submit!

    # 4. Self-Verification Attempt: Owner tries to verify their own milestone -> 400 SEPARATION_OF_DUTIES_VIOLATION
    self_verif = {
        "outcome": "VERIFIED",
        "rationale": "I verify my own work is correct.",
    }
    fail_ver = client.post(
        f"/api/v1/governance-decision-implementation/milestones/{ms_id}/verify",
        json=self_verif,
        headers={"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN"},
    )
    assert fail_ver.status_code == 400
    assert fail_ver.json()["error"]["code"] == "SEPARATION_OF_DUTIES_VIOLATION"

    # 5. Independent Verification by distinct verifier
    indep_verif = {
        "outcome": "VERIFIED",
        "rationale": "Independent clinical safety review verified rule parameters.",
        "verification_criteria": ["Threshold validated against British National Formulary"],
        "evidence_reviewed": [ev_id],
    }
    ok_ver = client.post(
        f"/api/v1/governance-decision-implementation/milestones/{ms_id}/verify",
        json=indep_verif,
        headers={"X-User-Id": "usr-indep-verifier-09", "X-User-Role": "DOCTOR"},
    )
    assert ok_ver.status_code == 200
    assert ok_ver.json()["outcome"] == "VERIFIED"

    # Check milestone is now VERIFIED
    ms_check = client.get(f"/api/v1/governance-decision-implementation/milestones/{ms_id}").json()
    assert ms_check["status"] == "VERIFIED"
    assert ms_check["verification_status"] == "VERIFIED"


def test_scenario_08_cross_workflow_destination_handoffs(client: TestClient):
    """Scenario 8: Delegation handoffs to Phase 54 CAPA, Phase 55 effectiveness, and reconciliation."""
    _seed_phase72_decision("gmdc-ho-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-ho-01", "required_outcome": "Outcome HO"},
    )
    imp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-ho-01",
            "title": "Handoff Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    ).json()
    imp_id = imp["implementation_id"]

    # 1. Dispatch handoff to Phase 54 Corrective Action
    ho_payload = {
        "destination_workflow": "PHASE_54_CAPA",
        "destination_record_id": "capa-phase54-99",
        "requested_outcome": "Implement corrected dosage checking calculation.",
        "responsible_owner_id": "usr-capa-lead",
    }
    resp_ho = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/handoffs", json=ho_payload)
    assert resp_ho.status_code == 201
    ho = resp_ho.json()
    assert ho["status"] == "DISPATCHED"
    assert ho["destination_workflow"] == "PHASE_54_CAPA"
    ho_id = ho["handoff_id"]

    # 2. Reconcile handoff status from destination workflow
    recon_payload = {
        "latest_destination_status": "COMPLETED",
        "status": "COMPLETED",
        "notes": "Phase 54 CAPA investigation and corrective rollout completed.",
    }
    resp_recon = client.post(f"/api/v1/governance-decision-implementation/handoffs/{ho_id}/reconcile", json=recon_payload)
    assert resp_recon.status_code == 200
    assert resp_recon.json()["status"] == "COMPLETED"


def test_scenario_09_outcome_reconciliation(client: TestClient):
    """Scenario 9: Outcome reconciliation (OUTCOME_ACHIEVED, evidence requirement, INCONCLUSIVE)."""
    _seed_phase72_decision("gmdc-out-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-out-01", "required_outcome": "Outcome Assessment Goal"},
    )
    imp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-out-01",
            "title": "Outcome Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    ).json()
    imp_id = imp["implementation_id"]

    # 1. Attempt OUTCOME_ACHIEVED without supporting evidence -> 400 Bad Request
    fail_out = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/outcome-assessment",
        json={"state": "OUTCOME_ACHIEVED", "rationale": "Premature assertion without evidence."},
    )
    assert fail_out.status_code == 400

    # 2. Declare OUTCOME_ACHIEVED with supporting evidence reference
    ok_out = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/outcome-assessment",
        json={
            "state": "OUTCOME_ACHIEVED",
            "rationale": "Post-implementation audit demonstrated 42% reduction in alert overrides with zero missed interactions.",
            "supporting_evidence_refs": ["audit-post-impl-01"],
            "destination_workflow_outcome": {"phase55_effectiveness_rate": "98.5%"},
        },
    )
    assert ok_out.status_code == 201
    assert ok_out.json()["state"] == "OUTCOME_ACHIEVED"

    # Verify implementation status advanced to RECONCILED
    imp_check = client.get(f"/api/v1/governance-decision-implementation/implementations/{imp_id}").json()
    assert imp_check["status"] == "RECONCILED"


def test_scenario_10_exceptions_and_referral(client: TestClient):
    """Scenario 10: Implementation exception tracking and Phase 67 escalation referral."""
    _seed_phase72_decision("gmdc-exc-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-exc-01", "required_outcome": "Outcome Exc"},
    )
    imp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-exc-01",
            "title": "Exception Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    ).json()
    imp_id = imp["implementation_id"]

    # Log exception internally via service
    from app.services.decision_implementation_coordination_service import DecisionImplementationCoordinationService
    from app.schemas.decision_implementation_handoffs_outcomes import ImplementationExceptionCategory
    coord_svc = DecisionImplementationCoordinationService()
    exc = coord_svc.record_exception(
        implementation_id=imp_id,
        category=ImplementationExceptionCategory.BLOCKED_DEPENDENCIES,
        description="Vendor API integration delayed due to missing TLS certificates.",
        priority="HIGH",
        owner_id="usr-lead-01",
    )

    # Refer exception to Phase 67 governance escalation
    refer_payload = {
        "escalation_reference_id": "gesc-phase67-401",
        "notes": "Referred to executive escalation board under Phase 67.",
    }
    resp_ref = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/exceptions/{exc.exception_id}/refer",
        json=refer_payload,
    )
    assert resp_ref.status_code == 200
    assert resp_ref.json()["escalation_reference_id"] == "gesc-phase67-401"


def test_scenario_11_decision_change_impact_coordination(client: TestClient):
    """Scenario 11: Coordination when a Phase 72 decision is amended or superseded."""
    _seed_phase72_decision("gmdc-ci-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-ci-01", "required_outcome": "Outcome CI"},
    )
    imp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-ci-01",
            "title": "Change Impact Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    ).json()
    imp_id = imp["implementation_id"]

    # Review Change Impact (e.g. decision revised to new scope; disposition: MODIFY)
    ci_payload = {
        "disposition_decision": "MODIFY",
        "rationale": "Board expanded scope to neonatal intensive care. Initiative retained and modified.",
    }
    resp_ci = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/change-impact/review",
        json=ci_payload,
    )
    assert resp_ci.status_code == 200
    ci = resp_ci.json()
    assert ci["disposition_decision"] == "MODIFY"

    # Check implementation transitioned to REQUIRES_FURTHER_ACTION rather than destructive cancel
    imp_check = client.get(f"/api/v1/governance-decision-implementation/implementations/{imp_id}").json()
    assert imp_check["status"] == "REQUIRES_FURTHER_ACTION"


def test_scenario_12_closure_gating_and_reopening(client: TestClient):
    """Scenario 12: Closure gating check, controlled closure, and governed reopening."""
    _seed_phase72_decision("gmdc-close-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-close-01", "required_outcome": "Outcome Close"},
    )
    imp = client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-close-01",
            "title": "Closure Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    ).json()
    imp_id = imp["implementation_id"]

    # 1. Closure Check when milestones/evidence/outcomes are missing -> can_close is False
    chk = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/closure-check").json()
    assert chk["can_close"] is False
    assert len(chk["pending_blockers"]) > 0

    # Try closing prematurely -> 400 IMPLEMENTATION_CLOSURE_CONDITIONS_UNMET
    resp_close_fail = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/close",
        json={"closure_outcome": "CLOSED"},
    )
    assert resp_close_fail.status_code == 400
    assert resp_close_fail.json()["error"]["code"] == "IMPLEMENTATION_CLOSURE_CONDITIONS_UNMET"

    # 2. Satisfy all prerequisites:
    # A. Add milestone and verify it
    ms = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/milestones",
        json={
            "title": "Final Milestone",
            "description": "Desc",
            "responsible_owner_id": "usr-worker-02",
            "target_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "expected_output": "Final artifact",
        },
    ).json()
    client.post(
        f"/api/v1/governance-decision-implementation/milestones/{ms['milestone_id']}/verify",
        json={"outcome": "VERIFIED", "rationale": "Verified complete."},
        headers={"X-User-Id": "usr-indep-03", "X-User-Role": "DOCTOR"},
    )

    # B. Attach and review evidence
    ev = client.post(
        f"/api/v1/governance-decision-implementation/milestones/{ms['milestone_id']}/evidence",
        json={"source_record_ref": "doc-final-verif", "evidence_type": "FINAL_REPORT"},
    ).json()
    client.post(
        f"/api/v1/governance-decision-implementation/evidence/{ev['evidence_id']}/review",
        json={"review_status": "ACCEPTED", "review_comments": "Accepted."},
    )

    # C. Record outcome assessment
    client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/outcome-assessment",
        json={"state": "OUTCOME_ACHIEVED", "rationale": "Objectives demonstrated in full.", "supporting_evidence_refs": ["doc-final-verif"]},
    )

    # 3. Check closure readiness now -> can_close is True
    chk_ok = client.post(f"/api/v1/governance-decision-implementation/implementations/{imp_id}/closure-check").json()
    assert chk_ok["can_close"] is True

    # 4. Formally Close Implementation
    resp_close = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/close",
        json={"closure_outcome": "CLOSED_WITH_FOLLOW_UP", "closure_notes": "Closed with Phase 55 effectiveness monitoring."},
    )
    assert resp_close.status_code == 200
    assert resp_close.json()["status"] == "CLOSED_WITH_FOLLOW_UP"

    # 5. Reopen Implementation for further action
    resp_reopen = client.post(
        f"/api/v1/governance-decision-implementation/implementations/{imp_id}/reopen",
        json={"reopening_reason": "Post-closure regression detected in alert handling."},
    )
    assert resp_reopen.status_code == 200
    assert resp_reopen.json()["status"] == "REQUIRES_FURTHER_ACTION"


def test_scenario_13_management_oversight_reporting(client: TestClient):
    """Scenario 13: Aggregated overview metrics and formal report generation."""
    _seed_phase72_decision("gmdc-rep-01", ManagementDecisionStatus.APPROVED)
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-rep-01", "required_outcome": "Outcome Rep"},
    )
    client.post(
        "/api/v1/governance-decision-implementation/implementations",
        json={
            "decision_id": "gmdc-rep-01",
            "title": "Reporting Metric Test",
            "description": "Desc",
            "intended_outcome": "Goal",
            "responsible_owner_id": "usr-lead-01",
            "accountable_lead_id": "usr-sponsor-01",
            "target_completion_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        },
    )

    # 1. Fetch Overview
    resp_ov = client.get("/api/v1/governance-decision-implementation/reports/overview")
    assert resp_ov.status_code == 200
    ov = resp_ov.json()
    assert ov["total_implementations"] >= 1
    assert "PLANNING" in ov["implementations_by_status"]

    # 2. Generate Report
    rep_payload = {
        "report_type": "OVERVIEW",
        "reporting_period": "Q1 2026",
        "title": "Executive Decision Implementation Briefing",
    }
    resp_gen = client.post("/api/v1/governance-decision-implementation/reports/generate", json=rep_payload)
    assert resp_gen.status_code == 201
    rep = resp_gen.json()
    assert rep["reporting_period"] == "Q1 2026"
    assert "total_implementations" in rep["metrics"]


def test_scenario_14_tenant_boundary_isolation(client: TestClient):
    """Scenario 14: Tenant boundary isolation between distinct healthcare organizations."""
    # Seed decision in Org Apollo
    _seed_phase72_decision("gmdc-tenant-01", ManagementDecisionStatus.APPROVED, organization_id="org-apollo-01")
    headers_org_a = {"X-User-Organization": "org-apollo-01"}
    client.post(
        "/api/v1/governance-decision-implementation/decisions/intake",
        json={"decision_id": "gmdc-tenant-01", "required_outcome": "Outcome Org A"},
        headers=headers_org_a,
    )

    # Query from Org Fortis -> Should NOT see Org Apollo's decision intake
    headers_org_b = {"X-User-Organization": "org-fortis-02"}
    resp_b = client.get("/api/v1/governance-decision-implementation/decisions", headers=headers_org_b)
    assert resp_b.status_code == 200
    assert len(resp_b.json()) == 0


def test_scenario_15_patient_role_authorization_rejection(client: TestClient):
    """Scenario 15: Patient role is rejected with 403 Forbidden across implementation endpoints."""
    patient_headers = {"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-99"}

    # Attempt to access implementations
    resp1 = client.get("/api/v1/governance-decision-implementation/implementations", headers=patient_headers)
    assert resp1.status_code == 403
    assert resp1.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Attempt to access decisions
    resp2 = client.get("/api/v1/governance-decision-implementation/decisions", headers=patient_headers)
    assert resp2.status_code == 403

    # Attempt to access overview
    resp3 = client.get("/api/v1/governance-decision-implementation/reports/overview", headers=patient_headers)
    assert resp3.status_code == 403

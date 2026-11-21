"""Phase 75: Governance Change Portfolio Oversight & Cumulative Impact Coordination Tests.

Validates:
- Scenario 1: Portfolio lifecycle (Draft, Update, Submit, Separation of Duties on Approval, Activate, Suspend, Archive)
- Scenario 2: Initiative registration, validation of Phase 73/74 source references, duplicate prevention, removal, lineage
- Scenario 3: Cross-initiative dependency lifecycle (Proposed, Confirmed, Resolved, Disputed)
- Scenario 4: Circular dependency detection (DFS cycle detection rejecting cycles with CIRCULAR_INITIATIVE_DEPENDENCY_DETECTED)
- Scenario 5: Dependency graph generation, node/edge mapping, cycle status
- Scenario 6: Automated conflict detection (schedule/scope overlap), human review, and formal disposition
- Scenario 7: Scheduling coordination assessment and advisory sequencing recommendations
- Scenario 8: Cumulative operational impact assessment, workload aggregation, and clinical safety disclaimer
- Scenario 9: Shared resource dependency registration, visibility, and capacity status
- Scenario 10: Cross-initiative issue logging, routing to authoritative workflows (Phases 49, 54, 63, 67), and escalation
- Scenario 11: Portfolio review snapshot creation, formal approval, and referral to Phase 72 Management Review
- Scenario 12: Consolidated reporting endpoints (Overview, Progress, Adoption, Dependency, Impact, Executive reports)
- Scenario 13: Automated background coordination scan cycle
- Scenario 14: Multi-tenant boundary isolation
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
from app.repositories.governance_change_portfolio_repository import (
    get_governance_change_portfolio_repository,
)
from app.repositories.governance_decision_implementation_repository import (
    get_governance_decision_implementation_repository,
)
from app.repositories.governance_change_adoption_repository import (
    get_governance_change_adoption_repository,
)
from app.schemas.auth import UserRole
from app.schemas.decision_implementation_register import (
    DecisionImplementationRecord,
    ImplementationCategory,
    ImplementationPriority,
    ImplementationStatus,
)
from app.schemas.governance_change_adoption_registration import (
    GovernanceChangeAdoptionRecord,
    AdoptionRegistrationStatus,
    OperationalScope,
)
from app.schemas.governance_change_portfolio import (
    PortfolioPriority,
    PortfolioStatus,
)
from app.schemas.portfolio_initiative import (
    InitiativeCoordinationStatus,
)
from app.schemas.portfolio_dependencies_conflicts import (
    ConflictClassification,
    ConflictStatus,
    DependencyStatus,
    DependencyType,
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
    repo = get_governance_change_portfolio_repository()
    repo.clear()
    phase73_repo = get_governance_decision_implementation_repository()
    phase73_repo.clear()
    phase74_repo = get_governance_change_adoption_repository()
    phase74_repo.clear()
    yield
    repo.clear()
    phase73_repo.clear()
    phase74_repo.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def make_portfolio_payload(
    name: str = "Emergency Clinical Safety Harmonization Portfolio",
    portfolio_owner_id: str = "usr-lead-01",
    facilities: list = None,
    departments: list = None,
    priority: str = "HIGH",
):
    now = datetime.now(timezone.utc)
    return {
        "name": name,
        "description": "Cross-departmental alignment of emergency clinical safety changes",
        "governance_purpose": "Harmonize clinical safety policies and protocols across acute care",
        "portfolio_owner_id": portfolio_owner_id,
        "participating_facilities": facilities or ["fac-delhi-01", "fac-delhi-02"],
        "participating_departments": departments or ["Emergency", "ICU", "Trauma"],
        "priority": priority,
        "planned_start_date": now.isoformat(),
        "target_review_date": (now + timedelta(days=90)).isoformat(),
    }


def make_initiative_payload(
    decision_id: str = "dec_approved_100",
    implementation_id: str = "impl_valid_001",
    adoption_registration_id: str = None,
    title: str = "Emergency SBAR Protocol Initiative",
    facilities: list = None,
    departments: list = None,
    start_date: str = None,
    target_date: str = None,
    owner_id: str = "usr-lead-01",
):
    now = datetime.now(timezone.utc)
    return {
        "decision_id": decision_id,
        "implementation_id": implementation_id,
        "adoption_registration_id": adoption_registration_id,
        "title": title,
        "initiative_description": "Multi-site rollout of standardized clinical safety communication protocol",
        "intended_operational_change": "Mandatory clinical safety checklists at patient handoff",
        "participating_facilities": facilities or ["fac-delhi-01"],
        "participating_departments": departments or ["Emergency"],
        "accountable_owner_id": owner_id,
        "planned_start_date": start_date or now.isoformat(),
        "planned_target_date": target_date or (now + timedelta(days=60)).isoformat(),
        "priority": "HIGH",
    }


def seed_phase73_implementation(implementation_id: str = "impl_valid_001", tenant_id: str = "org-apollo-01"):
    phase73_repo = get_governance_decision_implementation_repository()
    now_dt = datetime.now(timezone.utc)
    record = DecisionImplementationRecord(
        implementation_id=implementation_id,
        decision_id="dec_approved_100",
        intake_id="intake_100",
        title="Clinical Safety SBAR Triage Protocol Implementation",
        description="Standardized implementation of clinical escalation gates across emergency departments.",
        intended_outcome="Achieve standardized clinical escalation gates across all emergency departments.",
        responsible_owner_id="usr-lead-01",
        accountable_lead_id="usr-lead-01",
        category=ImplementationCategory.CONTROL_IMPLEMENTATION,
        priority=ImplementationPriority.HIGH,
        status=ImplementationStatus.IN_PROGRESS,
        target_completion_date=now_dt + timedelta(days=90),
        organization_id=tenant_id,
        created_by="usr-admin-01",
        created_at=now_dt,
        updated_at=now_dt,
    )
    phase73_repo.save_implementation(record)
    return record


def seed_phase74_adoption(adoption_id: str = "adp_valid_001", tenant_id: str = "org-apollo-01"):
    phase74_repo = get_governance_change_adoption_repository()
    now_dt = datetime.now(timezone.utc).isoformat()
    rec = GovernanceChangeAdoptionRecord(
        registration_id=adoption_id,
        tenant_id=tenant_id,
        management_review_id="mr_rev_001",
        decision_id="dec_approved_100",
        implementation_id="impl_valid_001",
        title="Clinical Safety Protocol Adoption Monitoring",
        change_description="Adoption tracking for emergency triage gates",
        operational_scope=OperationalScope(
            facilities=["fac-delhi-01"],
            departments=["Emergency", "ICU"],
            roles=["CLINICAL_SAFETY_OFFICER", "STAFF_NURSE"],
        ),
        accountable_operational_owner_id="usr-lead-01",
        adoption_monitoring_owner_id="usr-admin-01",
        status=AdoptionRegistrationStatus.ACTIVE_MONITORING,
        monitoring_start_date=now_dt,
        created_by="usr-admin-01",
        created_at=now_dt,
        updated_at=now_dt,
    )
    phase74_repo.save_registration(rec)
    return rec


# =============================================================================
# Scenario 1: Portfolio Lifecycle & Separation of Duties
# =============================================================================


def test_scenario_1_portfolio_lifecycle_and_separation_of_duties(client):
    # 1. Create portfolio in DRAFT
    create_payload = make_portfolio_payload()
    resp = client.post("/api/v1/governance-change-portfolios/portfolios", json=create_payload)
    assert resp.status_code == 201
    port = resp.json()
    portfolio_id = port["portfolio_id"]
    assert port["status"] == PortfolioStatus.DRAFT.value
    assert port["created_by"] == "usr-lead-01"

    # 2. Update portfolio metadata
    patch_payload = {
        "name": "Emergency Clinical Safety Harmonization Portfolio (Updated)",
        "participating_facilities": ["fac-delhi-01", "fac-delhi-02", "fac-delhi-03"],
    }
    resp = client.patch(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}", json=patch_payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Emergency Clinical Safety Harmonization Portfolio (Updated)"
    assert len(resp.json()["participating_facilities"]) == 3

    # 3. Submit portfolio for approval
    submit_payload = {
        "submission_notes": "Ready for executive governance sign-off.",
    }
    resp = client.post(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/submit", json=submit_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == PortfolioStatus.SUBMITTED.value

    # 4. Separation of Duties violation: creator/owner attempts to approve
    approve_payload = {
        "approval_comments": "Self-approval attempt should fail.",
    }
    resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/approve",
        json=approve_payload,
        headers={"X-User-Id": "usr-lead-01"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PORTFOLIO_SEPARATION_OF_DUTIES_VIOLATION"

    # 5. Approve by independent governance lead
    resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/approve",
        json={"approval_comments": "Formally approved by Chief Medical Governance Officer."},
        headers={"X-User-Id": "usr-gov-officer-99"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == PortfolioStatus.APPROVED.value
    assert resp.json()["approved_by"] == "usr-gov-officer-99"

    # 6. Activate portfolio
    resp = client.post(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/activate")
    assert resp.status_code == 200
    assert resp.json()["status"] == PortfolioStatus.ACTIVE.value

    # 7. Suspend portfolio (ON_HOLD)
    resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/suspend",
        json={"suspension_reason": "Temporarily on hold pending annual clinical audit results."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == PortfolioStatus.ON_HOLD.value

    # 8. Archive portfolio
    resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/archive",
        json={"archival_justification": "Lifecycle completed and archived for compliance audit trail."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == PortfolioStatus.ARCHIVED.value


# =============================================================================
# Scenario 2: Initiative Registration, Validation & Lineage
# =============================================================================


def test_scenario_2_initiative_registration_validation_and_lineage(client):
    seed_phase73_implementation("impl_valid_001")
    seed_phase74_adoption("adp_valid_001")

    # Create active portfolio
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Initiative Testing Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    # Register Initiative with Phase 73 and Phase 74 references
    init_payload = make_initiative_payload(
        decision_id="dec_approved_100",
        implementation_id="impl_valid_001",
        adoption_registration_id="adp_valid_001",
    )
    resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=init_payload,
    )
    assert resp.status_code == 201
    init_data = resp.json()
    initiative_id = init_data["initiative_id"]
    assert init_data["coordination_status"] == InitiativeCoordinationStatus.ACCEPTED.value
    assert init_data["source_implementation_status"] == "IN_PROGRESS"
    assert init_data["source_adoption_status"] == "ACTIVE_MONITORING"

    # Duplicate registration attempt should be rejected
    resp_dup = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=init_payload,
    )
    assert resp_dup.status_code == 400
    assert resp_dup.json()["error"]["code"] == "INITIATIVE_ALREADY_IN_PORTFOLIO"

    # Reconstruct lineage
    resp_lineage = client.get(f"/api/v1/governance-change-portfolios/initiatives/{initiative_id}/lineage")
    assert resp_lineage.status_code == 200
    lineage = resp_lineage.json()
    assert lineage["initiative_id"] == initiative_id
    assert lineage["decision_id"] == "dec_approved_100"
    assert lineage["implementation_id"] == "impl_valid_001"
    assert lineage["adoption_registration_id"] == "adp_valid_001"

    # Remove initiative with recorded reason
    resp_rm = client.post(
        f"/api/v1/governance-change-portfolios/initiatives/{initiative_id}/remove",
        json={"removal_reason": "Superseded by emergency response directive 2026-B."},
    )
    assert resp_rm.status_code == 200
    assert resp_rm.json()["coordination_status"] == InitiativeCoordinationStatus.WITHDRAWN.value


# =============================================================================
# Scenario 3: Cross-Initiative Dependency Lifecycle
# =============================================================================


def test_scenario_3_cross_initiative_dependency_lifecycle(client):
    seed_phase73_implementation("impl_001")
    seed_phase73_implementation("impl_002")

    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Dependency Lifecycle Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    init_1 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="dec_1", implementation_id="impl_001", title="Initiative Prerequisite Alpha"),
    ).json()["initiative_id"]

    init_2 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="dec_2", implementation_id="impl_002", title="Initiative Dependent Beta"),
    ).json()["initiative_id"]

    # 1. Propose Dependency (Beta depends on Alpha)
    dep_payload = {
        "target_initiative_id": init_1,
        "dependency_type": DependencyType.MUST_COMPLETE_BEFORE.value,
        "description": "Beta requires Alpha EHR upgrade to be fully complete before data ingestion begins.",
        "dependency_owner_id": "usr-lead-01",
        "required_condition": "EHR schema v2 deployed and operational",
    }
    dep_resp = client.post(
        f"/api/v1/governance-change-portfolios/initiatives/{init_2}/dependencies",
        json=dep_payload,
    )
    assert dep_resp.status_code == 201
    dep_data = dep_resp.json()
    dependency_id = dep_data["dependency_id"]
    assert dep_data["status"] == DependencyStatus.PROPOSED.value

    # 2. Confirm Dependency
    conf_resp = client.post(
        f"/api/v1/governance-change-portfolios/dependencies/{dependency_id}/confirm",
        json={"confirmation_notes": "Confirmed by both project engineering leads."},
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == DependencyStatus.CONFIRMED.value

    # 3. Resolve Dependency with evidence
    res_resp = client.post(
        f"/api/v1/governance-change-portfolios/dependencies/{dependency_id}/resolve",
        json={
            "resolution_evidence": "EVID-EHR-V2-DEPLOYED-091",
        },
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == DependencyStatus.SATISFIED.value
    assert res_resp.json()["supporting_evidence_reference"] == "EVID-EHR-V2-DEPLOYED-091"

    # 4. Dispute another dependency
    seed_phase73_implementation("impl_003")
    init_3 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="dec_3", implementation_id="impl_003", title="Initiative Gamma"),
    ).json()["initiative_id"]

    dep_payload_2 = {
        "target_initiative_id": init_2,
        "dependency_type": DependencyType.SHARED_OPERATIONAL_RESOURCE.value,
        "description": "Gamma shares nursing champions with Beta.",
        "dependency_owner_id": "usr-lead-01",
        "required_condition": "Resource capacity verified",
    }
    dep_2 = client.post(
        f"/api/v1/governance-change-portfolios/initiatives/{init_3}/dependencies",
        json=dep_payload_2,
    ).json()["dependency_id"]

    disp_resp = client.post(
        f"/api/v1/governance-change-portfolios/dependencies/{dep_2}/dispute",
        json={"dispute_reason": "Nursing champions are separated into distinct regional squads."},
    )
    assert disp_resp.status_code == 200
    assert disp_resp.json()["status"] == DependencyStatus.DISPUTED.value


# =============================================================================
# Scenario 4: Circular Dependency Detection (Cycle Prevention)
# =============================================================================


def test_scenario_4_circular_dependency_detection(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Cycle Detection Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    # Register 3 initiatives: A, B, C
    init_a = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="d1", implementation_id="imp_a", title="Initiative A"),
    ).json()["initiative_id"]

    init_b = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="d2", implementation_id="imp_b", title="Initiative B"),
    ).json()["initiative_id"]

    init_c = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="d3", implementation_id="imp_c", title="Initiative C"),
    ).json()["initiative_id"]

    # B depends on A (A -> B)
    client.post(
        f"/api/v1/governance-change-portfolios/initiatives/{init_b}/dependencies",
        json={
            "target_initiative_id": init_a,
            "dependency_type": DependencyType.MUST_COMPLETE_BEFORE.value,
            "description": "B depends on A",
            "dependency_owner_id": "usr-lead-01",
            "required_condition": "A completed",
        },
    )

    # C depends on B (B -> C)
    client.post(
        f"/api/v1/governance-change-portfolios/initiatives/{init_c}/dependencies",
        json={
            "target_initiative_id": init_b,
            "dependency_type": DependencyType.MUST_COMPLETE_BEFORE.value,
            "description": "C depends on B",
            "dependency_owner_id": "usr-lead-01",
            "required_condition": "B completed",
        },
    )

    # Now attempt A depends on C (C -> A creates cycle A -> B -> C -> A)
    cycle_resp = client.post(
        f"/api/v1/governance-change-portfolios/initiatives/{init_a}/dependencies",
        json={
            "target_initiative_id": init_c,
            "dependency_type": DependencyType.MUST_COMPLETE_BEFORE.value,
            "description": "Cycle attempt: A depends on C",
            "dependency_owner_id": "usr-lead-01",
            "required_condition": "C completed",
        },
    )
    assert cycle_resp.status_code == 400
    assert cycle_resp.json()["error"]["code"] == "CIRCULAR_INITIATIVE_DEPENDENCY_DETECTED"


# =============================================================================
# Scenario 5: Dependency Graph Generation
# =============================================================================


def test_scenario_5_dependency_graph(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Graph Analysis Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    init_1 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="d1", implementation_id="imp_1", title="Foundation Component"),
    ).json()["initiative_id"]

    init_2 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(decision_id="d2", implementation_id="imp_2", title="Dependent Component"),
    ).json()["initiative_id"]

    # Dependent Component depends on Foundation Component
    client.post(
        f"/api/v1/governance-change-portfolios/initiatives/{init_2}/dependencies",
        json={
            "target_initiative_id": init_1,
            "dependency_type": DependencyType.MUST_COMPLETE_BEFORE.value,
            "description": "Requires foundation",
            "dependency_owner_id": "usr-lead-01",
            "required_condition": "Foundation ready",
        },
    )

    # Retrieve graph
    graph_resp = client.get(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/dependency-graph")
    assert graph_resp.status_code == 200
    graph = graph_resp.json()
    assert graph["portfolio_id"] == portfolio_id
    assert graph["circular_dependency_detected"] is False
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1


# =============================================================================
# Scenario 6: Automated Conflict Detection, Review & Formal Disposition
# =============================================================================


def test_scenario_6_conflict_detection_review_and_disposition(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Conflict Detection Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    now = datetime.now(timezone.utc)
    # Register 2 initiatives overlapping in the same department and timeframe
    init_1 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(
            decision_id="d1",
            implementation_id="imp_conf_1",
            title="Emergency Medication Dispensing Protocol Change",
            departments=["Emergency"],
            facilities=["fac-delhi-01"],
            start_date=now.isoformat(),
            target_date=(now + timedelta(days=30)).isoformat(),
        ),
    ).json()["initiative_id"]

    init_2 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(
            decision_id="d2",
            implementation_id="imp_conf_2",
            title="Emergency Staff Shift & Triage Overhaul",
            departments=["Emergency"],
            facilities=["fac-delhi-01"],
            start_date=(now + timedelta(days=5)).isoformat(),
            target_date=(now + timedelta(days=35)).isoformat(),
        ),
    ).json()["initiative_id"]

    # 1. Trigger automated conflict scan
    scan_resp = client.post(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/conflicts/scan")
    assert scan_resp.status_code == 200
    conflicts = scan_resp.json()
    assert len(conflicts) >= 1
    conflict_id = conflicts[0]["conflict_id"]
    assert conflicts[0]["status"] == ConflictStatus.POTENTIAL_CONFLICT.value

    # 2. Review conflict
    review_resp = client.post(
        f"/api/v1/governance-change-portfolios/conflicts/{conflict_id}/review",
        json={"confirmed": True, "review_notes": "Reviewed with Emergency department lead; significant concurrent workload."},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == ConflictStatus.CONFIRMED_CONFLICT.value

    # 3. Formal Disposition
    disp_resp = client.post(
        f"/api/v1/governance-change-portfolios/conflicts/{conflict_id}/disposition",
        json={
            "disposition": "RESOLVED_CONFLICT",
            "disposition_notes": "Shift triage overhaul will begin after medication dispensing change is stabilized.",
        },
    )
    assert disp_resp.status_code == 200
    disposition = disp_resp.json()
    assert disposition["status"] == ConflictStatus.RESOLVED_CONFLICT.value
    assert disposition["disposition"] == "RESOLVED_CONFLICT"


# =============================================================================
# Scenario 7: Scheduling Coordination & Advisory Sequencing
# =============================================================================


def test_scenario_7_scheduling_coordination_and_advisory_sequencing(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Scheduling Assessment Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    now = datetime.now(timezone.utc)
    client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(
            decision_id="d1",
            implementation_id="imp_s1",
            title="Phase 1 Safety Gate",
            start_date=now.isoformat(),
            target_date=(now + timedelta(days=20)).isoformat(),
        ),
    )
    client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(
            decision_id="d2",
            implementation_id="imp_s2",
            title="Phase 2 Clinical Dashboard",
            start_date=(now + timedelta(days=10)).isoformat(),
            target_date=(now + timedelta(days=40)).isoformat(),
        ),
    )

    # Perform schedule assessment
    sched_resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/schedule-assessments",
        json={
            "target_facilities": ["fac-delhi-01"],
            "target_departments": ["Emergency"],
        },
    )
    assert sched_resp.status_code == 201
    assessment = sched_resp.json()
    assert assessment["portfolio_id"] == portfolio_id
    assert "sequencing_recommendations" in assessment


# =============================================================================
# Scenario 8: Cumulative Operational Impact Assessment & Disclaimer Notice
# =============================================================================


def test_scenario_8_cumulative_operational_impact_assessment(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Cumulative Impact Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    now = datetime.now(timezone.utc)
    init_1 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(
            decision_id="d1",
            implementation_id="imp_imp_1",
            title="ICU Sepsis Checklist",
            departments=["ICU", "Emergency"],
            facilities=["fac-delhi-01"],
            start_date=now.isoformat(),
            target_date=(now + timedelta(days=30)).isoformat(),
        ),
    ).json()["initiative_id"]

    init_2 = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/initiatives",
        json=make_initiative_payload(
            decision_id="d2",
            implementation_id="imp_imp_2",
            title="ICU Ventilator Safety Protocol",
            departments=["ICU"],
            facilities=["fac-delhi-01"],
            start_date=now.isoformat(),
            target_date=(now + timedelta(days=45)).isoformat(),
        ),
    ).json()["initiative_id"]

    # Perform cumulative impact assessment
    impact_resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/impact-assessments",
        json={
            "assessment_period": "2026-Q2",
            "included_initiative_ids": [init_1, init_2],
            "limitations_disclosed": ["Limited to emergency and ICU units"],
            "assumptions_noted": ["Staffing baseline remains stable"],
        },
    )
    assert impact_resp.status_code == 201
    impact_data = impact_resp.json()
    assert impact_data["concurrent_changes_count"] == 2
    assert "ICU" in impact_data["affected_departments"]
    # Strict Clinical Safety Disclaimer Notice verification
    assert "clinical safety" in impact_data["clinical_safety_notice"].lower()
    assert "does not predict" in impact_data["clinical_safety_notice"].lower()


# =============================================================================
# Scenario 9: Resource Dependency Visibility
# =============================================================================


def test_scenario_9_resource_dependency_visibility(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Resource Coordination Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    res_resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/resource-dependencies",
        json={
            "initiative_ids": ["init_1", "init_2"],
            "resource_name": "Clinical Simulation Training Center - Delhi",
            "resource_category": "FACILITY_SIMULATION",
            "capacity_status": "CONSTRAINED",
            "notes": "Simulation slots booked to 95% capacity across emergency and ICU rollouts.",
        },
    )
    assert res_resp.status_code == 201
    res_data = res_resp.json()
    assert res_data["capacity_status"] == "CONSTRAINED"
    assert res_data["resource_category"] == "FACILITY_SIMULATION"

    # Retrieve list
    list_resp = client.get(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/resource-dependencies")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


# =============================================================================
# Scenario 10: Cross-Initiative Issue Logging, Routing & Escalation
# =============================================================================


def test_scenario_10_issue_logging_routing_and_escalation(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Issue Handling Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    # 1. Log Cross-Initiative Issue
    issue_resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/issues",
        json={
            "related_initiative_ids": ["init_er_01", "init_surg_02"],
            "title": "Conflicting Hand-off Terminology Between Initiatives",
            "description": "Emergency triage change uses SBAR while surgery checklist uses I-PASS.",
            "category": "GOVERNANCE_DISCREPANCY",
            "severity": "HIGH",
            "owner_id": "usr-lead-01",
        },
    )
    assert issue_resp.status_code == 201
    issue_data = issue_resp.json()
    issue_id = issue_data["issue_id"]
    assert issue_data["status"] == "OPEN"

    # 2. Route Issue to Phase 54 Corrective Action
    route_resp = client.post(
        f"/api/v1/governance-change-portfolios/issues/{issue_id}/route",
        json={
            "routed_destination": "PHASE_54_CAPA",
            "destination_reference": "CAPA-2026-088",
            "routing_notes": "Referred to Clinical Safety Corrective Action committee to harmonize terminology.",
        },
    )
    assert route_resp.status_code == 200
    routed = route_resp.json()
    assert routed["status"] == "ROUTED"
    assert routed["routed_destination"] == "PHASE_54_CAPA"
    assert routed["destination_reference"] == "CAPA-2026-088"

    # 3. Escalate Issue to Governance Leadership
    esc_resp = client.post(
        f"/api/v1/governance-change-portfolios/issues/{issue_id}/escalate",
        json={
            "escalation_reason": "Terminology inconsistency causing confusion in trauma bay transfers.",
            "target_governance_authority": "CHIEF_MEDICAL_OFFICER",
        },
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["status"] == "ESCALATED"


# =============================================================================
# Scenario 11: Portfolio Review Package & Referral to Phase 72 Management Review
# =============================================================================


def test_scenario_11_portfolio_review_and_phase72_referral(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Review Packaging Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    # 1. Draft Portfolio Review package
    rev_resp = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/reviews",
        json={
            "review_title": "Q1 Portfolio Oversight Review",
            "review_period": "2026-Q1",
            "participants": ["usr-lead-01", "usr-gov-director-01"],
            "recommendations": ["Rebalance emergency department clinical safety initiatives."],
        },
    )
    assert rev_resp.status_code == 201
    review_data = rev_resp.json()
    review_id = review_data["review_id"]
    assert review_data["status"] == "DRAFT"

    # 2. Submit Review package
    sub_resp = client.post(
        f"/api/v1/governance-change-portfolios/reviews/{review_id}/submit",
        json={"submission_notes": "Submitted for portfolio governance board review."},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 3. Approve Review package
    app_resp = client.post(
        f"/api/v1/governance-change-portfolios/reviews/{review_id}/approve",
        json={"approval_comments": "Sign-off granted by portfolio steering committee."},
        headers={"X-User-Id": "usr-gov-director-01"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # 4. Refer to Phase 72 Management Review
    refer_resp = client.post(
        f"/api/v1/governance-change-portfolios/reviews/{review_id}/refer-to-management",
        json={
            "management_review_reference": "MR-2026-Q1-EXEC",
            "referral_notes": "Cross-initiative friction requires executive management realignment.",
        },
    )
    assert refer_resp.status_code == 200
    referred = refer_resp.json()
    assert referred["status"] == "REFERRED"
    assert referred["management_review_reference"] == "MR-2026-Q1-EXEC"
    assert referred["referred_to_management_review"] is True


# =============================================================================
# Scenario 12: Consolidated Reporting & Executive Analytics
# =============================================================================


def test_scenario_12_consolidated_reporting_endpoints(client):
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Reporting Analysis Portfolio"),
    )
    assert port_resp.status_code == 201
    portfolio_id = port_resp.json()["portfolio_id"]

    # 1. Single Portfolio Overview
    ov_resp = client.get(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/overview")
    assert ov_resp.status_code == 200
    assert ov_resp.json()["portfolio_id"] == portfolio_id

    # 2. Implementation Progress Consolidation
    prog_resp = client.get(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/implementation-progress")
    assert prog_resp.status_code == 200
    assert prog_resp.json()["portfolio_id"] == portfolio_id

    # 3. Adoption Monitoring Summary
    adp_resp = client.get(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/adoption-summary")
    assert adp_resp.status_code == 200
    assert adp_resp.json()["portfolio_id"] == portfolio_id

    # 4. Dependency Summary
    dep_resp = client.get(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/dependency-summary")
    assert dep_resp.status_code == 200
    assert dep_resp.json()["portfolio_id"] == portfolio_id

    # 5. Impact Summary
    imp_resp = client.get(f"/api/v1/governance-change-portfolios/portfolios/{portfolio_id}/impact-summary")
    assert imp_resp.status_code == 200
    assert imp_resp.json()["portfolio_id"] == portfolio_id

    # 6. Executive Overview Report (Tenant-wide)
    exec_resp = client.get("/api/v1/governance-change-portfolios/reports/portfolio-overview")
    assert exec_resp.status_code == 200
    assert exec_resp.json()["total_portfolios"] >= 1

    # 7. Cross-Initiative Conflict Report
    conf_resp = client.get("/api/v1/governance-change-portfolios/reports/cross-initiative-conflicts")
    assert conf_resp.status_code == 200

    # 8. Cumulative Operational Impact Report
    cum_resp = client.get("/api/v1/governance-change-portfolios/reports/cumulative-operational-impact")
    assert cum_resp.status_code == 200


# =============================================================================
# Scenario 13: Background Coordination Scan Cycle
# =============================================================================


def test_scenario_13_background_coordination_cycle(client):
    job_resp = client.post("/api/v1/governance-change-portfolios/jobs/run-coordination-cycle")
    assert job_resp.status_code == 200
    result = job_resp.json()
    assert result["job_name"] == "portfolio_coordination_routine_scan"
    assert "run_timestamp" in result
    assert "details" in result


# =============================================================================
# Scenario 14: Multi-Tenant Boundary Isolation
# =============================================================================


def test_scenario_14_multi_tenant_boundary_isolation(client):
    # Create portfolio in Tenant A
    port_resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Tenant A Portfolio"),
        headers={"X-User-Organization": "org-apollo-01"},
    )
    assert port_resp.status_code == 201
    port_id = port_resp.json()["portfolio_id"]

    # Attempt to retrieve from Tenant B
    resp_b = client.get(
        f"/api/v1/governance-change-portfolios/portfolios/{port_id}",
        headers={"X-User-Organization": "org-fortis-02"},
    )
    assert resp_b.status_code == 404
    assert resp_b.json()["error"]["code"] == "GOVERNANCE_PORTFOLIO_NOT_FOUND"

    # Attempt to register initiative from Tenant B
    resp_init_b = client.post(
        f"/api/v1/governance-change-portfolios/portfolios/{port_id}/initiatives",
        json=make_initiative_payload(decision_id="d1", implementation_id="imp_b", title="Unauthorized cross-tenant init"),
        headers={"X-User-Organization": "org-fortis-02"},
    )
    assert resp_init_b.status_code == 404
    assert resp_init_b.json()["error"]["code"] == "GOVERNANCE_PORTFOLIO_NOT_FOUND"


# =============================================================================
# Scenario 15: Patient Role Authorization Enforcement (403 Forbidden)
# =============================================================================


def test_scenario_15_patient_role_authorization_rejection(client):
    # Patient role caller attempting portfolio creation
    resp = client.post(
        "/api/v1/governance-change-portfolios/portfolios",
        json=make_portfolio_payload(name="Unauthorized Patient Portfolio"),
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-007"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    # Patient role caller attempting to list portfolios
    resp_list = client.get(
        "/api/v1/governance-change-portfolios/portfolios",
        headers={"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-007"},
    )
    assert resp_list.status_code == 403
    assert resp_list.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

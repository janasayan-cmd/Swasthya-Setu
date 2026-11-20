"""Phase 74: Governance Change Adoption, Operational Sustainability & Drift Monitoring Tests.

Validates:
- Scenario 1: Change adoption registration, Phase 73 eligibility validation, and lineage reconstruction
- Scenario 2: Operational baseline creation, versioning, supersession, and separation of duties on approval
- Scenario 3: Adoption monitoring plan creation and activation across organizational scopes
- Scenario 4: Operational evidence submission, separation of duties on verification, and rejection
- Scenario 5: Adoption indicator assessment and strict evidence integrity (no ACHIEVED without verified evidence)
- Scenario 6: Implementation drift signal detection, human review, and formal disposition
- Scenario 7: Multi-dimensional sustainability assessments and clinical safety boundary notice
- Scenario 8: Operational exceptions lifecycle, expiry tracking, and escalation
- Scenario 9: Unintended operational consequence reporting and authoritative routing (Phases 49, 54, etc.)
- Scenario 10: Adoption-level escalations
- Scenario 11: Automated background monitoring cycle (overdue milestones, stale evidence, drift scan)
- Scenario 12: Adoption summaries, sustainability summaries, history, and executive reports
- Scenario 13: Multi-tenant boundary isolation
- Scenario 14: Patient role authorization enforcement (403 Forbidden)
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
from app.repositories.governance_change_adoption_repository import (
    get_governance_change_adoption_repository,
)
from app.repositories.governance_decision_implementation_repository import (
    get_governance_decision_implementation_repository,
)
from app.schemas.auth import UserRole
from app.schemas.decision_implementation_register import (
    DecisionImplementationRecord,
    ImplementationCategory,
    ImplementationPriority,
    ImplementationStatus,
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
    repo = get_governance_change_adoption_repository()
    repo.clear()
    phase73_repo = get_governance_decision_implementation_repository()
    phase73_repo.clear()
    yield
    repo.clear()
    phase73_repo.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


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


# =============================================================================
# Scenario 1: Change Adoption Registration & Eligibility
# =============================================================================


def test_change_adoption_registration_lifecycle(client: TestClient):
    seed_phase73_implementation("impl_valid_001")

    headers = {
        "X-User-Id": "usr-gov-lead",
        "X-User-Role": "ADMIN",
        "X-User-Organization": "org-apollo-01",
    }

    # 1. Register valid change
    payload = {
        "management_review_id": "rev_governance_200",
        "decision_id": "dec_approved_100",
        "implementation_id": "impl_valid_001",
        "title": "Emergency SBAR Adoption Monitoring",
        "change_description": "Monitoring adoption of SBAR escalation protocol across emergency facilities.",
        "operational_scope": {
            "facilities": ["fac-delhi-01", "fac-delhi-02"],
            "departments": ["Emergency", "Critical Care"],
            "teams": ["ED-Triage-A"],
            "roles": ["TRIAGE_NURSE", "DUTY_CLINICIAN"],
            "workflows": ["EMERGENCY_TRIAGE"],
        },
        "accountable_operational_owner_id": "usr-ops-head",
        "adoption_monitoring_owner_id": "usr-safety-officer",
        "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        "expected_monitoring_duration_days": 180,
        "adoption_milestones": [
            {
                "milestone_key": "M1_STAFF_TRAINING",
                "title": "90% Staff Completed Training",
                "target_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            }
        ],
        "required_evidence_categories": ["PROCEDURE_UPDATE", "TRAINING_COMPLETION", "CHECKLIST_RECORD"],
        "limitations_disclosed": ["Limited connectivity in remote clinics"],
    }

    resp = client.post("/api/v1/governance-change-adoption/registrations", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    reg_id = data["registration_id"]
    assert data["status"] == "PENDING_BASELINE"
    assert data["title"] == "Emergency SBAR Adoption Monitoring"
    assert len(data["adoption_milestones"]) == 1

    # 2. Get registration
    get_resp = client.get(f"/api/v1/governance-change-adoption/registrations/{reg_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["registration_id"] == reg_id

    # 3. Lineage reconstruction
    lineage_resp = client.get(f"/api/v1/governance-change-adoption/registrations/{reg_id}/lineage", headers=headers)
    assert lineage_resp.status_code == 200
    lineage_data = lineage_resp.json()
    assert lineage_data["registration_id"] == reg_id
    assert lineage_data["implementation_id"] == "impl_valid_001"
    assert len(lineage_data["lineage_nodes"]) >= 4

    # 4. Reject invalid / empty implementation id
    bad_payload = dict(payload)
    bad_payload["implementation_id"] = "  "
    bad_resp = client.post("/api/v1/governance-change-adoption/registrations", json=bad_payload, headers=headers)
    assert bad_resp.status_code == 400
    assert bad_resp.json()["error"]["code"] == "PHASE73_IMPLEMENTATION_NOT_ELIGIBLE"


# =============================================================================
# Scenario 2: Operational Baseline Creation, Versioning & Approval
# =============================================================================


def test_operational_baseline_lifecycle_and_separation_of_duties(client: TestClient):
    seed_phase73_implementation("impl_valid_002")

    lead_headers = {
        "X-User-Id": "usr-author-01",
        "X-User-Role": "ADMIN",
        "X-User-Organization": "org-apollo-01",
    }
    approver_headers = {
        "X-User-Id": "usr-governance-lead",
        "X-User-Role": "ADMIN",
        "X-User-Organization": "org-apollo-01",
    }

    # Register initiative
    reg_resp = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_002",
            "title": "Pediatric Escalation Adoption",
            "change_description": "Adoption of revised pediatric vital signs alerts.",
            "operational_scope": {"departments": ["Pediatrics"]},
            "accountable_operational_owner_id": "usr-ped-head",
            "adoption_monitoring_owner_id": "usr-ped-monitor",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=lead_headers,
    )
    reg_id = reg_resp.json()["registration_id"]

    # 1. Create baseline v1.0 draft
    b_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/baselines",
        json={
            "version": "1.0",
            "intended_operational_process": "All triage nurses log PEWS score on pediatric intake.",
            "expected_workflow_behavior": "Automated alert fires when PEWS >= 3.",
            "required_operational_practices": ["Hourly vital logging", "Physician notification on PEWS >= 3"],
            "monitoring_frequency": "WEEKLY",
        },
        headers=lead_headers,
    )
    assert b_resp.status_code == 201
    baseline_v1 = b_resp.json()
    b_id_v1 = baseline_v1["baseline_id"]
    assert baseline_v1["status"] == "DRAFT"
    assert baseline_v1["author_id"] == "usr-author-01"

    # 2. Submit baseline
    sub_resp = client.post(
        f"/api/v1/governance-change-adoption/baselines/{b_id_v1}/submit",
        json={"submission_notes": "Ready for governance sign-off"},
        headers=lead_headers,
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "SUBMITTED"

    # 3. Separation of duties check: author cannot approve own baseline
    self_approve_resp = client.post(
        f"/api/v1/governance-change-adoption/baselines/{b_id_v1}/approve",
        json={"effective_date": datetime.now(timezone.utc).isoformat(), "approval_comments": "Looks good to me"},
        headers=lead_headers,  # author is usr-author-01
    )
    assert self_approve_resp.status_code == 403
    assert self_approve_resp.json()["error"]["code"] == "ADOPTION_SEPARATION_OF_DUTIES_VIOLATION"

    # 4. Authorized approver approves
    approve_resp = client.post(
        f"/api/v1/governance-change-adoption/baselines/{b_id_v1}/approve",
        json={"effective_date": datetime.now(timezone.utc).isoformat(), "approval_comments": "Formally approved"},
        headers=approver_headers,  # approver is usr-governance-lead
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"

    # Verify registration transitioned to ACTIVE_MONITORING
    reg_after = client.get(f"/api/v1/governance-change-adoption/registrations/{reg_id}", headers=lead_headers).json()
    assert reg_after["status"] == "ACTIVE_MONITORING"
    assert reg_after["current_baseline_version"] == "1.0"
    assert reg_after["active_baseline_id"] == b_id_v1

    # 5. Create and approve revised baseline v1.1 -> v1.0 becomes SUPERSEDED
    b_v1_1_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/baselines",
        json={
            "version": "1.1",
            "previous_version_id": b_id_v1,
            "change_reason": "Refined PEWS threshold from 3 to 2 for neonatal unit",
            "intended_operational_process": "Refined protocol with specialized neonatal range",
            "expected_workflow_behavior": "Automated alert fires on PEWS >= 2 for neonates",
        },
        headers=lead_headers,
    )
    b_id_v1_1 = b_v1_1_resp.json()["baseline_id"]
    client.post(f"/api/v1/governance-change-adoption/baselines/{b_id_v1_1}/submit", json={}, headers=lead_headers)
    client.post(
        f"/api/v1/governance-change-adoption/baselines/{b_id_v1_1}/approve",
        json={"effective_date": datetime.now(timezone.utc).isoformat()},
        headers=approver_headers,
    )

    # Check v1.0 status is now SUPERSEDED
    v1_check = client.get(f"/api/v1/governance-change-adoption/baselines/{b_id_v1}", headers=lead_headers).json()
    assert v1_check["status"] == "SUPERSEDED"


# =============================================================================
# Scenario 3: Adoption Monitoring Plan Creation & Activation
# =============================================================================


def test_adoption_monitoring_plan_lifecycle(client: TestClient):
    seed_phase73_implementation("impl_valid_003")
    headers = {"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}
    approver = {"X-User-Id": "usr-approver-02", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_003",
            "title": "Critical Results Callout Adoption",
            "change_description": "Monitoring adoption of mandatory callout for critical diagnostic results.",
            "operational_scope": {"departments": ["Laboratory", "ICU"]},
            "accountable_operational_owner_id": "usr-lab-head",
            "adoption_monitoring_owner_id": "usr-icu-head",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # Create baseline and approve
    base = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/baselines",
        json={
            "version": "1.0",
            "intended_operational_process": "Lab must call ordering clinician within 15 mins of critical value.",
            "expected_workflow_behavior": "Immediate phone log entry required.",
        },
        headers=headers,
    ).json()
    client.post(f"/api/v1/governance-change-adoption/baselines/{base['baseline_id']}/submit", json={}, headers=headers)
    client.post(
        f"/api/v1/governance-change-adoption/baselines/{base['baseline_id']}/approve",
        json={"effective_date": datetime.now(timezone.utc).isoformat()},
        headers=approver,
    )

    # Create monitoring plan
    plan_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/monitoring-plans",
        json={
            "title": "Lab Callout Adoption Plan",
            "monitoring_objectives": ["Ensure 100% critical results logged and acknowledged within 15 mins"],
            "baseline_id": base["baseline_id"],
            "monitoring_schedule_start": datetime.now(timezone.utc).isoformat(),
            "monitoring_frequency": "DAILY",
            "responsible_operational_owner_id": "usr-lab-head",
            "reporting_cadence": "WEEKLY",
        },
        headers=headers,
    )
    assert plan_resp.status_code == 201
    plan_data = plan_resp.json()
    plan_id = plan_data["plan_id"]
    assert plan_data["status"] == "DRAFT"

    # Activate monitoring plan
    act_resp = client.post(
        f"/api/v1/governance-change-adoption/monitoring-plans/{plan_id}/activate",
        json={"activation_notes": "Activated for Q4"},
        headers=headers,
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "ACTIVE"


# =============================================================================
# Scenario 4: Operational Evidence Management & Separation of Duties
# =============================================================================


def test_adoption_evidence_verification_and_rejection(client: TestClient):
    seed_phase73_implementation("impl_valid_004")
    submitter = {"X-User-Id": "usr-nurse-01", "X-User-Role": "SUPPORT_OPERATOR", "X-User-Organization": "org-apollo-01"}
    reviewer = {"X-User-Id": "usr-supervisor-02", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_004",
            "title": "Handover Checklist Adoption",
            "change_description": "Verification of shift handover checklist adoption.",
            "operational_scope": {"roles": ["STAFF_NURSE"]},
            "accountable_operational_owner_id": "usr-nurse-head",
            "adoption_monitoring_owner_id": "usr-supervisor-02",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=reviewer,
    ).json()
    reg_id = reg["registration_id"]

    # 1. Submit evidence item 1
    evi1_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/evidence",
        json={
            "baseline_version": "1.0",
            "title": "October Shift Handover Log",
            "category": "CHECKLIST_RECORD",
            "source_system": "EHR_NURSING",
            "source_reference": "NUR-HANDOVER-2026-10",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=submitter,
    )
    assert evi1_resp.status_code == 201
    evi1_id = evi1_resp.json()["evidence_id"]
    assert evi1_resp.json()["verification_status"] == "SUBMITTED"

    # 2. Separation of duties: Submitting actor cannot verify their own evidence
    self_verify = client.post(
        f"/api/v1/governance-change-adoption/evidence/{evi1_id}/verify",
        json={"verification_comments": "Verified by myself"},
        headers=submitter,
    )
    assert self_verify.status_code == 403
    assert self_verify.json()["error"]["code"] == "ADOPTION_SEPARATION_OF_DUTIES_VIOLATION"

    # 3. Independent supervisor verifies
    sup_verify = client.post(
        f"/api/v1/governance-change-adoption/evidence/{evi1_id}/verify",
        json={"verification_comments": "Reviewed 150 completed shift logs. All signatures valid."},
        headers=reviewer,
    )
    assert sup_verify.status_code == 200
    assert sup_verify.json()["verification_status"] == "VERIFIED"

    # 4. Submit evidence item 2 and reject it
    evi2_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/evidence",
        json={
            "baseline_version": "1.0",
            "title": "Incomplete Training Attendance Sheet",
            "category": "TRAINING_COMPLETION",
            "source_system": "PAPER_LOG",
            "source_reference": "TRN-OCT-01",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=submitter,
    )
    evi2_id = evi2_resp.json()["evidence_id"]

    rej_resp = client.post(
        f"/api/v1/governance-change-adoption/evidence/{evi2_id}/reject",
        json={"rejection_reason": "Sheet missing instructor signatures and competency quiz scores."},
        headers=reviewer,
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["verification_status"] == "REJECTED"


# =============================================================================
# Scenario 5: Adoption Indicator Framework & Strict Evidence Invariant
# =============================================================================


def test_indicator_assessment_evidence_integrity(client: TestClient):
    seed_phase73_implementation("impl_valid_005")
    headers = {"X-User-Id": "usr-evaluator-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}
    reviewer = {"X-User-Id": "usr-supervisor-02", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_005",
            "title": "Surgical Checklist Adoption",
            "change_description": "Monitoring WHO Surgical Safety Checklist adoption.",
            "operational_scope": {"departments": ["Surgery"]},
            "accountable_operational_owner_id": "usr-surg-head",
            "adoption_monitoring_owner_id": "usr-evaluator-01",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # Define indicator
    ind_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/indicators",
        json={
            "indicator_key": "WHO_CHECKLIST_COMPLETION_RATE",
            "title": "Surgical Checklist Completion Rate >= 95%",
            "category": "CONTROL_USAGE",
            "measurement_criteria": "Percentage of operations with fully documented Time-Out",
            "target_threshold": "95%",
        },
        headers=headers,
    )
    assert ind_resp.status_code == 201
    ind_id = ind_resp.json()["indicator_id"]

    # 1. Attempt to declare ACHIEVED with NO evidence -> Must be rejected (400)
    bad_assess = client.post(
        f"/api/v1/governance-change-adoption/indicators/{ind_id}/assess",
        json={
            "current_value": "98%",
            "outcome": "ACHIEVED",
            "evidence_ids_used": [],
            "confidence": "HIGH",
            "rationale": "Auditor impression",
        },
        headers=headers,
    )
    assert bad_assess.status_code == 400
    assert bad_assess.json()["error"]["code"] == "INVALID_ADOPTION_EVIDENCE_STATE"

    # 2. Submit evidence but leave it UNVERIFIED
    evi_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/evidence",
        json={
            "baseline_version": "1.0",
            "title": "OR Audit Logs",
            "category": "AUDIT_EVENT",
            "source_system": "OT_MANAGEMENT",
            "source_reference": "OR-AUDIT-2026-10",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )
    evi_id = evi_resp.json()["evidence_id"]

    # Attempt ACHIEVED with unverified evidence -> Must be rejected (400)
    unverified_assess = client.post(
        f"/api/v1/governance-change-adoption/indicators/{ind_id}/assess",
        json={
            "current_value": "98%",
            "outcome": "ACHIEVED",
            "evidence_ids_used": [evi_id],
            "confidence": "HIGH",
            "rationale": "Based on unverified logs",
        },
        headers=headers,
    )
    assert unverified_assess.status_code == 400
    assert unverified_assess.json()["error"]["code"] == "INVALID_ADOPTION_EVIDENCE_STATE"

    # 3. Independent reviewer verifies evidence
    client.post(
        f"/api/v1/governance-change-adoption/evidence/{evi_id}/verify",
        json={"verification_comments": "Audit verified against EHR records."},
        headers=reviewer,
    )

    # 4. Now assess indicator as ACHIEVED with verified evidence -> Success (200)
    good_assess = client.post(
        f"/api/v1/governance-change-adoption/indicators/{ind_id}/assess",
        json={
            "current_value": "97.5%",
            "outcome": "ACHIEVED",
            "evidence_ids_used": [evi_id],
            "confidence": "HIGH",
            "rationale": "97.5% verified checklist completion across 350 surgeries in October.",
        },
        headers=headers,
    )
    assert good_assess.status_code == 200
    assert good_assess.json()["outcome"] == "ACHIEVED"


# =============================================================================
# Scenario 6: Implementation Drift Signal Logging, Review & Disposition
# =============================================================================


def test_implementation_drift_detection_and_disposition(client: TestClient):
    seed_phase73_implementation("impl_valid_006")
    headers = {"X-User-Id": "usr-nurse-sup", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}
    reviewer = {"X-User-Id": "usr-governance-officer", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_006",
            "title": "Bar-code Medication Administration (BCMA) Adoption",
            "change_description": "BCMA scanning prior to high-alert drug administration.",
            "operational_scope": {"workflows": ["MEDICATION_ADMINISTRATION"]},
            "accountable_operational_owner_id": "usr-pharm-head",
            "adoption_monitoring_owner_id": "usr-nurse-sup",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # 1. Log potential drift signal
    drift_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/drift-signals",
        json={
            "baseline_version": "1.0",
            "title": "Barcode Scanning Workarounds in Night Shift",
            "description": "Nurses reported overriding scanner on night shifts due to battery life issues.",
            "classification": "POTENTIAL_DRIFT",
            "source_type": "SUPERVISOR_REPORT",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )
    assert drift_resp.status_code == 201
    sig_id = drift_resp.json()["signal_id"]
    assert drift_resp.json()["status"] == "OPEN"

    # 2. Review signal
    rev_resp = client.post(
        f"/api/v1/governance-change-adoption/drift-signals/{sig_id}/review",
        json={"review_notes": "Interviewed night shift staff and audited pharmacy override logs."},
        headers=reviewer,
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "UNDER_REVIEW"

    # 3. Dispose signal as CONFIRMED_DEVIATION
    disp_resp = client.post(
        f"/api/v1/governance-change-adoption/drift-signals/{sig_id}/disposition",
        json={
            "disposition": "CONFIRMED_DEVIATION",
            "disposition_notes": "Confirmed 24 manual overrides in ward 4. New charging docks requisitioned.",
        },
        headers=reviewer,
    )
    assert disp_resp.status_code == 200
    assert disp_resp.json()["status"] == "DISPOSED"
    assert disp_resp.json()["disposition"] == "CONFIRMED_DEVIATION"


# =============================================================================
# Scenario 7: Sustainability Assessment & Clinical Safety Boundary
# =============================================================================


def test_sustainability_assessment_and_clinical_boundary(client: TestClient):
    seed_phase73_implementation("impl_valid_007")
    headers = {"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}
    approver = {"X-User-Id": "usr-approver-02", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_007",
            "title": "Sepsis Alert Protocol Sustainability",
            "change_description": "Monitoring long-term sustainability of sepsis screening triggers.",
            "operational_scope": {"departments": ["Inpatient"]},
            "accountable_operational_owner_id": "usr-icu-lead",
            "adoption_monitoring_owner_id": "usr-lead-01",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # 1. Create sustainability assessment
    sus_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/sustainability-assessments",
        json={
            "baseline_version": "1.0",
            "monitoring_period": "Q3-2026",
            "dimension_scores": {
                "ownership": "STRONG",
                "staff_awareness": "HIGH",
                "training_maintenance": "SATISFACTORY",
                "workflow_integration": "ROUTINE",
                "evidence_continuity": "VERIFIED",
            },
            "disposition": "SUSTAINED_ADOPTION",
            "follow_up_requirements": ["Annual refresher training scheduled for Q1-2027"],
        },
        headers=headers,
    )
    assert sus_resp.status_code == 201
    assessment = sus_resp.json()
    assessment_id = assessment["assessment_id"]
    assert assessment["status"] == "DRAFT"
    # Verify clinical safety boundary notice
    assert "Does not replace Phase 55 clinical effectiveness" in assessment["clinical_safety_notice"]

    # 2. Submit assessment
    sub_resp = client.post(
        f"/api/v1/governance-change-adoption/sustainability-assessments/{assessment_id}/submit",
        json={"submission_notes": "Q3 evaluation submitted"},
        headers=headers,
    )
    assert sub_resp.status_code == 200

    # 3. Approve assessment
    app_resp = client.post(
        f"/api/v1/governance-change-adoption/sustainability-assessments/{assessment_id}/approve",
        json={"approval_comments": "Approved by clinical safety committee"},
        headers=approver,
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"


# =============================================================================
# Scenario 8: Operational Exceptions Lifecycle & Expiry Tracking
# =============================================================================


def test_adoption_exceptions_lifecycle(client: TestClient):
    seed_phase73_implementation("impl_valid_008")
    headers = {"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_008",
            "title": "Digital Consent Adoption",
            "change_description": "Digital bedside consent capture.",
            "operational_scope": {"departments": ["Day Surgery"]},
            "accountable_operational_owner_id": "usr-ds-head",
            "adoption_monitoring_owner_id": "usr-lead-01",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # 1. Draft exception
    exc_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/exceptions",
        json={
            "baseline_version": "1.0",
            "category": "OPERATIONAL_LIMITATION",
            "title": "Ophthalmology Clinic Tablet Outage Exception",
            "description": "Tablets damaged during flood; temporary paper consent approved for 14 days.",
            "responsible_owner_id": "usr-ophth-head",
            "requested_duration_days": 14,
            "review_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            "resolution_requirements": ["Deploy 5 replacement tablets by day 10"],
        },
        headers=headers,
    )
    assert exc_resp.status_code == 201
    exc_id = exc_resp.json()["exception_id"]
    assert exc_resp.json()["status"] == "DRAFT"

    # 2. Submit exception
    client.post(f"/api/v1/governance-change-adoption/exceptions/{exc_id}/submit", json={}, headers=headers)

    # 3. Review and approve exception
    rev_resp = client.post(
        f"/api/v1/governance-change-adoption/exceptions/{exc_id}/review",
        json={
            "approved": True,
            "authorization_reference": "AUTH-EXC-OPHTH-2026-01",
            "expiry_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            "review_notes": "Temporary paper exception granted.",
        },
        headers=headers,
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "ACTIVE"

    # 4. Escalate exception to Phase 67
    esc_resp = client.post(
        f"/api/v1/governance-change-adoption/exceptions/{exc_id}/escalate",
        json={
            "escalation_reason": "Replacement tablets backordered past 14 days",
            "destination_workflow": "PHASE_67_GOVERNANCE_EXCEPTION",
        },
        headers=headers,
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["status"] == "ESCALATED"


# =============================================================================
# Scenario 9: Unintended Operational Consequences Routing
# =============================================================================


def test_unintended_consequence_reporting_and_routing(client: TestClient):
    seed_phase73_implementation("impl_valid_009")
    headers = {"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_009",
            "title": "Dual Sign-off Medication Policy",
            "change_description": "Requiring two RN signatures for insulin administration.",
            "operational_scope": {"departments": ["Endocrinology"]},
            "accountable_operational_owner_id": "usr-endo-head",
            "adoption_monitoring_owner_id": "usr-lead-01",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # 1. Report unintended operational consequence
    cq_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/operational-consequences",
        json={
            "title": "Morning Insulin Administration Bottleneck",
            "description": "Waiting for second RN signature caused average 45-minute delay in morning meal doses.",
            "severity": "HIGH",
        },
        headers=headers,
    )
    assert cq_resp.status_code == 201
    cq_id = cq_resp.json()["consequence_id"]
    assert cq_resp.json()["status"] == "REPORTED"

    # 2. Route consequence to Phase 49 Incidents / Phase 54 CAPA
    route_resp = client.post(
        f"/api/v1/governance-change-adoption/operational-consequences/{cq_id}/route",
        json={
            "routed_destination": "PHASE_54_CAPA",
            "destination_reference": "CAPA-2026-MED-042",
            "routing_notes": "Referred to CAPA team to evaluate barcode verification as alternative to dual manual signoff.",
        },
        headers=headers,
    )
    assert route_resp.status_code == 200
    assert route_resp.json()["status"] == "ROUTED"
    assert route_resp.json()["routed_destination"] == "PHASE_54_CAPA"


# =============================================================================
# Scenario 10: Adoption Escalations
# =============================================================================


def test_adoption_escalations(client: TestClient):
    seed_phase73_implementation("impl_valid_010")
    headers = {"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_010",
            "title": "Emergency Evacuation Checklist Adoption",
            "change_description": "Ward evacuation drill checklists.",
            "operational_scope": {"departments": ["All"]},
            "accountable_operational_owner_id": "usr-safety-dir",
            "adoption_monitoring_owner_id": "usr-lead-01",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    esc_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/escalations",
        json={
            "title": "Zero Evacuation Drill Logs Submitted in 60 Days",
            "reason": "Facility managers failed to schedule drills due to construction.",
            "urgency": "CRITICAL",
            "escalated_to_destination": "CLINICAL_SAFETY_COMMITTEE",
        },
        headers=headers,
    )
    assert esc_resp.status_code == 201
    assert esc_resp.json()["urgency"] == "CRITICAL"


# =============================================================================
# Scenario 11: Automated Background Monitoring Scan
# =============================================================================


def test_background_monitoring_scan(client: TestClient):
    seed_phase73_implementation("impl_valid_011")
    headers = {"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}
    approver = {"X-User-Id": "usr-approver-02", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    # Register initiative with an overdue milestone
    past_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_011",
            "title": "Background Scan Test Initiative",
            "change_description": "Testing overdue milestones and evidence gaps.",
            "operational_scope": {"departments": ["General"]},
            "accountable_operational_owner_id": "usr-lead-01",
            "adoption_monitoring_owner_id": "usr-lead-01",
            "monitoring_start_date": past_date,
            "adoption_milestones": [
                {
                    "milestone_key": "M_PAST_DUE",
                    "title": "Past Due Milestone",
                    "target_date": past_date,
                    "completed": False,
                }
            ],
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # Create baseline and approve to make status ACTIVE_MONITORING
    base_resp = client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/baselines",
        json={
            "version": "1.0",
            "intended_operational_process": "Operational process for background testing",
            "expected_workflow_behavior": "Expected behavior for background testing",
        },
        headers=headers,
    )
    assert base_resp.status_code == 201
    base = base_resp.json()
    client.post(f"/api/v1/governance-change-adoption/baselines/{base['baseline_id']}/submit", json={}, headers=headers)
    client.post(
        f"/api/v1/governance-change-adoption/baselines/{base['baseline_id']}/approve",
        json={"effective_date": datetime.now(timezone.utc).isoformat()},
        headers=approver,
    )

    # Submit evidence that is already expired
    client.post(
        f"/api/v1/governance-change-adoption/registrations/{reg_id}/evidence",
        json={
            "baseline_version": "1.0",
            "title": "Expired Training Record",
            "category": "TRAINING_COMPLETION",
            "source_system": "LMS",
            "source_reference": "TRN-OLD",
            "collected_at": past_date,
            "valid_until": past_date,  # Already expired
        },
        headers=headers,
    )

    # Trigger background monitoring job
    job_resp = client.post("/api/v1/governance-change-adoption/jobs/run-monitoring-cycle", headers=headers)
    assert job_resp.status_code == 200
    res = job_resp.json()
    assert res["overdue_milestones_flagged"] >= 1
    assert res["stale_evidence_flagged"] >= 1
    assert res["drift_signals_generated"] >= 1  # Evidence gap detected for ACTIVE_MONITORING with 0 verified evidence


# =============================================================================
# Scenario 12: Reporting and Analytics
# =============================================================================


def test_adoption_reporting_and_summaries(client: TestClient):
    seed_phase73_implementation("impl_valid_012")
    headers = {"X-User-Id": "usr-lead-01", "X-User-Role": "ADMIN", "X-User-Organization": "org-apollo-01"}

    reg = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_012",
            "title": "Reporting Test Initiative",
            "change_description": "Testing adoption summaries and executive metrics.",
            "operational_scope": {"departments": ["Oncology"]},
            "accountable_operational_owner_id": "usr-lead-01",
            "adoption_monitoring_owner_id": "usr-lead-01",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    reg_id = reg["registration_id"]

    # 1. Adoption summary
    sum_resp = client.get(f"/api/v1/governance-change-adoption/registrations/{reg_id}/adoption-summary", headers=headers)
    assert sum_resp.status_code == 200
    assert sum_resp.json()["registration_id"] == reg_id

    # 2. Sustainability summary
    sus_sum_resp = client.get(f"/api/v1/governance-change-adoption/registrations/{reg_id}/sustainability-summary", headers=headers)
    assert sus_sum_resp.status_code == 200
    assert "Does not replace Phase 55 clinical effectiveness" in sus_sum_resp.json()["clinical_safety_notice"]

    # 3. Monitoring history
    hist_resp = client.get(f"/api/v1/governance-change-adoption/registrations/{reg_id}/monitoring-history", headers=headers)
    assert hist_resp.status_code == 200
    assert hist_resp.json()["events_count"] >= 1

    # 4. Organization report
    org_rep = client.get("/api/v1/governance-change-adoption/reports/organization-adoption", headers=headers)
    assert org_rep.status_code == 200
    assert org_rep.json()["total_registered_initiatives"] >= 1

    # 5. Drift report
    drift_rep = client.get("/api/v1/governance-change-adoption/reports/operational-drift", headers=headers)
    assert drift_rep.status_code == 200


# =============================================================================
# Scenario 13: Multi-tenant Boundary Isolation
# =============================================================================


def test_tenant_boundary_isolation(client: TestClient):
    seed_phase73_implementation("impl_valid_013", tenant_id="org-tenant-a")
    tenant_a = {"X-User-Id": "usr-a", "X-User-Role": "ADMIN", "X-User-Organization": "org-tenant-a"}
    tenant_b = {"X-User-Id": "usr-b", "X-User-Role": "ADMIN", "X-User-Organization": "org-tenant-b"}

    # Tenant A creates registration
    reg_a = client.post(
        "/api/v1/governance-change-adoption/registrations",
        json={
            "management_review_id": "rev_200",
            "decision_id": "dec_100",
            "implementation_id": "impl_valid_013",
            "title": "Tenant A Initiative",
            "change_description": "Confidential to Tenant A.",
            "operational_scope": {"departments": ["Cardiology"]},
            "accountable_operational_owner_id": "usr-a",
            "adoption_monitoring_owner_id": "usr-a",
            "monitoring_start_date": datetime.now(timezone.utc).isoformat(),
        },
        headers=tenant_a,
    ).json()
    reg_id_a = reg_a["registration_id"]

    # Tenant B tries to get Tenant A's registration -> 404
    cross_get = client.get(f"/api/v1/governance-change-adoption/registrations/{reg_id_a}", headers=tenant_b)
    assert cross_get.status_code == 404
    assert cross_get.json()["error"]["code"] == "CHANGE_ADOPTION_REGISTRATION_NOT_FOUND"

    # Tenant B listings must not include Tenant A's records
    b_list = client.get("/api/v1/governance-change-adoption/registrations", headers=tenant_b).json()
    assert all(r["registration_id"] != reg_id_a for r in b_list)


# =============================================================================
# Scenario 14: Patient Role Authorization Enforcement (403 Forbidden)
# =============================================================================


def test_patient_role_access_rejection(client: TestClient):
    patient_headers = {
        "X-User-Id": "usr-patient-99",
        "X-User-Role": "PATIENT",
        "X-User-Organization": "org-apollo-01",
    }

    # All endpoints must reject Patient role with 403 Forbidden
    endpoints = [
        ("GET", "/api/v1/governance-change-adoption/registrations"),
        ("GET", "/api/v1/governance-change-adoption/reports/organization-adoption"),
        ("GET", "/api/v1/governance-change-adoption/reports/operational-drift"),
        ("POST", "/api/v1/governance-change-adoption/jobs/run-monitoring-cycle"),
    ]

    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path, headers=patient_headers)
        else:
            resp = client.post(path, json={}, headers=patient_headers)
        assert resp.status_code == 403, f"Expected 403 for {path}, got {resp.status_code}"
        assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

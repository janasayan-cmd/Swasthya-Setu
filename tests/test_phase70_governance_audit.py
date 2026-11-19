"""Phase 70: Independent Clinical Safety Governance Audit Tests.

Validates:
- Scenario 1: Programme creation, approval, and listing
- Scenario 2: Audit lifecycle transitions (draft, schedule, in_progress, paused, resumed, cancelled)
- Scenario 3: Scope definition, approval, freeze on execution, and formal amendment
- Scenario 4: Auditor assignment, conflict declaration, and independence review (self-review blocked)
- Scenario 5: Audit criteria definition and control traceability
- Scenario 6: Evidence request lifecycle (request, submission, and review)
- Scenario 7: Audit test execution and supervisory review
- Scenario 8: Findings recording, confirmation, disputes, and auditee responses
- Scenario 9: Corrective action referral linking to Phase 54 and Phase 55
- Scenario 10: Audit report compilation, metrics aggregation, and peer review
- Scenario 11: Report governance approval enforcing separation of duties (author self-approval blocked)
- Scenario 12: Controlled audit closure (requires approved report) and controlled reopening
- Scenario 13: Tenant boundary isolation
- Scenario 14: Patient role authorization restrictions (403 Forbidden)
- Scenario 15: Specialized supervisory queues and aggregated management reporting
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
from app.repositories.governance_audit_repository import (
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_execution import AuditTestOutcome
from app.schemas.audit_finding_response import (
    AuditeeResponseType,
    AuditFindingCategory,
    AuditFindingSeverity,
)
from app.schemas.audit_programme import AuditPriority, AuditProgrammeCategory
from app.schemas.audit_report_closure import AuditConclusion
from app.schemas.audit_scope_planning import AuditLifecycleStatus, AuditScopeStatus
from app.schemas.auditor_assignment import AuditorRole, IndependenceStatus
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = (
        UserRole.ADMIN
        if role_str == "ADMIN"
        else (UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT)
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-gov-lead-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repository and configure auth dependency override."""
    repo = get_governance_audit_repository()
    repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# SCENARIO 1: Programme Creation, Approval & Listing
# =============================================================================

def test_audit_programme_lifecycle(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    # 1. Create programme
    payload = {
        "name": "Q3 2026 Clinical Safety & AI Governance Audit Programme",
        "description": "Systematic audit of clinical safety controls, risk handoffs, and compliance evidence.",
        "objectives": [
            "Verify Phase 54 CAPA execution effectiveness",
            "Examine Phase 68 decision authorization traceability",
            "Evaluate Phase 69 compliance evidence completeness",
        ],
        "category": "SCHEDULED_GOVERNANCE",
        "priority": "HIGH",
        "related_framework_ids": ["gfw-iso-14971", "gfw-dha-ai-01"],
    }
    resp = client.post("/api/v1/governance-audits/programmes", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    prog = resp.json()
    prog_id = prog["programme_id"]
    assert prog["status"] == "ACTIVE"
    assert prog["organization_id"] == "org-apollo-01"

    # 2. Approve programme
    appr_payload = {
        "approval_rationale": "Formally chartered by the Apollo Clinical Safety Oversight Committee."
    }
    resp_appr = client.post(
        f"/api/v1/governance-audits/programmes/{prog_id}/approve",
        json=appr_payload,
        headers=headers,
    )
    assert resp_appr.status_code == 200
    assert resp_appr.json()["status"] == "APPROVED"
    assert resp_appr.json()["approved_by"] == "usr-admin-01"

    # 3. List programmes
    resp_list = client.get("/api/v1/governance-audits/programmes", headers=headers)
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) == 1
    assert items[0]["programme_id"] == prog_id


# =============================================================================
# SCENARIO 2: Audit Lifecycle Transitions (Draft -> Scheduled -> In Progress -> Paused -> Resumed -> Cancelled)
# =============================================================================

def test_audit_lifecycle_transitions(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}

    # 1. Setup programme
    prog_resp = client.post(
        "/api/v1/governance-audits/programmes",
        json={
            "name": "Annual Medication Safety Audit",
            "description": "Medication governance audit",
            "objectives": ["Audit high-risk orders"],
        },
        headers=headers,
    )
    prog_id = prog_resp.json()["programme_id"]

    # 2. Create audit (starts in DRAFT)
    audit_resp = client.post(
        "/api/v1/governance-audits/audits",
        json={
            "programme_id": prog_id,
            "title": "Oncology Medication Safety Handoff Audit",
            "description": "Examines chemotherapeutic risk handoffs and authorization integrity.",
            "category": "SCHEDULED_GOVERNANCE",
            "priority": "HIGH",
        },
        headers=headers,
    )
    assert audit_resp.status_code == 201
    audit = audit_resp.json()
    audit_id = audit["audit_id"]
    assert audit["lifecycle_status"] == "DRAFT"

    # 3. Schedule and start immediately
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=14)
    sched_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/schedule",
        json={
            "scheduled_start_date": now.isoformat(),
            "scheduled_end_date": end.isoformat(),
            "start_immediately": True,
        },
        headers=headers,
    )
    assert sched_resp.status_code == 200
    assert sched_resp.json()["lifecycle_status"] == "IN_PROGRESS"

    # 4. Pause audit
    pause_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/pause",
        json={"paused_reason": "Auditee key personnel unavailable due to acute incident review."},
        headers=headers,
    )
    assert pause_resp.status_code == 200
    assert pause_resp.json()["lifecycle_status"] == "PAUSED"

    # 5. Resume audit
    resume_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/resume",
        headers=headers,
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["lifecycle_status"] == "IN_PROGRESS"

    # 6. Cancel audit
    cancel_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/cancel",
        json={"cancellation_reason": "Facility undergoing emergency operational restructuring."},
        headers=headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["lifecycle_status"] == "CANCELLED"


# =============================================================================
# SCENARIO 3: Scope Definition, Approval, Freeze & Formal Amendment
# =============================================================================

def test_scope_definition_freeze_and_amendment(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}

    # Setup audit
    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=headers,
    ).json()
    audit_id = audit["audit_id"]

    # 1. Define draft scope
    scope_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/scope",
        json={
            "included_governance_processes": ["CLINICAL_RISK_HANDOFF", "DECISION_ASSURANCE"],
            "included_safety_controls": ["CTRL-SAF-001", "CTRL-SAF-002"],
            "included_compliance_requirements": ["REQ-REG-001"],
            "scope_limitations": ["Emergency department night shift excluded due to pending system rollout."],
            "scope_exclusions": [
                {"item": "PHASE_22_ASYNC_JOBS", "justification": "Evaluated in technical infrastructure audit."}
            ],
        },
        headers=headers,
    )
    assert scope_resp.status_code == 201
    scope = scope_resp.json()
    assert scope["version"] == 1
    assert scope["status"] == "DRAFT"

    # 2. Approve scope
    appr_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/scope/approve",
        json={"approval_rationale": "Approved by governance lead for Q3 fieldwork."},
        headers=headers,
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "APPROVED"

    # 3. Schedule audit with start_immediately -> Scope becomes FROZEN
    now = datetime.now(timezone.utc)
    client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/schedule",
        json={
            "scheduled_start_date": now.isoformat(),
            "scheduled_end_date": (now + timedelta(days=7)).isoformat(),
            "start_immediately": True,
        },
        headers=headers,
    )

    # Verify scope is frozen
    get_scope = client.get(f"/api/v1/governance-audits/audits/{audit_id}/scope", headers=headers).json()
    assert get_scope["is_frozen"] is True
    assert get_scope["status"] == "FROZEN"

    # 4. Attempting to directly overwrite frozen scope fails with 400
    fail_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/scope",
        json={"included_governance_processes": ["UNAUTHORIZED_OVERWRITE"]},
        headers=headers,
    )
    assert fail_resp.status_code == 400
    assert fail_resp.json()["error"]["code"] == "SCOPE_FROZEN_MODIFICATION_FORBIDDEN"
    assert "frozen" in fail_resp.json()["error"]["message"].lower()

    # 5. Formal amendment workflow succeeds with version increment
    amend_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/scope/amend",
        json={
            "change_justification": "Expanded scope to include Phase 69 regulatory evidence validation.",
            "amended_processes": ["CLINICAL_RISK_HANDOFF", "DECISION_ASSURANCE", "COMPLIANCE_MONITORING"],
            "amended_controls": ["CTRL-SAF-001", "CTRL-SAF-002", "CTRL-SAF-003"],
        },
        headers=headers,
    )
    assert amend_resp.status_code == 200
    amended = amend_resp.json()
    assert amended["version"] == 2
    assert amended["status"] == "AMENDED"
    assert len(amended["change_history"]) == 1
    assert amended["change_history"][0]["change_justification"] == (
        "Expanded scope to include Phase 69 regulatory evidence validation."
    )


# =============================================================================
# SCENARIO 4: Auditor Assignment & Independence Review (Self-Review Blocked)
# =============================================================================

def test_auditor_independence_and_separation_of_duties(client):
    admin_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    # Setup audit
    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=admin_headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=admin_headers,
    ).json()
    audit_id = audit["audit_id"]

    # 1. Assign Auditor 1 with declared conflicts
    asgn1_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/assignments",
        json={
            "auditor_id": "usr-auditor-conflict-01",
            "auditor_name": "Dr. Sarah Lin",
            "auditor_role": "SUBJECT_MATTER_EXPERT",
            "declared_conflicts": [
                "Participated in initial design of oncology risk protocol in Phase 64."
            ],
            "conflict_mitigation": "Exempted from testing oncology handoff samples directly; testing triage only.",
        },
        headers=admin_headers,
    )
    assert asgn1_resp.status_code == 201
    asgn1 = asgn1_resp.json()
    assert asgn1["independence_status"] == "CONFLICT_IDENTIFIED"

    # 2. Assign Auditor 2 (Lead Auditor) with no conflicts
    asgn2_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/assignments",
        json={
            "auditor_id": "usr-auditor-lead-02",
            "auditor_name": "Dr. James Vance",
            "auditor_role": "LEAD_AUDITOR",
            "declared_conflicts": [],
        },
        headers=admin_headers,
    )
    assert asgn2_resp.status_code == 201
    asgn2 = asgn2_resp.json()
    assert asgn2["independence_status"] == "PENDING_REVIEW"

    # 3. Separation of duties: Auditor 1 attempting to review their own independence is BLOCKED
    self_review_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-auditor-conflict-01"}
    self_fail = client.post(
        f"/api/v1/governance-audits/assignments/{asgn1['assignment_id']}/independence-review",
        json={
            "independence_status": "VERIFIED_INDEPENDENT",
            "review_rationale": "I consider myself objective.",
        },
        headers=self_review_headers,
    )
    assert self_fail.status_code == 400
    assert self_fail.json()["error"]["code"] == "AUDITOR_INDEPENDENCE_CONFLICT"
    assert "own independence" in self_fail.json()["error"]["message"].lower()

    # 4. Independent review by Admin succeeds
    review_resp = client.post(
        f"/api/v1/governance-audits/assignments/{asgn1['assignment_id']}/independence-review",
        json={
            "independence_status": "MITIGATION_APPROVED",
            "review_rationale": "Documented scope exclusion is adequate; subject matter input limited to advisory role.",
            "conflict_mitigation": "Confirmed auditor will not test Phase 64 oncology handoffs.",
        },
        headers=admin_headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["independence_status"] == "MITIGATION_APPROVED"
    assert review_resp.json()["independence_reviewed_by"] == "usr-admin-01"


# =============================================================================
# SCENARIO 5: Criteria Definition & Phase 69 Mapping
# =============================================================================

def test_audit_criteria_creation(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=headers,
    ).json()
    audit_id = audit["audit_id"]

    crit_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/criteria",
        json={
            "criterion_code": "CRT-GOV-001",
            "title": "Phase 68 Governance Decision Traceability",
            "description": "Verify that all critical risk reviews have documented authorization provenance.",
            "source_framework_id": "gfw-iso-14971",
            "source_requirement_id": "greq-trace-001",
            "source_control_id": "ctrl-auth-005",
            "expected_evidence_description": "Cryptographically signed decision event log entries.",
            "sampling_strategy": "100% sample of high and critical severity decisions.",
        },
        headers=headers,
    )
    assert crit_resp.status_code == 201
    crit = crit_resp.json()
    assert crit["criterion_code"] == "CRT-GOV-001"
    assert crit["is_active"] is True

    # List criteria
    list_resp = client.get(f"/api/v1/governance-audits/audits/{audit_id}/criteria", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


# =============================================================================
# SCENARIO 6: Evidence Request Lifecycle (Request -> Submit -> Review)
# =============================================================================

def test_evidence_request_lifecycle(client):
    auditor_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-auditor-01"}
    auditee_headers = {"X-User-Role": "DOCTOR", "X-User-Id": "usr-auditee-02"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=auditor_headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=auditor_headers,
    ).json()
    audit_id = audit["audit_id"]

    # 1. Issue evidence request
    ev_req_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/evidence-requests",
        json={
            "description": "Provide decision assurance logs for oncology risk reviews in March 2026.",
            "responsible_auditee_id": "usr-auditee-02",
            "responsible_auditee_role": "CLINICAL_SAFETY_OFFICER",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        },
        headers=auditor_headers,
    )
    assert ev_req_resp.status_code == 201
    req = ev_req_resp.json()
    req_id = req["request_id"]
    assert req["status"] == "REQUESTED"

    # 2. Auditee submits evidence
    submit_resp = client.post(
        f"/api/v1/governance-audits/evidence-requests/{req_id}/submit",
        json={
            "submitted_evidence_refs": ["gev-log-2026-03-01", "gev-sig-2026-03-02"],
            "auditee_notes": "Logs extracted from immutable Phase 68 decision audit ledger.",
        },
        headers=auditee_headers,
    )
    assert submit_resp.status_code == 200
    submitted = submit_resp.json()
    assert submitted["status"] == "SUBMITTED"
    assert len(submitted["submitted_evidence_refs"]) == 2

    # 3. Auditor reviews evidence and accepts
    review_resp = client.post(
        f"/api/v1/governance-audits/evidence-requests/{req_id}/review",
        json={
            "review_outcome": "ACCEPTED",
            "review_comments": "Evidence is complete and signatures verified against authorized key register.",
        },
        headers=auditor_headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "ACCEPTED"
    assert review_resp.json()["reviewed_by"] == "usr-auditor-01"


# =============================================================================
# SCENARIO 7: Audit Test Execution & Supervisory Review
# =============================================================================

def test_audit_test_execution_and_review(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-auditor-01"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=headers,
    ).json()
    audit_id = audit["audit_id"]

    crit = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/criteria",
        json={
            "criterion_code": "CRT-001",
            "title": "C1",
            "description": "D1",
            "expected_evidence_description": "E1",
        },
        headers=headers,
    ).json()

    # 1. Create test procedure
    test_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/tests",
        json={
            "criterion_id": crit["criterion_id"],
            "test_procedure": "Sample 25 high-risk decisions and verify dual clinical authorization.",
            "sampling_approach": "RANDOM_STRATIFIED",
            "sample_selection_reference": "SAMPLE-SET-MARCH-2026",
        },
        headers=headers,
    )
    assert test_resp.status_code == 201
    test_record = test_resp.json()
    test_id = test_record["test_id"]
    assert test_record["outcome"] == "NOT_STARTED"

    # 2. Execute test
    exec_resp = client.post(
        f"/api/v1/governance-audits/tests/{test_id}/execute",
        json={
            "outcome": "PASSED",
            "observations": "All 25 sampled decisions contained dual verified electronic sign-offs.",
            "evidence_refs": ["gev-sample-log-01", "gev-sample-log-02"],
            "auditor_notes": "Fieldwork completed with no exceptions observed.",
        },
        headers=headers,
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["outcome"] == "PASSED"
    assert exec_resp.json()["executed_by"] == "usr-auditor-01"

    # 3. Peer review test
    review_resp = client.post(
        f"/api/v1/governance-audits/tests/{test_id}/review",
        json={
            "review_comments": "Sampling strategy aligns with risk audit guidelines. Outcome confirmed.",
            "confirmed_outcome": "PASSED",
        },
        headers={"X-User-Role": "ADMIN", "X-User-Id": "usr-supervisor-02"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["reviewed_by"] == "usr-supervisor-02"


# =============================================================================
# SCENARIO 8: Findings, Confirmation, Disputes & Auditee Responses
# =============================================================================

def test_findings_disputes_and_responses(client):
    auditor_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}
    auditee_headers = {"X-User-Role": "DOCTOR", "X-User-Id": "usr-auditee-02"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=auditor_headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=auditor_headers,
    ).json()
    audit_id = audit["audit_id"]

    # 1. Create finding
    finding_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/findings",
        json={
            "category": "CONTROL_GAP",
            "severity": "HIGH",
            "finding_statement": "Post-closure monitoring period terminated prematurely in 3 cases.",
            "observed_condition": "Phase 66 verification was concluded at 14 days rather than required 30 days.",
            "expected_condition": "Policy POL-SAF-021 dictates a minimum 30-day post-closure observation period.",
            "gap_description": "16-day gap in safety monitoring observations.",
            "potential_impact": "Delayed detection of late-onset clinical safety events.",
            "responsible_owner_id": "usr-auditee-02",
        },
        headers=auditor_headers,
    )
    assert finding_resp.status_code == 201
    finding = finding_resp.json()
    finding_id = finding["finding_id"]
    assert finding["status"] == "UNDER_REVIEW"

    # 2. Confirm finding by Lead Auditor
    conf_resp = client.post(
        f"/api/v1/governance-audits/findings/{finding_id}/confirm",
        json={"confirmation_rationale": "Verified through review of Phase 66 closure timestamps."},
        headers=auditor_headers,
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["is_confirmed"] is True
    assert conf_resp.json()["status"] == "CONFIRMED"

    # 3. Auditee submits a response (dispute or action plan)
    resp_payload = {
        "response_type": "ACCEPTED",
        "response_statement": "Acknowledged. Premature closure was caused by an ambiguous automated trigger.",
        "explanation": "A patch has been deployed to enforce minimum 30-day duration lock.",
        "proposed_corrective_action": "Refer to Phase 54 for formal CAPA tracking and Phase 55 effectiveness check.",
        "proposed_completion_date": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
    }
    auditee_resp = client.post(
        f"/api/v1/governance-audits/findings/{finding_id}/responses",
        json=resp_payload,
        headers=auditee_headers,
    )
    assert auditee_resp.status_code == 201
    resp_record = auditee_resp.json()
    response_id = resp_record["response_id"]

    # 4. Auditor reviews auditee response (self-review blocked)
    self_review_fail = client.post(
        f"/api/v1/governance-audits/findings/responses/{response_id}/review",
        json={"decision": "ACCEPTED", "review_comments": "Looks good to me."},
        headers=auditee_headers,
    )
    assert self_review_fail.status_code == 400
    assert self_review_fail.json()["error"]["code"] == "AUDITOR_INDEPENDENCE_CONFLICT"
    assert "own response" in self_review_fail.json()["error"]["message"].lower()

    # Auditor review succeeds
    review_resp = client.post(
        f"/api/v1/governance-audits/findings/responses/{response_id}/review",
        json={"decision": "ACCEPTED", "review_comments": "Proposed CAPA referral is appropriate."},
        headers=auditor_headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["auditor_review_decision"] == "ACCEPTED"


# =============================================================================
# SCENARIO 9: Corrective Action Referral (Phase 54 & Phase 55 Linkage)
# =============================================================================

def test_corrective_action_referral(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=headers,
    ).json()
    finding = client.post(
        f"/api/v1/governance-audits/audits/{audit['audit_id']}/findings",
        json={
            "category": "GOVERNANCE_WEAKNESS",
            "severity": "HIGH",
            "finding_statement": "Missing clinical governance escalation sign-off.",
            "observed_condition": "C1",
            "expected_condition": "E1",
            "gap_description": "G1",
        },
        headers=headers,
    ).json()
    finding_id = finding["finding_id"]

    # Link to Phase 54 action and Phase 55 evaluation
    link_resp = client.post(
        f"/api/v1/governance-audits/findings/{finding_id}/link-corrective-action",
        json={
            "phase54_action_ref": "act-capa-2026-0042",
            "phase55_eval_ref": "evl-effect-2026-0019",
            "notes": "Action referred to Medication Safety Committee for remediation tracking.",
        },
        headers=headers,
    )
    assert link_resp.status_code == 200
    linked = link_resp.json()
    assert linked["corrective_action_ref"] == "act-capa-2026-0042"
    assert linked["phase55_eval_ref"] == "evl-effect-2026-0019"
    assert linked["status"] == "FOLLOW_UP_PENDING"


# =============================================================================
# SCENARIO 10 & 11: Report Compilation, Peer Review & Separation of Duties
# =============================================================================

def test_audit_report_generation_and_approval_separation_of_duties(client):
    author_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-author-lead-01"}
    approver_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-governance-chair-02"}

    # Setup complete audit with 1 test and 1 finding
    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=author_headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=author_headers,
    ).json()
    audit_id = audit["audit_id"]

    crit = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/criteria",
        json={"criterion_code": "C1", "title": "T1", "description": "D1", "expected_evidence_description": "E1"},
        headers=author_headers,
    ).json()
    test_rec = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/tests",
        json={"criterion_id": crit["criterion_id"], "test_procedure": "P1"},
        headers=author_headers,
    ).json()
    client.post(
        f"/api/v1/governance-audits/tests/{test_rec['test_id']}/execute",
        json={"outcome": "PASSED", "observations": "Obs 1"},
        headers=author_headers,
    )

    finding = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/findings",
        json={
            "category": "DOCUMENTATION_GAP",
            "severity": "ROUTINE",
            "finding_statement": "Minor formatting non-conformance in risk registry.",
            "observed_condition": "O1",
            "expected_condition": "E1",
            "gap_description": "G1",
        },
        headers=author_headers,
    ).json()
    client.post(
        f"/api/v1/governance-audits/findings/{finding['finding_id']}/confirm",
        json={"confirmation_rationale": "Confirmed."},
        headers=author_headers,
    )

    # 1. Author compiles draft report
    rep_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/reports",
        json={
            "title": "Clinical Safety Governance Independent Audit Report",
            "executive_summary": "Overall governance posture is satisfactory with one routine documentation gap.",
            "audit_conclusion": "SATISFACTORY_WITH_CONDITIONS",
            "recommendations": ["Update risk register formatting template in next release."],
        },
        headers=author_headers,
    )
    assert rep_resp.status_code == 201
    rep = rep_resp.json()
    report_id = rep["report_id"]
    assert rep["status"] == "DRAFT"
    assert rep["tests_performed_count"] == 1
    assert rep["tests_passed_count"] == 1
    assert rep["tests_failed_count"] == 0
    assert "ROUTINE" in rep["findings_summary"]
    assert rep["findings_summary"]["ROUTINE"] == 1
    assert finding["finding_id"] in rep["confirmed_finding_ids"]

    # 2. Peer review
    peer_resp = client.post(
        f"/api/v1/governance-audits/reports/{report_id}/review",
        json={"review_comments": "Report accurately synthesizes test findings and criteria results."},
        headers={"X-User-Role": "ADMIN", "X-User-Id": "usr-peer-reviewer-03"},
    )
    assert peer_resp.status_code == 200
    assert peer_resp.json()["status"] == "PENDING_REVIEW"

    # 3. Separation of Duties: Author cannot approve their own report
    self_appr_fail = client.post(
        f"/api/v1/governance-audits/reports/{report_id}/approve",
        json={"approval_policy_ref": "POL-AUD-001"},
        headers=author_headers,
    )
    assert self_appr_fail.status_code == 400
    assert self_appr_fail.json()["error"]["code"] == "REPORT_SELF_APPROVAL_FORBIDDEN"
    assert "author cannot approve" in self_appr_fail.json()["error"]["message"].lower()

    # 4. Independent approval by Governance Chair succeeds
    appr_resp = client.post(
        f"/api/v1/governance-audits/reports/{report_id}/approve",
        json={
            "approval_policy_ref": "POL-AUD-GOV-001",
            "approval_comments": "Formally approved by the Clinical Safety Governance Committee.",
        },
        headers=approver_headers,
    )
    assert appr_resp.status_code == 200
    approved_rep = appr_resp.json()
    assert approved_rep["status"] == "APPROVED"
    assert approved_rep["approved_by"] == "usr-governance-chair-02"


# =============================================================================
# SCENARIO 12: Controlled Audit Closure & Reopening
# =============================================================================

def test_audit_closure_and_reopening(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}
    chair_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-chair-02"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=headers,
    ).json()
    audit_id = audit["audit_id"]

    # 1. Attempting to close audit without an approved report FAILS with 400
    fail_close = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/close",
        json={"closure_rationale": "Premature attempt to close."},
        headers=headers,
    )
    assert fail_close.status_code == 400
    assert fail_close.json()["error"]["code"] == "AUDIT_CLOSURE_CONDITIONS_UNMET"
    assert "approved audit report" in fail_close.json()["error"]["message"].lower()

    # 2. Generate and approve report
    rep = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/reports",
        json={
            "title": "Audit Report",
            "executive_summary": "Completed.",
            "audit_conclusion": "SATISFACTORY",
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/governance-audits/reports/{rep['report_id']}/approve",
        json={"approval_policy_ref": "POL-GOV-001"},
        headers=chair_headers,
    )

    # 3. Close audit with follow-up required
    close_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/close",
        json={
            "closure_rationale": "Fieldwork completed; follow-up monitoring required on routine actions.",
            "follow_up_required": True,
        },
        headers=headers,
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["lifecycle_status"] == "FOLLOW_UP_REQUIRED"

    # 4. Controlled reopening following new safety signal
    reopen_resp = client.post(
        f"/api/v1/governance-audits/audits/{audit_id}/reopen",
        json={
            "reopening_reason": "New safety signal surfaced in Phase 59 regarding related medication cluster.",
            "source_trigger_ref": "sig-phase59-2026-0811",
        },
        headers=headers,
    )
    assert reopen_resp.status_code == 200
    reopened = reopen_resp.json()
    assert reopened["lifecycle_status"] == "IN_PROGRESS"
    assert reopened["metadata"]["source_trigger_ref"] == "sig-phase59-2026-0811"


# =============================================================================
# SCENARIO 13: Tenant Boundary Isolation
# =============================================================================

def test_tenant_boundary_isolation(client):
    tenant1_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-org1", "X-User-Organization": "org-apollo-01"}
    tenant2_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-org2", "X-User-Organization": "org-other-02"}

    # Tenant 1 creates programme and audit
    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "Org 1 Programme", "description": "D1", "objectives": ["O1"]},
        headers=tenant1_headers,
    ).json()
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "Org 1 Audit", "description": "D1"},
        headers=tenant1_headers,
    ).json()

    # Tenant 2 attempts to access Tenant 1 audit -> 403 Forbidden
    resp = client.get(f"/api/v1/governance-audits/audits/{audit['audit_id']}", headers=tenant2_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CROSS_TENANT_ACCESS_FORBIDDEN"
    assert "tenant boundaries" in resp.json()["error"]["message"].lower()


# =============================================================================
# SCENARIO 14: Patient Role Forbidden
# =============================================================================

def test_patient_role_forbidden(client):
    patient_headers = {"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-01"}

    # Attempt to access queues
    resp_q = client.get("/api/v1/governance-audits/queues/review-required", headers=patient_headers)
    assert resp_q.status_code == 403

    # Attempt to access programmes
    resp_p = client.get("/api/v1/governance-audits/programmes", headers=patient_headers)
    assert resp_p.status_code == 403

    # Attempt to create audit
    resp_a = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": "p1", "title": "A1", "description": "D1"},
        headers=patient_headers,
    )
    assert resp_a.status_code == 403


# =============================================================================
# SCENARIO 15: Specialized Queues & Aggregated Management Reporting
# =============================================================================

def test_queues_and_aggregated_reporting(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}

    # 1. Create programme and overdue audit
    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "Reporting Programme", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()

    past_date = datetime.now(timezone.utc) - timedelta(days=5)
    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={
            "programme_id": prog["programme_id"],
            "title": "Overdue Safety Audit",
            "description": "D1",
            "planned_end_date": past_date.isoformat(),
        },
        headers=headers,
    ).json()

    # Schedule it so it is IN_PROGRESS
    client.post(
        f"/api/v1/governance-audits/audits/{audit['audit_id']}/schedule",
        json={
            "scheduled_start_date": (past_date - timedelta(days=10)).isoformat(),
            "scheduled_end_date": past_date.isoformat(),
            "start_immediately": True,
        },
        headers=headers,
    )

    # 2. Check overdue queue
    q_resp = client.get("/api/v1/governance-audits/queues/overdue", headers=headers)
    assert q_resp.status_code == 200
    overdue_items = q_resp.json()
    assert len(overdue_items) >= 1
    assert any(a["audit_id"] == audit["audit_id"] for a in overdue_items)

    # 3. Check summary report
    sum_resp = client.get("/api/v1/governance-audits/reports/summary", headers=headers)
    assert sum_resp.status_code == 200
    summary = sum_resp.json()
    assert summary["total_programmes"] >= 1
    assert summary["total_audits"] >= 1
    assert summary["audits_overdue"] >= 1

    # 4. Check findings report
    find_resp = client.get("/api/v1/governance-audits/reports/findings", headers=headers)
    assert find_resp.status_code == 200
    assert "total_findings" in find_resp.json()

    # 5. Check overdue report
    od_resp = client.get("/api/v1/governance-audits/reports/overdue", headers=headers)
    assert od_resp.status_code == 200
    assert od_resp.json()["overdue_audits_count"] >= 1

    # 6. Check follow-up status report
    fu_resp = client.get("/api/v1/governance-audits/reports/follow-up-status", headers=headers)
    assert fu_resp.status_code == 200
    assert "audits_requiring_follow_up" in fu_resp.json()

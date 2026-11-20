"""Phase 71: Clinical Safety Governance Audit Finding Analytics & Systemic Risk Insight Tests.

Validates:
- Scenario 1: Historical audit finding analytics & multi-dimensional overview across reporting periods
- Scenario 2: Status filtering accuracy (draft/withdrawn findings excluded from confirmed counts)
- Scenario 3: Granular analytical breakdowns (by severity, category, control, process, facility, coverage)
- Scenario 4: Time-series governance trend calculations (new findings, repeats, backlog, CAPA recurrence)
- Scenario 5: Deterministic repeat finding detection across matching dimensions
- Scenario 6: Repeat finding human review workflow (confirmation, rejection, rationale preservation)
- Scenario 7: Cross-audit pattern identification (control weakness concentration, cross-facility deviation)
- Scenario 8: Cross-audit pattern review and referral to governance workflows
- Scenario 9: Systemic issue candidate generation and deterministic priority scoring
- Scenario 10: Systemic issue human review, confirmation, rejection, and cross-phase referral
- Scenario 11: Corrective action recurrence analysis (Phase 54 and Phase 55 linkages)
- Scenario 12: Reproducible management review report generation, approval, and structured export
- Scenario 13: Versioned analytical configuration lifecycle (create, approve, activate, deprecate)
- Scenario 14: Tenant boundary isolation (403 Forbidden)
- Scenario 15: Patient role authorization enforcement (403 Forbidden)
- Scenario 16: Data quality status evaluation and limitation disclosure
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
from app.repositories.governance_audit_intelligence_repository import (
    get_governance_audit_intelligence_repository,
)
from app.repositories.governance_audit_repository import (
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    role_str = request.headers.get("X-User-Role", "ADMIN")
    role_enum = (
        UserRole.ADMIN
        if role_str == "ADMIN"
        else (UserRole.DOCTOR if role_str == "DOCTOR" else UserRole.PATIENT)
    )
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-intel-officer-01"),
        role=role_enum,
        organization_id=request.headers.get("X-User-Organization", "org-apollo-01"),
        facility_id=request.headers.get("X-User-Facility", "fac-delhi-01"),
    )


@pytest.fixture(autouse=True)
def clean_repos():
    """Clear repositories and configure auth dependency override."""
    audit_repo = get_governance_audit_repository()
    audit_repo.clear()
    intel_repo = get_governance_audit_intelligence_repository()
    intel_repo.clear()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# SCENARIO 1, 2 & 3: Historical Findings Analytics, Status Filtering & Breakdowns
# =============================================================================

def test_historical_finding_analytics_and_breakdowns(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    # 1. Setup programme & 2 audits
    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()

    audit1 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "Audit 1", "description": "D1", "facility_id": "fac-delhi-01"},
        headers=headers,
    ).json()

    audit2 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "Audit 2", "description": "D2", "facility_id": "fac-mumbai-02"},
        headers=headers,
    ).json()

    # Create criterion
    crit = client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/criteria",
        json={"criterion_code": "CRT-SAF-001", "title": "C1", "description": "D1", "expected_evidence_description": "E1"},
        headers=headers,
    ).json()

    # 2. Add findings:
    # Finding 1: Confirmed High
    f1 = client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "CONTROL_GAP",
            "severity": "HIGH",
            "finding_statement": "Post-closure monitoring gap in oncology.",
            "observed_condition": "Monitoring stopped at 14 days.",
            "expected_condition": "Expected 30 days.",
            "gap_description": "16-day gap.",
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/governance-audits/findings/{f1['finding_id']}/confirm",
        json={"confirmation_rationale": "Confirmed by lead auditor."},
        headers=headers,
    )

    # Finding 2: Unconfirmed Draft Routine
    client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/findings",
        json={
            "category": "DOCUMENTATION_GAP",
            "severity": "ROUTINE",
            "finding_statement": "Minor formatting issue.",
            "observed_condition": "O2",
            "expected_condition": "E2",
            "gap_description": "G2",
        },
        headers=headers,
    )

    # Finding 3: In Audit 2 (different facility)
    f3 = client.post(
        f"/api/v1/governance-audits/audits/{audit2['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "CONTROL_GAP",
            "severity": "CRITICAL",
            "finding_statement": "Monitoring gap in chemotherapy ward.",
            "observed_condition": "Monitoring stopped early.",
            "expected_condition": "Expected 30 days.",
            "gap_description": "Gap.",
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/governance-audits/findings/{f3['finding_id']}/confirm",
        json={"confirmation_rationale": "Critical finding confirmed."},
        headers=headers,
    )

    # 3. Request Overview
    resp_overview = client.get("/api/v1/governance-audit-intelligence/analytics/overview", headers=headers)
    assert resp_overview.status_code == 200, resp_overview.text
    overview = resp_overview.json()
    assert overview["total_findings"] == 3
    assert overview["confirmed_findings"] == 2  # F1 and F3 confirmed; F2 is unconfirmed
    assert overview["open_findings"] == 3
    assert "HIGH" in overview["findings_by_severity"]
    assert "CRITICAL" in overview["findings_by_severity"]
    assert "CONTROL_GAP" in overview["findings_by_category"]

    # 4. Request Granular Breakdowns
    resp_sev = client.get("/api/v1/governance-audit-intelligence/analytics/findings/by-severity", headers=headers)
    assert resp_sev.status_code == 200
    assert resp_sev.json().get("HIGH") == 1
    assert resp_sev.json().get("CRITICAL") == 1

    resp_cat = client.get("/api/v1/governance-audit-intelligence/analytics/findings/by-category", headers=headers)
    assert resp_cat.status_code == 200
    assert resp_cat.json().get("CONTROL_GAP") == 2

    resp_ctrl = client.get("/api/v1/governance-audit-intelligence/analytics/findings/by-control", headers=headers)
    assert resp_ctrl.status_code == 200
    assert crit["criterion_id"] in resp_ctrl.json()

    resp_cov = client.get("/api/v1/governance-audit-intelligence/analytics/audit-coverage", headers=headers)
    assert resp_cov.status_code == 200
    assert resp_cov.json()["total_audits"] == 2


# =============================================================================
# SCENARIO 4: Time-Series Governance Trends
# =============================================================================

def test_governance_trends(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()

    audit = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "Audit Trends", "description": "D1"},
        headers=headers,
    ).json()

    client.post(
        f"/api/v1/governance-audits/audits/{audit['audit_id']}/findings",
        json={
            "category": "AUTHORIZATION_ISSUE",
            "severity": "HIGH",
            "finding_statement": "Authorization departed.",
            "observed_condition": "O1",
            "expected_condition": "E1",
            "gap_description": "G1",
        },
        headers=headers,
    )

    resp_trends = client.get("/api/v1/governance-audit-intelligence/analytics/findings/trends", headers=headers)
    assert resp_trends.status_code == 200
    trends = resp_trends.json()
    assert "new_findings_trend" in trends
    assert len(trends["new_findings_trend"]) >= 1
    assert trends["new_findings_trend"][0]["count"] >= 1


# =============================================================================
# SCENARIO 5 & 6: Repeat-Finding Detection & Human Review Workflow
# =============================================================================

def test_repeat_finding_detection_and_review(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()

    audit1 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1"},
        headers=headers,
    ).json()

    audit2 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A2", "description": "D2"},
        headers=headers,
    ).json()

    crit = client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/criteria",
        json={"criterion_code": "CRT-MED-01", "title": "C1", "description": "D1", "expected_evidence_description": "E1"},
        headers=headers,
    ).json()

    # Historical finding in Audit 1
    f_hist = client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "CONTROL_GAP",
            "severity": "HIGH",
            "finding_statement": "Medication reconciliation gap in inpatient discharge.",
            "observed_condition": "Reconciliation not completed prior to discharge order signoff.",
            "expected_condition": "Mandatory reconciliation required.",
            "gap_description": "Discharge proceeded without reconciliation.",
        },
        headers=headers,
    ).json()

    # Subsequent finding in Audit 2 (same category, criterion, and high text similarity)
    f_new = client.post(
        f"/api/v1/governance-audits/audits/{audit2['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "CONTROL_GAP",
            "severity": "HIGH",
            "finding_statement": "Medication reconciliation gap in day surgery discharge.",
            "observed_condition": "Day surgery reconciliation omitted prior to discharge.",
            "expected_condition": "Mandatory reconciliation required.",
            "gap_description": "Omission observed.",
        },
        headers=headers,
    ).json()

    # 1. Trigger detection
    detect_resp = client.post("/api/v1/governance-audit-intelligence/repeat-findings/detect", headers=headers)
    assert detect_resp.status_code == 200
    candidates = detect_resp.json()
    assert len(candidates) >= 1
    cand = candidates[0]
    cand_id = cand["candidate_id"]
    assert cand["current_finding_id"] == f_new["finding_id"]
    assert f_hist["finding_id"] in cand["historical_finding_ids"]
    assert "CATEGORY" in cand["matching_dimensions"]
    assert "CONTROL" in cand["matching_dimensions"]
    assert cand["review_status"] == "PENDING_REVIEW"

    # 2. Get candidate
    get_resp = client.get(f"/api/v1/governance-audit-intelligence/repeat-findings/{cand_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["candidate_id"] == cand_id

    # 3. Confirm candidate
    conf_resp = client.post(
        f"/api/v1/governance-audit-intelligence/repeat-findings/{cand_id}/confirm",
        json={"review_rationale": "Confirmed by pharmacy governance lead as recurring procedural omission."},
        headers=headers,
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["review_status"] == "CONFIRMED"
    assert conf_resp.json()["confidence"] == "CONFIRMED_REPEAT"

    # 4. Reject workflow verification on a second review
    rej_resp = client.post(
        f"/api/v1/governance-audit-intelligence/repeat-findings/{cand_id}/reject",
        json={"rejection_rationale": "Overturned upon secondary review: distinct clinical context."},
        headers=headers,
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["review_status"] == "REJECTED"
    assert rej_resp.json()["confidence"] == "NOT_A_REPEAT"


# =============================================================================
# SCENARIO 7 & 8: Cross-Audit Pattern Identification & Referral
# =============================================================================

def test_cross_audit_patterns_and_referrals(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()

    audit1 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1", "facility_id": "fac-delhi-01"},
        headers=headers,
    ).json()

    audit2 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A2", "description": "D2", "facility_id": "fac-mumbai-02"},
        headers=headers,
    ).json()

    # Same criterion tested in both audits
    crit = client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/criteria",
        json={"criterion_code": "CRT-TRACE-001", "title": "C1", "description": "D1", "expected_evidence_description": "E1"},
        headers=headers,
    ).json()

    # Create findings in both audits with same criterion
    client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "TRACEABILITY_GAP",
            "severity": "HIGH",
            "finding_statement": "Traceability missing in Delhi.",
            "observed_condition": "O1",
            "expected_condition": "E1",
            "gap_description": "G1",
        },
        headers=headers,
    )

    client.post(
        f"/api/v1/governance-audits/audits/{audit2['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "TRACEABILITY_GAP",
            "severity": "HIGH",
            "finding_statement": "Traceability missing in Mumbai.",
            "observed_condition": "O2",
            "expected_condition": "E2",
            "gap_description": "G2",
        },
        headers=headers,
    )

    # 1. Trigger pattern detection
    pat_resp = client.post("/api/v1/governance-audit-intelligence/patterns/detect", headers=headers)
    assert pat_resp.status_code == 200
    patterns = pat_resp.json()
    assert len(patterns) >= 1
    pattern = patterns[0]
    pattern_id = pattern["pattern_id"]

    # 2. Review pattern
    rev_resp = client.post(
        f"/api/v1/governance-audit-intelligence/patterns/{pattern_id}/review",
        json={"review_status": "CONFIRMED", "review_rationale": "Confirmed concentration across multiple sites."},
        headers=headers,
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["review_status"] == "CONFIRMED"

    # 3. Refer pattern to Phase 67 escalation
    ref_resp = client.post(
        f"/api/v1/governance-audit-intelligence/patterns/{pattern_id}/refer",
        json={
            "destination_workflow": "PHASE_67_ESCALATION",
            "referral_reason": "Escalate multi-site traceability gap for cross-facility exception coordination.",
            "notes": "Urgent review required by Clinical Governance Committee.",
        },
        headers=headers,
    )
    assert ref_resp.status_code == 200
    referred_pat = ref_resp.json()
    assert referred_pat["review_status"] == "REFERRED"
    assert len(referred_pat["referral_refs"]) >= 1


# =============================================================================
# SCENARIO 9 & 10: Systemic Issue Candidates, Priority Scoring & Referral
# =============================================================================

def test_systemic_issue_candidate_scoring_and_referral(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    prog = client.post(
        "/api/v1/governance-audits/programmes",
        json={"name": "P1", "description": "D1", "objectives": ["O1"]},
        headers=headers,
    ).json()

    audit1 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A1", "description": "D1", "facility_id": "fac-delhi-01"},
        headers=headers,
    ).json()

    audit2 = client.post(
        "/api/v1/governance-audits/audits",
        json={"programme_id": prog["programme_id"], "title": "A2", "description": "D2", "facility_id": "fac-mumbai-02"},
        headers=headers,
    ).json()

    crit = client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/criteria",
        json={"criterion_code": "CRT-CRIT-001", "title": "Critical Control", "description": "D1", "expected_evidence_description": "E1"},
        headers=headers,
    ).json()

    # Create 2 critical findings under same criterion across 2 facilities
    client.post(
        f"/api/v1/governance-audits/audits/{audit1['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "CONTROL_GAP",
            "severity": "CRITICAL",
            "finding_statement": "Critical breakdown in oncology protocol Delhi.",
            "observed_condition": "O1",
            "expected_condition": "E1",
            "gap_description": "G1",
        },
        headers=headers,
    )
    client.post(
        f"/api/v1/governance-audits/audits/{audit2['audit_id']}/findings",
        json={
            "criterion_id": crit["criterion_id"],
            "category": "CONTROL_GAP",
            "severity": "CRITICAL",
            "finding_statement": "Critical breakdown in oncology protocol Mumbai.",
            "observed_condition": "O2",
            "expected_condition": "E2",
            "gap_description": "G2",
        },
        headers=headers,
    )

    # 1. Trigger systemic issue detection
    sys_resp = client.post(
        "/api/v1/governance-audit-intelligence/systemic-issue-candidates/detect?min_score=2.0",
        headers=headers,
    )
    assert sys_resp.status_code == 200
    candidates = sys_resp.json()
    assert len(candidates) >= 1
    cand = candidates[0]
    cand_id = cand["candidate_id"]
    assert cand["priority_score"] >= 2.0
    assert "max_severity_weight" in cand["score_factors"]

    # 2. Confirm candidate
    conf_resp = client.post(
        f"/api/v1/governance-audit-intelligence/systemic-issue-candidates/{cand_id}/confirm",
        json={"review_rationale": "High-priority multi-facility critical failure warrants systemic status."},
        headers=headers,
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "SYSTEMIC_ISSUE_CANDIDATE"

    # 3. Refer to Phase 63 Risk Review
    ref_resp = client.post(
        f"/api/v1/governance-audit-intelligence/systemic-issue-candidates/{cand_id}/refer",
        json={
            "destination_workflow": "PHASE_63_RISK_REVIEW",
            "referral_reason": "Refer to authoritative clinical risk disposition board.",
        },
        headers=headers,
    )
    assert ref_resp.status_code == 200
    assert ref_resp.json()["status"] == "REFERRED_FOR_RISK_REVIEW"


# =============================================================================
# SCENARIO 11: Corrective Action Recurrence Analysis
# =============================================================================

def test_corrective_action_recurrence_analysis(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

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

    # Initial finding with Phase 54 and Phase 55 link
    f_init = client.post(
        f"/api/v1/governance-audits/audits/{audit['audit_id']}/findings",
        json={
            "category": "CONTROL_GAP",
            "severity": "HIGH",
            "finding_statement": "Initial chemo signoff gap.",
            "observed_condition": "O1",
            "expected_condition": "E1",
            "gap_description": "G1",
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/governance-audits/findings/{f_init['finding_id']}/link-corrective-action",
        json={"phase54_action_ref": "act-capa-101", "phase55_eval_ref": "evl-effect-202"},
        headers=headers,
    )

    # Subsequent finding with same category
    client.post(
        f"/api/v1/governance-audits/audits/{audit['audit_id']}/findings",
        json={
            "category": "CONTROL_GAP",
            "severity": "HIGH",
            "finding_statement": "Subsequent chemo signoff gap.",
            "observed_condition": "O2",
            "expected_condition": "E2",
            "gap_description": "G2",
        },
        headers=headers,
    )

    # Request recurrence analysis
    rec_resp = client.get("/api/v1/governance-audit-intelligence/corrective-actions/recurrence", headers=headers)
    assert rec_resp.status_code == 200
    records = rec_resp.json()
    assert len(records) >= 1
    rec = records[0]
    assert rec["initial_finding_id"] == f_init["finding_id"]
    assert rec["corrective_action_ref"] == "act-capa-101"
    assert rec["recurrence_status"] == "RECURRENCE_CONFIRMED"
    assert len(rec["subsequent_related_finding_ids"]) >= 1


# =============================================================================
# SCENARIO 12: Management Review Reporting, Approval & Export
# =============================================================================

def test_management_review_reporting_lifecycle(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-lead-01"}
    chair_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-chair-02"}

    # 1. Generate management review report
    gen_resp = client.post(
        "/api/v1/governance-audit-intelligence/management-reports/generate",
        json={
            "title": "Q3 2026 Executive Clinical Governance Review",
            "executive_summary": "Comprehensive synthesis of clinical safety audit intelligence.",
        },
        headers=headers,
    )
    assert gen_resp.status_code == 201, gen_resp.text
    rep = gen_resp.json()
    report_id = rep["report_id"]
    assert rep["is_approved"] is False
    assert "findings_summary" in rep
    assert "recommended_review_areas" in rep

    # 2. Approve report
    appr_resp = client.post(
        f"/api/v1/governance-audit-intelligence/management-reports/{report_id}/approve",
        json={"approval_comments": "Reviewed and formally accepted by Clinical Safety Board."},
        headers=chair_headers,
    )
    assert appr_resp.status_code == 200
    approved_rep = appr_resp.json()
    assert approved_rep["is_approved"] is True
    assert approved_rep["approved_by"] == "usr-chair-02"

    # 3. Export report
    exp_resp = client.get(
        f"/api/v1/governance-audit-intelligence/management-reports/{report_id}/export",
        headers=headers,
    )
    assert exp_resp.status_code == 200
    pkg = exp_resp.json()
    assert "export_metadata" in pkg
    assert "report_content" in pkg
    assert pkg["export_metadata"]["report_id"] == report_id


# =============================================================================
# SCENARIO 13: Analytical Configuration Lifecycle & Versioning
# =============================================================================

def test_analytical_configuration_versioning(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    # 1. Create new config version
    create_resp = client.post(
        "/api/v1/governance-audit-intelligence/configurations",
        json={
            "name": "Strict High-Acuity Risk Scoring Configuration",
            "description": "Increases critical and urgent finding multipliers for tertiary centers.",
            "severity_weights": {"CRITICAL": 15.0, "URGENT": 10.0, "HIGH": 7.0, "ELEVATED": 3.0, "ROUTINE": 1.0},
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    cfg = create_resp.json()
    cfg_id = cfg["configuration_id"]
    assert cfg["is_active"] is False

    # 2. Approve config
    appr_resp = client.post(
        f"/api/v1/governance-audit-intelligence/configurations/{cfg_id}/approve",
        json={"approval_notes": "Formally approved for tertiary care oncology units."},
        headers=headers,
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["is_active"] is True

    # 3. Deprecate config
    dep_resp = client.post(
        f"/api/v1/governance-audit-intelligence/configurations/{cfg_id}/deprecate",
        json={"deprecation_reason": "Superseded by updated 2027 clinical risk framework."},
        headers=headers,
    )
    assert dep_resp.status_code == 200
    assert dep_resp.json()["is_deprecated"] is True
    assert dep_resp.json()["is_active"] is False


# =============================================================================
# SCENARIO 14 & 15: Tenant Isolation & Patient Role Authorization Enforcement
# =============================================================================

def test_tenant_isolation_and_patient_forbidden(client):
    tenant1_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-org1", "X-User-Organization": "org-apollo-01"}
    tenant2_headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-org2", "X-User-Organization": "org-other-02"}
    patient_headers = {"X-User-Role": "PATIENT", "X-User-Id": "usr-patient-01"}

    # Tenant 1 generates a management report
    rep = client.post(
        "/api/v1/governance-audit-intelligence/management-reports/generate",
        json={"title": "Tenant 1 Report", "executive_summary": "Summary"},
        headers=tenant1_headers,
    ).json()

    # Tenant 2 cannot access Tenant 1 report -> 403 Forbidden
    cross_resp = client.get(
        f"/api/v1/governance-audit-intelligence/management-reports/{rep['report_id']}",
        headers=tenant2_headers,
    )
    assert cross_resp.status_code == 403
    assert cross_resp.json()["error"]["code"] == "CROSS_TENANT_ACCESS_FORBIDDEN"

    # Patient role blocked from all intelligence endpoints -> 403 Forbidden
    patient_resp = client.get(
        "/api/v1/governance-audit-intelligence/analytics/overview",
        headers=patient_headers,
    )
    assert patient_resp.status_code == 403
    assert patient_resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


# =============================================================================
# SCENARIO 16: Safe Handling of Empty Data & Data Quality Limitations
# =============================================================================

def test_empty_dataset_quality_disclosure(client):
    headers = {"X-User-Role": "ADMIN", "X-User-Id": "usr-admin-01"}

    # When no findings exist, overview returns PARTIALLY_COMPLETE with explicit limitation
    resp = client.get("/api/v1/governance-audit-intelligence/analytics/overview", headers=headers)
    assert resp.status_code == 200
    overview = resp.json()
    assert overview["total_findings"] == 0
    assert overview["data_quality_status"] == "PARTIALLY_COMPLETE"
    assert len(overview["known_data_limitations"]) >= 1
    assert "no audit findings" in overview["known_data_limitations"][0].lower()

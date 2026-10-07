"""Tests for Phase 53: Clinical Safety Assurance Reporting & Governed Safety Oversight."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.safety_assurance import (
    ControlCategory,
    ControlEffectivenessState,
    AssuranceLifecycleState,
    EvidenceQualityState,
)
from app.schemas.safety_report import (
    SafetyReportType,
    SafetyReportLifecycleState,
    SafetyReportQualityState,
    SafetyReportReviewDecision,
)
from app.repositories.safety_report_repository import safety_report_repository
from app.repositories.safety_assurance_repository import safety_assurance_repository
from app.schemas.safety_assurance import AssuranceEvaluationRecord, AssuranceScopeRecord

from fastapi import Request
from app.api.deps import get_current_user
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext

client = TestClient(app)


def mock_current_user(request: Request) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=request.headers.get("X-User-Id", "usr-789"),
        role=UserRole.ADMIN,
        organization_id=request.headers.get("X-User-Organization", "org-123"),
        facility_id=request.headers.get("X-User-Facility", "fac-456"),
    )


@pytest.fixture(autouse=True)
def reset_repositories():
    """Reset the in-memory repositories before each test."""
    safety_report_repository.reset()
    safety_assurance_repository.reset()
    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    safety_report_repository.reset()
    safety_assurance_repository.reset()

@pytest.fixture
def auth_headers():
    """Returns headers for an authenticated safety officer."""
    return {
        "Authorization": "Bearer test_token",
        "X-User-Role": "SAFETY_OFFICER",
        "X-User-Organization": "org-123",
        "X-User-Facility": "fac-456",
        "X-User-Id": "usr-789",
    }

def seed_assurance_data(org_id: str):
    """Seed Phase 52 assurance data to aggregate into a report."""
    now = datetime.now(timezone.utc)
    
    # 1. Effective Control
    eval1 = AssuranceEvaluationRecord(
        control_id="ctrl-med-1",
        control_version="v1.0",
        control_category=ControlCategory.MEDICATION_SAFETY_GATE,
        lifecycle_state=AssuranceLifecycleState.ASSURANCE_ACCEPTED,
        effectiveness_state=ControlEffectivenessState.EFFECTIVE_OBSERVED,
        evidence_quality=EvidenceQualityState.COMPLETE,
        organization_id=org_id,
        evaluated_at=now - timedelta(hours=1),
        scope=AssuranceScopeRecord(
            control_id="ctrl-med-1",
            control_version="v1.0",
            observation_start=now - timedelta(days=2),
            observation_end=now - timedelta(days=1),
        )
    )
    safety_assurance_repository.save_evaluation(eval1)
    
    # 2. Degraded Control
    eval2 = AssuranceEvaluationRecord(
        control_id="ctrl-triage-1",
        control_version="v2.0",
        control_category=ControlCategory.TRIAGE_SAFETY_GATE,
        lifecycle_state=AssuranceLifecycleState.DEGRADED,
        effectiveness_state=ControlEffectivenessState.DEGRADED,
        evidence_quality=EvidenceQualityState.PARTIAL,
        degradation_state="DEGRADED",
        regression_detected=True,
        organization_id=org_id,
        evaluated_at=now - timedelta(hours=2),
        scope=AssuranceScopeRecord(
            control_id="ctrl-triage-1",
            control_version="v2.0",
            observation_start=now - timedelta(days=2),
            observation_end=now - timedelta(days=1),
        )
    )
    safety_assurance_repository.save_evaluation(eval2)


def test_safety_report_lifecycle(auth_headers):
    """Test requesting, generating, and reviewing a safety report."""
    seed_assurance_data("org-123")
    
    start = datetime.now(timezone.utc) - timedelta(days=7)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    
    # 1. Request Report
    req_payload = {
        "report_type": SafetyReportType.CONTROL_ASSURANCE_SUMMARY.value,
        "time_period_start": start.isoformat(),
        "time_period_end": end.isoformat(),
    }
    
    resp_req = client.post("/api/v1/safety-reports", json=req_payload, headers=auth_headers)
    assert resp_req.status_code == 202
    report_data = resp_req.json()["data"]
    report_id = report_data["report_id"]
    assert report_data["lifecycle_state"] == SafetyReportLifecycleState.REQUESTED.value
    
    # 2. Generate Report
    resp_gen = client.post(f"/api/v1/safety-reports/{report_id}/generate", headers=auth_headers)
    assert resp_gen.status_code == 202
    gen_data = resp_gen.json()["data"]
    
    # Verify aggregation
    distribution = gen_data["distribution"]
    assert distribution["total_controls_evaluated"] == 2
    assert distribution["effective_observed"] == 1
    assert distribution["degraded"] == 1
    
    # Verify report quality (since one is PARTIAL, overall should not be HIGH_CONFIDENCE)
    assert gen_data["quality_state"] == SafetyReportQualityState.PARTIAL_EVIDENCE.value
    
    # Verify degradations mapped correctly
    assert gen_data["degradations_detected"] == 1
    assert gen_data["regressions_detected"] == 1
    
    # With partial evidence/degradations, review should be required
    assert gen_data["lifecycle_state"] == SafetyReportLifecycleState.REVIEW_REQUIRED.value
    
    # 3. Review Report
    resp_rev = client.post(
        f"/api/v1/safety-reports/{report_id}/review",
        json={
            "report_version": gen_data["report_version"],
            "decision": SafetyReportReviewDecision.ACCEPT_WITH_LIMITATIONS.value,
            "review_summary": "Report accepted, noting degradation in triage control.",
        },
        headers=auth_headers
    )
    assert resp_rev.status_code == 200
    rev_data = resp_rev.json()["data"]
    assert rev_data["lifecycle_state"] == SafetyReportLifecycleState.APPROVED_FOR_USE.value
    
    # 4. Publish Report
    resp_pub = client.post(f"/api/v1/safety-reports/{report_id}/publish", headers=auth_headers)
    assert resp_pub.status_code == 200
    pub_data = resp_pub.json()["data"]
    assert pub_data["lifecycle_state"] == SafetyReportLifecycleState.PUBLISHED.value


def test_safety_report_tenant_isolation(auth_headers):
    """Ensure organization B cannot view organization A's reports."""
    start = datetime.now(timezone.utc) - timedelta(days=7)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    
    # Org A requests a report
    req_payload = {
        "report_type": SafetyReportType.ORGANIZATION_SAFETY_ASSURANCE_REPORT.value,
        "time_period_start": start.isoformat(),
        "time_period_end": end.isoformat(),
    }
    
    resp_req = client.post("/api/v1/safety-reports", json=req_payload, headers=auth_headers)
    report_id = resp_req.json()["data"]["report_id"]
    
    # Org B tries to read the report
    bad_headers = {
        "Authorization": "Bearer test_token",
        "X-User-Role": "SAFETY_OFFICER",
        "X-User-Organization": "org-999", # Different org
        "X-User-Id": "usr-999",
    }
    
    resp_read = client.get(f"/api/v1/safety-reports/{report_id}", headers=bad_headers)
    assert resp_read.status_code == 403

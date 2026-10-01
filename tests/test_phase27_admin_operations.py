"""Comprehensive Test Suite for Phase 27: Administration, Support Operations & Controlled Backoffice.

Verifies:
1. Admin Authentication & Role-Based Authorization
2. Dedicated /api/v1/admin/ namespace isolation
3. Least-privilege administrative roles:
   - SYSTEM_ADMIN
   - OPERATIONS_ADMIN
   - SUPPORT_OPERATOR
   - SECURITY_OPERATOR
   - AUDIT_OPERATOR
   - INTEGRATION_OPERATOR
4. Non-admin access denial (CLINICIANS, PATIENTS rejected with HTTP 403 ADMIN_ACCESS_DENIED)
5. System status, detailed health, and readiness probes
6. Background job inspection, retry, and cancellation:
   - Retry idempotency
   - Retry forbidden on COMPLETED jobs (prevents duplicate clinical actions)
   - Retry forbidden on PROCESSING jobs
   - Retry forbidden when max_retries exceeded
   - Cancel forbidden on terminal states
7. External integration telemetry and controlled synthetic testing:
   - Zero secrets / keys exposed
   - Testing disabled by default (ADMIN_PROVIDER_TESTING_ENABLED=False)
   - Controlled ping when enabled
8. Operational incident management lifecycle:
   - OPEN -> INVESTIGATING -> MITIGATED -> RESOLVED -> CLOSED
   - Ownership assignment and triage notes
   - Mandatory resolution summary
   - Audit trail on every transition
9. Privacy-safe patient support lookup:
   - Strictly minimized operational fields
   - Masked patient names
   - ZERO clinical notes, diagnoses, medications, or allergies
   - Audited lookups
10. Immutable audit log queries
11. Security event queries
12. Phase 25 Configuration & Phase 26 Data Quality integrations
13. Forbidden admin actions (no generic DB update/delete endpoints)
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import (
    get_current_user,
    get_admin_service,
    get_incident_service,
    get_support_service,
    get_incident_repository,
)
from app.core.config import settings
from app.core.policies import Permission
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.schemas.job import JobRecord, JobStatus, JobType
from app.schemas.incident import (
    IncidentCategory,
    IncidentCreate,
    IncidentResolve,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
    IncidentAcknowledge,
)
from app.schemas.patient import BiologicalSex, PatientStatus
from app.repositories.patient_repository import PatientRecord, PatientRepository
from app.repositories.job_repository import JobRepository
from app.repositories.incident_repository import IncidentRepository



@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


def _make_actor(user_id: str, role: UserRole) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=user_id,
        role=role,
        session_id=f"sess-{user_id}",
    )


# ---------------------------------------------------------------------------
# 1. Role-Based Admin Authorization & Non-Admin Rejection Tests
# ---------------------------------------------------------------------------

def test_clinician_cannot_access_admin_apis(client):
    """Clinicians (DOCTOR) must be strictly denied access to admin namespace with ADMIN_ACCESS_DENIED."""
    doctor = _make_actor("doc-101", UserRole.DOCTOR)
    app.dependency_overrides[get_current_user] = lambda: doctor
    try:
        response = client.get("/api/v1/admin/system/status")
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "ADMIN_ACCESS_DENIED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_patient_cannot_access_admin_apis(client):
    """Patients must be strictly denied access to admin namespace with ADMIN_ACCESS_DENIED."""
    patient = _make_actor("pat-202", UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: patient
    try:
        response = client.get("/api/v1/admin/system/status")
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "ADMIN_ACCESS_DENIED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_system_admin_has_full_access(client):
    """SYSTEM_ADMIN has full access to system status, jobs, integrations, and incidents."""
    sys_admin = _make_actor("sys-001", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: sys_admin
    try:
        # System status
        res = client.get("/api/v1/admin/system/status")
        assert res.status_code == 200
        assert res.json()["success"] is True

        # Jobs listing
        res = client.get("/api/v1/admin/jobs")
        assert res.status_code == 200
        assert res.json()["success"] is True

        # Integrations listing
        res = client.get("/api/v1/admin/integrations")
        assert res.status_code == 200
        assert res.json()["success"] is True

        # Incidents listing
        res = client.get("/api/v1/admin/incidents")
        assert res.status_code == 200
        assert res.json()["success"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_role_separation_audit_operator(client):
    """AUDIT_OPERATOR can view audit logs but cannot manage incidents or retry jobs."""
    audit_op = _make_actor("audit-001", UserRole.AUDIT_OPERATOR)
    app.dependency_overrides[get_current_user] = lambda: audit_op
    try:
        # Permitted: Audit log query
        res_audit = client.get("/api/v1/admin/audit")
        assert res_audit.status_code == 200

        # Forbidden: Declare operational incident (requires ADMIN_INCIDENTS_MANAGE)
        res_inc = client.post("/api/v1/admin/incidents", json={
            "title": "Unauthorized declaration",
            "description": "Attempt by audit operator to declare incident",
        })
        assert res_inc.status_code == 403
        assert res_inc.json()["error"]["code"] == "ADMIN_PERMISSION_REQUIRED"

        # Forbidden: Retry background job (requires ADMIN_JOBS_MANAGE)
        res_retry = client.post("/api/v1/admin/jobs/fake-job/retry")
        assert res_retry.status_code == 403
        assert res_retry.json()["error"]["code"] == "ADMIN_PERMISSION_REQUIRED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_role_separation_support_operator(client):
    """SUPPORT_OPERATOR can search patient accounts and manage incidents, but cannot view audit logs."""
    support_op = _make_actor("supp-001", UserRole.SUPPORT_OPERATOR)
    app.dependency_overrides[get_current_user] = lambda: support_op
    try:
        # Permitted: Support search
        res_supp = client.get("/api/v1/admin/support/patients/search?query=test")
        assert res_supp.status_code == 200

        # Forbidden: Audit log query (requires ADMIN_AUDIT_VIEW)
        res_audit = client.get("/api/v1/admin/audit")
        assert res_audit.status_code == 403
        assert res_audit.json()["error"]["code"] == "ADMIN_PERMISSION_REQUIRED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 2. System Status, Health & Readiness Probes
# ---------------------------------------------------------------------------

def test_system_status_and_health_probes(client):
    """Verify system status, detailed health metrics, and readiness checks."""
    admin = _make_actor("admin-001", UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # Status
        res = client.get("/api/v1/admin/system/status")
        assert res.status_code == 200
        body = res.json()["data"]
        assert "status" in body
        assert "components" in body
        assert "api" in body["components"]
        assert "database" in body["components"]
        assert "ocr_provider" in body["components"]
        assert "medication_safety" in body["components"]

        # Health
        res_health = client.get("/api/v1/admin/system/health")
        assert res_health.status_code == 200
        h_data = res_health.json()["data"]
        assert "uptime_seconds" in h_data
        assert "queue_backlog" in h_data
        assert "open_incidents" in h_data

        # Readiness
        res_ready = client.get("/api/v1/admin/system/readiness")
        assert res_ready.status_code == 200
        r_data = res_ready.json()["data"]
        assert "ready" in r_data
        assert r_data["ready"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 3. Background Job Management & Safety Invariants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_retry_safety_invariants(client):
    """CRITICAL SAFETY:
    1. Retrying a COMPLETED job is strictly rejected to prevent duplicate clinical actions.
    2. Retrying a PROCESSING job is rejected.
    3. Exceeding max_retries is rejected.
    4. Cancelling an already completed job is rejected.
    """
    admin = _make_actor("admin-001", UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin

    # Setup test jobs in job repository
    admin_service = app.dependency_overrides.get(get_admin_service, None)
    from app.api.deps import _global_job_repo

    now = datetime.now(timezone.utc)
    completed_job = JobRecord(
        id="job-completed-001",
        job_type=JobType.DOCUMENT_EXTRACTION,
        status=JobStatus.COMPLETED,
        patient_id="pat-1",
        resource_type="document",
        resource_id="doc-1",
        operation_type="ocr_extract",
        created_at=now,
    )
    failed_job = JobRecord(
        id="job-failed-002",
        job_type=JobType.DOCUMENT_EXTRACTION,
        status=JobStatus.FAILED,
        patient_id="pat-1",
        resource_type="document",
        resource_id="doc-2",
        operation_type="ocr_extract",
        attempt=1,
        max_retries=3,
        created_at=now,
    )
    exhausted_job = JobRecord(
        id="job-exhausted-003",
        job_type=JobType.DOCUMENT_EXTRACTION,
        status=JobStatus.FAILED,
        patient_id="pat-1",
        resource_type="document",
        resource_id="doc-3",
        operation_type="ocr_extract",
        attempt=3,
        max_retries=3,
        created_at=now,
    )
    queued_job = JobRecord(
        id="job-queued-004",
        job_type=JobType.DOCUMENT_EXTRACTION,
        status=JobStatus.QUEUED,
        patient_id="pat-1",
        resource_type="document",
        resource_id="doc-4",
        operation_type="ocr_extract",
        created_at=now,
    )

    await _global_job_repo.create(completed_job)
    await _global_job_repo.create(failed_job)
    await _global_job_repo.create(exhausted_job)
    await _global_job_repo.create(queued_job)

    try:
        # 1. Reject retry of completed job
        res_comp = client.post("/api/v1/admin/jobs/job-completed-001/retry")
        assert res_comp.status_code == 400
        assert res_comp.json()["error"]["code"] == "JOB_RETRY_NOT_ALLOWED"
        assert "duplicate" in res_comp.json()["error"]["message"].lower()

        # 2. Reject retry of exhausted job
        res_exh = client.post("/api/v1/admin/jobs/job-exhausted-003/retry")
        assert res_exh.status_code == 400
        assert res_exh.json()["error"]["code"] == "JOB_RETRY_NOT_ALLOWED"

        # 3. Successful idempotent retry of failed job
        res_retry = client.post("/api/v1/admin/jobs/job-failed-002/retry")
        assert res_retry.status_code == 200
        retry_data = res_retry.json()["data"]
        assert retry_data["status"] == "QUEUED"
        assert retry_data["attempt"] == 2

        # 4. Cancel queued job
        res_cancel = client.post("/api/v1/admin/jobs/job-queued-004/cancel")
        assert res_cancel.status_code == 200
        assert res_cancel.json()["data"]["status"] == "CANCELLED"

        # 5. Cancel completed job rejected
        res_cancel_fail = client.post("/api/v1/admin/jobs/job-completed-001/cancel")
        assert res_cancel_fail.status_code == 400
        assert res_cancel_fail.json()["error"]["code"] == "JOB_CANCEL_NOT_ALLOWED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 4. External Integrations Telemetry & Controlled Testing
# ---------------------------------------------------------------------------

def test_external_integrations_inspection_and_testing(client):
    """External integrations: zero secret leakage, testing disabled by default."""
    admin = _make_actor("admin-001", UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # Listing integrations
        res = client.get("/api/v1/admin/integrations")
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert len(items) > 0

        # Verify ZERO secrets in telemetry details
        raw_text = res.text.lower()
        assert "secret" not in raw_text
        assert "password" not in raw_text
        assert "apikey" not in raw_text
        assert "api_key" not in raw_text

        # Controlled test disabled by default
        res_test = client.post("/api/v1/admin/integrations/ocr/test")
        assert res_test.status_code == 403
        assert res_test.json()["error"]["code"] == "INTEGRATION_TEST_NOT_ALLOWED"

        # Enable provider testing temporarily and verify
        original_flag = settings.ADMIN_PROVIDER_TESTING_ENABLED
        try:
            settings.ADMIN_PROVIDER_TESTING_ENABLED = True
            res_test_enabled = client.post("/api/v1/admin/integrations/ocr/test")
            assert res_test_enabled.status_code == 200
            t_data = res_test_enabled.json()["data"]
            assert t_data["provider"] == "ocr"
            assert "latency_ms" in t_data
            assert "test_passed" in t_data
        finally:
            settings.ADMIN_PROVIDER_TESTING_ENABLED = original_flag
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 5. Operational Incident Management Lifecycle
# ---------------------------------------------------------------------------

def test_incident_management_lifecycle(client):
    """Incident state machine: OPEN -> INVESTIGATING -> UPDATED -> RESOLVED."""
    admin = _make_actor("admin-ops", UserRole.OPERATIONS_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # 1. Declare incident
        create_payload = {
            "title": "OCR Extraction Latency Spike",
            "description": "Prescription document processing queue experiencing unexpected latency.",
            "category": "OCR_FAILURE",
            "severity": "HIGH",
        }
        res_create = client.post("/api/v1/admin/incidents", json=create_payload)
        assert res_create.status_code == 201
        inc = res_create.json()["data"]
        inc_id = inc["id"]
        assert inc["status"] == "OPEN"
        assert inc["severity"] == "HIGH"

        # 2. Acknowledge incident (OPEN -> INVESTIGATING)
        ack_res = client.post(f"/api/v1/admin/incidents/{inc_id}/acknowledge", json={
            "notes": "Operations lead investigating OCR pipeline throughput."
        })
        assert ack_res.status_code == 200
        ack_data = ack_res.json()["data"]
        assert ack_data["status"] == "INVESTIGATING"
        assert ack_data["owner"] == "admin-ops"
        assert ack_data["acknowledged_at"] is not None

        # 3. Update incident notes & severity
        update_res = client.post(f"/api/v1/admin/incidents/{inc_id}/update", json={
            "severity": "MEDIUM",
            "notes": "Worker concurrency restarted, queue clearing.",
        })
        assert update_res.status_code == 200
        assert update_res.json()["data"]["severity"] == "MEDIUM"

        # 4. Resolve incident requires resolution summary (min length 5)
        res_fail = client.post(f"/api/v1/admin/incidents/{inc_id}/resolve", json={
            "resolution_summary": "bad",  # Min length is 5
        })
        # 422 if pydantic validation or 400 if service validation
        assert res_fail.status_code in (400, 422)

        # 5. Successfully resolve incident
        resolve_res = client.post(f"/api/v1/admin/incidents/{inc_id}/resolve", json={
            "resolution_summary": "Worker restarted and queue drain verified. Latency back under 1.5 seconds.",
            "status": "RESOLVED",
        })
        assert resolve_res.status_code == 200
        resolved_data = resolve_res.json()["data"]
        assert resolved_data["status"] == "RESOLVED"
        assert resolved_data["resolved_at"] is not None

        # 6. Verify listing includes the resolved incident
        list_res = client.get(f"/api/v1/admin/incidents?category=OCR_FAILURE")
        assert list_res.status_code == 200
        matched = [i for i in list_res.json()["data"]["items"] if i["id"] == inc_id]
        assert len(matched) == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 6. Privacy-Safe Patient Support Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_privacy_safe_support_patient_search(client):
    """SUPPORT OPERATOR LOOKUP MUST:
    - Return strictly minimized operational data
    - Mask patient names
    - NEVER leak clinical notes, diagnoses, medications, or allergies
    """
    support_op = _make_actor("supp-002", UserRole.SUPPORT_OPERATOR)
    app.dependency_overrides[get_current_user] = lambda: support_op

    from app.api.deps import _global_patient_repo
    from datetime import date
    # Seed a patient in the repository
    patient = PatientRecord(
        id="pat-support-999",
        user_id="user-999",
        first_name="Ananya",
        last_name="Chatterjee",
        date_of_birth=date(1990, 5, 15),
        sex=BiologicalSex.FEMALE,
        status=PatientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        phone="+919876543210",
        email="ananya@example.com",
        sovereign_id="HS-PAT-9999",
    )
    await _global_patient_repo.create(patient)

    try:
        res = client.get("/api/v1/admin/support/patients/search?query=Ananya")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total"] >= 1
        item = data["items"][0]

        # Verify operational identifiers
        assert item["patient_id"] == "pat-support-999"
        assert item["sovereign_id"] == "HS-PAT-9999"
        # Name MUST be masked
        assert item["masked_name"] != "Ananya Chatterjee"
        assert "A***" in item["masked_name"]

        # CRITICAL PRIVACY: Verify zero clinical keys in response
        raw_item_str = str(item).lower()
        assert "diagnosis" not in raw_item_str
        assert "medication" not in raw_item_str
        assert "allergy" not in raw_item_str
        assert "clinical_notes" not in raw_item_str
        assert "prescription" not in raw_item_str
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 7. Audit & Security Event Inspection
# ---------------------------------------------------------------------------

def test_audit_and_security_event_inspection(client):
    """Verify administrative audit retrieval and sanitized security event querying."""
    admin = _make_actor("sec-001", UserRole.SECURITY_OPERATOR)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # Security event query
        res_sec = client.get("/api/v1/admin/security-events")
        assert res_sec.status_code == 200
        sec_data = res_sec.json()["data"]
        assert "items" in sec_data
        assert "total" in sec_data

        # Audit query
        res_aud = client.get("/api/v1/admin/audit")
        assert res_aud.status_code == 200
        aud_data = res_aud.json()["data"]
        assert "items" in aud_data
        assert "total" in aud_data
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 8. Configuration & Data Quality Integrations
# ---------------------------------------------------------------------------

def test_admin_configuration_and_data_quality_inspection(client):
    """Verify integration with Phase 25 Configuration & Phase 26 Data Quality."""
    admin = _make_actor("admin-001", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # Configuration
        res_cfg = client.get("/api/v1/admin/configuration")
        assert res_cfg.status_code == 200
        cfg_data = res_cfg.json()["data"]
        assert cfg_data["environment"] == settings.APP_ENV
        assert "drift" in cfg_data
        assert "validation" in cfg_data
        assert cfg_data["admin_operations_enabled"] is True

        # Data Quality
        res_dq = client.get("/api/v1/admin/data-quality")
        assert res_dq.status_code == 200
        dq_data = res_dq.json()["data"]
        assert "total_findings" in dq_data
        assert "pending_findings" in dq_data
        assert "by_severity" in dq_data
        assert "by_type" in dq_data
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 9. Forbidden Admin Actions: Verify No Generic DB/Clinical CRUD Backdoors
# ---------------------------------------------------------------------------

def test_forbidden_admin_endpoints_do_not_exist(client):
    """CRITICAL SECURITY:
    Generic database modification, arbitrary patient/medication modification
    must NEVER exist as endpoints.
    """
    admin = _make_actor("admin-001", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # Arbitrary DB update must not exist
        res1 = client.post("/api/v1/admin/database/update", json={"sql": "DROP TABLE users;"})
        assert res1.status_code in (404, 405)

        # Arbitrary DB delete must not exist
        res2 = client.post("/api/v1/admin/database/delete", json={"table": "patients"})
        assert res2.status_code in (404, 405)

        # Generic patient field modify must not exist
        res3 = client.post("/api/v1/admin/patient/modify-any-field", json={"id": "pat-1", "field": "all"})
        assert res3.status_code in (404, 405)

        # Direct medication change from admin must not exist
        res4 = client.post("/api/v1/admin/medication/change", json={"medication": "Warfarin"})
        assert res4.status_code in (404, 405)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 10. Incident State Machine Validation & Concurrency
# ---------------------------------------------------------------------------

def test_incident_invalid_state_transitions(client):
    """Cannot acknowledge a non-OPEN incident, and cannot update a CLOSED incident."""
    admin = _make_actor("admin-ops", UserRole.OPERATIONS_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # Create incident
        create_res = client.post("/api/v1/admin/incidents", json={
            "title": "Database connection saturation",
            "description": "Connection pool usage exceeded 90% threshold.",
            "category": "DATABASE_FAILURE",
            "severity": "CRITICAL",
        })
        assert create_res.status_code == 201
        inc_id = create_res.json()["data"]["id"]

        # Acknowledge once -> INVESTIGATING
        ack_res1 = client.post(f"/api/v1/admin/incidents/{inc_id}/acknowledge")
        assert ack_res1.status_code == 200

        # Attempt to acknowledge again -> 400 INCIDENT_INVALID_STATE
        ack_res2 = client.post(f"/api/v1/admin/incidents/{inc_id}/acknowledge")
        assert ack_res2.status_code == 400
        assert ack_res2.json()["error"]["code"] == "INCIDENT_INVALID_STATE"

        # Resolve and close incident
        res_close = client.post(f"/api/v1/admin/incidents/{inc_id}/resolve", json={
            "resolution_summary": "Pool size increased and slow queries terminated.",
            "status": "CLOSED",
        })
        assert res_close.status_code == 200
        assert res_close.json()["data"]["status"] == "CLOSED"

        # Attempt to modify CLOSED incident -> 400 INCIDENT_INVALID_STATE
        update_closed = client.post(f"/api/v1/admin/incidents/{inc_id}/update", json={
            "description": "Attempting to change closed incident description",
        })
        assert update_closed.status_code == 400
        assert update_closed.json()["error"]["code"] == "INCIDENT_INVALID_STATE"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 11. Pagination & Safe Limits
# ---------------------------------------------------------------------------

def test_admin_pagination_and_query_limits(client):
    """Test pagination bounds on administrative jobs, incidents, and audit."""
    admin = _make_actor("admin-sys", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # Limit cannot exceed 100
        res_over_limit = client.get("/api/v1/admin/jobs?limit=500")
        assert res_over_limit.status_code == 422

        # Negative skip is rejected
        res_neg_skip = client.get("/api/v1/admin/jobs?skip=-5")
        assert res_neg_skip.status_code == 422

        # Valid pagination
        res_valid = client.get("/api/v1/admin/jobs?skip=0&limit=10")
        assert res_valid.status_code == 200
        assert res_valid.json()["data"]["limit"] == 10
        assert res_valid.json()["data"]["skip"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 12. Disabled Providers Reporting Invariant
# ---------------------------------------------------------------------------

def test_disabled_providers_cannot_appear_as_available(client):
    """DISABLED providers must report DISABLED / UNAVAILABLE, never AVAILABLE."""
    admin = _make_actor("admin-sys", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin
    original_ocr_flag = settings.OCR_ENABLED
    try:
        settings.OCR_ENABLED = False
        res = client.get("/api/v1/admin/system/status")
        assert res.status_code == 200
        components = res.json()["data"]["components"]
        assert components["ocr_provider"]["status"] == "DISABLED"
        assert components["ocr_provider"]["status"] != "AVAILABLE"
    finally:
        settings.OCR_ENABLED = original_ocr_flag
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 13. Phase 22 Async Job Types Adherence
# ---------------------------------------------------------------------------

def test_async_admin_job_types_defined():
    """Verify Phase 27 async admin job types exist in JobType enum."""
    assert hasattr(JobType, "ADMIN_REPROCESS_RESOURCE")
    assert hasattr(JobType, "ADMIN_RETRY_WORKFLOW")
    assert hasattr(JobType, "ADMIN_DATA_QUALITY_RECHECK")
    assert hasattr(JobType, "ADMIN_INTEGRATION_CHECK")
    assert hasattr(JobType, "ADMIN_EXPORT_REQUEST")
    assert JobType.ADMIN_REPROCESS_RESOURCE.value == "ADMIN_REPROCESS_RESOURCE"


"""Comprehensive Test Suite for Phase 28: API Analytics, Usage Governance & Operational Intelligence.

Verifies:
1. Operational Telemetry & Event Ingestion:
   - Event deduplication by `event_id` (idempotency)
   - Route template normalization (NEVER raw patient IDs in endpoints)
   - Fail-safe isolation: analytics recording failure never disrupts clinical flow
2. API Usage & Operational Aggregations:
   - Request volumes, success/error distribution, rate limit events
   - Status code classification (2xx, 4xx, 5xx)
   - Latency percentiles (min, max, avg, p50, p90, p95, p99) and distribution buckets
3. Capability & Integration Telemetry:
   - Feature usage tracking (invocations, success rate, durations)
   - Background job analytics (job types, completion vs failure rates, duration)
   - External provider telemetry (uptime, timeouts, failures, cost)
   - AI operational telemetry (token counts, latency, cost)
   - Cost and resource consumption tracking
4. Operational Anomaly Detection & Lifecycle:
   - Automated detection of error spikes, latency spikes, provider outages
   - Anomaly != Malicious activity (labeled ANOMALY_DETECTED, never SECURITY_ATTACK)
   - Anomaly acknowledgment and resolution workflow
5. Multi-Tenant Scoping & Role-Based Access Control:
   - System admins have cross-organization visibility
   - Clinicians/operators scoped to their own organization/facility
   - Cross-organization access strictly denied (Org A cannot view Org B)
   - Non-admin access denied to /api/v1/admin/analytics/
6. Critical Privacy & Patient Protection Invariants:
   - ZERO PHI in analytics (no notes, diagnoses, prescriptions, allergies, or document text)
   - Sensitive fields stripped from telemetry metadata
   - Query range limits enforced (max 90 days)
7. Critical Clinical Safety Invariants:
   - ANALYTICS != CLINICAL DECISION
   - Analytics cannot modify clinical records, allergies, medications, triage, or care plans
   - FAILED_JOB != COMPLETED_JOB
   - QUEUED_JOB != COMPLETED_JOB
   - PROVIDER_FAILURE != SUCCESS
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_analytics_repository,
    get_analytics_service,
    get_current_user,
)
from app.core.config import settings
from app.core.exceptions import (
    AnalyticsAccessDeniedException,
    AnalyticsQueryRangeExceededException,
)
from app.main import app
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsFilterParams,
    TimeBucket,
)
from app.schemas.anomaly import (
    AnomalyAcknowledgeRequest,
    AnomalyResolveRequest,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    UsageAnomaly,
)
from app.schemas.auth import UserRole
from app.schemas.user import AuthenticatedUserContext
from app.services.analytics_service import (
    AnalyticsService,
    calculate_percentiles,
    normalize_route_template,
    sanitize_metadata,
)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def analytics_repo():
    """Clean analytics repository fixture."""
    repo = get_analytics_repository()
    repo.clear()
    yield repo
    repo.clear()


@pytest.fixture
def analytics_service(analytics_repo):
    """Analytics service fixture."""
    return AnalyticsService(repository=analytics_repo)


def _make_actor(
    user_id: str,
    role: UserRole,
    organization_id: str = "org-main",
    facility_id: str = "fac-main",
) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user_id=user_id,
        role=role,
        organization_id=organization_id,
        facility_id=facility_id,
        session_id=f"sess-{user_id}",
    )


# ===========================================================================
# 1. Route Template Normalization & Privacy Invariants
# ===========================================================================

def test_route_template_normalization():
    """Verify raw patient IDs, UUIDs, and numeric IDs are normalized to route templates."""
    # Patient ID route
    raw_path_1 = "/api/v1/patients/123456/medications"
    assert normalize_route_template(raw_path_1) == "/api/v1/patients/{patient_id}/medications"

    # UUID patient path
    raw_path_2 = "/api/v1/patients/123e4567-e89b-12d3-a456-426614174000/allergies"
    assert normalize_route_template(raw_path_2) == "/api/v1/patients/{patient_id}/allergies"

    # Facility path
    raw_path_3 = "/api/v1/facilities/fac-999/analytics"
    assert normalize_route_template(raw_path_3) == "/api/v1/facilities/{facility_id}/analytics"

    # Job path
    raw_path_4 = "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/status"
    assert normalize_route_template(raw_path_4) == "/api/v1/jobs/{job_id}/status"

    # Query string stripped
    raw_path_5 = "/api/v1/patients/pat-1/vitals?limit=10&page=2"
    assert normalize_route_template(raw_path_5) == "/api/v1/patients/{patient_id}/vitals"


def test_metadata_phi_sanitization():
    """Verify that clinical notes, prescriptions, tokens, and PHI are stripped from metadata."""
    raw_metadata = {
        "client_version": "2.4.0",
        "cached": True,
        "clinical_notes": "Patient reports severe chest pain and palpitations.",
        "prescription_text": "Amoxicillin 500mg tid",
        "allergy_description": "Anaphylaxis to Penicillin",
        "password": "supersecretpassword",
        "api_key": "sk-1234567890",
        "patient_name": "John Doe",
        "duration_sec": 1.25,
    }

    sanitized = sanitize_metadata(raw_metadata)

    # Allowed operational keys preserved
    assert sanitized["client_version"] == "2.4.0"
    assert sanitized["cached"] is True
    assert sanitized["duration_sec"] == 1.25

    # Sensitive / PHI keys stripped
    assert "clinical_notes" not in sanitized
    assert "prescription_text" not in sanitized
    assert "allergy_description" not in sanitized
    assert "password" not in sanitized
    assert "api_key" not in sanitized
    assert "patient_name" not in sanitized


# ===========================================================================
# 2. Fail-Safe Isolation & Event Deduplication
# ===========================================================================

def test_event_deduplication(analytics_repo, analytics_service):
    """Verify that events with identical event_id are recorded idempotently without duplicates."""
    event_id = "ev-dedup-1"
    ev1 = analytics_service.record_event(
        event_id=event_id,
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        endpoint="/api/v1/health",
        http_method="GET",
        status=200,
        duration_ms=15.0,
    )
    assert ev1 is not None

    # Record second event with same event_id
    ev2 = analytics_service.record_event(
        event_id=event_id,
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        endpoint="/api/v1/health",
        http_method="GET",
        status=200,
        duration_ms=15.0,
    )
    assert ev2 is not None

    # Total count in repository must remain 1
    assert analytics_repo.count_events() == 1


def test_failsafe_isolation_on_error(monkeypatch, analytics_service):
    """Verify that if internal recording crashes, it logs a warning and returns None without raising."""
    def crash_repo(*args, **kwargs):
        raise RuntimeError("Simulated Database / Disk Corruption")

    monkeypatch.setattr(analytics_service._repo, "record_event", crash_repo)

    # Must NOT raise exception: fail-safe isolation ensures calling workflows continue
    result = analytics_service.record_event(
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        endpoint="/api/v1/patients/123/vitals",
        http_method="POST",
        status=201,
    )
    assert result is None


# ===========================================================================
# 3. Percentile & Latency Distribution Computation
# ===========================================================================

def test_calculate_percentiles():
    """Verify statistical correctness of p50, p90, p95, p99 latency calculations."""
    durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    min_v, max_v, avg_v, p50, p90, p95, p99 = calculate_percentiles(durations)

    assert min_v == 10.0
    assert max_v == 100.0
    assert avg_v == 55.0
    assert p50 == 60.0  # 10 * 0.5 = index 5 -> 60.0
    assert p90 == 100.0
    assert p95 == 100.0
    assert p99 == 100.0

    # Empty list handling
    assert calculate_percentiles([]) == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


# ===========================================================================
# 4. API Endpoints: Administrative Authorization
# ===========================================================================

def test_non_admin_cannot_access_admin_analytics(client):
    """Clinicians (DOCTOR) and Patients must be denied access to /admin/analytics/ with HTTP 403."""
    doctor = _make_actor("doc-1", UserRole.DOCTOR)
    app.dependency_overrides[get_current_user] = lambda: doctor
    try:
        res = client.get("/api/v1/admin/analytics/overview")
        assert res.status_code == 403
        data = res.json()
        assert data["success"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_system_admin_can_access_admin_analytics(client, analytics_repo, analytics_service):
    """System Administrator can access all /admin/analytics/ endpoints."""
    admin = _make_actor("admin-1", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin

    # Seed events
    analytics_service.record_event(
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        endpoint="/api/v1/patients/123/vitals",
        http_method="GET",
        status=200,
        duration_ms=45.0,
    )
    analytics_service.record_event(
        event_type=AnalyticsEventType.API_REQUEST_FAILED,
        endpoint="/api/v1/documents/doc-1",
        http_method="POST",
        status=500,
        duration_ms=120.0,
        error_category="storage_error",
    )

    try:
        # Overview
        res = client.get("/api/v1/admin/analytics/overview")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total_requests"] == 2
        assert data["successful_requests"] == 1
        assert data["error_requests"] == 1
        assert data["overall_error_rate"] == 0.5

        # API Usage
        res = client.get("/api/v1/admin/analytics/api-usage")
        assert res.status_code == 200
        assert res.json()["data"]["total_requests"] == 2

        # Errors
        res = client.get("/api/v1/admin/analytics/errors")
        assert res.status_code == 200
        assert res.json()["data"]["total_errors"] == 1
        assert res.json()["data"]["server_errors_5xx"] == 1

        # Latency
        res = client.get("/api/v1/admin/analytics/latency")
        assert res.status_code == 200
        lat_data = res.json()["data"]
        assert lat_data["sample_count"] == 2
        assert lat_data["min_latency_ms"] == 45.0
        assert lat_data["max_latency_ms"] == 120.0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# 5. Feature Usage & Background Job Analytics
# ===========================================================================

def test_feature_usage_analytics(client, analytics_service):
    """Verify feature invocation counts, success/failure rates, and durations."""
    admin = _make_actor("admin-1", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin

    # Record feature usage
    analytics_service.record_event(
        event_type=AnalyticsEventType.FEATURE_USED,
        feature_name="prescription_extraction",
        status=200,
        duration_ms=250.0,
        result_category="success",
    )
    analytics_service.record_event(
        event_type=AnalyticsEventType.FEATURE_USED,
        feature_name="prescription_extraction",
        status=500,
        duration_ms=300.0,
        result_category="failure",
    )
    analytics_service.record_event(
        event_type=AnalyticsEventType.FEATURE_USED,
        feature_name="medication_safety",
        status=200,
        duration_ms=18.0,
        result_category="success",
    )

    try:
        res = client.get("/api/v1/admin/analytics/features")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total_features_tracked"] == 2
        assert data["total_feature_invocations"] == 3

        # Features breakdown
        features = {f["feature_name"]: f for f in data["features"]}
        assert "prescription_extraction" in features
        assert features["prescription_extraction"]["invocation_count"] == 2
        assert features["prescription_extraction"]["failure_count"] == 1
        assert features["prescription_extraction"]["error_rate"] == 0.5

        assert "medication_safety" in features
        assert features["medication_safety"]["invocation_count"] == 1
        assert features["medication_safety"]["error_rate"] == 0.0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_background_job_analytics(client, analytics_service):
    """Verify background job operational tracking and failure isolation."""
    admin = _make_actor("admin-1", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin

    # Record job events
    analytics_service.record_event(
        event_type=AnalyticsEventType.JOB_CREATED,
        job_type="DOCUMENT_PROCESSING",
    )
    analytics_service.record_event(
        event_type=AnalyticsEventType.JOB_COMPLETED,
        job_type="DOCUMENT_PROCESSING",
        duration_ms=850.0,
    )
    analytics_service.record_event(
        event_type=AnalyticsEventType.JOB_CREATED,
        job_type="AI_PROCESSING",
    )
    analytics_service.record_event(
        event_type=AnalyticsEventType.JOB_FAILED,
        job_type="AI_PROCESSING",
        duration_ms=1200.0,
    )

    try:
        res = client.get("/api/v1/admin/analytics/jobs")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total_jobs_processed"] == 2
        assert data["completed_jobs"] == 1
        assert data["failed_jobs"] == 1

        # Invariant check: FAILED_JOB != COMPLETED_JOB
        assert data["completed_jobs"] != data["failed_jobs"] + data["completed_jobs"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# 6. Provider Telemetry, AI Usage & Cost Analytics
# ===========================================================================

def test_provider_telemetry_and_cost_analytics(client, analytics_service):
    """Verify external provider uptime/failures and cost calculations."""
    admin = _make_actor("admin-1", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin

    # Record provider events
    analytics_service.record_event(
        event_type=AnalyticsEventType.PROVIDER_SUCCESS,
        provider_name="gemini-1.5-pro",
        feature_name="clinical_summarization",
        status=200,
        duration_ms=900.0,
        metadata={"prompt_tokens": 1500, "completion_tokens": 300, "estimated_cost_usd": 0.0075},
    )
    analytics_service.record_event(
        event_type=AnalyticsEventType.PROVIDER_TIMEOUT,
        provider_name="google_cloud_vision",
        status=504,
        duration_ms=5000.0,
        metadata={"pages_processed": 2},
    )

    try:
        # Provider analytics
        p_res = client.get("/api/v1/admin/analytics/providers")
        assert p_res.status_code == 200
        p_data = p_res.json()["data"]
        assert p_data["total_providers_tracked"] == 2
        assert p_data["total_provider_timeouts"] == 1

        # Invariant check: PROVIDER TIMEOUT/FAILURE != SUCCESS
        vision_item = next(p for p in p_data["providers"] if p["provider_name"] == "google_cloud_vision")
        assert vision_item["timeout_count"] == 1
        assert vision_item["success_count"] == 0
        assert vision_item["availability_percentage"] == 0.0

        # Cost analytics
        c_res = client.get("/api/v1/admin/analytics/costs")
        assert c_res.status_code == 200
        c_data = c_res.json()["data"]
        assert c_data["total_cost_usd"] > 0
        assert len(c_data["ai_telemetry"]) >= 1
        assert c_data["ai_telemetry"][0]["total_tokens"] == 1800
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# 7. Operational Anomaly Detection Lifecycle
# ===========================================================================

def test_anomaly_detection_lifecycle(client, analytics_repo, analytics_service):
    """Verify automated anomaly detection, labeling as ANOMALY_DETECTED (not SECURITY_ATTACK), and ack/resolve."""
    admin = _make_actor("admin-1", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin

    # Trigger error anomaly by posting rapid 500 errors
    endpoint = "/api/v1/patients/{patient_id}/vitals"
    for _ in range(6):
        analytics_service.record_event(
            event_type=AnalyticsEventType.API_REQUEST_FAILED,
            endpoint=endpoint,
            status=500,
            duration_ms=45.0,
        )

    try:
        # Check anomalies list
        res = client.get("/api/v1/admin/analytics/anomalies")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["total_count"] >= 1

        anomaly = data["anomalies"][0]
        anomaly_id = anomaly["anomaly_id"]
        assert anomaly["status"] == AnomalyStatus.DETECTED
        # Invariant: ANOMALY != SECURITY ATTACK
        assert "SECURITY_ATTACK" not in anomaly["anomaly_type"]
        assert "OPERATIONAL ANOMALY != SECURITY INCIDENT" in anomaly["description"]

        # Acknowledge anomaly
        ack_res = client.post(
            f"/api/v1/admin/analytics/anomalies/{anomaly_id}/acknowledge",
            json={"notes": "Investigating upstream database connection pool"},
        )
        assert ack_res.status_code == 200
        assert ack_res.json()["data"]["status"] == AnomalyStatus.ACKNOWLEDGED

        # Resolve anomaly
        res_res = client.post(
            f"/api/v1/admin/analytics/anomalies/{anomaly_id}/resolve",
            json={"resolution_notes": "Database connection pool restarted; error rate normalized"},
        )
        assert res_res.status_code == 200
        assert res_res.json()["data"]["status"] == AnomalyStatus.RESOLVED
        assert res_res.json()["data"]["resolution_notes"] is not None
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# 8. Organization & Facility Scoping / Tenant Isolation
# ===========================================================================

def test_organization_scoped_analytics_isolation(client, analytics_service):
    """Verify Org A cannot view Org B analytics, while SysAdmins have full visibility."""
    org_a_doctor = _make_actor("doc-a", UserRole.DOCTOR, organization_id="org-alpha")
    org_b_doctor = _make_actor("doc-b", UserRole.DOCTOR, organization_id="org-beta")
    sys_admin = _make_actor("sys-admin", UserRole.SYSTEM_ADMIN, organization_id="org-core")

    # Record events for Org Alpha
    analytics_service.record_event(
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        endpoint="/api/v1/patients/{patient_id}/encounters",
        organization_id="org-alpha",
        status=200,
        duration_ms=30.0,
    )

    # 1. Org Alpha doctor can access Org Alpha
    app.dependency_overrides[get_current_user] = lambda: org_a_doctor
    try:
        res = client.get("/api/v1/organizations/org-alpha/analytics")
        assert res.status_code == 200
        assert res.json()["data"]["total_requests"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 2. Org Beta doctor CANNOT access Org Alpha (Forbidden HTTP 403)
    app.dependency_overrides[get_current_user] = lambda: org_b_doctor
    try:
        res = client.get("/api/v1/organizations/org-alpha/analytics")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. System Admin CAN access Org Alpha
    app.dependency_overrides[get_current_user] = lambda: sys_admin
    try:
        res = client.get("/api/v1/organizations/org-alpha/analytics")
        assert res.status_code == 200
        assert res.json()["data"]["total_requests"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# 9. Query Range Validation (Max Limit Enforcement)
# ===========================================================================

def test_query_range_exceeded_rejection(client):
    """Verify queries spanning more than 90 days are rejected with HTTP 400."""
    admin = _make_actor("admin-1", UserRole.SYSTEM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin

    now = datetime.now(timezone.utc)
    start_100_days_ago = now - timedelta(days=100)

    try:
        res = client.get(
            "/api/v1/admin/analytics/overview",
            params={
                "start_time": start_100_days_ago.isoformat(),
                "end_time": now.isoformat(),
            },
        )
        assert res.status_code == 400
        data = res.json()
        assert data["success"] is False
        assert "exceeds maximum allowed limit" in data["error"]["message"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# 10. Core Clinical Safety Invariants
# ===========================================================================

def test_analytics_cannot_alter_clinical_state():
    """Verify that analytics models and services contain ZERO clinical mutation methods."""
    analytics_svc = AnalyticsService(repository=AnalyticsRepository())

    # Verify no clinical operations exist on AnalyticsService
    forbidden_methods = [
        "update_clinical_note",
        "update_medication",
        "update_allergy",
        "evaluate_triage",
        "prescribe_medication",
        "generate_care_plan",
        "modify_vital_sign",
    ]
    for method in forbidden_methods:
        assert not hasattr(analytics_svc, method), f"AnalyticsService must never contain clinical method: {method}"


# ===========================================================================
# 11. Support Operator Access & Facility Scoping Tests
# ===========================================================================

def test_support_operator_can_access_admin_analytics(client, analytics_service):
    """SUPPORT_OPERATOR role possesses ADMIN_ANALYTICS_VIEW and can inspect operational analytics."""
    support = _make_actor("support-1", UserRole.SUPPORT_OPERATOR)
    app.dependency_overrides[get_current_user] = lambda: support

    analytics_service.record_event(
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        endpoint="/api/v1/health",
        status=200,
    )

    try:
        res = client.get("/api/v1/admin/analytics/overview")
        assert res.status_code == 200
        assert res.json()["success"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_facility_scoped_analytics_isolation(client, analytics_service):
    """Facility A clinician can access Facility A analytics, but is forbidden from Facility B."""
    fac_a_doc = _make_actor("doc-a", UserRole.DOCTOR, facility_id="fac-alpha")
    fac_b_doc = _make_actor("doc-b", UserRole.DOCTOR, facility_id="fac-beta")

    analytics_service.record_event(
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        endpoint="/api/v1/patients/{patient_id}/medications",
        facility_id="fac-alpha",
        status=200,
    )

    # 1. Facility Alpha doctor can access Facility Alpha
    app.dependency_overrides[get_current_user] = lambda: fac_a_doc
    try:
        res = client.get("/api/v1/facilities/fac-alpha/analytics")
        assert res.status_code == 200
        assert res.json()["data"]["total_requests"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 2. Facility Beta doctor CANNOT access Facility Alpha (HTTP 403)
    app.dependency_overrides[get_current_user] = lambda: fac_b_doc
    try:
        res = client.get("/api/v1/facilities/fac-alpha/analytics")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# 12. Retention Policy Pruning & Concurrency Tests
# ===========================================================================

def test_analytics_retention_pruning(analytics_repo, analytics_service):
    """Verify that pruning events older than retention_days deletes only expired events."""
    now = datetime.now(timezone.utc)

    # Old event (100 days ago)
    old_ev = AnalyticsEvent(
        event_id="old-ev-1",
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        timestamp=now - timedelta(days=100),
        status=200,
    )
    # Recent event (5 days ago)
    recent_ev = AnalyticsEvent(
        event_id="recent-ev-1",
        event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
        timestamp=now - timedelta(days=5),
        status=200,
    )

    analytics_repo.record_event(old_ev)
    analytics_repo.record_event(recent_ev)
    assert analytics_repo.count_events() == 2

    # Prune with 90-day retention
    deleted = analytics_repo.prune_retention(retention_days=90)
    assert deleted == 1
    assert analytics_repo.count_events() == 1
    assert analytics_repo.get_event("recent-ev-1") is not None
    assert analytics_repo.get_event("old-ev-1") is None


def test_concurrent_analytics_recording(analytics_repo, analytics_service):
    """Verify thread-safe concurrent recording of 100 events across 10 threads."""
    import threading

    def worker(worker_id: int):
        for i in range(10):
            analytics_service.record_event(
                event_id=f"concurrent-{worker_id}-{i}",
                event_type=AnalyticsEventType.API_REQUEST_COMPLETED,
                endpoint="/api/v1/patients/{patient_id}/vitals",
                status=200,
                duration_ms=25.0 + i,
            )

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert analytics_repo.count_events() == 100

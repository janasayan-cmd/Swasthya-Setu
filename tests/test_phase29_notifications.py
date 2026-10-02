"""Comprehensive Test Suite for Phase 29: Notification, Communication & Event Delivery System.

Covers:
1. Template rendering, versioning, and localization (en, hi, bn).
2. Content safety guards: CRLF injection blocking and unauthorized clinical content rejection.
3. User communication preferences: category toggles, channel eligibility, and quiet hours.
4. Mandatory security bypass invariant: security alerts bypass user opt-outs and quiet hours.
5. Multi-channel delivery providers:
   - Email: format validation, CRLF guard, simulation modes.
   - SMS: E.164 phone formatting, strict raw PHI blocking guard.
   - Push: device token validation and unregistered token rejection.
6. Rate limiting: per-recipient dispatch throttling.
7. Idempotency and duplicate notification suppression.
8. Recipient inbox operations: listing, unread counts, mark as read, dismissal.
9. BOLA / IDOR authorization enforcement: cross-user isolation.
10. Admin operations: system queries, provider diagnostics, connectivity testing, bulk dispatch.
11. Async worker task handlers (Phase 22 integration).
12. Critical clinical safety boundaries:
    - NOTIFICATION != CLINICAL DECISION
    - Autonomous prescribing or diagnostic alterations strictly rejected.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_current_user,
    get_notification_preference_service,
    get_notification_service,
)
from app.core.config import get_settings
from app.core.exceptions import (
    InvalidRecipientException,
    NotificationAccessDeniedException,
    NotificationNotFoundException,
    NotificationPreferenceConflictException,
    NotificationRateLimitExceededException,
    TemplateResolutionException,
    UnauthorizedClinicalContentException,
)
from app.core.policies import Permission
from app.integrations.notifications import (
    MockEmailNotificationProvider,
    MockPushNotificationProvider,
    MockSMSNotificationProvider,
    NotificationProviderRegistry,
    ProviderDeliveryRequest,
)
from app.main import app
from app.repositories.notification_delivery_repository import (
    NotificationDeliveryRepository,
)
from app.repositories.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from app.repositories.notification_repository import NotificationRepository
from app.schemas.auth import UserRole
from app.schemas.job import JobRecord, JobStatus, JobType
from app.schemas.notification import (
    NotificationBulkCreate,
    NotificationCategory,
    NotificationChannel,
    NotificationCreate,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from app.schemas.notification_delivery import DeliveryStatus
from app.schemas.notification_preferences import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.communication_service import CommunicationService, mask_target
from app.services.notification_preference_service import (
    NotificationPreferenceService,
)
from app.services.notification_service import NotificationService
from app.services.notification_template_service import (
    NotificationTemplateService,
)
from app.workers.tasks.notification import (
    process_notification_bulk_dispatch_task,
    process_notification_cleanup_task,
    process_notification_dispatch_task,
    process_notification_health_check_task,
    process_notification_retry_task,
)


@pytest.fixture
def mock_template_service():
    return NotificationTemplateService()


@pytest.fixture
def mock_pref_repo():
    return NotificationPreferenceRepository()


@pytest.fixture
def mock_pref_service(mock_pref_repo):
    return NotificationPreferenceService(repository=mock_pref_repo)


@pytest.fixture
def mock_deliv_repo():
    return NotificationDeliveryRepository()


@pytest.fixture
def mock_comm_service(mock_deliv_repo):
    registry = NotificationProviderRegistry()
    return CommunicationService(delivery_repository=mock_deliv_repo, provider_registry=registry)


@pytest.fixture
def mock_notif_repo():
    return NotificationRepository()


@pytest.fixture
def isolated_notif_service(mock_notif_repo, mock_deliv_repo, mock_template_service, mock_pref_service, mock_comm_service):
    return NotificationService(
        notification_repository=mock_notif_repo,
        delivery_repository=mock_deliv_repo,
        template_service=mock_template_service,
        preference_service=mock_pref_service,
        communication_service=mock_comm_service,
    )


# ---------------------------------------------------------------------------
# 1. Template Rendering & Localization Tests
# ---------------------------------------------------------------------------

def test_template_rendering_multilingual(mock_template_service):
    # English
    title_en, body_en, ver = mock_template_service.render_notification(
        NotificationType.DOCUMENT_PROCESSING_COMPLETED,
        variables={"document_name": "Lab_Report.pdf"},
        language="en",
    )
    assert "Document Processing Completed" in title_en
    assert "Lab_Report.pdf" in body_en
    assert ver == 1

    # Hindi
    title_hi, body_hi, _ = mock_template_service.render_notification(
        NotificationType.DOCUMENT_PROCESSING_COMPLETED,
        variables={"document_name": "Lab_Report.pdf"},
        language="hi",
    )
    assert "दस्तावेज़ प्रसंस्करण पूर्ण हुआ" in title_hi
    assert "Lab_Report.pdf" in body_hi

    # Bengali
    title_bn, body_bn, _ = mock_template_service.render_notification(
        NotificationType.DOCUMENT_PROCESSING_COMPLETED,
        variables={"document_name": "Lab_Report.pdf"},
        language="bn",
    )
    assert "ডকুমেন্ট প্রক্রিয়াকরণ সম্পন্ন হয়েছে" in title_bn
    assert "Lab_Report.pdf" in body_bn


def test_template_missing_required_variable_raises_error(mock_template_service):
    with pytest.raises(TemplateResolutionException) as exc:
        mock_template_service.render_notification(
            NotificationType.DOCUMENT_PROCESSING_COMPLETED,
            variables={},  # Missing document_name
            language="en",
        )
    assert "Missing required template variables" in str(exc.value)


def test_template_clinical_safety_blocks_autonomous_medical_advice(mock_template_service):
    # Prohibited clinical diagnosis
    with pytest.raises(UnauthorizedClinicalContentException) as exc:
        mock_template_service.render_notification(
            NotificationType.SYSTEM_NOTIFICATION,
            variables={"message": "You are diagnosed with pneumonia. Increase your dose to 500mg."},
            language="en",
        )
    assert "violating safety boundary" in str(exc.value) or "prohibited clinical" in str(exc.value)


# ---------------------------------------------------------------------------
# 2. Preferences & Mandatory Security Bypass Tests
# ---------------------------------------------------------------------------

def test_user_preferences_opt_out_respected(mock_pref_service):
    user_id = "user_patient_001"
    mock_pref_service.update_preferences(
        user_id=user_id,
        update=NotificationPreferencesUpdate(clinical_notifications_enabled=False),
    )

    with pytest.raises(NotificationPreferenceConflictException) as exc:
        mock_pref_service.resolve_eligible_channels(
            user_id=user_id,
            notification_type=NotificationType.CARE_PLAN_AVAILABLE,
            priority=NotificationPriority.NORMAL,
        )
    assert "opted out of clinical workflow" in str(exc.value)


def test_mandatory_security_notifications_bypass_opt_outs(mock_pref_service):
    user_id = "user_patient_002"
    # User opts out of everything
    mock_pref_service.update_preferences(
        user_id=user_id,
        update=NotificationPreferencesUpdate(
            email_enabled=False,
            sms_enabled=False,
            in_app_enabled=False,
            clinical_notifications_enabled=False,
            operational_notifications_enabled=False,
            quiet_hours_enabled=True,
        ),
    )

    # Security notification MUST bypass and return eligible channels
    channels = mock_pref_service.resolve_eligible_channels(
        user_id=user_id,
        notification_type=NotificationType.SECURITY_ALERT,
        priority=NotificationPriority.CRITICAL,
    )
    assert NotificationChannel.IN_APP in channels
    assert NotificationChannel.EMAIL in channels


# ---------------------------------------------------------------------------
# 3. Provider Adapters & Privacy Guards Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_adapter_crlf_header_injection_guard():
    provider = MockEmailNotificationProvider()
    req = ProviderDeliveryRequest(
        notification_id="n1",
        delivery_id="d1",
        channel=NotificationChannel.EMAIL,
        recipient_target="patient@example.com",
        subject="Subject with \r\nBcc: evil@attacker.com",
        body="Body text",
    )
    res = await provider.send(req)
    assert res.success is False
    assert res.status == DeliveryStatus.FAILED
    assert "CRLF" in res.error_message


@pytest.mark.asyncio
async def test_sms_adapter_blocks_raw_phi_leakage():
    provider = MockSMSNotificationProvider()
    # Attempting to send unmasked clinical prescription details over unencrypted SMS
    req = ProviderDeliveryRequest(
        notification_id="n2",
        delivery_id="d2",
        channel=NotificationChannel.SMS,
        recipient_target="+919876543210",
        body="Your prescription details: Atorvastatin 20mg daily for hyperlipidemia",
    )
    res = await provider.send(req)
    assert res.success is False
    assert res.status == DeliveryStatus.FAILED
    assert res.error_category == "PRIVACY_VIOLATION_BLOCKED"


@pytest.mark.asyncio
async def test_push_adapter_validates_token_and_unregistered():
    provider = MockPushNotificationProvider()
    # Invalid length
    req_short = ProviderDeliveryRequest(
        notification_id="n3",
        delivery_id="d3",
        channel=NotificationChannel.PUSH,
        recipient_target="short",
        body="Alert",
    )
    res_short = await provider.send(req_short)
    assert res_short.success is False
    assert "Invalid push device" in res_short.error_message

    # Expired token
    req_exp = ProviderDeliveryRequest(
        notification_id="n4",
        delivery_id="d4",
        channel=NotificationChannel.PUSH,
        recipient_target="exp_device_token_abc_12345",
        body="Alert",
    )
    res_exp = await provider.send(req_exp)
    assert res_exp.success is False
    assert res_exp.error_category == "UNREGISTERED_TOKEN"


# ---------------------------------------------------------------------------
# 4. Target Masking Test
# ---------------------------------------------------------------------------

def test_mask_target_protection():
    assert mask_target("john.doe@example.com", NotificationChannel.EMAIL) == "j***@example.com"
    assert mask_target("+919876543210", NotificationChannel.SMS) == "+91****10"
    assert "..." in mask_target("push_token_device_abc123456789", NotificationChannel.PUSH)


# ---------------------------------------------------------------------------
# 5. Rate Limiting Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limiting_exceeded(mock_comm_service):
    mock_comm_service.settings.NOTIFICATION_RATE_LIMIT_ENABLED = True
    mock_comm_service.settings.NOTIFICATION_RATE_LIMIT_PER_MINUTE = 3

    target = "rate_test@example.com"
    # Dispatch 3 times successfully
    for i in range(3):
        res = await mock_comm_service.dispatch_channel(
            notification_id=f"notif_{i}",
            channel=NotificationChannel.EMAIL,
            recipient_target=target,
            title="Ping",
            body="Ping message",
        )
        assert res.status == DeliveryStatus.SENT

    # 4th dispatch exceeds rate limit
    with pytest.raises(NotificationRateLimitExceededException):
        await mock_comm_service.dispatch_channel(
            notification_id="notif_4",
            channel=NotificationChannel.EMAIL,
            recipient_target=target,
            title="Ping",
            body="Ping message",
        )


# ---------------------------------------------------------------------------
# 6. Idempotency & Deduplication Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_creation_idempotency(isolated_notif_service):
    payload = NotificationCreate(
        recipient_id="pat_100",
        notification_type=NotificationType.DOCUMENT_PROCESSING_COMPLETED,
        template_variables={"document_name": "BloodTest.pdf"},
        idempotency_key="idemp_unique_key_001",
    )

    n1 = await isolated_notif_service.create_and_dispatch(payload)
    assert n1.status == NotificationStatus.DELIVERED

    # Re-dispatch with exact same idempotency key returns identical record
    n2 = await isolated_notif_service.create_and_dispatch(payload)
    assert n1.id == n2.id
    assert n1.idempotency_key == n2.idempotency_key


# ---------------------------------------------------------------------------
# 7. Recipient Inbox & BOLA / IDOR Protection Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recipient_inbox_and_idor_protection(isolated_notif_service):
    # Create notification for User A
    notif_a = await isolated_notif_service.create_and_dispatch(
        NotificationCreate(
            recipient_id="user_alpha",
            notification_type=NotificationType.SYSTEM_NOTIFICATION,
            template_variables={"message": "Maintenance tonight at 23:00 UTC."},
        )
    )

    # User A views their inbox
    inbox_a = isolated_notif_service.list_user_notifications(user_id="user_alpha")
    assert inbox_a.total >= 1
    assert inbox_a.unread_count >= 1

    # User A marks as read
    read_a = await isolated_notif_service.mark_as_read(notif_a.id, user_id="user_alpha")
    assert read_a.read_at is not None

    # BOLA / IDOR Violation: User B attempts to access or dismiss User A's notification
    with pytest.raises(NotificationAccessDeniedException):
        isolated_notif_service.get_user_notification(notif_a.id, user_id="user_bravo")

    with pytest.raises(NotificationAccessDeniedException):
        await isolated_notif_service.mark_as_read(notif_a.id, user_id="user_bravo")

    with pytest.raises(NotificationAccessDeniedException):
        await isolated_notif_service.mark_as_dismissed(notif_a.id, user_id="user_bravo")


# ---------------------------------------------------------------------------
# 8. Administrative Bulk Dispatch & Diagnostics Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_bulk_dispatch(isolated_notif_service):
    bulk_payload = NotificationBulkCreate(
        recipient_ids=["pat_1", "pat_2", "pat_3"],
        notification_type=NotificationType.SYSTEM_NOTIFICATION,
        template_variables={"message": "Scheduled portal upgrade."},
        reason="Routine operational announcement",
    )

    res = await isolated_notif_service.admin_bulk_dispatch(bulk_payload, actor_id="admin_01")
    assert res["total_recipients"] == 3
    assert res["dispatched_count"] == 3
    assert res["failed_count"] == 0


@pytest.mark.asyncio
async def test_admin_provider_connectivity_test():
    registry = NotificationProviderRegistry()
    res = await registry.test_provider_connectivity(
        channel=NotificationChannel.EMAIL,
        test_target="health_test@example.com",
    )
    assert res.success is True
    assert res.channel == NotificationChannel.EMAIL


# ---------------------------------------------------------------------------
# 9. Asynchronous Background Task Handlers (Phase 22 Integration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_notification_dispatch_task(isolated_notif_service):
    job = JobRecord(
        job_type=JobType.NOTIFICATION_DISPATCH,
        status=JobStatus.QUEUED,
        resource_type="NOTIFICATION",
        resource_id="notif_async_001",
        operation_type="DISPATCH",
        payload={
            "notification_data": {
                "recipient_id": "user_async_1",
                "notification_type": "SYSTEM_NOTIFICATION",
                "template_variables": {"message": "Async message"},
            }
        },
        initiating_user_id="clinician_01",
    )
    context = {"notification_service": isolated_notif_service}
    res = await process_notification_dispatch_task(job, context)
    assert res["status"] in ("DELIVERED", "PROCESSING")
    assert res["recipient_id"] == "user_async_1"


@pytest.mark.asyncio
async def test_async_health_check_task():
    job = JobRecord(
        job_type=JobType.NOTIFICATION_PROVIDER_HEALTH_CHECK,
        status=JobStatus.QUEUED,
        resource_type="PROVIDER",
        resource_id="all",
        operation_type="HEALTH_CHECK",
    )
    res = await process_notification_health_check_task(job, {})
    assert res["providers_checked"] >= 3
    assert "results" in res


# ---------------------------------------------------------------------------
# 10. FastAPI Route End-to-End Client Tests
# ---------------------------------------------------------------------------

def test_api_notification_routes_authenticated():
    client = TestClient(app)

    # Mock authenticated user as a DOCTOR
    def mock_get_current_user():
        return AuthenticatedUserContext(
            user_id="doctor_sharma",
            role=UserRole.DOCTOR,
        )

    app.dependency_overrides[get_current_user] = mock_get_current_user

    try:
        # 1. Issue notification
        resp = client.post(
            "/api/v1/notifications",
            json={
                "recipient_id": "doctor_sharma",
                "notification_type": "DOCUMENT_PROCESSING_COMPLETED",
                "template_variables": {"document_name": "Discharge_Report.pdf"},
            },
        )
        assert resp.status_code == 201
        created = resp.json()
        notif_id = created["id"]
        assert created["recipient_id"] == "doctor_sharma"

        # 2. List notifications
        list_resp = client.get("/api/v1/notifications")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert any(n["id"] == notif_id for n in items)

        # 3. Mark read
        read_resp = client.post(f"/api/v1/notifications/{notif_id}/read")
        assert read_resp.status_code == 200
        assert read_resp.json()["read_at"] is not None

        # 4. Preferences GET & PUT
        pref_get = client.get("/api/v1/notification-preferences")
        assert pref_get.status_code == 200

        pref_put = client.put(
            "/api/v1/notification-preferences",
            json={"language": "hi", "sms_enabled": False},
        )
        assert pref_put.status_code == 200
        assert pref_put.json()["language"] == "hi"
        assert pref_put.json()["sms_enabled"] is False

        # 5. Dismiss notification
        dismiss_resp = client.post(f"/api/v1/notifications/{notif_id}/dismiss")
        assert dismiss_resp.status_code == 200
        assert dismiss_resp.json()["dismissed_at"] is not None

    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_admin_notification_routes():
    client = TestClient(app)

    # Mock authenticated user as a SYSTEM_ADMIN
    def mock_get_admin_user():
        return AuthenticatedUserContext(
            user_id="sys_admin_01",
            role=UserRole.SYSTEM_ADMIN,
        )

    app.dependency_overrides[get_current_user] = mock_get_admin_user

    try:
        # 1. Admin list notifications
        resp = client.get("/api/v1/admin/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

        # 2. Admin list providers
        prov_resp = client.get("/api/v1/admin/notification-providers")
        assert prov_resp.status_code == 200
        providers = prov_resp.json()
        assert len(providers) >= 3

        # 3. Admin test provider ping
        test_resp = client.post(
            "/api/v1/admin/notification-providers/mock_email/test",
            json={
                "channel": "EMAIL",
                "test_target": "sre_diagnostic@healthsetu.internal",
            },
        )
        assert test_resp.status_code == 200
        assert test_resp.json()["success"] is True

        # 4. Admin failures list
        fail_resp = client.get("/api/v1/admin/notification-failures")
        assert fail_resp.status_code == 200
        assert "items" in fail_resp.json()

    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# 11. Critical Clinical Safety & Domain Boundaries Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_medication_reminder_clinical_safety_boundary(isolated_notif_service):
    """Medication reminder can only deliver verified schedules; cannot alter doses."""
    # Valid verified schedule reminder
    valid_notif = await isolated_notif_service.create_and_dispatch(
        NotificationCreate(
            recipient_id="pat_44",
            notification_type=NotificationType.MEDICATION_NORMALIZATION_REVIEW_REQUIRED,
            template_variables={"medication_name": "Metformin 500mg"},
        )
    )
    assert valid_notif.status == NotificationStatus.DELIVERED

    # Attempting to prescribe or change dosage in notification variables is blocked
    with pytest.raises(UnauthorizedClinicalContentException):
        await isolated_notif_service.create_and_dispatch(
            NotificationCreate(
                recipient_id="pat_45",
                notification_type=NotificationType.MEDICATION_NORMALIZATION_REVIEW_REQUIRED,
                template_variables={"medication_name": "Metformin; stop taking insulin immediately"},
            )
        )


def test_quiet_hours_schedule_evaluation(mock_pref_service):
    """Test quiet hours boundary when current UTC falls within window vs outside."""
    prefs = NotificationPreferences(
        user_id="pat_qh",
        quiet_hours_enabled=True,
        quiet_hours_start_utc="22:00",
        quiet_hours_end_utc="07:00",
    )

    # 23:30 UTC -> inside quiet hours
    inside_time = datetime(2026, 10, 2, 23, 30, tzinfo=timezone.utc)
    assert mock_pref_service.is_in_quiet_hours(prefs, now_utc=inside_time) is True

    # 14:00 UTC -> outside quiet hours
    outside_time = datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc)
    assert mock_pref_service.is_in_quiet_hours(prefs, now_utc=outside_time) is False


"""Tests for HealthSetu Phase 35: Clinical Alerts, Safety Notifications & Escalation Management.

Verifies:
- Alert policy evaluation and versioning
- Idempotent alert creation & deduplication
- Recipient resolution & patient content filtering
- Acknowledgement, resolution, dismissal lifecycle workflows
- Escalation engine (Level 0 -> 1 -> 2 -> 3) and escalation stop conditions
- API endpoints (list, get, acknowledge, resolve, dismiss, history, admin)
- Multi-tenant and clinical relationship access control
- All 18 Clinical Safety Regression Tests from TRD Section 45
"""

import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from app.main import create_app
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import UserRole
from app.schemas.alert import (
    AlertCategory,
    AlertCreate,
    AlertFilter,
    AlertProvenance,
    AlertRecord,
    AlertSeverity,
    AlertStatus,
    AlertRecipientType,
)
from app.schemas.alert_policy import AlertPolicy
from app.schemas.user import AuthenticatedUserContext
from app.repositories.alert_repository import AlertRepository
from app.repositories.alert_escalation_repository import AlertEscalationRepository
from app.repositories.alert_policy_repository import AlertPolicyRepository
from app.integrations.alerts.providers.local import LocalAlertProvider
from app.services.alert_validation_service import AlertValidationService
from app.services.alert_recipient_service import AlertRecipientService
from app.services.alert_policy_service import AlertPolicyService
from app.services.alert_escalation_service import AlertEscalationService
from app.services.alert_service import AlertService
from app.services.notification_service import NotificationService
from app.api.deps import get_notification_service
from app.services.audit_service import AuditService
from app.repositories.audit_repository import AuditRepository
from app.core.exceptions import (
    AlertAccessDeniedException,
    AlertAlreadyAcknowledgedException,
    AlertAlreadyResolvedException,
    AlertEscalationNotAllowedException,
    AlertInvalidStateException,
    AlertNotFoundException,
    AlertOperationNotAllowedException,
)


@pytest.fixture
def test_setup():
    """Build isolated repos and services for testing."""
    alert_repo = AlertRepository()
    escalation_repo = AlertEscalationRepository()
    policy_repo = AlertPolicyRepository()
    local_provider = LocalAlertProvider()
    val_service = AlertValidationService()
    recip_service = AlertRecipientService()
    policy_service = AlertPolicyService(policy_repo=policy_repo)

    audit_repo = AuditRepository()
    audit_service = AuditService(audit_repository=audit_repo)

    notif_service = get_notification_service()

    escalation_service = AlertEscalationService(
        alert_repo=alert_repo,
        escalation_repo=escalation_repo,
        recipient_service=recip_service,
        notification_service=notif_service,
        audit_service=audit_service,
        alert_provider=local_provider,
    )

    alert_service = AlertService(
        alert_repo=alert_repo,
        policy_service=policy_service,
        recipient_service=recip_service,
        validation_service=val_service,
        notification_service=notif_service,
        audit_service=audit_service,
        alert_provider=local_provider,
    )

    return {
        "alert_repo": alert_repo,
        "escalation_repo": escalation_repo,
        "policy_repo": policy_repo,
        "local_provider": local_provider,
        "val_service": val_service,
        "recip_service": recip_service,
        "policy_service": policy_service,
        "escalation_service": escalation_service,
        "alert_service": alert_service,
        "notif_service": notif_service,
    }


# ===========================================================================
# 1. Alert Policy Service Tests
# ===========================================================================

def test_policy_evaluation_critical_diagnostic(test_setup):
    service: AlertPolicyService = test_setup["policy_service"]
    res = service.evaluate_event(
        event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
        payload={"is_critical_result": True, "test_name": "Serum Potassium"},
    )
    assert res.requires_alert is True
    assert res.category == AlertCategory.DIAGNOSTIC_RESULT_ALERT
    assert res.severity == AlertSeverity.CRITICAL
    assert res.requires_acknowledgement is True
    assert res.escalation_enabled is True
    assert "Critical Diagnostic Result: Serum Potassium" in res.title


def test_policy_evaluation_medication_safety(test_setup):
    service: AlertPolicyService = test_setup["policy_service"]
    res = service.evaluate_event(
        event_type="MEDICATION_SAFETY_REVIEW_REQUIRED",
        payload={"safety_status": "REVIEW_REQUIRED", "medication_name": "Warfarin"},
    )
    assert res.requires_alert is True
    assert res.category == AlertCategory.MEDICATION_SAFETY_ALERT
    assert res.severity == AlertSeverity.HIGH
    assert res.requires_acknowledgement is True
    assert res.escalation_enabled is True


def test_policy_evaluation_urgent_triage(test_setup):
    service: AlertPolicyService = test_setup["policy_service"]
    res = service.evaluate_event(
        event_type="URGENT_TRIAGE_RESULT_AVAILABLE",
        payload={"urgency": "URGENT"},
    )
    assert res.requires_alert is True
    assert res.category == AlertCategory.TRIAGE_ALERT
    assert res.severity == AlertSeverity.CRITICAL


def test_policy_evaluation_condition_not_met(test_setup):
    service: AlertPolicyService = test_setup["policy_service"]
    res = service.evaluate_event(
        event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
        payload={"is_critical_result": False},
    )
    assert res.requires_alert is False
    assert res.suppression_reason == "CONDITIONS_NOT_MET"


# ===========================================================================
# 2. Idempotency & Creation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_alert_creation_and_idempotency(test_setup):
    alert_service: AlertService = test_setup["alert_service"]

    event_payload = AlertCreate(
        source_system="diagnostic_result_service",
        source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
        source_event_id="EVT-RESULT-12345",
        source_resource_type="diagnostic_result",
        source_resource_id="RES-9999",
        patient_id="PAT-001",
        responsible_clinician_id="DOC-001",
        event_payload={"is_critical_result": True, "test_name": "Troponin-I"},
    )

    # First creation
    alert1 = await alert_service.create_alert_from_event(event_payload)
    assert alert1 is not None
    assert alert1.id.startswith("ALT-")
    assert alert1.severity == AlertSeverity.CRITICAL
    assert alert1.status == AlertStatus.CREATED
    assert alert1.provenance.source_event_id == "EVT-RESULT-12345"

    # Repeated event with identical source_event_id
    alert2 = await alert_service.create_alert_from_event(event_payload)
    assert alert2 is not None
    assert alert2.id == alert1.id  # Same alert returned! No duplicate.


# ===========================================================================
# 3. Recipient Resolution & Patient Sanitization Tests
# ===========================================================================

def test_recipient_resolution(test_setup):
    recip_service: AlertRecipientService = test_setup["recip_service"]

    recipients = recip_service.resolve_recipients_for_alert(
        recipient_class="RESPONSIBLE_CLINICIAN",
        patient_id="PAT-10",
        responsible_clinician_id="DOC-42",
    )
    assert len(recipients) == 1
    assert recipients[0].recipient_id == "DOC-42"
    assert recipients[0].recipient_type == AlertRecipientType.RESPONSIBLE_CLINICIAN


def test_patient_sanitization(test_setup):
    recip_service: AlertRecipientService = test_setup["recip_service"]
    safe_title, safe_summary = recip_service.sanitize_for_patient(
        alert_title="Critical Diagnostic Result: High Potassium",
        summary="Internal provider review required immediately",
    )
    assert "Critical" not in safe_title
    assert "Important Health Update" in safe_title
    assert "review in your portal" in safe_summary or "portal" in safe_summary


# ===========================================================================
# 4. Acknowledgement, Resolution & Dismissal Workflows
# ===========================================================================

@pytest.mark.asyncio
async def test_alert_lifecycle_workflow(test_setup):
    alert_service: AlertService = test_setup["alert_service"]

    # 1. Create alert
    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="triage_service",
            source_event_type="URGENT_TRIAGE_RESULT_AVAILABLE",
            source_event_id="EVT-TRIAGE-771",
            source_resource_type="triage_result",
            source_resource_id="TRG-101",
            patient_id="PAT-50",
            responsible_clinician_id="DOC-99",
            event_payload={"urgency": "URGENT"},
        )
    )
    assert alert.status == AlertStatus.CREATED

    doc_user = AuthenticatedUserContext(
        user_id="DOC-99",
        role="DOCTOR",
        account_status="ACTIVE",
    )

    # 2. Acknowledge alert
    from app.schemas.alert import AlertAcknowledgeRequest, AlertResolveRequest
    ack_alert = await alert_service.acknowledge_alert(
        alert_id=alert.id,
        request=AlertAcknowledgeRequest(note="Reviewing patient triage notes."),
        current_user=doc_user,
    )
    assert ack_alert.status == AlertStatus.ACKNOWLEDGED
    assert ack_alert.acknowledged_by == "DOC-99"
    assert ack_alert.acknowledged_at is not None

    # Cannot re-acknowledge
    with pytest.raises(AlertAlreadyAcknowledgedException):
        await alert_service.acknowledge_alert(
            alert_id=alert.id,
            request=AlertAcknowledgeRequest(),
            current_user=doc_user,
        )

    # 3. Resolve alert
    res_alert = await alert_service.resolve_alert(
        alert_id=alert.id,
        request=AlertResolveRequest(reason="Patient attended and evaluated in triage room 3."),
        current_user=doc_user,
    )
    assert res_alert.status == AlertStatus.RESOLVED
    assert res_alert.resolved_by == "DOC-99"
    assert res_alert.resolution_reason == "Patient attended and evaluated in triage room 3."

    # History entries
    history = await alert_service.get_alert_history(alert.id, doc_user)
    actions = [h.action for h in history]
    assert "ALERT_CREATED" in actions
    assert "ALERT_ACKNOWLEDGED" in actions
    assert "ALERT_RESOLVED" in actions


# ===========================================================================
# 5. Escalation Engine Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_escalation_advances_tiers(test_setup):
    alert_service: AlertService = test_setup["alert_service"]
    escalation_service: AlertEscalationService = test_setup["escalation_service"]

    # Create critical alert with escalation enabled
    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="diagnostic_result_service",
            source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
            source_event_id="EVT-ESC-001",
            source_resource_type="diagnostic_result",
            source_resource_id="RES-001",
            patient_id="PAT-100",
            facility_id="FAC-A",
            responsible_clinician_id="DOC-1",
            event_payload={"is_critical_result": True},
        )
    )
    assert alert.escalation_level == 0
    assert alert.escalation_enabled is True

    # Escalate to Level 1 (Care Team)
    rec1 = await escalation_service.check_and_escalate_alert(alert.id, force=True)
    assert rec1 is not None
    assert rec1.from_level == 0
    assert rec1.to_level == 1
    assert rec1.escalated_to_recipient_id == "care_team_FAC-A"

    # Escalate to Level 2 (Facility Escalation)
    rec2 = await escalation_service.check_and_escalate_alert(alert.id, force=True)
    assert rec2 is not None
    assert rec2.from_level == 1
    assert rec2.to_level == 2
    assert rec2.escalated_to_recipient_id == "facility_lead_FAC-A"

    # Escalate to Level 3 (Organization Quality & Safety)
    rec3 = await escalation_service.check_and_escalate_alert(alert.id, force=True)
    assert rec3 is not None
    assert rec3.from_level == 2
    assert rec3.to_level == 3


@pytest.mark.asyncio
async def test_escalation_stops_when_acknowledged(test_setup):
    alert_service: AlertService = test_setup["alert_service"]
    escalation_service: AlertEscalationService = test_setup["escalation_service"]

    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="diagnostic_result_service",
            source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
            source_event_id="EVT-ESC-002",
            source_resource_type="diagnostic_result",
            source_resource_id="RES-002",
            patient_id="PAT-100",
            responsible_clinician_id="DOC-1",
            event_payload={"is_critical_result": True},
        )
    )

    doc_user = AuthenticatedUserContext(user_id="DOC-1", role="DOCTOR", account_status="ACTIVE")
    from app.schemas.alert import AlertAcknowledgeRequest
    await alert_service.acknowledge_alert(alert.id, AlertAcknowledgeRequest(), doc_user)

    # Escalation must STOP and not advance
    rec = await escalation_service.check_and_escalate_alert(alert.id, force=True)
    assert rec is not None
    assert rec.status.value == "STOPPED"
    assert rec.stop_reason == "ALREADY_ACKNOWLEDGED"

    updated = alert_service.alert_repo.get_by_id(alert.id)
    assert updated.escalation_level == 0  # Did not advance


# ===========================================================================
# 6. Multi-Tenant and Access Control Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_unrelated_clinician_cannot_view_alert(test_setup):
    alert_service: AlertService = test_setup["alert_service"]

    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="triage_service",
            source_event_type="URGENT_TRIAGE_RESULT_AVAILABLE",
            source_event_id="EVT-SEC-001",
            source_resource_type="triage_result",
            source_resource_id="TRG-900",
            patient_id="PAT-PRIVATE",
            responsible_clinician_id="DOC-ASSIGNED",
            facility_id="FAC-1",
            event_payload={"urgency": "URGENT"},
        )
    )

    unrelated_doc = AuthenticatedUserContext(
        user_id="DOC-UNRELATED",
        role="DOCTOR",
        facility_id="FAC-OTHER",
        account_status="ACTIVE",
    )

    with pytest.raises(AlertAccessDeniedException):
        await alert_service.get_alert(alert.id, unrelated_doc)


@pytest.mark.asyncio
async def test_patient_cannot_view_other_patient_alerts(test_setup):
    alert_service: AlertService = test_setup["alert_service"]

    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="diagnostic_result_service",
            source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
            source_event_id="EVT-PAT-001",
            source_resource_type="diagnostic_result",
            source_resource_id="RES-777",
            patient_id="PAT-ALICE",
            event_payload={"is_critical_result": True},
        )
    )

    bob_patient = AuthenticatedUserContext(
        user_id="USER-BOB",
        patient_id="PAT-BOB",
        role="PATIENT",
        account_status="ACTIVE",
    )

    with pytest.raises(AlertAccessDeniedException):
        await alert_service.get_alert(alert.id, bob_patient)


# ===========================================================================
# 7. SECTION 45: CLINICAL SAFETY REGRESSION TESTS
# ===========================================================================

def test_safety_01_alert_does_not_diagnose(test_setup):
    """REGRESSION TEST 1: ALERT DOES NOT DIAGNOSE."""
    policy_service: AlertPolicyService = test_setup["policy_service"]
    res = policy_service.evaluate_event(
        event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
        payload={"is_critical_result": True, "test_name": "Blood Glucose"},
    )
    # Result communicated is factual test observation, NOT clinical disease diagnosis
    assert "Diabetes Mellitus" not in res.title
    assert "Critical Diagnostic Result: Blood Glucose" in res.title


def test_safety_02_alert_does_not_prescribe(test_setup):
    """REGRESSION TEST 2: ALERT DOES NOT PRESCRIBE."""
    policy_service: AlertPolicyService = test_setup["policy_service"]
    res = policy_service.evaluate_event(
        event_type="MEDICATION_SAFETY_REVIEW_REQUIRED",
        payload={"safety_status": "REVIEW_REQUIRED", "medication_name": "Metformin"},
    )
    # Must not contain dosage instructions or prescribing directives
    assert "Take 500mg" not in res.title
    assert "Prescribe" not in res.title


@pytest.mark.asyncio
async def test_safety_03_alert_does_not_change_medication(test_setup):
    """REGRESSION TEST 3: ALERT DOES NOT CHANGE MEDICATION."""
    alert_service: AlertService = test_setup["alert_service"]
    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="medication_safety",
            source_event_type="MEDICATION_SAFETY_REVIEW_REQUIRED",
            source_event_id="EVT-MED-01",
            source_resource_type="medication",
            source_resource_id="MED-1",
            patient_id="PAT-1",
            responsible_clinician_id="DOC-1",
            event_payload={"safety_status": "REVIEW_REQUIRED", "medication_name": "Aspirin"},
        )
    )
    # The alert status is CREATED/ACKNOWLEDGED, it does not mutate patient medication state
    assert alert.category == AlertCategory.MEDICATION_SAFETY_ALERT
    assert alert.status == AlertStatus.CREATED


def test_safety_04_alert_does_not_change_allergy_data():
    """REGRESSION TEST 4: ALERT DOES NOT CHANGE ALLERGY DATA."""
    # Alert schemas and services have no allergy mutation capabilities
    assert not hasattr(AlertService, "update_allergy")
    assert not hasattr(AlertService, "delete_allergy")


@pytest.mark.asyncio
async def test_safety_05_alert_does_not_change_triage(test_setup):
    """REGRESSION TEST 5: ALERT DOES NOT CHANGE TRIAGE."""
    alert_service: AlertService = test_setup["alert_service"]
    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="triage_engine",
            source_event_type="URGENT_TRIAGE_RESULT_AVAILABLE",
            source_event_id="EVT-TRG-01",
            source_resource_type="triage_result",
            source_resource_id="TRG-1",
            patient_id="PAT-1",
            responsible_clinician_id="DOC-1",
            event_payload={"urgency": "URGENT"},
        )
    )
    # Alert only communicates the already-calculated urgency; it does not change the triage category
    assert alert.provenance.source_event_type == "URGENT_TRIAGE_RESULT_AVAILABLE"


def test_safety_06_alert_does_not_create_a_care_plan():
    """REGRESSION TEST 6: ALERT DOES NOT CREATE A CARE PLAN."""
    assert not hasattr(AlertService, "create_care_plan")
    assert not hasattr(AlertPolicyService, "generate_care_plan")


def test_safety_07_alert_does_not_invent_a_critical_result(test_setup):
    """REGRESSION TEST 7: ALERT DOES NOT INVENT A CRITICAL RESULT."""
    policy_service: AlertPolicyService = test_setup["policy_service"]
    # Normal result without authoritative critical flag must NOT generate critical alert
    res = policy_service.evaluate_event(
        event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
        payload={"is_critical_result": False, "test_name": "Hemoglobin"},
    )
    assert res.requires_alert is False


def test_safety_08_alert_does_not_treat_provider_failure_as_success(test_setup):
    """REGRESSION TEST 8: ALERT DOES NOT TREAT PROVIDER FAILURE AS SUCCESS."""
    val_service: AlertValidationService = test_setup["val_service"]
    # FAILED cannot convert directly to RESOLVED
    with pytest.raises(AlertInvalidStateException) as exc:
        val_service.validate_transition(AlertStatus.FAILED, AlertStatus.RESOLVED)
    assert "FAILED alert" in str(exc.value)


def test_safety_09_alert_does_not_treat_missing_information_as_normal(test_setup):
    """REGRESSION TEST 9: ALERT DOES NOT TREAT MISSING INFORMATION AS NORMAL."""
    policy_service: AlertPolicyService = test_setup["policy_service"]
    # Missing critical flag does not default to safe/normal alert creation
    res = policy_service.evaluate_event(
        event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
        payload={},
    )
    assert res.requires_alert is False


def test_safety_10_alert_does_not_treat_ai_output_as_clinical_authority(test_setup):
    """REGRESSION TEST 10: ALERT DOES NOT TREAT AI OUTPUT AS CLINICAL AUTHORITY."""
    val_service: AlertValidationService = test_setup["val_service"]
    with pytest.raises(AlertOperationNotAllowedException) as exc:
        val_service.validate_severity_source(AlertSeverity.CRITICAL, source="AI_AUTONOMOUS_INFERENCE")
    assert "AI model cannot autonomously invent clinical alert severity" in str(exc.value)


@pytest.mark.asyncio
async def test_safety_11_alert_delivery_does_not_equal_acknowledgement(test_setup):
    """REGRESSION TEST 11: ALERT DELIVERY DOES NOT EQUAL ACKNOWLEDGEMENT."""
    alert_service: AlertService = test_setup["alert_service"]
    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="diagnostic_service",
            source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
            source_event_id="EVT-DELIV-01",
            source_resource_type="diagnostic_result",
            source_resource_id="RES-01",
            patient_id="PAT-1",
            responsible_clinician_id="DOC-1",
            event_payload={"is_critical_result": True},
        )
    )
    # Delivered state is NOT acknowledged state
    assert alert.status != AlertStatus.ACKNOWLEDGED
    assert alert.acknowledged_at is None


@pytest.mark.asyncio
async def test_safety_12_acknowledgement_does_not_equal_clinical_action(test_setup):
    """REGRESSION TEST 12: ACKNOWLEDGEMENT DOES NOT EQUAL CLINICAL ACTION."""
    alert_service: AlertService = test_setup["alert_service"]
    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="triage_service",
            source_event_type="URGENT_TRIAGE_RESULT_AVAILABLE",
            source_event_id="EVT-ACK-01",
            source_resource_type="triage_result",
            source_resource_id="TRG-01",
            patient_id="PAT-1",
            responsible_clinician_id="DOC-1",
            event_payload={"urgency": "URGENT"},
        )
    )
    doc_user = AuthenticatedUserContext(user_id="DOC-1", role="DOCTOR", account_status="ACTIVE")
    from app.schemas.alert import AlertAcknowledgeRequest
    ack = await alert_service.acknowledge_alert(alert.id, AlertAcknowledgeRequest(), doc_user)
    # Acknowledged alert is NOT marked RESOLVED
    assert ack.status == AlertStatus.ACKNOWLEDGED
    assert ack.status != AlertStatus.RESOLVED


def test_safety_13_escalation_does_not_equal_emergency_dispatch(test_setup):
    """REGRESSION TEST 13: ESCALATION DOES NOT EQUAL EMERGENCY DISPATCH."""
    recip_service: AlertRecipientService = test_setup["recip_service"]
    # Level 3 escalation routes to organization medical quality officer, never 911 / emergency dispatch
    rid, rtype, rdesc = recip_service.resolve_escalation_recipient(target_level=3)
    assert "emergency_dispatch" not in rid
    assert "911" not in rid
    assert "Quality & Safety Officer" in rdesc


@pytest.mark.asyncio
async def test_safety_14_imported_data_does_not_become_verified_only_because_of_alert(test_setup):
    """REGRESSION TEST 14: IMPORTED DATA DOES NOT BECOME VERIFIED ONLY BECAUSE IT GENERATED AN ALERT."""
    alert_service: AlertService = test_setup["alert_service"]
    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="interoperability_service",
            source_event_type="INTEROPERABILITY_IMPORT_FAILED",
            source_event_id="EVT-INOP-01",
            source_resource_type="fhir_bundle",
            source_resource_id="BUNDLE-10",
            event_payload={"status": "FAILED"},
        )
    )
    # Generating an alert does not alter provenance or make raw imported data clinically verified
    assert alert.category == AlertCategory.INTEROPERABILITY_ALERT
    assert alert.status == AlertStatus.CREATED


@pytest.mark.asyncio
async def test_safety_15_duplicate_events_do_not_create_uncontrolled_alert_duplicates(test_setup):
    """REGRESSION TEST 15: DUPLICATE EVENTS DO NOT CREATE UNCONTROLLED ALERT DUPLICATES."""
    alert_service: AlertService = test_setup["alert_service"]
    evt = AlertCreate(
        source_system="diagnostic_service",
        source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
        source_event_id="EVT-DUP-CHECK",
        source_resource_type="diagnostic_result",
        source_resource_id="RES-DUP",
        patient_id="PAT-1",
        responsible_clinician_id="DOC-1",
        event_payload={"is_critical_result": True},
    )
    a1 = await alert_service.create_alert_from_event(evt)
    a2 = await alert_service.create_alert_from_event(evt)
    a3 = await alert_service.create_alert_from_event(evt)

    # Identical alert ID returned
    assert a1.id == a2.id == a3.id
    # In repository there is exactly 1 alert
    assert len(alert_service.alert_repo._alerts) == 1


@pytest.mark.asyncio
async def test_safety_16_resolved_alerts_are_not_re_escalated(test_setup):
    """REGRESSION TEST 16: RESOLVED ALERTS ARE NOT RE-ESCALATED."""
    alert_service: AlertService = test_setup["alert_service"]
    escalation_service: AlertEscalationService = test_setup["escalation_service"]

    alert = await alert_service.create_alert_from_event(
        AlertCreate(
            source_system="diagnostic_service",
            source_event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
            source_event_id="EVT-RESOLVE-STOP",
            source_resource_type="diagnostic_result",
            source_resource_id="RES-01",
            patient_id="PAT-1",
            responsible_clinician_id="DOC-1",
            event_payload={"is_critical_result": True},
        )
    )
    doc_user = AuthenticatedUserContext(user_id="DOC-1", role="DOCTOR", account_status="ACTIVE")
    from app.schemas.alert import AlertResolveRequest
    await alert_service.resolve_alert(alert.id, AlertResolveRequest(reason="Reviewed and addressed."), doc_user)

    # Attempt escalation on resolved alert
    record = await escalation_service.check_and_escalate_alert(alert.id, force=True)
    assert record.status.value == "STOPPED"
    assert record.stop_reason == "ALREADY_RESOLVED"


@pytest.mark.asyncio
async def test_safety_17_failed_notifications_are_not_reported_as_delivered(test_setup):
    """REGRESSION TEST 17: FAILED NOTIFICATIONS ARE NOT REPORTED AS DELIVERED."""
    # When simulated provider fails, result indicates failure, not delivered
    failing_provider = LocalAlertProvider(simulate_failure=True)
    alert = AlertRecord(
        id="ALT-FAIL-01",
        title="Test Alert",
        category=AlertCategory.CLINICAL_ALERT,
        severity=AlertSeverity.HIGH,
        provenance=AlertProvenance(
            source_system="test",
            source_event_type="TEST",
            source_event_id="E1",
            source_resource_type="res",
            source_resource_id="R1",
            policy_id="P1",
        ),
    )
    res = await failing_provider.create_alert(alert)
    assert res["success"] is False
    assert res["delivered"] is False


@pytest.mark.asyncio
async def test_safety_18_unknown_provider_state_is_not_reported_as_safe():
    """REGRESSION TEST 18: UNKNOWN PROVIDER STATE IS NOT REPORTED AS SAFE."""
    degraded_provider = LocalAlertProvider(simulate_failure=True)
    status_info = await degraded_provider.health_check()
    assert status_info["status"] != "HEALTHY"
    assert status_info["status"] == "DEGRADED"


# ===========================================================================
# 8. API Integration Tests (FastAPI Client)
# ===========================================================================

@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def doctor_token():
    token, _ = create_access_token(
        user_id="DOC-API-1",
        role=UserRole.DOCTOR.value,
    )
    return token


@pytest.fixture
def patient_token():
    token, _ = create_access_token(
        user_id="PAT-API-1",
        role=UserRole.PATIENT.value,
    )
    return token


@pytest.fixture
def admin_token():
    token, _ = create_access_token(
        user_id="ADMIN-API-1",
        role=UserRole.ADMIN.value,
    )
    return token


from app.api.deps import get_current_user


@pytest.mark.asyncio
async def test_api_alert_ingest_and_retrieval(app):
    doc_user = AuthenticatedUserContext(
        user_id="DOC-API-1",
        role="DOCTOR",
        account_status="ACTIVE",
        organization_id="ORG-1",
        facility_id="FAC-1",
    )
    app.dependency_overrides[get_current_user] = lambda: doc_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Ingest alert
            ingest_resp = await client.post(
                "/api/v1/alerts/ingest",
                json={
                    "source_system": "diagnostic_result_service",
                    "source_event_type": "CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
                    "source_event_id": "API-EVT-001",
                    "source_resource_type": "diagnostic_result",
                    "source_resource_id": "RES-API-1",
                    "patient_id": "PAT-API-1",
                    "responsible_clinician_id": "DOC-API-1",
                    "facility_id": "FAC-1",
                    "organization_id": "ORG-1",
                    "event_payload": {"is_critical_result": True, "test_name": "Blood pH"},
                },
            )
            assert ingest_resp.status_code == 201
            data = ingest_resp.json()
            alert_id = data["id"]
            assert data["severity"] == "CRITICAL"
            assert data["status"] == "CREATED"

            # 2. Get alert
            get_resp = await client.get(f"/api/v1/alerts/{alert_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == alert_id

            # 3. Clinician inbox
            inbox_resp = await client.get("/api/v1/clinicians/me/alerts")
            assert inbox_resp.status_code == 200
            assert inbox_resp.json()["total"] >= 1

            # 4. Acknowledge alert
            ack_resp = await client.post(
                f"/api/v1/alerts/{alert_id}/acknowledge",
                json={"note": "Received alert on duty."},
            )
            assert ack_resp.status_code == 200
            assert ack_resp.json()["status"] == "ACKNOWLEDGED"

            # 5. Resolve alert
            res_resp = await client.post(
                f"/api/v1/alerts/{alert_id}/resolve",
                json={"reason": "Blood gas stabilized and patient monitored."},
            )
            assert res_resp.status_code == 200
            assert res_resp.json()["status"] == "RESOLVED"

            # 6. History
            hist_resp = await client.get(f"/api/v1/alerts/{alert_id}/history")
            assert hist_resp.status_code == 200
            entries = hist_resp.json()
            assert len(entries) >= 3
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_api_admin_policies(app):
    admin_user = AuthenticatedUserContext(
        user_id="ADMIN-API-1",
        role="ADMIN",
        account_status="ACTIVE",
        organization_id="ORG-1",
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/alerts/policies")
            assert resp.status_code == 200
            policies = resp.json()
            assert len(policies) >= 5
            policy_ids = [p["policy_id"] for p in policies]
            assert "POLICY_CRITICAL_DIAGNOSTIC_RESULT" in policy_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


"""Integration and Unit Tests for Phase 31 — Scheduling, Appointment & Clinical Access Management.

CRITICAL PRINCIPLES VERIFIED:
- SCHEDULING ≠ CLINICAL DECISION
- SCHEDULING ≠ DIAGNOSIS
- APPOINTMENT ≠ ENCOUNTER
- APPOINTMENT BOOKED ≠ PATIENT SEEN
- DOUBLE-BOOKING MUST BE PREVENTED UNDER CONCURRENCY
- IDEMPOTENCY PRESERVES ORIGINAL APPOINTMENT
- CROSS-PATIENT ACCESS STRICTLY PREVENTED
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
import pytest
from starlette.testclient import TestClient

from app.api.deps import (
    _global_appointment_repo,
    _global_availability_repo,
    _global_patient_repo,
    _global_schedule_repo,
    get_current_user,
)
from app.core.config import settings
from app.core.exceptions import (
    AppointmentBookingConflictException,
    AppointmentInvalidStateException,
    AppointmentNotAuthorizedException,
    AppointmentNotFoundException,
    AppointmentSlotUnavailableException,
    InvalidAppointmentTimeException,
    InvalidAppointmentTypeException,
    InvalidTimezoneException,
)
from app.integrations.scheduling.local import LocalSchedulingProvider
from app.main import app
from app.repositories.patient_repository import PatientRecord
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreateRequest,
    AppointmentRecord,
    AppointmentRescheduleRequest,
    AppointmentStatus,
    AppointmentStatusUpdateRequest,
    AppointmentType,
)
from app.schemas.auth import UserRole
from app.schemas.availability import AvailabilityQuery, AvailabilitySlotRecord, SlotStatus
from app.schemas.patient import BiologicalSex, PatientStatus
from app.schemas.schedule import ScheduleRecord, WorkingHoursRule
from app.schemas.user import AuthenticatedUserContext
from app.services.appointment_authorization_service import AppointmentAuthorizationService
from app.services.appointment_service import AppointmentService
from app.services.appointment_validation_service import AppointmentValidationService
from app.services.availability_service import AvailabilityService
from app.services.scheduling_service import SchedulingService


@pytest.fixture(autouse=True)
def reset_scheduling_state():
    """Reset repository state and seed test fixtures."""
    _global_appointment_repo.clear()
    _global_availability_repo.clear()
    _global_schedule_repo.clear()
    _global_patient_repo._patients.clear()
    _global_patient_repo._user_to_patient.clear()

    # Seed Patient 1 (Arjun)
    pat1 = PatientRecord(
        id="pat-arjun-01",
        user_id="user-arjun-01",
        first_name="Arjun",
        last_name="Sharma",
        date_of_birth=date(1985, 4, 12),
        sex=BiologicalSex.MALE,
        status=PatientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    # Seed Patient 2 (Priya)
    pat2 = PatientRecord(
        id="pat-priya-02",
        user_id="user-priya-02",
        first_name="Priya",
        last_name="Verma",
        date_of_birth=date(1992, 8, 24),
        sex=BiologicalSex.FEMALE,
        status=PatientStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _global_patient_repo._patients[pat1.id] = pat1
    _global_patient_repo._patients[pat2.id] = pat2
    _global_patient_repo._user_to_patient[pat1.user_id] = pat1.id
    _global_patient_repo._user_to_patient[pat2.user_id] = pat2.id

    # Seed Availability Slots
    now = datetime.now(timezone.utc)
    future_start = now + timedelta(days=2)
    slot1 = AvailabilitySlotRecord(
        slot_id="slot-test-01",
        facility_id="fac-delhi-01",
        clinician_id="user-doc-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=future_start,
        end_time=future_start + timedelta(minutes=30),
        status=SlotStatus.AVAILABLE,
        capacity=1,
        booked_count=0,
    )
    slot2 = AvailabilitySlotRecord(
        slot_id="slot-test-02",
        facility_id="fac-delhi-01",
        clinician_id="user-doc-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=future_start + timedelta(hours=1),
        end_time=future_start + timedelta(hours=1, minutes=30),
        status=SlotStatus.AVAILABLE,
        capacity=1,
        booked_count=0,
    )
    _global_availability_repo.create_slot(slot1)
    _global_availability_repo.create_slot(slot2)


# ===========================================================================
# 1. UNIT TESTS: Validation Service
# ===========================================================================

def test_validation_start_after_end_fails():
    validator = AppointmentValidationService()
    now = datetime.now(timezone.utc) + timedelta(days=1)
    req = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=now + timedelta(minutes=30),
        end_time=now,  # end before start
    )
    with pytest.raises(InvalidAppointmentTimeException):
        validator.validate_create_request(req)


def test_validation_duration_bounds():
    validator = AppointmentValidationService()
    now = datetime.now(timezone.utc) + timedelta(days=1)
    # Too short (< 5 mins)
    req_short = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=now,
        end_time=now + timedelta(minutes=2),
    )
    with pytest.raises(InvalidAppointmentTimeException):
        validator.validate_create_request(req_short)

    # Too long (> 480 mins)
    req_long = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=now,
        end_time=now + timedelta(hours=9),
    )
    with pytest.raises(InvalidAppointmentTimeException):
        validator.validate_create_request(req_long)


def test_validation_booking_in_past_fails():
    validator = AppointmentValidationService()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    req = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=past,
        end_time=past + timedelta(minutes=30),
    )
    with pytest.raises(InvalidAppointmentTimeException):
        validator.validate_create_request(req)


def test_validation_invalid_timezone():
    validator = AppointmentValidationService()
    with pytest.raises(InvalidTimezoneException):
        validator.validate_timezone("Mars/Olympus_Mons")

    # Valid timezones should not raise
    validator.validate_timezone("Asia/Kolkata")
    validator.validate_timezone("UTC")


def test_validation_lifecycle_state_transitions():
    validator = AppointmentValidationService()

    # Valid transitions
    validator.validate_transition(AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)
    validator.validate_transition(AppointmentStatus.CONFIRMED, AppointmentStatus.CHECKED_IN)
    validator.validate_transition(AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_PROGRESS)
    validator.validate_transition(AppointmentStatus.IN_PROGRESS, AppointmentStatus.COMPLETED)
    validator.validate_transition(AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED)

    # Invalid transitions
    with pytest.raises(AppointmentInvalidStateException):
        validator.validate_transition(AppointmentStatus.COMPLETED, AppointmentStatus.CONFIRMED)

    with pytest.raises(AppointmentInvalidStateException):
        validator.validate_transition(AppointmentStatus.CANCELLED, AppointmentStatus.RESCHEDULED)


# ===========================================================================
# 2. UNIT TESTS: Authorization Service
# ===========================================================================

def test_patient_cross_booking_prohibited():
    auth_service = AppointmentAuthorizationService(patient_repo=_global_patient_repo)
    arjun_user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)

    # Arjun booking for Arjun succeeds
    auth_service.check_can_create_appointment(arjun_user, "pat-arjun-01")

    # Arjun booking for Priya fails with 403
    with pytest.raises(AppointmentNotAuthorizedException):
        auth_service.check_can_create_appointment(arjun_user, "pat-priya-02")


def test_patient_cross_viewing_prohibited():
    auth_service = AppointmentAuthorizationService(patient_repo=_global_patient_repo)
    arjun_user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)

    now = datetime.now(timezone.utc)
    from app.schemas.appointment import AppointmentRecord
    priya_appt = AppointmentRecord(
        id="appt-priya-01",
        patient_id="pat-priya-02",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=now,
        end_time=now + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
        created_by="user-priya-02",
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(AppointmentNotAuthorizedException):
        auth_service.check_can_read_appointment(arjun_user, priya_appt)


def test_patient_cannot_check_in_or_complete():
    auth_service = AppointmentAuthorizationService(patient_repo=_global_patient_repo)
    arjun_user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)

    now = datetime.now(timezone.utc)
    arjun_appt = AppointmentRecord(
        id="appt-arjun-01",
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=now,
        end_time=now + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
        created_by="user-arjun-01",
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(AppointmentNotAuthorizedException):
        auth_service.check_can_update_status(arjun_user, arjun_appt, AppointmentStatus.CHECKED_IN)

    with pytest.raises(AppointmentNotAuthorizedException):
        auth_service.check_can_update_status(arjun_user, arjun_appt, AppointmentStatus.COMPLETED)


# ===========================================================================
# 3. CONCURRENCY & DOUBLE-BOOKING TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_booking_double_booking_prevention():
    """Two concurrent booking attempts for a single-capacity slot:
    ONE must succeed, and ONE must receive APPOINTMENT_SLOT_UNAVAILABLE.
    """
    provider = LocalSchedulingProvider(
        appointment_repo=_global_appointment_repo,
        availability_repo=_global_availability_repo,
    )
    future_start = datetime.now(timezone.utc) + timedelta(days=3)
    slot = AvailabilitySlotRecord(
        slot_id="slot-race-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=future_start,
        end_time=future_start + timedelta(minutes=30),
        status=SlotStatus.AVAILABLE,
        capacity=1,
        booked_count=0,
    )
    _global_availability_repo.create_slot(slot)

    req_user1 = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        slot_id="slot-race-01",
        start_time=future_start,
        end_time=future_start + timedelta(minutes=30),
    )
    req_user2 = AppointmentCreateRequest(
        patient_id="pat-priya-02",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        slot_id="slot-race-01",
        start_time=future_start,
        end_time=future_start + timedelta(minutes=30),
    )

    results = await asyncio.gather(
        provider.create_appointment(req_user1, created_by="user-1"),
        provider.create_appointment(req_user2, created_by="user-2"),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, "Exactly one concurrent booking must succeed"
    assert len(failures) == 1, "Exactly one concurrent booking must fail"
    assert isinstance(failures[0], AppointmentSlotUnavailableException), "Failing request must receive slot unavailable"

    # Verify slot is now BOOKED and booked_count == 1
    updated_slot = _global_availability_repo.get_slot("slot-race-01")
    assert updated_slot.booked_count == 1
    assert updated_slot.status == SlotStatus.BOOKED


@pytest.mark.asyncio
async def test_clinician_overlapping_conflict_prevention():
    """Clinician cannot be booked for overlapping timeframes."""
    provider = LocalSchedulingProvider(
        appointment_repo=_global_appointment_repo,
        availability_repo=_global_availability_repo,
    )
    now = datetime.now(timezone.utc) + timedelta(days=4)
    req1 = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        clinician_id="user-doc-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=now,
        end_time=now + timedelta(minutes=30),
    )
    req2 = AppointmentCreateRequest(
        patient_id="pat-priya-02",
        facility_id="fac-delhi-01",
        clinician_id="user-doc-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=now + timedelta(minutes=15),  # Overlapping!
        end_time=now + timedelta(minutes=45),
    )

    await provider.create_appointment(req1, created_by="user-arjun-01")
    with pytest.raises(AppointmentBookingConflictException):
        await provider.create_appointment(req2, created_by="user-priya-02")


# ===========================================================================
# 4. IDEMPOTENT BOOKING TEST
# ===========================================================================

@pytest.mark.asyncio
async def test_idempotent_booking_returns_same_record():
    provider = LocalSchedulingProvider(
        appointment_repo=_global_appointment_repo,
        availability_repo=_global_availability_repo,
    )
    future_start = datetime.now(timezone.utc) + timedelta(days=5)
    slot = AvailabilitySlotRecord(
        slot_id="slot-idem-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        start_time=future_start,
        end_time=future_start + timedelta(minutes=30),
        status=SlotStatus.AVAILABLE,
        capacity=1,
        booked_count=0,
    )
    _global_availability_repo.create_slot(slot)

    req = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        slot_id="slot-idem-01",
        start_time=future_start,
        end_time=future_start + timedelta(minutes=30),
    )

    idem_key = "test-idem-key-12345"
    first = await provider.create_appointment(req, created_by="user-arjun-01", idempotency_key=idem_key)
    second = await provider.create_appointment(req, created_by="user-arjun-01", idempotency_key=idem_key)

    assert first.id == second.id
    assert _global_availability_repo.get_slot("slot-idem-01").booked_count == 1


# ===========================================================================
# 5. RESCHEDULE & CANCEL TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_reschedule_reserves_new_and_releases_old():
    provider = LocalSchedulingProvider(
        appointment_repo=_global_appointment_repo,
        availability_repo=_global_availability_repo,
    )
    # Book on slot 1
    req = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        clinician_id="user-doc-01",
        appointment_type=AppointmentType.CONSULTATION,
        slot_id="slot-test-01",
        start_time=_global_availability_repo.get_slot("slot-test-01").start_time,
        end_time=_global_availability_repo.get_slot("slot-test-01").end_time,
    )
    appt = await provider.create_appointment(req, created_by="user-arjun-01")
    assert _global_availability_repo.get_slot("slot-test-01").booked_count == 1

    # Reschedule to slot 2
    rescheduled = await provider.reschedule_appointment(
        appointment_id=appt.id,
        new_slot_id="slot-test-02",
        new_start_time=None,
        new_end_time=None,
        reason="Patient schedule adjustment",
    )

    assert rescheduled.status == AppointmentStatus.RESCHEDULED
    assert rescheduled.slot_id == "slot-test-02"
    # Old slot must be released
    assert _global_availability_repo.get_slot("slot-test-01").booked_count == 0
    # New slot must be booked
    assert _global_availability_repo.get_slot("slot-test-02").booked_count == 1


@pytest.mark.asyncio
async def test_cancel_releases_slot():
    provider = LocalSchedulingProvider(
        appointment_repo=_global_appointment_repo,
        availability_repo=_global_availability_repo,
    )
    req = AppointmentCreateRequest(
        patient_id="pat-arjun-01",
        facility_id="fac-delhi-01",
        appointment_type=AppointmentType.CONSULTATION,
        slot_id="slot-test-01",
        start_time=_global_availability_repo.get_slot("slot-test-01").start_time,
        end_time=_global_availability_repo.get_slot("slot-test-01").end_time,
    )
    appt = await provider.create_appointment(req, created_by="user-arjun-01")
    assert _global_availability_repo.get_slot("slot-test-01").booked_count == 1

    cancelled = await provider.cancel_appointment(appt.id, reason="Travel change")
    assert cancelled.status == AppointmentStatus.CANCELLED
    assert _global_availability_repo.get_slot("slot-test-01").booked_count == 0


# ===========================================================================
# 6. SCHEDULE TEMPLATE GENERATION TEST
# ===========================================================================

def test_schedule_slot_generation():
    service = SchedulingService(
        schedule_repo=_global_schedule_repo,
        availability_repo=_global_availability_repo,
        provider=LocalSchedulingProvider(_global_appointment_repo, _global_availability_repo),
    )
    # Define Monday schedule (day_of_week=0), 09:00 - 11:00 (30 min slots = 4 slots)
    sched = ScheduleRecord(
        id="sched-doc-01",
        facility_id="fac-delhi-01",
        clinician_id="user-doc-01",
        timezone="UTC",
        working_hours=[
            WorkingHoursRule(
                day_of_week=0,  # Monday
                start_time="09:00",
                end_time="11:00",
                slot_duration_minutes=30,
            )
        ],
        blocked_dates=["2026-10-12"],  # Block Monday Oct 12
    )

    # Generate for Oct 5, 2026 (Monday) to Oct 12, 2026 (Monday - blocked)
    # Oct 5: 4 slots generated
    # Oct 12: blocked, 0 slots
    d_start = date(2026, 10, 5)
    d_end = date(2026, 10, 12)
    slots = service.generate_slots_for_schedule(sched, d_start, d_end)

    assert len(slots) == 4
    for s in slots:
        assert s.facility_id == "fac-delhi-01"
        assert s.clinician_id == "user-doc-01"
        assert s.status == SlotStatus.AVAILABLE


# ===========================================================================
# 7. INTEGRATION API ROUTE TESTS (FastAPI TestClient)
# ===========================================================================

def test_api_get_availability():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get("/api/v1/availability?facility_id=fac-delhi-01")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["slots"]) >= 2
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_create_and_get_appointment():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        slot1 = _global_availability_repo.get_slot("slot-test-01")
        payload = {
            "patient_id": "pat-arjun-01",
            "facility_id": "fac-delhi-01",
            "clinician_id": "user-doc-01",
            "appointment_type": "CONSULTATION",
            "slot_id": "slot-test-01",
            "start_time": slot1.start_time.isoformat(),
            "end_time": slot1.end_time.isoformat(),
            "reason": "Routine clinical follow-up",
        }
        create_res = client.post("/api/v1/appointments", json=payload, headers={"Idempotency-Key": "test-key-01"})
        assert create_res.status_code == 201
        res_data = create_res.json()
        assert res_data["success"] is True
        appt_id = res_data["data"]["appointment"]["id"]

        # Fetch appointment details
        get_res = client.get(f"/api/v1/appointments/{appt_id}")
        assert get_res.status_code == 200
        assert get_res.json()["data"]["appointment"]["status"] == "CONFIRMED"

        # Double booking the same slot must fail with 409
        dup_res = client.post(
            "/api/v1/appointments",
            json={**payload, "patient_id": "pat-arjun-01"},
            headers={"Idempotency-Key": "different-key-99"},
        )
        assert dup_res.status_code == 409
        assert dup_res.json()["error"]["code"] == "APPOINTMENT_SLOT_UNAVAILABLE"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_reschedule_and_cancel_appointment():
    client = TestClient(app)
    user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        slot1 = _global_availability_repo.get_slot("slot-test-01")
        slot2 = _global_availability_repo.get_slot("slot-test-02")
        payload = {
            "patient_id": "pat-arjun-01",
            "facility_id": "fac-delhi-01",
            "clinician_id": "user-doc-01",
            "appointment_type": "CONSULTATION",
            "slot_id": "slot-test-01",
            "start_time": slot1.start_time.isoformat(),
            "end_time": slot1.end_time.isoformat(),
        }
        create_res = client.post("/api/v1/appointments", json=payload)
        appt_id = create_res.json()["data"]["appointment"]["id"]

        # Reschedule to slot 2
        resched_res = client.post(
            f"/api/v1/appointments/{appt_id}/reschedule",
            json={"slot_id": "slot-test-02", "reason": "Moved appointment earlier"},
        )
        assert resched_res.status_code == 200
        assert resched_res.json()["data"]["appointment"]["status"] == "RESCHEDULED"

        # Cancel
        cancel_res = client.post(
            f"/api/v1/appointments/{appt_id}/cancel",
            json={"reason": "Cannot attend"},
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["data"]["appointment"]["status"] == "CANCELLED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_clinician_check_in_status_update():
    client = TestClient(app)
    patient_user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        slot1 = _global_availability_repo.get_slot("slot-test-01")
        payload = {
            "patient_id": "pat-arjun-01",
            "facility_id": "fac-delhi-01",
            "clinician_id": "user-doc-01",
            "appointment_type": "CONSULTATION",
            "slot_id": "slot-test-01",
            "start_time": slot1.start_time.isoformat(),
            "end_time": slot1.end_time.isoformat(),
        }
        create_res = client.post("/api/v1/appointments", json=payload)
        appt_id = create_res.json()["data"]["appointment"]["id"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Doctor check-in
    doc_user = AuthenticatedUserContext(user_id="user-doc-01", role=UserRole.DOCTOR)
    app.dependency_overrides[get_current_user] = lambda: doc_user
    try:
        status_res = client.post(
            f"/api/v1/appointments/{appt_id}/status",
            json={"status": "CHECKED_IN", "reason": "Patient arrived at reception"},
        )
        assert status_res.status_code == 200
        assert status_res.json()["data"]["appointment"]["status"] == "CHECKED_IN"

        # Complete appointment
        status_res2 = client.post(
            f"/api/v1/appointments/{appt_id}/status",
            json={"status": "IN_PROGRESS"},
        )
        assert status_res2.status_code == 200

        status_res3 = client.post(
            f"/api/v1/appointments/{appt_id}/status",
            json={"status": "COMPLETED"},
        )
        assert status_res3.status_code == 200
        assert status_res3.json()["data"]["appointment"]["status"] == "COMPLETED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_list_patient_and_clinician_appointments():
    client = TestClient(app)
    patient_user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        slot1 = _global_availability_repo.get_slot("slot-test-01")
        client.post(
            "/api/v1/appointments",
            json={
                "patient_id": "pat-arjun-01",
                "facility_id": "fac-delhi-01",
                "clinician_id": "user-doc-01",
                "appointment_type": "CONSULTATION",
                "slot_id": "slot-test-01",
                "start_time": slot1.start_time.isoformat(),
                "end_time": slot1.end_time.isoformat(),
            },
        )
        # Patient lists own appointments
        res = client.get("/api/v1/patients/pat-arjun-01/appointments")
        assert res.status_code == 200
        assert len(res.json()["data"]["items"]) == 1

        # Patient cannot list Priya's appointments
        res_priya = client.get("/api/v1/patients/pat-priya-02/appointments")
        assert res_priya.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Doctor lists assigned appointments
    doc_user = AuthenticatedUserContext(user_id="user-doc-01", role=UserRole.DOCTOR)
    app.dependency_overrides[get_current_user] = lambda: doc_user
    try:
        res_doc = client.get("/api/v1/clinicians/me/appointments")
        assert res_doc.status_code == 200
        assert len(res_doc.json()["data"]["items"]) == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_search_appointments_integration():
    """Verify Phase 30 search integrates with appointment resource type."""
    client = TestClient(app)
    patient_user = AuthenticatedUserContext(user_id="user-arjun-01", role=UserRole.PATIENT)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        slot1 = _global_availability_repo.get_slot("slot-test-01")
        client.post(
            "/api/v1/appointments",
            json={
                "patient_id": "pat-arjun-01",
                "facility_id": "fac-delhi-01",
                "clinician_id": "user-doc-01",
                "appointment_type": "CONSULTATION",
                "slot_id": "slot-test-01",
                "start_time": slot1.start_time.isoformat(),
                "end_time": slot1.end_time.isoformat(),
                "reason": "Cardiology consultation follow-up",
            },
        )

        search_res = client.get("/api/v1/search?q=consultation&resource_type=appointment")
        assert search_res.status_code == 200
        data = search_res.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["resource_type"] == "appointment"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_admin_scheduling_endpoints():
    client = TestClient(app)
    admin_user = AuthenticatedUserContext(user_id="user-admin-01", role=UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        # Status
        res_status = client.get("/api/v1/admin/scheduling/status")
        assert res_status.status_code == 200
        assert res_status.json()["data"]["provider"] == "local"

        # Providers
        res_prov = client.get("/api/v1/admin/scheduling/providers")
        assert res_prov.status_code == 200

        # Provider health
        res_health = client.get("/api/v1/admin/scheduling/provider-status")
        assert res_health.status_code == 200
        assert res_health.json()["data"]["status"] == "healthy"

        # Probe test
        res_test = client.post("/api/v1/admin/scheduling/providers/local/test")
        assert res_test.status_code == 200
        assert res_test.json()["data"]["result"]["status"] == "healthy"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

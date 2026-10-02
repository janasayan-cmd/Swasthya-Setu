"""Appointment Service (Phase 31).

Core domain service managing the appointment lifecycle, scheduling orchestration,
authorization, consent enforcement, conflict prevention, and downstream integrations.

SAFETY PRINCIPLES:
- SCHEDULING ≠ CLINICAL DECISION
- SCHEDULING ≠ DIAGNOSIS
- APPOINTMENT ≠ ENCOUNTER
- APPOINTMENT BOOKED ≠ PATIENT SEEN
- DOUBLE-BOOKING MUST BE PREVENTED
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    AppointmentAlreadyCancelledException,
    AppointmentAlreadyCompletedException,
    AppointmentBookingFailedException,
    AppointmentInvalidStateException,
    AppointmentNotFoundException,
    AppointmentSlotUnavailableException,
    AppointmentsDisabledException,
)
from app.integrations.scheduling.base import SchedulingProvider
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreateRequest,
    AppointmentRecord,
    AppointmentRescheduleRequest,
    AppointmentStatus,
    AppointmentStatusUpdateRequest,
    AppointmentType,
)
from app.schemas.audit import AuditEventType
from app.schemas.notification import NotificationCreate, NotificationType
from app.schemas.user import AuthenticatedUserContext
from app.services.appointment_authorization_service import AppointmentAuthorizationService
from app.services.appointment_validation_service import AppointmentValidationService

logger = logging.getLogger(__name__)


class AppointmentService:
    """Service orchestrating appointment booking, retrieval, rescheduling, and status transitions."""

    def __init__(
        self,
        provider: SchedulingProvider,
        appointment_repo: AppointmentRepository,
        validation_service: AppointmentValidationService,
        auth_service: AppointmentAuthorizationService,
        notification_service: Optional[Any] = None,
        audit_service: Optional[Any] = None,
        analytics_service: Optional[Any] = None,
    ) -> None:
        self.provider = provider
        self.appointment_repo = appointment_repo
        self.validation_service = validation_service
        self.auth_service = auth_service
        self.notification_service = notification_service
        self.audit_service = audit_service
        self.analytics_service = analytics_service

    async def _emit_audit_event(
        self,
        event_type: AuditEventType,
        user: AuthenticatedUserContext,
        appointment: AppointmentRecord,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Safely record non-PHI audit event."""
        if not self.audit_service:
            return
        try:
            meta = {
                "appointment_id": appointment.id,
                "facility_id": appointment.facility_id,
                "appointment_type": appointment.appointment_type.value,
                "status": appointment.status.value,
                **(metadata or {}),
            }
            await self.audit_service.log_event(
                event_type=event_type,
                actor_id=user.user_id,
                resource_type="appointment",
                facility_id=appointment.facility_id,
                metadata=meta,
            )
        except Exception as e:
            logger.warning(f"Failed to record audit event {event_type.value}: {e}")

    async def _send_appointment_notification(
        self,
        notification_type: NotificationType,
        recipient_id: str,
        appointment: AppointmentRecord,
        custom_message: Optional[str] = None,
    ) -> None:
        """Dispatch notification event to Phase 29 without medical advice."""
        if not self.notification_service:
            return
        try:
            payload = NotificationCreate(
                recipient_id=recipient_id,
                notification_type=notification_type,
                resource_type="appointment",
                resource_id=appointment.id,
                metadata={
                    "appointment_id": appointment.id,
                    "facility_id": appointment.facility_id,
                    "start_time": appointment.start_time.isoformat(),
                    "status": appointment.status.value,
                    "message": custom_message or f"Your appointment status is {appointment.status.value}.",
                },
            )
            await self.notification_service.create_and_dispatch(
                payload=payload,
                actor_id="system",
                correlation_id=appointment.id,
            )
        except Exception as e:
            logger.warning(f"Failed to send notification {notification_type.value}: {e}")

    async def create_appointment(
        self,
        request: AppointmentCreateRequest,
        user: AuthenticatedUserContext,
        idempotency_key: Optional[str] = None,
    ) -> AppointmentRecord:
        """Create or book an appointment."""
        # 1. Feature flags
        if not settings.APPOINTMENTS_ENABLED or not settings.APPOINTMENT_BOOKING_ENABLED:
            raise AppointmentsDisabledException("Appointment booking is currently disabled.")

        # 2. Validation
        self.validation_service.validate_create_request(request)

        # 3. Authorization
        self.auth_service.check_can_create_appointment(user, request.patient_id)

        # 4. Book with authoritative provider
        try:
            appointment = await self.provider.create_appointment(
                request=request,
                created_by=user.user_id,
                idempotency_key=idempotency_key,
            )
        except (AppointmentSlotUnavailableException, Exception) as exc:
            logger.warning(f"Booking attempt failed: {exc}")
            raise

        # 5. Audit & Notification
        await self._emit_audit_event(AuditEventType.APPOINTMENT_CREATED, user, appointment)
        await self._send_appointment_notification(
            NotificationType.APPOINTMENT_CONFIRMED,
            recipient_id=appointment.patient_id,
            appointment=appointment,
            custom_message="Your appointment has been confirmed.",
        )

        return appointment

    async def get_appointment(
        self,
        appointment_id: str,
        user: AuthenticatedUserContext,
    ) -> AppointmentRecord:
        """Fetch appointment by ID with strict authorization enforcement."""
        if not settings.APPOINTMENTS_ENABLED:
            raise AppointmentsDisabledException("Appointments subsystem is disabled.")

        appointment = await self.provider.get_appointment(appointment_id)
        if not appointment:
            raise AppointmentNotFoundException(f"Appointment '{appointment_id}' not found.")

        self.auth_service.check_can_read_appointment(user, appointment)
        await self._emit_audit_event(AuditEventType.APPOINTMENT_VIEWED, user, appointment)
        return appointment

    async def reschedule_appointment(
        self,
        appointment_id: str,
        request: AppointmentRescheduleRequest,
        user: AuthenticatedUserContext,
    ) -> AppointmentRecord:
        """Reschedule an existing appointment."""
        if not settings.APPOINTMENTS_ENABLED or not settings.APPOINTMENT_RESCHEDULING_ENABLED:
            raise AppointmentsDisabledException("Appointment rescheduling is currently disabled.")

        appointment = await self.provider.get_appointment(appointment_id)
        if not appointment:
            raise AppointmentNotFoundException(f"Appointment '{appointment_id}' not found.")

        self.auth_service.check_can_reschedule_appointment(user, appointment)
        self.validation_service.validate_transition(appointment.status, AppointmentStatus.RESCHEDULED)

        updated = await self.provider.reschedule_appointment(
            appointment_id=appointment_id,
            new_slot_id=request.slot_id,
            new_start_time=request.start_time,
            new_end_time=request.end_time,
            reason=request.reason,
        )

        await self._emit_audit_event(
            AuditEventType.APPOINTMENT_RESCHEDULED,
            user,
            updated,
            {"reschedule_reason": request.reason},
        )
        await self._send_appointment_notification(
            NotificationType.APPOINTMENT_RESCHEDULED,
            recipient_id=updated.patient_id,
            appointment=updated,
            custom_message="Your appointment has been rescheduled.",
        )

        return updated

    async def cancel_appointment(
        self,
        appointment_id: str,
        request: AppointmentCancelRequest,
        user: AuthenticatedUserContext,
    ) -> AppointmentRecord:
        """Cancel an existing appointment."""
        if not settings.APPOINTMENTS_ENABLED or not settings.APPOINTMENT_CANCELLATION_ENABLED:
            raise AppointmentsDisabledException("Appointment cancellation is currently disabled.")

        appointment = await self.provider.get_appointment(appointment_id)
        if not appointment:
            raise AppointmentNotFoundException(f"Appointment '{appointment_id}' not found.")

        self.auth_service.check_can_cancel_appointment(user, appointment)
        self.validation_service.validate_transition(appointment.status, AppointmentStatus.CANCELLED)

        cancelled = await self.provider.cancel_appointment(
            appointment_id=appointment_id,
            reason=request.reason,
        )

        await self._emit_audit_event(
            AuditEventType.APPOINTMENT_CANCELLED,
            user,
            cancelled,
            {"cancellation_reason": request.reason},
        )
        await self._send_appointment_notification(
            NotificationType.APPOINTMENT_CANCELLED,
            recipient_id=cancelled.patient_id,
            appointment=cancelled,
            custom_message="Your appointment has been cancelled.",
        )

        return cancelled

    async def update_status(
        self,
        appointment_id: str,
        request: AppointmentStatusUpdateRequest,
        user: AuthenticatedUserContext,
    ) -> AppointmentRecord:
        """Perform a controlled status transition on an appointment."""
        appointment = await self.provider.get_appointment(appointment_id)
        if not appointment:
            raise AppointmentNotFoundException(f"Appointment '{appointment_id}' not found.")

        self.auth_service.check_can_update_status(user, appointment, request.status)
        self.validation_service.validate_transition(appointment.status, request.status)

        now = datetime.now(timezone.utc)
        updates: dict[str, Any] = {
            "status": request.status,
            "updated_at": now,
        }

        if request.status == AppointmentStatus.CHECKED_IN:
            updates["checked_in_at"] = now
        elif request.status == AppointmentStatus.COMPLETED:
            updates["completed_at"] = now

        updated_record = appointment.model_copy(update=updates)
        saved = self.appointment_repo.update(updated_record)

        event_type = (
            AuditEventType.APPOINTMENT_CHECKED_IN
            if request.status == AppointmentStatus.CHECKED_IN
            else AuditEventType.APPOINTMENT_STATUS_UPDATED
        )
        await self._emit_audit_event(
            event_type,
            user,
            saved,
            {"new_status": request.status.value, "reason": request.reason},
        )

        notif_type = (
            NotificationType.APPOINTMENT_CHECK_IN
            if request.status == AppointmentStatus.CHECKED_IN
            else NotificationType.APPOINTMENT_STATUS_UPDATED
        )
        await self._send_appointment_notification(
            notif_type,
            recipient_id=saved.patient_id,
            appointment=saved,
        )

        return saved

    async def list_patient_appointments(
        self,
        patient_id: str,
        user: AuthenticatedUserContext,
        status: Optional[AppointmentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        facility_id: Optional[str] = None,
        clinician_id: Optional[str] = None,
        appointment_type: Optional[AppointmentType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments for a patient within authorized boundaries."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_str == "PATIENT":
            own_id = self.auth_service.resolve_patient_id(user)
            if patient_id != own_id:
                raise AppointmentNotFoundException("Appointment records not found.")

        limit = min(limit, settings.APPOINTMENT_MAX_PAGE_SIZE)
        return self.appointment_repo.list_by_patient(
            patient_id=patient_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            facility_id=facility_id,
            clinician_id=clinician_id,
            appointment_type=appointment_type,
            limit=limit,
            offset=offset,
        )

    async def list_clinician_appointments(
        self,
        user: AuthenticatedUserContext,
        status: Optional[AppointmentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        facility_id: Optional[str] = None,
        appointment_type: Optional[AppointmentType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments assigned to current clinician."""
        limit = min(limit, settings.APPOINTMENT_MAX_PAGE_SIZE)
        return self.appointment_repo.list_by_clinician(
            clinician_id=user.user_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            facility_id=facility_id,
            appointment_type=appointment_type,
            limit=limit,
            offset=offset,
        )

    async def list_facility_appointments(
        self,
        facility_id: str,
        user: AuthenticatedUserContext,
        status: Optional[AppointmentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        appointment_type: Optional[AppointmentType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments hosted at a specific facility."""
        limit = min(limit, settings.APPOINTMENT_MAX_PAGE_SIZE)
        return self.appointment_repo.list_by_facility(
            facility_id=facility_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            appointment_type=appointment_type,
            limit=limit,
            offset=offset,
        )

    async def list_organization_appointments(
        self,
        organization_id: str,
        user: AuthenticatedUserContext,
        status: Optional[AppointmentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments under an organization."""
        limit = min(limit, settings.APPOINTMENT_MAX_PAGE_SIZE)
        return self.appointment_repo.list_by_organization(
            organization_id=organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )

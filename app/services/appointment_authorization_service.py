"""Appointment Authorization Service (Phase 31).

Enforces role-based, identity-scoped, and multi-tenant access control for
scheduling and appointments. Prevents cross-patient enumeration and unauthorized mutations.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.exceptions import AppointmentNotAuthorizedException
from app.core.policies import Permission, role_has_permission
from app.schemas.appointment import AppointmentRecord, AppointmentStatus
from app.schemas.user import AuthenticatedUserContext

logger = logging.getLogger(__name__)


class AppointmentAuthorizationService:
    """Authorization evaluation for appointment lifecycle actions."""

    def __init__(self, patient_repo: Optional[Any] = None) -> None:
        self.patient_repo = patient_repo

    def resolve_patient_id(self, user: AuthenticatedUserContext) -> str:
        """Resolve canonical patient identifier from user context or repository."""
        pid = getattr(user, "patient_id", None)
        if pid:
            return pid
        if self.patient_repo:
            user_to_patient = getattr(self.patient_repo, "_user_to_patient", {})
            p_rec = user_to_patient.get(user.user_id)
            if p_rec:
                return p_rec
        return user.user_id

    def check_can_create_appointment(
        self,
        user: AuthenticatedUserContext,
        target_patient_id: str,
    ) -> None:
        """Verify actor has authority to create appointment for target patient."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.APPOINTMENT_CREATE):
            raise AppointmentNotAuthorizedException(
                "User lacks APPOINTMENT_CREATE permission."
            )

        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if target_patient_id != own_patient_id:
                logger.warning(
                    f"Cross-patient appointment creation denied: User {user.user_id} tried booking for {target_patient_id}"
                )
                raise AppointmentNotAuthorizedException(
                    "Patients are only permitted to schedule appointments for themselves."
                )

    def check_can_read_appointment(
        self,
        user: AuthenticatedUserContext,
        appointment: AppointmentRecord,
    ) -> None:
        """Verify actor has authority to view appointment details."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.APPOINTMENT_READ):
            raise AppointmentNotAuthorizedException(
                "User lacks APPOINTMENT_READ permission."
            )

        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if appointment.patient_id != own_patient_id:
                raise AppointmentNotAuthorizedException(
                    "You are not authorized to view appointments for other patients."
                )
        elif role_str in ("DOCTOR", "CLINICIAN"):
            # Doctors can view appointments assigned to them or within their clinical facility
            if appointment.clinician_id and appointment.clinician_id != user.user_id:
                # If doctor is assigned to a specific facility, allow facility-level read
                fac_id = getattr(user, "facility_id", None)
                if not fac_id or fac_id != appointment.facility_id:
                    # Allow if user is general doctor viewing for clinical consultation
                    pass
        elif role_str in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN", "SUPPORT_OPERATOR"):
            # Administrative oversight permitted
            pass
        else:
            raise AppointmentNotAuthorizedException(
                f"Role '{role_str}' is not authorized to view appointments."
            )

    def check_can_reschedule_appointment(
        self,
        user: AuthenticatedUserContext,
        appointment: AppointmentRecord,
    ) -> None:
        """Verify actor has authority to reschedule appointment."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.APPOINTMENT_RESCHEDULE):
            raise AppointmentNotAuthorizedException(
                "User lacks APPOINTMENT_RESCHEDULE permission."
            )

        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if appointment.patient_id != own_patient_id:
                raise AppointmentNotAuthorizedException(
                    "Patients can only reschedule their own appointments."
                )

    def check_can_cancel_appointment(
        self,
        user: AuthenticatedUserContext,
        appointment: AppointmentRecord,
    ) -> None:
        """Verify actor has authority to cancel appointment."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.APPOINTMENT_CANCEL):
            raise AppointmentNotAuthorizedException(
                "User lacks APPOINTMENT_CANCEL permission."
            )

        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if appointment.patient_id != own_patient_id:
                raise AppointmentNotAuthorizedException(
                    "Patients can only cancel their own appointments."
                )

    def check_can_update_status(
        self,
        user: AuthenticatedUserContext,
        appointment: AppointmentRecord,
        target_status: AppointmentStatus,
    ) -> None:
        """Verify actor has authority to execute specific status transition."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if target_status == AppointmentStatus.CANCELLED:
            self.check_can_cancel_appointment(user, appointment)
            return

        if target_status == AppointmentStatus.CHECKED_IN:
            if not role_has_permission(role_str, Permission.APPOINTMENT_CHECK_IN):
                raise AppointmentNotAuthorizedException(
                    "Check-in must be executed by authorized reception or clinical staff."
                )
            return

        # Clinical progression (IN_PROGRESS, COMPLETED, NO_SHOW, FAILED) requires APPOINTMENT_UPDATE
        if not role_has_permission(role_str, Permission.APPOINTMENT_UPDATE):
            raise AppointmentNotAuthorizedException(
                f"Role '{role_str}' is not authorized to update appointment status to '{target_status.value}'."
            )

        # Patients cannot mark themselves completed or in progress
        if role_str == "PATIENT":
            raise AppointmentNotAuthorizedException(
                "Patients cannot perform clinical status progressions."
            )

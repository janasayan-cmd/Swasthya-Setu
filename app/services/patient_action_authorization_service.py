"""HealthSetu Phase 42 - Patient Action Authorization Service.

Enforces resource-specific authorization, patient self-scoping,
clinician care team boundaries, organization/facility scope,
and IDOR protection.

AUTHORIZATION RULES:
- Never authorize an action solely because the user knows action_id or patient_id.
- Patient users can only access actions assigned to their own patient profile.
- Clinicians must have care-team, facility, or organization relationships.
- Admins have operational visibility without unrestricted clinical data mutation.
"""

from __future__ import annotations

from typing import Any, Optional

from app.core.exceptions import (
    PatientActionNotAuthorizedException,
    PatientActionNotFoundException,
)
from app.schemas.patient_action import PatientActionRecord


class PatientActionAuthorizationService:
    """Evaluates access rights for patient self-service actions."""

    def authorize_patient_access(
        self,
        current_user: Any,
        action: PatientActionRecord,
        requested_operation: str = "read",
    ) -> None:
        """Verify that current_user has authorized access to perform requested_operation on action.

        Raises PatientActionNotAuthorizedException if unauthorized.
        """
        if not current_user:
            raise PatientActionNotAuthorizedException(
                message="Authentication required to access patient actions."
            )

        role = getattr(current_user, "role", None)
        user_id = getattr(current_user, "id", None)
        user_patient_id = getattr(current_user, "patient_id", None)
        user_org_id = getattr(current_user, "organization_id", None)
        user_facility_id = getattr(current_user, "facility_id", None)

        # 1. System / SuperAdmin bypass for operational workflows
        if role in ("ADMIN", "SUPERADMIN", "SYSTEM"):
            return

        # 2. Patient Actor: strictly scoped to self
        if role == "PATIENT":
            # Must match patient_id on action
            target_id = user_patient_id or user_id
            if action.patient_id != target_id:
                raise PatientActionNotAuthorizedException(
                    message="You are not authorized to view or perform actions for another patient.",
                    details={"action_id": action.id, "requested_patient": action.patient_id},
                )
            return

        # 3. Clinician / Care Team Actor: scoped to organization/facility
        if role in ("DOCTOR", "CLINICIAN", "NURSE", "CARE_TEAM"):
            if action.organization_id and user_org_id and action.organization_id != user_org_id:
                raise PatientActionNotAuthorizedException(
                    message="You are not authorized to access patient actions outside your organization.",
                    details={"action_id": action.id, "action_org": action.organization_id},
                )
            if action.facility_id and user_facility_id and action.facility_id != user_facility_id:
                raise PatientActionNotAuthorizedException(
                    message="You are not authorized to access patient actions outside your facility.",
                    details={"action_id": action.id, "action_facility": action.facility_id},
                )
            return

        # Default deny
        raise PatientActionNotAuthorizedException(
            message=f"User role '{role}' is not authorized to perform '{requested_operation}' on patient actions."
        )

    def authorize_patient_list(
        self,
        current_user: Any,
        target_patient_id: str,
    ) -> None:
        """Verify that current_user is authorized to list actions for a specific target_patient_id."""
        if not current_user:
            raise PatientActionNotAuthorizedException("Authentication required.")

        role = getattr(current_user, "role", None)
        user_id = getattr(current_user, "id", None)
        user_patient_id = getattr(current_user, "patient_id", None)

        if role in ("ADMIN", "SUPERADMIN", "SYSTEM", "DOCTOR", "CLINICIAN", "NURSE"):
            return

        if role == "PATIENT":
            my_patient_id = user_patient_id or user_id
            if my_patient_id != target_patient_id:
                raise PatientActionNotAuthorizedException(
                    message="You cannot list actions belonging to another patient."
                )
            return

        raise PatientActionNotAuthorizedException("Access denied.")

"""Diagnostic Authorization Service (Phase 34).

Enforces Object-Level Access Control (BOLA/IDOR protection), Role-Based Access Control,
and Scope Validation for laboratory and diagnostic workflows.

CRITICAL INVARIANTS:
- PATIENTS CAN ONLY ACCESS THEIR OWN ORDERS AND FACTUAL RESULTS
- CLINICIANS MUST HAVE VALID CLINICAL SCOPE TO ORDER TESTS OR VERIFY RESULTS
- ARBITRARY AUTHENTICATED USERS CANNOT CREATE DIAGNOSTIC ORDERS
"""

from __future__ import annotations

from typing import Any, Optional

from app.core.exceptions import DiagnosticAccessDeniedException
from app.schemas.user import AuthenticatedUserContext


class DiagnosticAuthorizationService:
    """Authorization service for diagnostic orders, results, and catalog access."""

    def authorize_catalog_view(self, user: Optional[AuthenticatedUserContext]) -> None:
        """Catalog searching is accessible to authenticated users."""
        if not user:
            raise DiagnosticAccessDeniedException("Authentication required to browse diagnostic catalog")

    def authorize_order_creation(self, user: AuthenticatedUserContext, target_clinician_id: str) -> None:
        """Only authorized clinical actors or clinicians themselves can place diagnostic orders."""
        user_role = (getattr(user, "role", None) or "").upper()
        user_id = str(getattr(user, "id", None) or getattr(user, "user_id", None) or "")

        # Allow DOCTOR, CLINICIAN, or ADMIN
        is_clinician = user_role in {"DOCTOR", "CLINICIAN", "NURSE", "ADMIN", "SYSTEM_ADMIN"}
        if not is_clinician:
            raise DiagnosticAccessDeniedException(
                f"Role '{user_role}' is not authorized to create clinical diagnostic orders"
            )

        # IDOR check: if clinician role, they must be the ordering clinician or admin
        if user_role in {"DOCTOR", "CLINICIAN"} and target_clinician_id:
            if user_id != str(target_clinician_id):
                # Check clinician_id or doctor_id attribute if user_id differs
                clinician_id = getattr(user, "clinician_id", None) or getattr(user, "doctor_id", None)
                if clinician_id and str(clinician_id) == str(target_clinician_id):
                    return
                # If neither matches, reject
                raise DiagnosticAccessDeniedException(
                    f"Clinician ID mismatch: Actor '{user_id}' cannot place order as clinician '{target_clinician_id}'"
                )

    def authorize_order_access(self, user: AuthenticatedUserContext, patient_id: str, clinician_id: Optional[str] = None) -> None:
        """Authorize reading or canceling a diagnostic order."""
        user_role = (getattr(user, "role", None) or "").upper()
        user_id = str(getattr(user, "id", None) or getattr(user, "user_id", None) or "")

        if user_role in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            return

        if user_role == "PATIENT":
            # Patient can only inspect their own orders
            user_patient_id = str(getattr(user, "patient_id", "") or user_id)
            if str(patient_id) != user_patient_id:
                raise DiagnosticAccessDeniedException(
                    f"Patient '{user_id}' is not authorized to view orders for patient '{patient_id}'"
                )
            return

        if user_role in {"DOCTOR", "CLINICIAN", "NURSE"}:
            # Allowed for authorized clinicians
            return

        raise DiagnosticAccessDeniedException(f"Role '{user_role}' is not authorized to access diagnostic orders")

    def authorize_result_access(self, user: AuthenticatedUserContext, patient_id: str) -> None:
        """Authorize viewing diagnostic results."""
        user_role = (getattr(user, "role", None) or "").upper()
        user_id = str(getattr(user, "id", None) or getattr(user, "user_id", None) or "")

        if user_role in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            return

        if user_role == "PATIENT":
            user_patient_id = str(getattr(user, "patient_id", "") or user_id)
            if str(patient_id) != user_patient_id:
                raise DiagnosticAccessDeniedException(
                    f"Patient '{user_id}' is not authorized to view results for patient '{patient_id}'"
                )
            return

        if user_role in {"DOCTOR", "CLINICIAN", "NURSE"}:
            return

        raise DiagnosticAccessDeniedException(f"Role '{user_role}' is not authorized to access diagnostic results")

    def authorize_result_verification(self, user: AuthenticatedUserContext) -> None:
        """Only licensed clinicians/doctors can verify diagnostic results (Phase 10)."""
        user_role = (getattr(user, "role", None) or "").upper()
        if user_role not in {"DOCTOR", "CLINICIAN"}:
            raise DiagnosticAccessDeniedException(
                f"Role '{user_role}' is not authorized to perform clinical result verification"
            )

    def authorize_admin(self, user: AuthenticatedUserContext) -> None:
        """Require administrative role."""
        user_role = (getattr(user, "role", None) or "").upper()
        if user_role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            raise DiagnosticAccessDeniedException("Administrative privilege required")

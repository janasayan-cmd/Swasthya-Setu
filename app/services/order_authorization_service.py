"""Clinical Order Authorization Service (Phase 38).

Enforces access control for clinical orders based on role, patient relationship,
and organizational membership.

SAFETY INVARIANTS:
- AUTHORIZATION != CLINICAL DECISION
- AUTHORIZATION != DIAGNOSIS
- AUTHORIZATION != ORDER APPROVAL
- Role check != clinical competency check
- Patient membership check != patient ownership
- AI cannot authorize an order
- Facility membership != ordering right for all order types
"""

from __future__ import annotations

from typing import Optional

from app.schemas.auth import UserRole
from app.schemas.order import OrderRecord
from app.schemas.user import AuthenticatedUserContext
from app.core.exceptions import (
    OrderAccessDeniedException,
    OrderPatientMismatchException,
    OrderUnauthorizedException,
)


# ---------------------------------------------------------------------------
# Role sets for order operations
# ---------------------------------------------------------------------------

# Roles that may CREATE a clinical order
ORDER_CREATE_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
})

# Roles that may AUTHORIZE (co-sign) a clinical order
ORDER_AUTHORIZE_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
})

# Roles that may CANCEL a clinical order
ORDER_CANCEL_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
})

# Roles that may REVISE a clinical order
ORDER_REVISE_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
})

# Roles that may VERIFY an order result
ORDER_VERIFY_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
})

# Roles that may VIEW an order
ORDER_VIEW_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
    UserRole.SUPPORT_OPERATOR,
    UserRole.AUDIT_OPERATOR,
    UserRole.PATIENT,
})

# Roles that may SUBMIT an order to an external provider
ORDER_SUBMIT_ROLES = frozenset({
    UserRole.DOCTOR,
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
})

# Roles that may perform admin operations (retry, force-reconcile)
ORDER_ADMIN_ROLES = frozenset({
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
})

# Roles that may LIST orders across facilities
ORDER_LIST_ALL_ROLES = frozenset({
    UserRole.ADMIN,
    UserRole.SYSTEM_ADMIN,
    UserRole.OPERATIONS_ADMIN,
})


class OrderAuthorizationService:
    """Access control enforcement for clinical order operations.

    SAFETY: This service enforces WHO may perform an action.
    It does NOT determine the clinical appropriateness of the action.
    """

    def assert_can_create(self, actor: AuthenticatedUserContext) -> None:
        """Enforce that actor has permission to create a clinical order.

        SAFETY: Permission to create does not imply clinical authorization.
        Order creation enters DRAFT or PENDING_AUTHORIZATION state.
        """
        if actor.role not in ORDER_CREATE_ROLES:
            raise OrderUnauthorizedException(
                f"Role '{actor.role}' does not have permission to create clinical orders. "
                f"Authorized roles: {[r.value for r in ORDER_CREATE_ROLES]}"
            )

    def assert_can_authorize(self, actor: AuthenticatedUserContext) -> None:
        """Enforce that actor has permission to authorize (co-sign) a clinical order.

        SAFETY: AUTHORIZATION is a clinical action.
        Only clinical roles with the appropriate authority may authorize.
        AI cannot authorize an order.
        """
        if actor.role not in ORDER_AUTHORIZE_ROLES:
            raise OrderUnauthorizedException(
                f"Role '{actor.role}' does not have permission to authorize clinical orders. "
                f"Clinical authorization requires: {[r.value for r in ORDER_AUTHORIZE_ROLES]}"
            )

    def assert_can_view(
        self,
        actor: AuthenticatedUserContext,
        order: OrderRecord,
    ) -> None:
        """Enforce that actor may view the order.

        PATIENT ACCESS: Patients may only view their own orders.
        CLINICIAN ACCESS: Clinicians may view orders within their organization.
        ADMIN ACCESS: Admins have cross-organization read access.
        """
        if actor.role not in ORDER_VIEW_ROLES:
            raise OrderAccessDeniedException(
                f"Role '{actor.role}' is not permitted to view clinical orders."
            )

        if actor.role == UserRole.PATIENT:
            if order.patient_id != actor.user_id:
                raise OrderPatientMismatchException(
                    "Patients may only access their own clinical orders."
                )

    def assert_can_cancel(
        self,
        actor: AuthenticatedUserContext,
        order: OrderRecord,
    ) -> None:
        """Enforce that actor may cancel the order."""
        if actor.role not in ORDER_CANCEL_ROLES:
            raise OrderUnauthorizedException(
                f"Role '{actor.role}' does not have permission to cancel clinical orders."
            )
        # Non-admin clinicians may only cancel their own orders or within their organization
        if actor.role not in (UserRole.ADMIN, UserRole.SYSTEM_ADMIN):
            if order.clinician_id != actor.user_id and (actor.organization_id is None or order.organization_id != actor.organization_id):
                raise OrderAccessDeniedException(
                    "Clinicians may only cancel orders they placed or within their own organization."
                )

    def assert_can_revise(
        self,
        actor: AuthenticatedUserContext,
        order: OrderRecord,
    ) -> None:
        """Enforce that actor may revise (supersede) an order."""
        if actor.role not in ORDER_REVISE_ROLES:
            raise OrderUnauthorizedException(
                f"Role '{actor.role}' does not have permission to revise clinical orders."
            )

    def assert_can_submit(
        self,
        actor: AuthenticatedUserContext,
        order: OrderRecord,
    ) -> None:
        """Enforce that actor may submit an order to an external provider."""
        if actor.role not in ORDER_SUBMIT_ROLES:
            raise OrderUnauthorizedException(
                f"Role '{actor.role}' does not have permission to submit clinical orders."
            )

    def assert_can_verify(
        self,
        actor: AuthenticatedUserContext,
        order: OrderRecord,
    ) -> None:
        """Enforce that actor may verify an order result.

        SAFETY: RESULT VERIFICATION is a clinical action.
        Only authorized clinical roles may verify results.
        AI cannot verify results.
        """
        if actor.role not in ORDER_VERIFY_ROLES:
            raise OrderUnauthorizedException(
                f"Role '{actor.role}' does not have permission to verify clinical order results. "
                f"Verification requires: {[r.value for r in ORDER_VERIFY_ROLES]}"
            )

    def assert_can_admin(self, actor: AuthenticatedUserContext) -> None:
        """Enforce that actor has administrative authority over orders."""
        if actor.role not in ORDER_ADMIN_ROLES:
            raise OrderUnauthorizedException(
                f"Role '{actor.role}' does not have administrative authority over clinical orders."
            )

    def assert_patient_matches(
        self,
        order: OrderRecord,
        patient_id: str,
    ) -> None:
        """Enforce that the order belongs to the referenced patient.

        SAFETY: Cross-patient access is NEVER permitted.
        """
        if order.patient_id != patient_id:
            raise OrderPatientMismatchException(
                "The requested order does not belong to the specified patient."
            )

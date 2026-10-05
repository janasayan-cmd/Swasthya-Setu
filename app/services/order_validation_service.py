"""Clinical Order Validation Service (Phase 38).

Structural and clinical context validation for order creation, authorization,
cancellation, and revision requests.

SAFETY INVARIANTS:
- VALIDATION DOES NOT PERFORM CLINICAL DECISIONS.
- VALIDATION DOES NOT PERFORM DIAGNOSIS.
- MISSING REQUIRED FIELDS => REJECT. Do not silently infer.
- VALIDATION != AUTHORIZATION.
- STRUCTURAL VALID ORDER != CLINICALLY AUTHORIZED ORDER.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas.order import (
    ENABLED_ORDER_TYPES,
    OrderCreate,
    OrderRecord,
    OrderStatus,
    OrderType,
)
from app.core.exceptions import (
    OrderInvalidException,
    OrderMissingClinicalContextException,
    OrderTypeUnsupportedException,
)


# ---------------------------------------------------------------------------
# Valid State Transition Map (TRD Section 12)
# ---------------------------------------------------------------------------

# Defines which status transitions are permitted by the domain contract.
# TRANSITIONS NOT IN THIS MAP ARE FORBIDDEN at the service layer.
VALID_TRANSITIONS: Dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({
        OrderStatus.PENDING_AUTHORIZATION,
        OrderStatus.AUTHORIZED,
        OrderStatus.CANCELLED,
        OrderStatus.SUPERSEDED,
    }),
    OrderStatus.PENDING_AUTHORIZATION: frozenset({
        OrderStatus.AUTHORIZED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
        OrderStatus.SUPERSEDED,
    }),
    OrderStatus.AUTHORIZED: frozenset({
        OrderStatus.QUEUED,
        OrderStatus.TRANSMITTING,
        OrderStatus.TRANSMITTED,
        OrderStatus.ACCEPTED,
        OrderStatus.TRANSMISSION_UNKNOWN,
        OrderStatus.FAILED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.CANCELLED,
        OrderStatus.SUPERSEDED,
    }),
    OrderStatus.QUEUED: frozenset({
        OrderStatus.TRANSMITTING,
        OrderStatus.TRANSMITTED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.CANCELLED,
    }),
    OrderStatus.TRANSMITTING: frozenset({
        OrderStatus.TRANSMITTED,
        OrderStatus.ACCEPTED,
        OrderStatus.TRANSMISSION_UNKNOWN,
        OrderStatus.PROVIDER_UNAVAILABLE,
        OrderStatus.FAILED,
        OrderStatus.RETRY_PENDING,
        OrderStatus.RECONCILIATION_REQUIRED,
    }),
    OrderStatus.TRANSMITTED: frozenset({
        OrderStatus.ACCEPTED,
        OrderStatus.IN_PROGRESS,
        OrderStatus.RESULT_AVAILABLE,
        OrderStatus.COMPLETED,
        OrderStatus.FAILED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.CANCELLED,
        OrderStatus.RECONCILIATION_REQUIRED,
        OrderStatus.TRANSMISSION_UNKNOWN,
    }),
    OrderStatus.ACCEPTED: frozenset({
        OrderStatus.IN_PROGRESS,
        OrderStatus.RESULT_PENDING,
        OrderStatus.RESULT_AVAILABLE,
        OrderStatus.COMPLETED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.CANCELLED,
        OrderStatus.FAILED,
    }),
    OrderStatus.IN_PROGRESS: frozenset({
        OrderStatus.PARTIALLY_COMPLETED,
        OrderStatus.COMPLETED,
        OrderStatus.RESULT_PENDING,
        OrderStatus.RESULT_AVAILABLE,
        OrderStatus.FAILED,
        OrderStatus.CANCEL_REQUESTED,
    }),
    OrderStatus.PARTIALLY_COMPLETED: frozenset({
        OrderStatus.COMPLETED,
        OrderStatus.RESULT_PENDING,
        OrderStatus.RESULT_AVAILABLE,
        OrderStatus.FAILED,
    }),
    OrderStatus.RESULT_PENDING: frozenset({
        OrderStatus.RESULT_AVAILABLE,
        OrderStatus.FAILED,
    }),
    OrderStatus.RESULT_AVAILABLE: frozenset({
        OrderStatus.VERIFICATION_PENDING,
        OrderStatus.VERIFIED,
        OrderStatus.COMPLETED,
    }),
    OrderStatus.VERIFICATION_PENDING: frozenset({
        OrderStatus.VERIFIED,
        OrderStatus.FAILED,
    }),
    OrderStatus.CANCEL_REQUESTED: frozenset({
        OrderStatus.CANCELLED,
        OrderStatus.RECONCILIATION_REQUIRED,
    }),
    OrderStatus.TRANSMISSION_UNKNOWN: frozenset({
        OrderStatus.RECONCILIATION_REQUIRED,
        OrderStatus.RETRY_PENDING,
        OrderStatus.TRANSMITTED,
        OrderStatus.FAILED,
    }),
    OrderStatus.PROVIDER_UNAVAILABLE: frozenset({
        OrderStatus.RETRY_PENDING,
        OrderStatus.RECONCILIATION_REQUIRED,
        OrderStatus.FAILED,
    }),
    OrderStatus.RETRY_PENDING: frozenset({
        OrderStatus.TRANSMITTING,
        OrderStatus.FAILED,
        OrderStatus.RECONCILIATION_REQUIRED,
    }),
    OrderStatus.RECONCILIATION_REQUIRED: frozenset({
        OrderStatus.TRANSMITTING,
        OrderStatus.CANCELLED,
        OrderStatus.FAILED,
        OrderStatus.AUTHORIZED,
    }),
    # Terminal states — no transitions allowed
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.VERIFIED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.FAILED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
    OrderStatus.SUPERSEDED: frozenset(),
}


class OrderValidationService:
    """Structural and operational validation for clinical orders.

    SAFETY: This service DOES NOT make clinical decisions.
    It validates structure, completeness, and state consistency.
    """

    def validate_create(self, payload: OrderCreate) -> None:
        """Validate a new order creation request.

        SAFETY RULES:
        1. patient_id is MANDATORY and cannot be inferred.
        2. clinician_id is MANDATORY.
        3. organization_id and facility_id are MANDATORY.
        4. Order type must be explicitly enabled.
        5. MEDICATION_ORDER type requires medication_order_details.
        6. Missing context => rejection, NOT silent inference.
        """
        errors: List[str] = []

        if not payload.patient_id or not payload.patient_id.strip():
            errors.append("patient_id is required and cannot be inferred.")

        if not payload.clinician_id or not payload.clinician_id.strip():
            errors.append("clinician_id is required.")

        if not payload.organization_id or not payload.organization_id.strip():
            errors.append("organization_id is required.")

        if not payload.facility_id or not payload.facility_id.strip():
            errors.append("facility_id is required.")

        if not payload.items:
            errors.append("Order must contain at least one order item.")

        # Order type enablement check
        if payload.order_type not in ENABLED_ORDER_TYPES:
            raise OrderTypeUnsupportedException(
                f"Order type '{payload.order_type}' is not supported under the current domain contract. "
                f"Supported types: {[t.value for t in ENABLED_ORDER_TYPES]}"
            )

        # Medication order safety check
        if payload.order_type in (OrderType.MEDICATION_ORDER, OrderType.MEDICATION):
            if not payload.medication_order_details:
                errors.append(
                    "medication_order_details is required for MEDICATION_ORDER. "
                    "Missing medication details must NOT be silently inferred."
                )
            else:
                required_medication_fields = ["medication_name", "dose", "route", "frequency"]
                missing = [
                    f for f in required_medication_fields
                    if not payload.medication_order_details.get(f)
                ]
                if missing:
                    errors.append(
                        f"medication_order_details is missing required fields: {missing}. "
                        "Missing medication parameters must NOT be silently inferred."
                    )

        # Referral order safety check
        if payload.order_type in (OrderType.REFERRAL_ORDER, OrderType.REFERRAL):
            if not payload.referral_details:
                errors.append(
                    "referral_details is required for REFERRAL_ORDER. "
                    "NOTE: REFERRAL != APPOINTMENT. REFERRAL != TRANSFER."
                )

        if errors:
            raise OrderMissingClinicalContextException(
                f"Order creation validation failed: {'; '.join(errors)}"
            )

    def validate_transition(
        self,
        order: OrderRecord,
        new_status: OrderStatus,
    ) -> None:
        """Validate that a requested status transition is permitted.

        Raises OrderInvalidTransitionException if the transition is not allowed.
        """
        from app.core.exceptions import (
            OrderAlreadyCancelledException,
            OrderAlreadyCompletedException,
            OrderInvalidTransitionException,
        )

        # Terminal state checks
        if order.status == OrderStatus.CANCELLED:
            raise OrderAlreadyCancelledException()

        if order.status == OrderStatus.COMPLETED:
            raise OrderAlreadyCompletedException()

        allowed = VALID_TRANSITIONS.get(order.status, frozenset())
        if new_status not in allowed:
            raise OrderInvalidTransitionException(
                f"Transition from '{order.status}' to '{new_status}' is not permitted. "
                f"Allowed transitions: {[s.value for s in allowed] if allowed else 'NONE (terminal state)'}"
            )

    def validate_cancel(self, order: OrderRecord) -> None:
        """Validate a cancellation request against the order's current state."""
        from app.core.exceptions import (
            OrderAlreadyCancelledException,
            OrderAlreadyCompletedException,
            OrderCancellationNotSupportedException,
        )

        if order.status == OrderStatus.CANCELLED:
            raise OrderAlreadyCancelledException()

        if order.status in (OrderStatus.COMPLETED, OrderStatus.VERIFIED):
            raise OrderAlreadyCompletedException(
                "Completed or verified orders cannot be cancelled."
            )

        if order.status in (OrderStatus.SUPERSEDED, OrderStatus.REJECTED):
            raise OrderCancellationNotSupportedException(
                f"Orders in '{order.status}' state cannot be cancelled."
            )

    def validate_revise(self, order: OrderRecord) -> None:
        """Validate that a revision (supersession) is permitted for the order."""
        from app.core.exceptions import (
            OrderRevisionInvalidException,
            OrderAlreadyCancelledException,
        )

        if order.status in (
            OrderStatus.CANCELLED,
            OrderStatus.COMPLETED,
            OrderStatus.VERIFIED,
            OrderStatus.SUPERSEDED,
        ):
            raise OrderRevisionInvalidException(
                f"Order in '{order.status}' state cannot be revised. "
                "Original order is preserved."
            )

    def validate_authorize(self, order: OrderRecord) -> None:
        """Validate that an order can be authorized from its current state."""
        from app.core.exceptions import OrderInvalidStateException

        if order.status not in (OrderStatus.DRAFT, OrderStatus.PENDING_AUTHORIZATION):
            raise OrderInvalidStateException(
                f"Order must be in DRAFT or PENDING_AUTHORIZATION state for authorization. "
                f"Current state: {order.status}"
            )

    def validate_verify(self, order: OrderRecord) -> None:
        """Validate that an order result can be verified."""
        from app.core.exceptions import OrderInvalidStateException

        if order.status not in (
            OrderStatus.RESULT_AVAILABLE,
            OrderStatus.VERIFICATION_PENDING,
            OrderStatus.COMPLETED,
        ):
            raise OrderInvalidStateException(
                f"Order must have results available for verification. "
                f"Current state: {order.status}"
            )

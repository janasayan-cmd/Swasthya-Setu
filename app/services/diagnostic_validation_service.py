"""Diagnostic Validation Service (Phase 34).

Enforces clinical safety invariants, lifecycle state machines, unit/range integrity,
and specimen status validation.

CRITICAL CLINICAL SAFETY BOUNDARIES:
- DIAGNOSTIC ORDER != DIAGNOSIS
- LAB RESULT != CLINICAL INTERPRETATION
- ABNORMAL RESULT != DIAGNOSIS
- CRITICAL RESULT FLAG != AUTONOMOUS TREATMENT DECISION
- REFERENCE RANGE != UNIVERSAL NORMALITY (NEVER INVENT MISSING RANGES)
- MISSING UNIT != ASSUMED UNIT (NEVER SILENTLY CONVERT UNITS)
- COMPLETED ORDERS CANNOT BE ARBITRARILY CANCELLED
"""

from __future__ import annotations

import re
from typing import List, Optional

from app.core.exceptions import (
    DiagnosticOrderInvalidStateException,
    DiagnosticOrderValidationFailedException,
    InvalidResultUnitException,
    InvalidResultValueException,
    SpecimenInvalidStateException,
)
from app.schemas.diagnostic_order import DiagnosticOrderCreate, DiagnosticOrderStatus
from app.schemas.diagnostic_result import (
    DiagnosticResultItemCreate,
    ReferenceRange,
)
from app.schemas.specimen import SpecimenStatus


# Allowed lifecycle transitions for Diagnostic Orders
ALLOWED_ORDER_TRANSITIONS = {
    DiagnosticOrderStatus.DRAFT: {
        DiagnosticOrderStatus.REQUESTED,
        DiagnosticOrderStatus.CANCELLED,
    },
    DiagnosticOrderStatus.REQUESTED: {
        DiagnosticOrderStatus.PLACED,
        DiagnosticOrderStatus.ACCEPTED,
        DiagnosticOrderStatus.SCHEDULED,
        DiagnosticOrderStatus.SPECIMEN_PENDING,
        DiagnosticOrderStatus.CANCELLED,
        DiagnosticOrderStatus.REJECTED,
        DiagnosticOrderStatus.FAILED,
    },
    DiagnosticOrderStatus.PLACED: {
        DiagnosticOrderStatus.ACCEPTED,
        DiagnosticOrderStatus.SCHEDULED,
        DiagnosticOrderStatus.SPECIMEN_PENDING,
        DiagnosticOrderStatus.IN_PROGRESS,
        DiagnosticOrderStatus.CANCELLED,
        DiagnosticOrderStatus.REJECTED,
        DiagnosticOrderStatus.FAILED,
        DiagnosticOrderStatus.UNKNOWN,
    },
    DiagnosticOrderStatus.ACCEPTED: {
        DiagnosticOrderStatus.SCHEDULED,
        DiagnosticOrderStatus.SPECIMEN_PENDING,
        DiagnosticOrderStatus.IN_PROGRESS,
        DiagnosticOrderStatus.CANCELLED,
        DiagnosticOrderStatus.FAILED,
    },
    DiagnosticOrderStatus.SCHEDULED: {
        DiagnosticOrderStatus.SPECIMEN_PENDING,
        DiagnosticOrderStatus.IN_PROGRESS,
        DiagnosticOrderStatus.CANCELLED,
    },
    DiagnosticOrderStatus.SPECIMEN_PENDING: {
        DiagnosticOrderStatus.IN_PROGRESS,
        DiagnosticOrderStatus.CANCELLED,
        DiagnosticOrderStatus.REJECTED,
    },
    DiagnosticOrderStatus.IN_PROGRESS: {
        DiagnosticOrderStatus.COMPLETED,
        DiagnosticOrderStatus.FAILED,
        DiagnosticOrderStatus.CANCELLED,
    },
    DiagnosticOrderStatus.COMPLETED: set(),  # Terminal state
    DiagnosticOrderStatus.CANCELLED: set(),  # Terminal state
    DiagnosticOrderStatus.REJECTED: set(),   # Terminal state
    DiagnosticOrderStatus.FAILED: {
        DiagnosticOrderStatus.REQUESTED,  # Allow retry
        DiagnosticOrderStatus.CANCELLED,
    },
    DiagnosticOrderStatus.UNKNOWN: {
        DiagnosticOrderStatus.ACCEPTED,
        DiagnosticOrderStatus.IN_PROGRESS,
        DiagnosticOrderStatus.COMPLETED,
        DiagnosticOrderStatus.FAILED,
        DiagnosticOrderStatus.CANCELLED,
    },
}

# Allowed specimen transitions
ALLOWED_SPECIMEN_TRANSITIONS = {
    SpecimenStatus.ORDERED: {
        SpecimenStatus.COLLECTION_PENDING,
        SpecimenStatus.COLLECTED,
        SpecimenStatus.CANCELLED,
    },
    SpecimenStatus.COLLECTION_PENDING: {
        SpecimenStatus.COLLECTED,
        SpecimenStatus.CANCELLED,
    },
    SpecimenStatus.COLLECTED: {
        SpecimenStatus.RECEIVED,
        SpecimenStatus.REJECTED,
        SpecimenStatus.CANCELLED,
    },
    SpecimenStatus.RECEIVED: {
        SpecimenStatus.PROCESSING,
        SpecimenStatus.REJECTED,
    },
    SpecimenStatus.PROCESSING: {
        SpecimenStatus.COMPLETED,
        SpecimenStatus.REJECTED,
    },
    SpecimenStatus.REJECTED: set(),   # Terminal state
    SpecimenStatus.COMPLETED: set(),  # Terminal state
    SpecimenStatus.CANCELLED: set(),  # Terminal state
    SpecimenStatus.UNKNOWN: {
        SpecimenStatus.COLLECTED,
        SpecimenStatus.RECEIVED,
        SpecimenStatus.REJECTED,
        SpecimenStatus.PROCESSING,
        SpecimenStatus.COMPLETED,
    },
}

# Known clinical unit characters pattern
VALID_UNIT_PATTERN = re.compile(r"^[a-zA-Z0-9/%*^._\s\-\[\]\(\)]+$")

# Prohibited clinical diagnosis assertion keywords in orders or comments
PROHIBITED_AUTONOMOUS_DIAGNOSES = [
    "autonomous diagnosis",
    "confirmed diagnosis of",
    "prescribe automatic",
    "treat autonomously",
]


class DiagnosticValidationService:
    """Validation service for diagnostic entities and lifecycle operations."""

    def validate_order_creation(self, order_create: DiagnosticOrderCreate) -> None:
        """Validate integrity and clinical safety of order creation request."""
        if not order_create.patient_id or not order_create.patient_id.strip():
            raise DiagnosticOrderValidationFailedException("patient_id is required")

        if not order_create.clinician_id or not order_create.clinician_id.strip():
            raise DiagnosticOrderValidationFailedException("clinician_id is required")

        if not order_create.organization_id or not order_create.organization_id.strip():
            raise DiagnosticOrderValidationFailedException("organization_id is required")

        if not order_create.facility_id or not order_create.facility_id.strip():
            raise DiagnosticOrderValidationFailedException("facility_id is required")

        if not order_create.items:
            raise DiagnosticOrderValidationFailedException("Order must contain at least one diagnostic test item")

        for item in order_create.items:
            if not item.test_id or not item.test_id.strip():
                raise DiagnosticOrderValidationFailedException("Each item must have a valid test_id")

        if order_create.clinical_reason:
            lower_reason = order_create.clinical_reason.lower()
            for kw in PROHIBITED_AUTONOMOUS_DIAGNOSES:
                if kw in lower_reason:
                    raise DiagnosticOrderValidationFailedException(
                        f"Clinical reason contains prohibited autonomous assertion '{kw}'"
                    )

    def validate_order_transition(
        self,
        current_status: DiagnosticOrderStatus,
        new_status: DiagnosticOrderStatus,
    ) -> None:
        """Validate order lifecycle state machine."""
        if current_status == new_status:
            return

        allowed = ALLOWED_ORDER_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise DiagnosticOrderInvalidStateException(
                f"Invalid order transition from '{current_status.value}' to '{new_status.value}'"
            )

    def validate_order_cancellation(self, current_status: DiagnosticOrderStatus) -> None:
        """Verify order can be cancelled."""
        if current_status == DiagnosticOrderStatus.COMPLETED:
            raise DiagnosticOrderInvalidStateException(
                "Completed diagnostic orders cannot be cancelled; completed results exist"
            )
        if current_status == DiagnosticOrderStatus.CANCELLED:
            raise DiagnosticOrderInvalidStateException("Order is already cancelled")
        if current_status == DiagnosticOrderStatus.REJECTED:
            raise DiagnosticOrderInvalidStateException("Cannot cancel an already rejected order")

    def validate_specimen_transition(
        self,
        current_status: SpecimenStatus,
        new_status: SpecimenStatus,
    ) -> None:
        """Validate specimen lifecycle state machine."""
        if current_status == new_status:
            return

        allowed = ALLOWED_SPECIMEN_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise SpecimenInvalidStateException(
                f"Invalid specimen transition from '{current_status.value}' to '{new_status.value}'"
            )

    def validate_result_items(self, items: List[DiagnosticResultItemCreate]) -> None:
        """Validate analyte measurements."""
        if not items:
            raise InvalidResultValueException("Diagnostic result must contain at least one analyte measurement")

        for item in items:
            if not item.analyte_name or not item.analyte_name.strip():
                raise InvalidResultValueException("Analyte name is required for all result items")

            # Must have either numeric or qualitative value
            if item.numeric_value is None and not item.qualitative_value:
                raise InvalidResultValueException(
                    f"Analyte '{item.analyte_name}' must have either numeric_value or qualitative_value"
                )

            # If unit is provided, validate format
            if item.unit:
                if not VALID_UNIT_PATTERN.match(item.unit):
                    raise InvalidResultUnitException(
                        f"Unit '{item.unit}' for analyte '{item.analyte_name}' has invalid syntax"
                    )

            # Validate reference range integrity if present
            if item.reference_range:
                self.validate_reference_range(item.reference_range, item.analyte_name)

    def validate_reference_range(self, ref_range: ReferenceRange, analyte_name: str) -> None:
        """Validate reference range bounds."""
        if not ref_range.is_available:
            return

        if ref_range.low is not None and ref_range.high is not None:
            if ref_range.low > ref_range.high:
                raise InvalidResultValueException(
                    f"Reference range for '{analyte_name}' has low ({ref_range.low}) greater than high ({ref_range.high})"
                )

"""Insurance, Authorization & Claim Validation Service (Phase 33).

Centralizes deterministic validation of:
- Integer minor unit monetary arithmetic (paise/cents)
- Coverage date validity (effective date <= termination date)
- Identifier formats
- Strict state machine transitions for Coverages, Pre-Authorizations, and Claims
- Claim line item totals and currency consistency
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from app.core.exceptions import (
    AuthorizationInvalidStateException,
    ClaimAmountMismatchException,
    ClaimCurrencyMismatchException,
    ClaimInvalidStateException,
    ClaimValidationFailedException,
    InsuranceIdentifierInvalidException,
    InsuranceInvalidStateException,
)
from app.schemas.authorization import PreAuthorizationStatus
from app.schemas.claim import ClaimItemCreate, ClaimItemRecord, ClaimStatus
from app.schemas.insurance import CoverageStatus, InsuranceCoverageCreate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strict State Machine Transition Graphs
# ---------------------------------------------------------------------------

VALID_COVERAGE_TRANSITIONS: dict[CoverageStatus, set[CoverageStatus]] = {
    CoverageStatus.UNVERIFIED: {
        CoverageStatus.ACTIVE,
        CoverageStatus.INACTIVE,
        CoverageStatus.EXPIRED,
        CoverageStatus.PENDING,
        CoverageStatus.UNKNOWN,
    },
    CoverageStatus.PENDING: {
        CoverageStatus.ACTIVE,
        CoverageStatus.INACTIVE,
        CoverageStatus.UNVERIFIED,
        CoverageStatus.UNKNOWN,
    },
    CoverageStatus.ACTIVE: {
        CoverageStatus.INACTIVE,
        CoverageStatus.EXPIRED,
        CoverageStatus.TERMINATED,
        CoverageStatus.UNKNOWN,
    },
    CoverageStatus.INACTIVE: {
        CoverageStatus.ACTIVE,
        CoverageStatus.TERMINATED,
        CoverageStatus.EXPIRED,
    },
    CoverageStatus.EXPIRED: {
        CoverageStatus.ACTIVE,  # Renewed
        CoverageStatus.TERMINATED,
    },
    CoverageStatus.TERMINATED: set(),  # Terminal state
    CoverageStatus.UNKNOWN: {
        CoverageStatus.ACTIVE,
        CoverageStatus.INACTIVE,
        CoverageStatus.EXPIRED,
        CoverageStatus.TERMINATED,
        CoverageStatus.UNVERIFIED,
    },
}

VALID_AUTH_TRANSITIONS: dict[PreAuthorizationStatus, set[PreAuthorizationStatus]] = {
    PreAuthorizationStatus.DRAFT: {
        PreAuthorizationStatus.REQUESTED,
        PreAuthorizationStatus.SUBMITTED,
        PreAuthorizationStatus.CANCELLED,
    },
    PreAuthorizationStatus.REQUESTED: {
        PreAuthorizationStatus.SUBMITTED,
        PreAuthorizationStatus.PENDING,
        PreAuthorizationStatus.CANCELLED,
        PreAuthorizationStatus.FAILED,
    },
    PreAuthorizationStatus.SUBMITTED: {
        PreAuthorizationStatus.PENDING,
        PreAuthorizationStatus.APPROVED,
        PreAuthorizationStatus.PARTIALLY_APPROVED,
        PreAuthorizationStatus.DENIED,
        PreAuthorizationStatus.UNKNOWN,
        PreAuthorizationStatus.FAILED,
    },
    PreAuthorizationStatus.PENDING: {
        PreAuthorizationStatus.APPROVED,
        PreAuthorizationStatus.PARTIALLY_APPROVED,
        PreAuthorizationStatus.DENIED,
        PreAuthorizationStatus.CANCELLED,
        PreAuthorizationStatus.UNKNOWN,
        PreAuthorizationStatus.FAILED,
    },
    PreAuthorizationStatus.APPROVED: {
        PreAuthorizationStatus.EXPIRED,
        PreAuthorizationStatus.CANCELLED,
    },
    PreAuthorizationStatus.PARTIALLY_APPROVED: {
        PreAuthorizationStatus.EXPIRED,
        PreAuthorizationStatus.CANCELLED,
    },
    PreAuthorizationStatus.DENIED: set(),
    PreAuthorizationStatus.CANCELLED: set(),
    PreAuthorizationStatus.EXPIRED: set(),
    PreAuthorizationStatus.UNKNOWN: {
        PreAuthorizationStatus.PENDING,
        PreAuthorizationStatus.APPROVED,
        PreAuthorizationStatus.PARTIALLY_APPROVED,
        PreAuthorizationStatus.DENIED,
        PreAuthorizationStatus.FAILED,
    },
    PreAuthorizationStatus.FAILED: {
        PreAuthorizationStatus.SUBMITTED,  # Retry
    },
}

VALID_CLAIM_TRANSITIONS: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.DRAFT: {
        ClaimStatus.VALIDATION_FAILED,
        ClaimStatus.READY,
        ClaimStatus.SUBMITTED,
        ClaimStatus.CANCELLED,
    },
    ClaimStatus.VALIDATION_FAILED: {
        ClaimStatus.DRAFT,
        ClaimStatus.READY,
        ClaimStatus.CANCELLED,
    },
    ClaimStatus.READY: {
        ClaimStatus.SUBMITTED,
        ClaimStatus.DRAFT,
        ClaimStatus.CANCELLED,
    },
    ClaimStatus.SUBMITTED: {
        ClaimStatus.RECEIVED,
        ClaimStatus.PENDING,
        ClaimStatus.ADJUDICATED,
        ClaimStatus.APPROVED,
        ClaimStatus.PARTIALLY_APPROVED,
        ClaimStatus.DENIED,
        ClaimStatus.REJECTED,
        ClaimStatus.UNKNOWN,
        ClaimStatus.FAILED,
    },
    ClaimStatus.RECEIVED: {
        ClaimStatus.PENDING,
        ClaimStatus.ADJUDICATED,
        ClaimStatus.APPROVED,
        ClaimStatus.PARTIALLY_APPROVED,
        ClaimStatus.DENIED,
        ClaimStatus.REJECTED,
        ClaimStatus.UNKNOWN,
    },
    ClaimStatus.PENDING: {
        ClaimStatus.ADJUDICATED,
        ClaimStatus.APPROVED,
        ClaimStatus.PARTIALLY_APPROVED,
        ClaimStatus.DENIED,
        ClaimStatus.REJECTED,
        ClaimStatus.UNKNOWN,
    },
    ClaimStatus.ADJUDICATED: {
        ClaimStatus.APPROVED,
        ClaimStatus.PARTIALLY_APPROVED,
        ClaimStatus.DENIED,
        ClaimStatus.PAID,
        ClaimStatus.PARTIALLY_PAID,
    },
    ClaimStatus.APPROVED: {
        ClaimStatus.PAID,
        ClaimStatus.PARTIALLY_PAID,
    },
    ClaimStatus.PARTIALLY_APPROVED: {
        ClaimStatus.PAID,
        ClaimStatus.PARTIALLY_PAID,
    },
    ClaimStatus.DENIED: {
        ClaimStatus.RESUBMITTED,
    },
    ClaimStatus.REJECTED: {
        ClaimStatus.RESUBMITTED,
        ClaimStatus.DRAFT,
    },
    ClaimStatus.PAID: set(),
    ClaimStatus.PARTIALLY_PAID: {
        ClaimStatus.PAID,
    },
    ClaimStatus.RESUBMITTED: {
        ClaimStatus.SUBMITTED,
        ClaimStatus.RECEIVED,
        ClaimStatus.PENDING,
    },
    ClaimStatus.UNKNOWN: {
        ClaimStatus.RECEIVED,
        ClaimStatus.PENDING,
        ClaimStatus.ADJUDICATED,
        ClaimStatus.APPROVED,
        ClaimStatus.PARTIALLY_APPROVED,
        ClaimStatus.DENIED,
        ClaimStatus.REJECTED,
        ClaimStatus.FAILED,
    },
    ClaimStatus.FAILED: {
        ClaimStatus.SUBMITTED,  # Safe retry
        ClaimStatus.CANCELLED,
    },
    ClaimStatus.CANCELLED: set(),
}


class InsuranceValidationService:
    """Deterministic validation logic for insurance, pre-authorizations, and claims."""

    @classmethod
    def validate_coverage_create(cls, payload: InsuranceCoverageCreate) -> None:
        """Validate newly registered policy payload."""
        if not payload.policy_number or len(payload.policy_number.strip()) < 2:
            raise InsuranceIdentifierInvalidException("Policy number must be at least 2 characters")
        if not payload.member_id or len(payload.member_id.strip()) < 2:
            raise InsuranceIdentifierInvalidException("Member ID must be at least 2 characters")

        if payload.start_date and payload.end_date:
            if payload.start_date > payload.end_date:
                raise InsuranceIdentifierInvalidException(
                    f"Policy start date {payload.start_date} cannot be after end date {payload.end_date}"
                )

    @classmethod
    def validate_coverage_transition(cls, current: CoverageStatus, target: CoverageStatus) -> None:
        """Enforce strict coverage lifecycle transition rules."""
        if current == target:
            return
        allowed = VALID_COVERAGE_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InsuranceInvalidStateException(
                f"Illegal coverage state transition from {current.value} to {target.value}"
            )

    @classmethod
    def validate_auth_transition(cls, current: PreAuthorizationStatus, target: PreAuthorizationStatus) -> None:
        """Enforce strict pre-authorization lifecycle transition rules."""
        if current == target:
            return
        allowed = VALID_AUTH_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise AuthorizationInvalidStateException(
                f"Illegal authorization state transition from {current.value} to {target.value}"
            )

    @classmethod
    def validate_claim_transition(cls, current: ClaimStatus, target: ClaimStatus) -> None:
        """Enforce strict claim lifecycle transition rules."""
        if current == target:
            return
        allowed = VALID_CLAIM_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ClaimInvalidStateException(
                f"Illegal claim state transition from {current.value} to {target.value}"
            )

    @classmethod
    def calculate_claim_item_total(cls, item: ClaimItemCreate) -> int:
        """Deterministic integer minor unit calculation: (unit_price * qty) + tax - discount."""
        gross = item.unit_price_in_minor_units * item.quantity
        total = gross + item.tax_in_minor_units - item.discount_in_minor_units
        if total < 0:
            raise ClaimValidationFailedException(
                f"Discount ({item.discount_in_minor_units}) cannot exceed gross ({gross}) + tax ({item.tax_in_minor_units})"
            )
        return total

    @classmethod
    def calculate_claim_totals(
        cls,
        items: List[ClaimItemCreate],
        claim_id: str,
        default_currency: str = "INR",
    ) -> Tuple[List[ClaimItemRecord], int]:
        """Aggregate line items and calculate deterministic total in minor units."""
        if not items:
            raise ClaimValidationFailedException("Claim must contain at least one billable line item")

        total = 0
        records: List[ClaimItemRecord] = []

        import uuid
        for item in items:
            if item.currency.upper() != default_currency.upper():
                raise ClaimCurrencyMismatchException(
                    f"Line item currency {item.currency} does not match claim currency {default_currency}"
                )
            item_tot = cls.calculate_claim_item_total(item)
            total += item_tot

            record = ClaimItemRecord(
                id=f"clm_itm_{uuid.uuid4().hex[:12]}",
                claim_id=claim_id,
                description=item.description,
                service_code=item.service_code,
                category=item.category,
                unit_price_in_minor_units=item.unit_price_in_minor_units,
                quantity=item.quantity,
                tax_in_minor_units=item.tax_in_minor_units,
                discount_in_minor_units=item.discount_in_minor_units,
                total_in_minor_units=item_tot,
                currency=item.currency.upper(),
                appointment_id=item.appointment_id,
                invoice_item_id=item.invoice_item_id,
            )
            records.append(record)

        return records, total

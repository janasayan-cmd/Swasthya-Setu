"""Phase 48: Safety Retry & Unknown Outcome Service.

Guards against unsafe blind retries of sensitive clinical operations,
enforces idempotency boundaries, and mandates reconciliation for unknown outcomes.
"""

from typing import Any
from app.core.exceptions import (
    ReconciliationRequiredException,
    UnknownOutcomeException,
    UnsafeRetryException,
)
from app.repositories.safety_repository import SafetyRepository, safety_repository


class SafetyRetryService:
    """Service governing clinical retry safety and unknown outcome reconciliation."""

    def __init__(self, repository: SafetyRepository | None = None) -> None:
        self.repository = repository or safety_repository

    def validate_retry_safety(self, op_key: str, operation_name: str) -> None:
        """Verify whether an operation can safely be attempted or retried.

        Raises UnsafeRetryException if already successfully executed.
        Raises ReconciliationRequiredException if outcome was unknown (e.g. timeout after dispatch).
        """
        prior_execution = self.repository.get_operation_execution(op_key)
        if not prior_execution:
            return

        status = prior_execution.get("status")
        if status == "SUCCESS":
            raise UnsafeRetryException(
                f"Unsafe retry prevented: operation '{operation_name}' with key '{op_key}' has already succeeded.",
                details={"op_key": op_key, "executed_at": str(prior_execution.get("executed_at"))},
            )

        if status == "UNKNOWN":
            raise ReconciliationRequiredException(
                f"Prior attempt for '{operation_name}' ended with an unknown outcome (e.g. timeout). Clinical reconciliation is required before retry.",
                details={"op_key": op_key, "required_action": "RECONCILIATION_REQUIRED"},
            )

    def record_attempt_result(self, op_key: str, status: str, check_id: str) -> None:
        """Record outcome of an operational attempt."""
        self.repository.record_operation_execution(op_key, status, check_id)

    def handle_upstream_timeout(self, op_key: str, check_id: str, operation_name: str) -> None:
        """Handle timeout where outcome cannot be verified. Records UNKNOWN and raises UnknownOutcomeException."""
        self.record_attempt_result(op_key, "UNKNOWN", check_id)
        raise UnknownOutcomeException(
            f"Upstream provider timed out during '{operation_name}'. State is indeterminate; reconciliation required.",
            details={"op_key": op_key, "check_id": check_id},
        )


# Global singleton
safety_retry_service = SafetyRetryService()

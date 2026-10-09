"""Phase 64: Clinical Safety Risk Handoff Concurrency Service.

Protects against race conditions and out-of-order state transitions.
"""

from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_handoff import SafetyRiskHandoffRecord


class SafetyRiskHandoffConcurrencyService:
    """Enforces optimistic concurrency checks for handoff updates."""

    @classmethod
    def increment_version(cls, handoff: SafetyRiskHandoffRecord) -> None:
        """Increment record modification version."""
        handoff.version += 1

    @classmethod
    def verify_version(
        cls,
        handoff: SafetyRiskHandoffRecord,
        expected_version: Optional[int],
    ) -> None:
        """Verify that record has not been concurrently mutated."""
        if expected_version is not None and handoff.version != expected_version:
            raise AppException(
                code=ErrorCode.CONCURRENCY_CONFLICT,
                message=f"Handoff '{handoff.handoff_id}' was modified concurrently (current v{handoff.version}, expected v{expected_version}).",
                status_code=status.HTTP_409_CONFLICT,
            )

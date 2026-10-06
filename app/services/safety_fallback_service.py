"""Phase 48: Safety Fallback & Circuit Breaker Service.

Implements circuit-breaker pattern for external safety providers, governs
approved fallback provider routing, and enforces fail-safe unavailable defaults.
"""

from typing import Any
from app.core.exceptions import SafetyEvaluationUnavailableException
from app.repositories.safety_repository import SafetyRepository, safety_repository
from app.schemas.safety_result import SafetyStatus


class SafetyFallbackService:
    """Service governing provider circuit breakers and fallback selection."""

    def __init__(self, repository: SafetyRepository | None = None) -> None:
        self.repository = repository or safety_repository

    def get_circuit_state(self, provider_name: str) -> str:
        """Retrieve current circuit state for a provider."""
        return self.repository.get_circuit_state(provider_name)

    def record_failure(self, provider_name: str, threshold: int = 3) -> dict[str, Any]:
        """Record provider failure and potentially open circuit."""
        return self.repository.record_circuit_failure(provider_name, threshold)

    def record_success(self, provider_name: str) -> None:
        """Record provider success and reset circuit to CLOSED."""
        self.repository.record_circuit_success(provider_name)

    def execute_with_fallback(
        self,
        primary_provider: str,
        fallback_provider: str | None,
        provider_call_status: str | None,
        allow_fallback: bool = True,
    ) -> dict[str, Any]:
        """Evaluate provider status, applying fallback if permitted.

        Returns safe evaluation outcome. Raises SafetyEvaluationUnavailableException if
        both primary and fallback are unavailable. NEVER returns a reassuring CLEAR on failure.
        """
        circuit_state = self.get_circuit_state(primary_provider)

        # If primary failed or circuit is open
        is_primary_failed = (
            circuit_state == "OPEN"
            or provider_call_status in ["TIMEOUT", "ERROR", "UNAVAILABLE", "FAILED"]
        )

        if not is_primary_failed:
            self.record_success(primary_provider)
            return {
                "provider": primary_provider,
                "status": SafetyStatus.ALLOWED,
                "fallback_used": False,
            }

        # Primary has failed
        self.record_failure(primary_provider)

        if allow_fallback and fallback_provider:
            # Check fallback circuit
            fb_circuit = self.get_circuit_state(fallback_provider)
            if fb_circuit != "OPEN":
                return {
                    "provider": fallback_provider,
                    "status": SafetyStatus.ALLOWED,
                    "fallback_used": True,
                    "reason": f"Primary provider '{primary_provider}' unavailable; routed to approved fallback '{fallback_provider}'",
                }

        # No safe fallback available -> Fail safe state
        raise SafetyEvaluationUnavailableException(
            f"Clinical safety provider '{primary_provider}' is unavailable and no viable fallback exists. Operation fails safe.",
            details={
                "primary_provider": primary_provider,
                "circuit_state": circuit_state,
                "fallback_provider": fallback_provider,
                "fail_safe_status": SafetyStatus.UNAVAILABLE.value,
            },
        )


# Global singleton
safety_fallback_service = SafetyFallbackService()

"""Phase 48: Safety Policy Service.

Loads, validates, and governs versioned safety policies and action boundaries.
Ensures historical decisions preserve their original policy references.
"""

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import SafetyPolicyBlockedException
from app.repositories.safety_repository import SafetyRepository, safety_repository
from app.schemas.safety_policy import SafetyPolicyRecord, SafetyPolicyType


class SafetyPolicyService:
    """Service governing safety policies and action restrictions."""

    def __init__(self, repository: SafetyRepository | None = None) -> None:
        self.repository = repository or safety_repository

    def get_policy(self, policy_type: SafetyPolicyType, version: str | None = None) -> SafetyPolicyRecord:
        """Retrieve active or specific versioned policy. Defaults to baseline if not registered."""
        policy = self.repository.get_policy(policy_type, version)
        if policy:
            return policy

        # Construct default fallback policy if not registered
        now = datetime.now(timezone.utc)
        default_policy = SafetyPolicyRecord(
            policy_id=f"POL-{policy_type.value}-1.0.0",
            policy_type=policy_type,
            policy_version=version or "1.0.0",
            name=f"Default {policy_type.value} Policy",
            description="Default safety policy baseline.",
            mandatory_controls=["AUTHORIZATION_CHECK", "CONSENT_CHECK", "VERSION_FRESHNESS_CHECK"],
            prohibited_actions=["AUTONOMOUS_CLINICAL_ACTION"],
            fail_safe_status="BLOCKED",
            effective_timestamp=now,
            is_active=True,
        )
        self.repository.register_policy(default_policy)
        return default_policy

    def evaluate_action_permission(
        self,
        policy_type: SafetyPolicyType,
        action: str,
        policy_version: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check whether an action is permitted under the applicable policy.

        Returns (is_allowed, reason_code).
        """
        policy = self.get_policy(policy_type, policy_version)
        normalized_action = action.upper().replace(":", "_").replace("-", "_")

        for prohibited in policy.prohibited_actions:
            if prohibited.upper() in normalized_action or normalized_action in prohibited.upper():
                return False, f"PROHIBITED_ACTION_{prohibited}"

        return True, None

    def assert_action_permitted(
        self,
        policy_type: SafetyPolicyType,
        action: str,
        policy_version: str | None = None,
    ) -> None:
        """Assert action is allowed; raise SafetyPolicyBlockedException if blocked."""
        allowed, reason = self.evaluate_action_permission(policy_type, action, policy_version)
        if not allowed:
            raise SafetyPolicyBlockedException(
                f"Action '{action}' is prohibited under safety policy '{policy_type.value}' ({policy_version or '1.0.0'}).",
                details={"action": action, "policy_type": policy_type.value, "reason": reason},
            )

    def list_policies(self) -> list[SafetyPolicyRecord]:
        """List all registered safety policies."""
        return self.repository.list_policies()


# Global singleton
safety_policy_service = SafetyPolicyService()

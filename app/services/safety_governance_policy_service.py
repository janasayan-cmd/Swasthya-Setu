"""Phase 51: Safety Governance Policy Service.

Enforces:
- Server-side authority validation
- Separation of duties (author != approver, identifier != validator)
- AI authority prohibitions (AI cannot accept risk, approve changes, or close governance)
- Expiry and staleness evaluations
- Multi-tenancy and organization boundaries
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Optional

from app.core.config import settings
from app.core.exceptions import (
    AISafetyGovernanceAuthorityProhibitedException,
    RiskAccessDeniedException,
    SafetyChangeApprovalDeniedException,
    SafetyChangeScopeInvalidException,
)
from app.schemas.risk import RiskRecord
from app.schemas.safety_change import SafetyChangeRecord

logger = logging.getLogger("app.safety_governance_policy_service")


class SafetyGovernancePolicyService:
    """Enforces clinical safety governance rules, authority gates, and separation of duties."""

    def assert_human_safety_authority(self, actor_id: str, actor_role: str, action: str) -> None:
        """Validate that actor is human and not an AI assistant / bot."""
        role_upper = (actor_role or "").upper()
        actor_upper = (actor_id or "").upper()
        if (
            "AI" in role_upper
            or "BOT" in role_upper
            or "MODEL" in role_upper
            or "LLM" in role_upper
            or "AI-" in actor_upper
        ):
            logger.warning(
                "Blocked autonomous AI attempt to perform governed action '%s' by actor '%s' (%s)",
                action,
                actor_id,
                actor_role,
            )
            raise AISafetyGovernanceAuthorityProhibitedException(
                f"AI systems cannot autonomously perform safety governance action '{action}'. "
                "Human clinical safety authority is mandatory."
            )

    def validate_separation_of_duties(
        self,
        creator_id: str,
        approver_id: str,
        operation_name: str = "approve_change",
    ) -> None:
        """Ensure that the author of a safety change does not approve their own change."""
        if not settings.SAFETY_GOVERNANCE_SEPARATION_OF_DUTIES_ENFORCED:
            return

        if creator_id and approver_id and creator_id == approver_id:
            logger.warning(
                "Separation of duties violation: creator '%s' attempted to self-approve change for '%s'",
                creator_id,
                operation_name,
            )
            raise SafetyChangeApprovalDeniedException(
                f"Separation of duties violation: change author cannot {operation_name} their own safety change."
            )

    def validate_org_boundary(
        self,
        record_org_id: Optional[str],
        actor_org_id: Optional[str],
        entity_type: str = "risk",
    ) -> None:
        """Validate multi-tenant organization boundary."""
        if not record_org_id or not actor_org_id:
            return
        if record_org_id != actor_org_id:
            logger.warning(
                "Cross-organization boundary violation on %s: record_org=%s, actor_org=%s",
                entity_type,
                record_org_id,
                actor_org_id,
            )
            raise RiskAccessDeniedException(
                f"Cross-organization access denied for {entity_type}."
            )

    def is_acceptance_expired(self, accepted_at: datetime, expires_at: Optional[datetime]) -> bool:
        """Check whether temporary risk acceptance has reached expiry."""
        if not expires_at:
            return False
        return datetime.now(timezone.utc) >= expires_at

    def calculate_acceptance_expiry(self, days: Optional[int] = None) -> datetime:
        """Compute expiration timestamp for temporary risk acceptance."""
        valid_days = days or settings.SAFETY_GOVERNANCE_DEFAULT_ACCEPTANCE_EXPIRY_DAYS
        return datetime.now(timezone.utc) + timedelta(days=valid_days)


# Global singleton policy service
safety_governance_policy_service = SafetyGovernancePolicyService()

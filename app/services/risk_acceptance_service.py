"""Phase 51: Risk Acceptance & Expiry Management Service.

Governs explicit residual risk acceptance, separation of duties between assessment and acceptance,
expiration tracking (ACCEPTED -> EXPIRING -> EXPIRED -> REASSESSMENT_REQUIRED),
and rejection / deferral workflows.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import (
    RiskAcceptanceDeniedException,
    RiskAcceptanceExpiredException,
    RiskAlreadyAcceptedException,
    RiskAlreadyClosedException,
    RiskAssessmentRequiredException,
    RiskNotFoundException,
    RiskVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.risk import RiskHistoryEntry, RiskRecord
from app.schemas.safety_approval import (
    RiskAcceptanceRequest,
    RiskAcceptanceRecord,
)
from app.schemas.safety_governance import (
    RiskSeverity,
    RiskState,
)
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.risk_acceptance_service")


class RiskAcceptanceService:
    """Service governing explicit authorization for residual risk acceptance."""

    def __init__(
        self,
        repository: Optional[SafetyGovernanceRepository] = None,
        policy_service: Optional[SafetyGovernancePolicyService] = None,
        audit_svc: Optional[AuditService] = None,
        metrics_svc: Optional[SafetyGovernanceMetricsService] = None,
    ) -> None:
        self.repository = repository or safety_governance_repository
        self.policy_service = policy_service or safety_governance_policy_service
        self.audit_service = audit_svc or audit_service
        self.metrics_service = metrics_svc or safety_governance_metrics_service

    async def accept_risk(
        self,
        risk_id: str,
        request: RiskAcceptanceRequest,
        authority_id: str,
        authority_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RiskAcceptanceRecord:
        """Explicitly accept residual clinical risk under authorized governance policy.

        Cannot be inferred from inactivity, deployment, or AI suggestion.
        """
        # 1. Authority validation (AI cannot accept risk)
        self.policy_service.assert_human_safety_authority(authority_id, authority_role, "accept_risk")

        # 2. Retrieve risk & validate multi-tenancy
        risk = self.repository.get_risk(risk_id)
        if not risk:
            raise RiskNotFoundException(f"Clinical safety risk '{risk_id}' not found.")
        self.policy_service.validate_org_boundary(risk.organization_id, organization_id, "risk")

        if risk.is_closed:
            raise RiskAlreadyClosedException(f"Cannot accept closed risk '{risk_id}'.")

        # Concurrency protection
        if request.expected_risk_version is not None and risk.version != request.expected_risk_version:
            raise RiskVersionConflictException(
                f"Version conflict on risk acceptance: expected {request.expected_risk_version}, current {risk.version}."
            )

        # Must have completed structured assessment
        if not risk.latest_assessment_id:
            raise RiskAssessmentRequiredException(
                f"Cannot accept risk '{risk_id}' without an authorized risk assessment."
            )

        # Separation of duties check
        self.policy_service.validate_separation_of_duties(
            creator_id=risk.created_by_id,
            approver_id=authority_id,
            operation_name="accept_risk",
        )

        # CRITICAL severity risks cannot be routinely accepted without escalation
        if request.residual_risk_severity == RiskSeverity.CRITICAL:
            if "DIRECTOR" not in authority_role.upper() and "CHIEF" not in authority_role.upper() and "ADMIN" not in authority_role.upper():
                raise RiskAcceptanceDeniedException(
                    "Critical residual risk acceptance requires Executive / Safety Director authority."
                )

        # Calculate expiry
        expires_at = self.policy_service.calculate_acceptance_expiry(request.expires_in_days)
        now = datetime.now(timezone.utc)

        acceptance = RiskAcceptanceRecord(
            risk_id=risk.id,
            bound_risk_version=risk.version,
            residual_risk_severity=request.residual_risk_severity,
            residual_risk_likelihood=request.residual_risk_likelihood,
            residual_risk_impact=request.residual_risk_impact,
            acceptance_scope=request.acceptance_scope,
            reason=request.reason,
            evidence_summary=request.evidence_summary,
            authority_id=authority_id,
            authority_role=authority_role,
            is_temporary=True,
            expires_at=expires_at,
            is_expired=False,
            accepted_at=now,
        )

        persisted_acceptance = self.repository.save_acceptance(acceptance)

        # Transition risk state to ACCEPTED
        previous_state = risk.state
        risk.state = RiskState.ACCEPTED
        risk.latest_acceptance_id = persisted_acceptance.id
        risk.residual_severity = request.residual_risk_severity
        risk.residual_likelihood = request.residual_risk_likelihood
        risk.residual_impact = request.residual_risk_impact
        risk.version += 1
        risk.updated_at = now
        self.repository.save_risk(risk)

        # Append history entry
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=RiskState.ACCEPTED,
                action="RISK_ACCEPTED",
                actor_id=authority_id,
                actor_role=authority_role,
                reason=request.reason,
                details={
                    "acceptance_id": persisted_acceptance.id,
                    "expires_at": expires_at.isoformat(),
                    "residual_severity": request.residual_risk_severity.value,
                },
            )
        )

        self.metrics_service.increment("risk_accepted_count")
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.RISK_ACCEPTED,
                    outcome="ALLOW",
                    actor_id=authority_id,
                    action="safety_governance:risk:accept",
                    resource_type="risk_acceptance",
                    resource_id=persisted_acceptance.id,
                    metadata={"risk_id": risk.id, "expires_at": expires_at.isoformat()},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for risk acceptance: %s", ex)

        return persisted_acceptance

    async def reject_risk(
        self,
        risk_id: str,
        reason: str,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RiskRecord:
        """Reject a proposed risk / risk-acceptance, requiring redesign or escalation."""
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "reject_risk")

        risk = self.repository.get_risk(risk_id)
        if not risk:
            raise RiskNotFoundException(f"Clinical safety risk '{risk_id}' not found.")
        self.policy_service.validate_org_boundary(risk.organization_id, organization_id, "risk")

        previous_state = risk.state
        risk.state = RiskState.REJECTED
        risk.version += 1
        risk.updated_at = datetime.now(timezone.utc)
        self.repository.save_risk(risk)

        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=RiskState.REJECTED,
                action="RISK_REJECTED",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
            )
        )

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.RISK_REJECTED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:risk:reject",
                    resource_type="clinical_risk",
                    resource_id=risk.id,
                    metadata={"reason": reason},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for risk rejection: %s", ex)

        return risk

    def verify_acceptance_validity(self, risk_id: str) -> None:
        """Check if active risk acceptance is expired; transition to REASSESSMENT_REQUIRED if expired."""
        risk = self.repository.get_risk(risk_id)
        if not risk or not risk.latest_acceptance_id:
            return

        acceptance = self.repository.get_acceptance(risk.latest_acceptance_id)
        if not acceptance:
            return

        if self.policy_service.is_acceptance_expired(acceptance.accepted_at, acceptance.expires_at):
            acceptance.is_expired = True
            self.repository.save_acceptance(acceptance)

            if risk.state == RiskState.ACCEPTED:
                risk.state = RiskState.REASSESSMENT_REQUIRED
                risk.version += 1
                risk.updated_at = datetime.now(timezone.utc)
                self.repository.save_risk(risk)

                self.repository.add_risk_history(
                    RiskHistoryEntry(
                        risk_id=risk.id,
                        version=risk.version,
                        previous_state=RiskState.ACCEPTED,
                        new_state=RiskState.REASSESSMENT_REQUIRED,
                        action="ACCEPTANCE_EXPIRED",
                        actor_id="system",
                        actor_role="GOVERNANCE_SYSTEM",
                        reason=f"Risk acceptance expired on {acceptance.expires_at.isoformat()}",
                    )
                )

            self.metrics_service.increment("expired_acceptance_count")
            raise RiskAcceptanceExpiredException(
                f"Risk acceptance for '{risk_id}' expired at {acceptance.expires_at.isoformat()}. Reassessment required."
            )


# Global singleton risk acceptance service
risk_acceptance_service = RiskAcceptanceService()

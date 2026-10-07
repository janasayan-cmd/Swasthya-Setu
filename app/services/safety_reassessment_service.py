"""Phase 51: Safety Risk Reassessment Service.

Governs triggers for risk reassessment:
- New incident from Phase 49 or recurrent signal
- Mitigation failure
- Validation failure or unexpected post-change monitoring results
- Expired temporary risk acceptance
- Subsystem configuration or policy shifts
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    RiskAlreadyClosedException,
    RiskNotFoundException,
    RiskVersionConflictException,
)
from app.repositories.safety_governance_repository import (
    SafetyGovernanceRepository,
    safety_governance_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.risk import RiskHistoryEntry, RiskRecord, RiskReassessRequest
from app.schemas.safety_governance import RiskState
from app.services.audit_service import AuditService, audit_service
from app.services.safety_governance_metrics_service import (
    SafetyGovernanceMetricsService,
    safety_governance_metrics_service,
)
from app.services.safety_governance_policy_service import (
    SafetyGovernancePolicyService,
    safety_governance_policy_service,
)

logger = logging.getLogger("app.safety_reassessment_service")


class SafetyReassessmentService:
    """Service governing clinical risk reassessments and trigger workflows."""

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

    async def trigger_reassessment(
        self,
        risk_id: str,
        request: RiskReassessRequest,
        actor_id: str,
        actor_role: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RiskRecord:
        """Trigger formal reassessment of a risk upon new safety signals or expired conditions."""
        # 1. Authority validation
        self.policy_service.assert_human_safety_authority(actor_id, actor_role, "trigger_reassessment")

        # 2. Retrieve risk & validate
        risk = self.repository.get_risk(risk_id)
        if not risk:
            raise RiskNotFoundException(f"Clinical safety risk '{risk_id}' not found.")
        self.policy_service.validate_org_boundary(risk.organization_id, organization_id, "risk")

        if risk.is_closed:
            raise RiskAlreadyClosedException(
                f"Cannot trigger reassessment on closed risk '{risk_id}'. Reopening required first."
            )

        if request.expected_version is not None and risk.version != request.expected_version:
            raise RiskVersionConflictException(
                f"Version conflict during reassessment: expected {request.expected_version}, current {risk.version}."
            )

        now = datetime.now(timezone.utc)
        previous_state = risk.state
        risk.state = RiskState.REASSESSMENT_REQUIRED
        if request.new_evidence:
            for ev in request.new_evidence:
                risk.evidence_references.append({**ev, "attached_during": "reassessment", "attached_at": now.isoformat()})

        risk.version += 1
        risk.updated_at = now
        self.repository.save_risk(risk)

        # Append history entry
        self.repository.add_risk_history(
            RiskHistoryEntry(
                risk_id=risk.id,
                version=risk.version,
                previous_state=previous_state,
                new_state=RiskState.REASSESSMENT_REQUIRED,
                action="REASSESSMENT_TRIGGERED",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.trigger_reason,
                details={"evidence_attached_count": len(request.new_evidence)},
            )
        )

        self.metrics_service.increment("reassessment_count")
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.SAFETY_REASSESSMENT_REQUESTED,
                    outcome="ALLOW",
                    actor_id=actor_id,
                    action="safety_governance:risk:reassess",
                    resource_type="clinical_risk",
                    resource_id=risk.id,
                    metadata={"trigger_reason": request.trigger_reason},
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit record failed for reassessment: %s", ex)

        return risk


# Global singleton safety reassessment service
safety_reassessment_service = SafetyReassessmentService()

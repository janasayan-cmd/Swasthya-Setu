"""Decision Application Service (Phase 47).

Orchestrates controlled downstream execution of approved decisions,
enforcing final pre-application readiness checks, version staleness detection,
and downstream audit linkage.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
import uuid

from app.core.exceptions import (
    DecisionContextStaleException,
    DecisionNotFoundException,
    DecisionVersionConflictException,
)
from app.repositories.decision_repository import (
    DecisionRepository,
    decision_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.decisions import DecisionApplyRequest, DecisionRecord, DecisionStatus
from app.services.audit_service import AuditService
from app.services.decision_context_service import (
    DecisionContextService,
    decision_context_service,
)
from app.services.decision_validation_service import (
    DecisionValidationService,
    decision_validation_service,
)

logger = logging.getLogger(__name__)


class DecisionApplicationService:
    """Manages verified application of approved decisions into active clinical workflows."""

    def __init__(
        self,
        repository: Optional[DecisionRepository] = None,
        context_service: Optional[DecisionContextService] = None,
        validation_service: Optional[DecisionValidationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or decision_repository
        self.context_service = context_service or decision_context_service
        self.validation_service = validation_service or decision_validation_service
        self.audit_service = audit_service

    async def _record_audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.audit_service:
            return
        try:
            await self.audit_service.record(
                event_type=event_type,
                outcome="ALLOW",
                actor_id=actor_id,
                action="APPLY",
                resource_type="decision",
                resource_id=resource_id,
                metadata=metadata,
            )
        except Exception as ex:
            logger.warning("Failed to record application audit for decision %s: %s", resource_id, ex)

    async def apply_decision(
        self,
        decision_id: str,
        request: DecisionApplyRequest,
        actor_id: str,
        actor_role: str,
    ) -> DecisionRecord:
        """Apply an approved decision outcome to clinical workflow."""
        decision = self.repository.get_decision(decision_id)
        if not decision:
            raise DecisionNotFoundException(f"Decision {decision_id} not found.")

        # 1. Readiness check
        self.validation_service.validate_application_readiness(decision, actor_role)

        # 2. Stale context revalidation (Phase 46 integration)
        self.context_service.validate_not_stale(decision)

        # 3. Expected resource version validation if specified
        if request.expected_resource_version is not None and decision.resource_type and decision.resource_id:
            current_ver = self.context_service.capture_current_resource_version(
                decision.resource_type, decision.resource_id
            )
            if current_ver is not None and current_ver != request.expected_resource_version:
                raise DecisionVersionConflictException(
                    f"Resource {decision.resource_type}:{decision.resource_id} version changed. "
                    f"Expected {request.expected_resource_version}, current is {current_ver}."
                )

        # 4. Commit application state
        now = datetime.now(timezone.utc)
        decision.status = DecisionStatus.APPLIED
        decision.applied_at = now
        decision.downstream_action_type = request.downstream_action_type or "CLINICAL_WORKFLOW"
        decision.downstream_action_id = f"act-{uuid.uuid4().hex[:10]}"

        self.repository.update_decision(decision)

        await self._record_audit(
            event_type=AuditEventType.DECISION_APPLIED,
            actor_id=actor_id,
            resource_id=decision.id,
            metadata={
                "decision_type": decision.decision_type.value,
                "downstream_action_type": decision.downstream_action_type,
                "downstream_action_id": decision.downstream_action_id,
                "application_reason": request.application_reason,
            },
        )

        return decision


decision_application_service = DecisionApplicationService()

"""Decision Review Service (Phase 47).

Orchestrates human oversight of clinical decisions, recording reviewer identity,
clinical reasoning, status transitions, and modifications.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple

from app.core.exceptions import DecisionNotFoundException
from app.repositories.decision_repository import (
    DecisionRepository,
    decision_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.decision_review import (
    DecisionReviewRecord,
    DecisionReviewRequest,
    ReviewAction,
)
from app.schemas.decisions import DecisionRecord, DecisionStatus
from app.services.audit_service import AuditService
from app.services.decision_validation_service import (
    DecisionValidationService,
    decision_validation_service,
)

logger = logging.getLogger(__name__)


class DecisionReviewService:
    """Manages clinician oversight review workflows and state transitions."""

    def __init__(
        self,
        repository: Optional[DecisionRepository] = None,
        validation_service: Optional[DecisionValidationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or decision_repository
        self.validation_service = validation_service or decision_validation_service
        self.audit_service = audit_service

    async def _record_audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        action: str,
        resource_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Safely record audit event without raw PHI."""
        if not self.audit_service:
            return
        try:
            await self.audit_service.record(
                event_type=event_type,
                outcome="ALLOW",
                actor_id=actor_id,
                action=action,
                resource_type="decision",
                resource_id=resource_id,
                metadata=metadata,
            )
        except Exception as ex:
            logger.warning("Audit recording failed for decision review %s: %s", resource_id, ex)

    async def submit_review(
        self,
        decision_id: str,
        request: DecisionReviewRequest,
        reviewer_id: str,
        reviewer_role: str,
    ) -> Tuple[DecisionRecord, DecisionReviewRecord]:
        """Submit a clinical review decision."""
        decision = self.repository.get_decision(decision_id)
        if not decision:
            raise DecisionNotFoundException(f"Decision {decision_id} not found.")

        # Validate permission & eligibility
        self.validation_service.validate_review_permission(
            decision=decision,
            reviewer_role=reviewer_role,
            action=request.action,
        )

        previous_status = decision.status

        # Determine resulting status
        if request.action == ReviewAction.APPROVED:
            resulting_status = DecisionStatus.APPROVED
            audit_event = AuditEventType.DECISION_APPROVED
        elif request.action == ReviewAction.REJECTED:
            resulting_status = DecisionStatus.REJECTED
            audit_event = AuditEventType.DECISION_REJECTED
        elif request.action == ReviewAction.MODIFIED:
            resulting_status = DecisionStatus.APPROVED
            audit_event = AuditEventType.DECISION_MODIFIED
            if request.modifications:
                updated_payload = copy.deepcopy(decision.output_payload)
                updated_payload.update(request.modifications)
                decision.output_payload = updated_payload
        elif request.action == ReviewAction.RETURNED_FOR_REVIEW:
            resulting_status = DecisionStatus.REVIEW_REQUIRED
            audit_event = AuditEventType.DECISION_REVIEWED
        else:
            resulting_status = DecisionStatus.UNDER_REVIEW
            audit_event = AuditEventType.DECISION_REVIEWED

        decision.status = resulting_status
        self.repository.update_decision(decision)

        review_record = DecisionReviewRecord(
            decision_id=decision.id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            action=request.action,
            review_reason=request.reason,
            previous_status=previous_status,
            resulting_status=resulting_status,
            modifications=request.modifications,
            reviewed_at=datetime.now(timezone.utc),
        )
        self.repository.add_review(review_record)

        await self._record_audit(
            event_type=audit_event,
            actor_id=reviewer_id,
            action=request.action.value,
            resource_id=decision.id,
            metadata={
                "decision_type": decision.decision_type.value,
                "previous_status": previous_status.value,
                "resulting_status": resulting_status.value,
                "review_reason": request.reason,
            },
        )

        return decision, review_record


decision_review_service = DecisionReviewService()

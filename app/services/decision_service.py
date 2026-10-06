"""Clinical Decision Service (Phase 47).

Orchestrates clinical decision lifecycle, traceability record creation,
safety boundary enforcement, and supersession links.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import settings
from app.core.exceptions import (
    DecisionNotFoundException,
)
from app.repositories.decision_repository import (
    DecisionRepository,
    decision_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.decisions import (
    DecisionCreateRequest,
    DecisionProvenanceSource,
    DecisionRecord,
    DecisionStatus,
    DecisionType,
)
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


class DecisionService:
    """Master service managing clinical decision creation, status, and retrieval."""

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
                action="CREATE",
                resource_type="decision",
                resource_id=resource_id,
                metadata=metadata,
            )
        except Exception as ex:
            logger.warning("Audit record failed for decision %s: %s", resource_id, ex)

    async def create_decision(
        self,
        request: DecisionCreateRequest,
        actor_id: str,
        actor_role: str,
        actor_type: DecisionProvenanceSource = DecisionProvenanceSource.SYSTEM,
        correlation_id: Optional[str] = None,
    ) -> DecisionRecord:
        """Create a traceable clinical decision record."""
        # 1. Enforce safety boundaries
        self.validation_service.validate_safety_boundaries(
            decision_type=request.decision_type,
            initiating_actor_role=actor_role,
        )

        # 2. Check idempotency early
        if request.idempotency_key:
            cached = self.repository.get_by_idempotency_key(request.idempotency_key)
            if cached:
                return cached

        # 3. Capture current resource version if needed and not supplied
        resource_version = request.resource_version
        if resource_version is None and request.resource_type and request.resource_id:
            resource_version = self.context_service.capture_current_resource_version(
                request.resource_type, request.resource_id
            )

        # 4. Determine initial status based on oversight requirements
        requires_oversight = request.requires_human_oversight
        if getattr(settings, "DECISION_REQUIRE_HUMAN_OVERSIGHT", True):
            # High-risk types always require oversight
            high_risk_types = {
                DecisionType.MEDICATION_SAFETY_WARNING,
                DecisionType.CARE_PLAN_RECOMMENDATION,
                DecisionType.DATA_RECONCILIATION_RECOMMENDATION,
                DecisionType.EXTERNAL_DATA_RECONCILIATION_RESULT,
            }
            if request.decision_type in high_risk_types:
                requires_oversight = True

        status = DecisionStatus.REVIEW_REQUIRED if requires_oversight else DecisionStatus.GENERATED

        now = datetime.now(timezone.utc)
        record = DecisionRecord(
            decision_type=request.decision_type,
            patient_id=request.patient_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            resource_version=resource_version,
            status=status,
            initiating_actor_id=actor_id,
            initiating_actor_role=actor_role,
            initiating_actor_type=actor_type,
            source_service=request.source_service,
            inputs=request.inputs,
            output_payload=request.output_payload,
            rule_metadata=request.rule_metadata,
            model_metadata=request.model_metadata,
            requires_human_oversight=requires_oversight,
            expires_at=request.expires_at,
            correlation_id=correlation_id,
            idempotency_key=request.idempotency_key,
            created_at=now,
            updated_at=now,
        )

        committed = self.repository.create_decision(record)

        await self._record_audit(
            event_type=AuditEventType.DECISION_CREATED,
            actor_id=actor_id,
            resource_id=committed.id,
            metadata={
                "decision_type": committed.decision_type.value,
                "status": committed.status.value,
                "requires_oversight": committed.requires_human_oversight,
                "source_service": committed.source_service,
            },
        )

        return committed

    async def supersede_decision(
        self,
        old_decision_id: str,
        new_decision_id: str,
        actor_id: str,
    ) -> None:
        """Mark old decision as superseded by new decision."""
        old = self.repository.get_decision(old_decision_id)
        if not old:
            raise DecisionNotFoundException(f"Decision {old_decision_id} not found.")

        new = self.repository.get_decision(new_decision_id)
        if not new:
            raise DecisionNotFoundException(f"Decision {new_decision_id} not found.")

        self.repository.supersede_decision(old_decision_id, new_decision_id)

        await self._record_audit(
            event_type=AuditEventType.DECISION_SUPERSEDED,
            actor_id=actor_id,
            resource_id=old_decision_id,
            metadata={
                "superseded_by": new_decision_id,
            },
        )

    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        """Fetch decision record by ID."""
        return self.repository.get_decision(decision_id)

    def list_by_patient(self, patient_id: str, limit: int = 50) -> List[DecisionRecord]:
        """List decision records for patient."""
        return self.repository.list_by_patient(patient_id, limit=limit)

    def list_by_resource(self, resource_type: str, resource_id: str, limit: int = 50) -> List[DecisionRecord]:
        """List decision records for specific clinical resource."""
        return self.repository.list_by_resource(resource_type, resource_id, limit=limit)


decision_service = DecisionService()

"""Phase 49: Corrective & Preventive Action Service.

Orchestrates remediation actions, integrating with Phase 36 clinical tasks
and Phase 46 clinical record versioning corrections.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import IncidentNotFoundException
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.corrective_actions import (
    ActionStatus,
    ActionType,
    CorrectiveActionCreateRequest,
    CorrectiveActionRecord,
    CorrectiveActionStatusUpdateRequest,
)
from app.services.audit_service import AuditService, audit_service

logger = logging.getLogger("app.corrective_action_service")


class CorrectiveActionService:
    """Service governing corrective and preventive remediation actions."""

    def __init__(
        self,
        repository: Optional[SafetyIncidentRepository] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_incident_repository
        self.audit_service = audit_svc or audit_service

    async def create_action(
        self,
        incident_id: str,
        request: CorrectiveActionCreateRequest,
        created_by_id: str,
        request_id: Optional[str] = None,
    ) -> CorrectiveActionRecord:
        """Create a new corrective or preventive action plan item."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")

        action = CorrectiveActionRecord(
            incident_id=incident_id,
            action_type=request.action_type,
            is_preventive=request.is_preventive,
            title=request.title,
            description=request.description,
            status=ActionStatus.CREATED,
            assigned_to_id=request.assigned_to_id,
            assigned_to_role=request.assigned_to_role,
        )
        self.repository.save_action(action)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_CORRECTIVE_ACTION_CREATED,
                    outcome="ALLOW",
                    actor_id=created_by_id,
                    action=f"incident:action:create:{request.action_type.value}",
                    resource_type="corrective_action",
                    resource_id=action.id,
                    metadata={
                        "incident_id": incident_id,
                        "action_type": request.action_type.value,
                        "is_preventive": request.is_preventive,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for action %s: %s", action.id, ex)

        return action

    def update_action_status(
        self,
        action_id: str,
        request: CorrectiveActionStatusUpdateRequest,
        updated_by_id: str,
    ) -> CorrectiveActionRecord:
        """Advance status of a corrective action (e.g. COMPLETED, VERIFIED)."""
        action = self.repository.get_action(action_id)
        if not action:
            raise IncidentNotFoundException(f"Corrective action '{action_id}' not found.")

        now = datetime.now(timezone.utc)
        action.status = request.status
        if request.resolution_details:
            action.resolution_details = request.resolution_details
        if request.linked_task_id:
            action.linked_task_id = request.linked_task_id

        if request.status == ActionStatus.COMPLETED and not action.completed_at:
            action.completed_at = now
        elif request.status == ActionStatus.VERIFIED:
            action.verified_at = now
            action.verified_by_id = updated_by_id

        return self.repository.save_action(action)

    def list_actions(self, incident_id: str) -> List[CorrectiveActionRecord]:
        """List all corrective actions linked to an incident."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")
        return self.repository.list_actions(incident_id)


# Global singleton
corrective_action_service = CorrectiveActionService()

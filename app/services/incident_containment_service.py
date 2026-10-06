"""Phase 49: Incident Containment Service.

Orchestrates and tracks safety containment actions (e.g. disabling a failing provider,
pausing an affected workflow, or requiring manual review) to mitigate active risks.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from app.core.exceptions import IncidentInvalidStateException, IncidentNotFoundException
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.incidents import (
    IncidentContainmentRequest,
    IncidentRecord,
    IncidentStatus,
)
from app.services.audit_service import AuditService, audit_service

logger = logging.getLogger("app.incident_containment_service")


class IncidentContainmentService:
    """Service governing risk containment orchestration."""

    def __init__(
        self,
        repository: Optional[SafetyIncidentRepository] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_incident_repository
        self.audit_service = audit_svc or audit_service

    async def record_containment(
        self,
        incident_id: str,
        request: IncidentContainmentRequest,
        contained_by_id: str,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Apply containment action to an incident to mitigate active risk."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")
        if incident.status in [IncidentStatus.CLOSED, IncidentStatus.REJECTED]:
            raise IncidentInvalidStateException(
                f"Cannot apply containment to incident '{incident_id}' in state '{incident.status.value}'."
            )

        now = datetime.now(timezone.utc)
        incident.containment_status = "CONTAINED"
        incident.containment_action = f"[{request.containment_type}] {request.containment_action}"
        incident.contained_at = now
        incident.status = IncidentStatus.CONTAINED
        incident.updated_at = now

        self.repository.save_incident(incident)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_CONTAINED,
                    outcome="ALLOW",
                    actor_id=contained_by_id,
                    action=f"incident:contain:{request.containment_type}",
                    resource_type="safety_incident",
                    resource_id=incident.id,
                    metadata={
                        "incident_id": incident.id,
                        "containment_type": request.containment_type,
                        "containment_action": request.containment_action,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for containment on %s: %s", incident.id, ex)

        return incident


# Global singleton
incident_containment_service = IncidentContainmentService()

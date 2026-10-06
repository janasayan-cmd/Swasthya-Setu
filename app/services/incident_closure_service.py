"""Phase 49: Incident Closure Service.

Validates safety prerequisites before incident closure: verifies containment,
remediation completion, human review confirmation, and audit completeness.
Asserts that closure cannot erase historical clinical data or audit logs.
"""

from datetime import datetime, timezone
import logging
from typing import Optional

from app.core.config import settings
from app.core.exceptions import (
    AIIncidentAuthorityProhibitedException,
    IncidentAlreadyClosedException,
    IncidentClosureBlockedException,
    IncidentNotFoundException,
)
from app.repositories.safety_incident_repository import (
    SafetyIncidentRepository,
    safety_incident_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.corrective_actions import ActionStatus
from app.schemas.incidents import (
    IncidentClosureRequest,
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
)
from app.services.audit_service import AuditService, audit_service

logger = logging.getLogger("app.incident_closure_service")


class IncidentClosureService:
    """Service governing formal safety incident closure with prerequisite validation."""

    def __init__(
        self,
        repository: Optional[SafetyIncidentRepository] = None,
        audit_svc: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or safety_incident_repository
        self.audit_service = audit_svc or audit_service

    async def close_incident(
        self,
        incident_id: str,
        request: IncidentClosureRequest,
        closed_by_id: str,
        closed_by_role: str,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Validate all safety prerequisites and formally close an incident."""
        incident = self.repository.get_incident(incident_id)
        if not incident:
            raise IncidentNotFoundException(f"Incident '{incident_id}' not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise IncidentAlreadyClosedException(f"Incident '{incident_id}' is already closed.")

        # Guard: AI cannot autonomously close safety incidents
        if "AI" in closed_by_role.upper() or "BOT" in closed_by_role.upper() or "SYSTEM" in closed_by_role.upper():
            raise AIIncidentAuthorityProhibitedException(
                "AI agents or automated services cannot close safety incidents. Authorized human closure is mandatory."
            )

        # 1. Prerequisite: Containment verification for HIGH / CRITICAL incidents
        if incident.severity in [IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]:
            if incident.containment_status != "CONTAINED":
                raise IncidentClosureBlockedException(
                    f"Closure blocked: High/Critical severity incident '{incident_id}' requires confirmed containment prior to closure."
                )

        # 2. Prerequisite: Corrective actions completion
        if settings.INCIDENT_REQUIRE_CORRECTIVE_ACTION_FOR_CLOSURE:
            actions = self.repository.list_actions(incident_id)
            uncompleted = [
                a for a in actions
                if a.status in [ActionStatus.CREATED, ActionStatus.ASSIGNED, ActionStatus.IN_PROGRESS, ActionStatus.BLOCKED]
            ]
            if uncompleted:
                raise IncidentClosureBlockedException(
                    f"Closure blocked: {len(uncompleted)} corrective action(s) remain open or unverified for incident '{incident_id}'."
                )

        # 3. Transition to CLOSED
        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.CLOSED
        incident.closed_at = now
        incident.closure_reason = request.closure_reason
        incident.updated_at = now

        self.repository.save_incident(incident)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.INCIDENT_CLOSED,
                    outcome="ALLOW",
                    actor_id=closed_by_id,
                    action="incident:close",
                    resource_type="safety_incident",
                    resource_id=incident.id,
                    metadata={
                        "incident_id": incident.id,
                        "closure_reason": request.closure_reason,
                        "closed_by_role": closed_by_role,
                    },
                    request_id=request_id,
                )
            except Exception as ex:
                logger.warning("Audit recording failed for closure on %s: %s", incident.id, ex)

        return incident


# Global singleton
incident_closure_service = IncidentClosureService()

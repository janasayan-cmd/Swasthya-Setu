"""Incident Management Service (Phase 27).

Manages operational incidents across HealthSetu subsystems:
- Outages, connectivity failures, worker degradation, security events
- Enforces strict lifecycle state machine:
  OPEN -> INVESTIGATING -> MITIGATED -> RESOLVED -> CLOSED
- Audits every administrative transition with operator correlation
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from app.core.exceptions import (
    IncidentInvalidStateException,
    IncidentNotFoundException,
)
from app.core.logging import get_logger
from app.repositories.incident_repository import IncidentRepository
from app.schemas.audit import AuditActor, AuditEventRecord, AuditEventType
from app.schemas.incident import (
    IncidentAcknowledge,
    IncidentCategory,
    IncidentCreate,
    IncidentRecord,
    IncidentResolve,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService

logger = get_logger("app.services.incident_service")


class IncidentService:
    """Business service governing operational incident lifecycle and audit trails."""

    def __init__(
        self,
        incident_repo: IncidentRepository,
        audit_service: AuditService,
    ) -> None:
        self._repo = incident_repo
        self._audit = audit_service

    async def create_incident(
        self,
        payload: IncidentCreate,
        actor: AuthenticatedUserContext,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Declare a new operational incident and log audit event."""
        now = datetime.now(timezone.utc)
        incident = IncidentRecord(
            title=payload.title,
            description=payload.description,
            category=payload.category,
            severity=payload.severity,
            status=IncidentStatus.OPEN,
            detected_at=now,
            correlation_id=payload.correlation_id or request_id,
            created_by=actor.user_id,
            updated_by=actor.user_id,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata,
        )
        saved = await self._repo.create(incident)

        logger.warning(
            f"Operational incident created: id={saved.id} category={saved.category} severity={saved.severity} title='{saved.title}'",
            extra={"incident_id": saved.id, "actor_id": actor.user_id, "request_id": request_id},
        )

        await self._log_audit(
            event_type=AuditEventType.ADMIN_INCIDENT_CREATED,
            actor=actor,
            incident_id=saved.id,
            request_id=request_id,
            details={"category": saved.category.value, "severity": saved.severity.value, "title": saved.title},
        )
        return saved

    async def get_incident(self, incident_id: str) -> IncidentRecord:
        """Retrieve incident by ID or raise IncidentNotFoundException."""
        incident = await self._repo.get(incident_id)
        if not incident:
            raise IncidentNotFoundException(incident_id)
        return incident

    async def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        category: Optional[IncidentCategory] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[IncidentRecord], int]:
        """Query incidents with pagination and filtering."""
        return await self._repo.list(
            status=status,
            severity=severity,
            category=category,
            skip=skip,
            limit=limit,
        )

    async def acknowledge_incident(
        self,
        incident_id: str,
        payload: IncidentAcknowledge,
        actor: AuthenticatedUserContext,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Transition incident from OPEN to INVESTIGATING with owner assignment."""
        incident = await self.get_incident(incident_id)
        if incident.status != IncidentStatus.OPEN:
            raise IncidentInvalidStateException(
                f"Incident '{incident_id}' is in status '{incident.status.value}' and cannot be acknowledged. Expected 'OPEN'."
            )

        now = datetime.now(timezone.utc)
        incident.status = IncidentStatus.INVESTIGATING
        incident.acknowledged_at = now
        incident.owner = payload.owner or actor.user_id
        incident.updated_by = actor.user_id
        incident.updated_at = now
        if payload.notes:
            incident.metadata["acknowledgement_notes"] = payload.notes

        updated = await self._repo.update(incident)

        await self._log_audit(
            event_type=AuditEventType.ADMIN_INCIDENT_UPDATED,
            actor=actor,
            incident_id=updated.id,
            request_id=request_id,
            details={"transition": "OPEN->INVESTIGATING", "owner": updated.owner},
        )
        return updated

    async def update_incident(
        self,
        incident_id: str,
        payload: IncidentUpdate,
        actor: AuthenticatedUserContext,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Update active incident details, notes, or severity."""
        incident = await self.get_incident(incident_id)
        if incident.status == IncidentStatus.CLOSED:
            raise IncidentInvalidStateException(
                f"Incident '{incident_id}' is CLOSED and cannot be modified."
            )

        now = datetime.now(timezone.utc)
        if payload.status:
            # Prevent direct transitions to closed without resolution summary
            if payload.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED) and not incident.resolution_summary:
                raise IncidentInvalidStateException(
                    "Resolving or closing an incident requires a resolution summary via the resolve endpoint."
                )
            incident.status = payload.status

        if payload.severity:
            incident.severity = payload.severity
        if payload.description:
            incident.description = payload.description
        if payload.owner:
            incident.owner = payload.owner
        if payload.notes:
            progress_notes = incident.metadata.get("progress_notes", [])
            progress_notes.append({
                "note": payload.notes,
                "recorded_by": actor.user_id,
                "recorded_at": now.isoformat(),
            })
            incident.metadata["progress_notes"] = progress_notes

        incident.updated_by = actor.user_id
        incident.updated_at = now

        updated = await self._repo.update(incident)

        await self._log_audit(
            event_type=AuditEventType.ADMIN_INCIDENT_UPDATED,
            actor=actor,
            incident_id=updated.id,
            request_id=request_id,
            details={"status": updated.status.value, "severity": updated.severity.value},
        )
        return updated

    async def resolve_incident(
        self,
        incident_id: str,
        payload: IncidentResolve,
        actor: AuthenticatedUserContext,
        request_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Mark operational incident resolved or closed with mandatory summary."""
        incident = await self.get_incident(incident_id)
        if incident.status == IncidentStatus.CLOSED:
            raise IncidentInvalidStateException(f"Incident '{incident_id}' is already CLOSED.")

        now = datetime.now(timezone.utc)
        target_status = payload.status if payload.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED) else IncidentStatus.RESOLVED
        incident.status = target_status
        incident.resolved_at = now
        if target_status == IncidentStatus.CLOSED:
            incident.closed_at = now
        incident.resolution_summary = payload.resolution_summary
        incident.updated_by = actor.user_id
        incident.updated_at = now

        updated = await self._repo.update(incident)

        logger.info(
            f"Operational incident resolved: id={updated.id} status={updated.status.value} resolved_by={actor.user_id}",
            extra={"incident_id": updated.id, "actor_id": actor.user_id, "request_id": request_id},
        )

        await self._log_audit(
            event_type=AuditEventType.ADMIN_INCIDENT_RESOLVED,
            actor=actor,
            incident_id=updated.id,
            request_id=request_id,
            details={"status": updated.status.value, "resolution_summary": payload.resolution_summary},
        )
        return updated

    async def _log_audit(
        self,
        event_type: AuditEventType,
        actor: AuthenticatedUserContext,
        incident_id: str,
        request_id: Optional[str],
        details: dict[str, Any],
    ) -> None:
        try:
            event = AuditEventRecord(
                event_type=event_type,
                actor_id=actor.user_id,
                resource_type="operational_incident",
                resource_id=incident_id,
                outcome="ALLOW",
                request_id=request_id,
                metadata=details,
            )
            await self._audit.record_event(event)
        except Exception as e:
            logger.error(f"Failed to record incident audit event: {e}")

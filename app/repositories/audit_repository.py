"""Audit event repository — database team contract definition.

DATABASE TEAM DEPENDENCY — PHASE 3
====================================
This repository defines the data access contract for the audit/security
event log table.

Required audit_events entity fields:
  id            : Primary Key (UUID)
  event_type    : VARCHAR (see AuditEventType enum)
  actor_id      : NULLABLE VARCHAR — user ID of the requester
  action        : NULLABLE VARCHAR — permission/action string
  resource_type : NULLABLE VARCHAR — type of resource targeted
  resource_id   : NULLABLE VARCHAR — ID of resource targeted
  outcome       : VARCHAR ('ALLOW' or 'DENY')
  reason_code   : NULLABLE VARCHAR — internal denial reason
  request_id    : NULLABLE VARCHAR — HTTP correlation ID
  metadata_json : NULLABLE JSONB — supplementary non-PHI metadata
  created_at    : TIMESTAMP WITH TIME ZONE (immutable — audit records are append-only)

IMPORTANT constraints:
  - Audit records are APPEND-ONLY. No UPDATE or DELETE.
  - Retention policies are governed by compliance/legal requirements.
  - Consent revocation does NOT delete audit records.
  - Access tokens and passwords are NEVER stored in audit records.

Until the database team delivers these, audit records are emitted as
structured log lines only. The structured log output is the interim
audit trail.
"""

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.schemas.audit import AuditEventRecord
from app.core.logging import get_logger

logger = get_logger("app.audit")


class AuditRepository(BaseRepository[Any]):
    """Repository for appending immutable audit event records.

    Phase 3 implementation: structured logging as interim audit trail.
    When database team delivers the audit_events table, replace
    _persist_to_log() with a database INSERT.
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session=session)  # type: ignore[arg-type]
        # In-memory buffer for test inspection
        self._events: list[AuditEventRecord] = []

    async def append(self, event: AuditEventRecord) -> None:
        """Append an immutable audit event record.

        Phase 3: emits to structured log. Database persistence is a
        DATABASE TEAM DEPENDENCY.

        NOTE FOR DATABASE TEAM:
        When audit_events table is ready, replace with:
            async with self.session.begin():
                orm_obj = AuditEventModel(
                    event_type=event.event_type.value,
                    actor_id=event.actor_id,
                    action=event.action,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    outcome=event.outcome,
                    reason_code=event.reason_code,
                    request_id=event.request_id,
                    metadata_json=event.metadata,
                    created_at=event.timestamp,
                )
                self.session.add(orm_obj)
        """
        # Interim: structured log line (the sanitizer in logging.py ensures PHI protection)
        logger.info(
            f"AUDIT: {event.event_type.value} | outcome={event.outcome}",
            extra={
                "event_type": event.event_type.value,
                "actor_id": event.actor_id,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "outcome": event.outcome,
                "reason_code": event.reason_code,
                "request_id": event.request_id,
            },
        )
        # Also store in memory for test assertions
        self._events.append(event)

    async def create(self, event: Any) -> None:
        """Alias for append to satisfy repository contract."""
        await self.append(event)

    async def get_recent_events(
        self,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEventRecord]:
        """Retrieve recent audit events (in-memory fallback, test use only).

        NOTE FOR DATABASE TEAM:
        Replace with indexed query:
            stmt = select(AuditEventModel)
                .where(AuditEventModel.actor_id == actor_id)
                .order_by(AuditEventModel.created_at.desc())
                .limit(limit)
        """
        results = list(self._events)
        if actor_id:
            results = [e for e in results if e.actor_id == actor_id]
        return results[-limit:]

    async def list_events(
        self,
        skip: int = 0,
        limit: int = 50,
        event_type: str | None = None,
        actor_id: str | None = None,
        patient_id: str | None = None,
    ) -> tuple[list[AuditEventRecord], int]:
        """Query immutable audit events with pagination and filtering."""
        matched = list(self._events)
        if event_type:
            matched = [
                e for e in matched
                if (e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)) == event_type
            ]
        if actor_id:
            matched = [
                e for e in matched
                if getattr(e, "actor_id", None) == actor_id or (getattr(e, "actor", None) and getattr(e.actor, "actor_id", None) == actor_id)
            ]
        if patient_id:
            matched = [
                e for e in matched
                if (getattr(e, "resource_type", "") == "patient" and getattr(e, "resource_id", "") == patient_id)
                or (isinstance(getattr(e, "details", None), dict) and str(getattr(e, "details", {})).find(patient_id) != -1)
            ]

        total = len(matched)
        matched.reverse()
        return matched[skip : skip + limit], total


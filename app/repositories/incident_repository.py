"""Incident Repository (Phase 27).

DATABASE TEAM DEPENDENCY — PHASE 27
===================================
Thread-safe in-memory repository implementing the data contract for operational incidents.

Expected PostgreSQL table:
- operational_incidents (id, title, description, category, severity, status,
                         detected_at, acknowledged_at, resolved_at, closed_at,
                         owner, correlation_id, resolution_summary, created_by,
                         updated_by, created_at, updated_at, metadata)
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from app.repositories.base import BaseRepository
from app.schemas.incident import (
    IncidentCategory,
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
)


class IncidentRepository(BaseRepository[Any]):
    """Thread-safe repository managing operational incident records."""

    def __init__(self, session: Any = None) -> None:
        super().__init__(session=session)
        self._incidents: Dict[str, IncidentRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, incident: IncidentRecord) -> IncidentRecord:
        """Persist a new operational incident record."""
        async with self._lock:
            self._incidents[incident.id] = incident
            return incident

    async def get(self, incident_id: str) -> Optional[IncidentRecord]:
        """Lookup incident by unique incident ID."""
        async with self._lock:
            return self._incidents.get(incident_id)

    async def update(self, incident: IncidentRecord) -> IncidentRecord:
        """Update incident state, assignments, or resolution."""
        async with self._lock:
            self._incidents[incident.id] = incident
            return incident

    async def list(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        category: Optional[IncidentCategory] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[IncidentRecord], int]:
        """List operational incidents with filtering and pagination."""
        async with self._lock:
            matched = list(self._incidents.values())
            if status is not None:
                matched = [i for i in matched if i.status == status]
            if severity is not None:
                matched = [i for i in matched if i.severity == severity]
            if category is not None:
                matched = [i for i in matched if i.category == category]

            total = len(matched)
            # Sort newest first
            matched.sort(key=lambda i: i.created_at, reverse=True)
            return matched[skip : skip + limit], total

    async def count_open(self) -> int:
        """Count currently unresolved (OPEN or INVESTIGATING or MITIGATED) incidents."""
        async with self._lock:
            return sum(
                1 for i in self._incidents.values()
                if i.status in (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATED)
            )

    def clear(self) -> None:
        """Clear all stored incidents (test fixture helper)."""
        self._incidents.clear()

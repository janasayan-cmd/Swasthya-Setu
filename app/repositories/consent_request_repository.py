"""Consent Request Repository & Database Contract.

DATABASE TEAM DEPENDENCY — PHASE 43
===================================
This repository defines the data access contract expected for consent requests.
Until the database team delivers database migrations/models, this repository
operates with in-memory persistence adhering strictly to the interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.schemas.consent import ConsentRecipientType, ConsentRequestStatus


@dataclass
class ConsentRequestRecord:
    """Internal database model representation for a consent request."""
    id: str
    patient_id: str
    requester_id: str
    requester_role: str
    grantee_id: str
    recipient_type: str
    purpose: str
    resource_scopes: List[str]
    action_scopes: List[str]
    requested_duration_days: int
    status: ConsentRequestStatus
    created_at: datetime
    notes: Optional[str] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None


class ConsentRequestRepository(BaseRepository[Any]):
    """Repository managing consent requests."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session=session)  # type: ignore[arg-type]
        self._requests: dict[str, ConsentRequestRecord] = {}

    async def create_request(self, record: ConsentRequestRecord) -> ConsentRequestRecord:
        """Persist a new consent request."""
        self._requests[record.id] = record
        return record

    async def get_by_id(self, request_id: str) -> Optional[ConsentRequestRecord]:
        """Fetch request by primary key."""
        return self._requests.get(request_id)

    async def update_request(self, record: ConsentRequestRecord) -> ConsentRequestRecord:
        """Update consent request attributes."""
        self._requests[record.id] = record
        return record

    async def list_by_patient(
        self,
        patient_id: str,
        status_filter: Optional[ConsentRequestStatus] = None,
    ) -> List[ConsentRequestRecord]:
        """List requests for a given patient subject."""
        items = [r for r in self._requests.values() if r.patient_id == patient_id]
        if status_filter:
            items = [r for r in items if r.status == status_filter]
        return sorted(items, key=lambda x: x.created_at, reverse=True)

    async def list_by_requester(
        self,
        requester_id: str,
        status_filter: Optional[ConsentRequestStatus] = None,
    ) -> List[ConsentRequestRecord]:
        """List requests initiated by a specific user/clinician."""
        items = [r for r in self._requests.values() if r.requester_id == requester_id]
        if status_filter:
            items = [r for r in items if r.status == status_filter]
        return sorted(items, key=lambda x: x.created_at, reverse=True)

    async def list_all(
        self,
        status_filter: Optional[ConsentRequestStatus] = None,
    ) -> List[ConsentRequestRecord]:
        """List all requests (administrative view)."""
        items = list(self._requests.values())
        if status_filter:
            items = [r for r in items if r.status == status_filter]
        return sorted(items, key=lambda x: x.created_at, reverse=True)

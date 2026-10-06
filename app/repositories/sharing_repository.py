"""Clinical Data Sharing Repository and Database Contract Definition (Phase 44).

DATABASE TEAM DEPENDENCY — PHASE 44
====================================
This repository defines the data access contract expected from the Database
Team's clinical sharing entities.

Required SharingRequest entity fields:
  id                 : Primary Key (UUID / string)
  patient_id         : FOREIGN KEY -> users.id (patient subject)
  requester_id       : FOREIGN KEY -> users.id (actor initiating share)
  requester_role     : VARCHAR (e.g., 'PATIENT', 'CLINICIAN', 'ADMIN')
  sharing_type       : VARCHAR / ENUM (matches SharingType values)
  recipient_id       : VARCHAR / FOREIGN KEY (recipient actor/facility/org)
  recipient_type     : VARCHAR / ENUM (DestinationType)
  destination_url    : NULLABLE VARCHAR (validated external endpoint)
  resource_scopes    : JSON ARRAY (explicit resource categories)
  action             : VARCHAR / ENUM (SharingAction)
  purpose            : VARCHAR (clinical/operational purpose)
  delivery_method    : VARCHAR / ENUM (DeliveryMethod)
  requested_format   : VARCHAR (e.g., 'JSON', 'FHIR_R4')
  status             : VARCHAR / ENUM (SharingStatus)
  consent_id         : NULLABLE FOREIGN KEY -> consents.id
  idempotency_key    : NULLABLE VARCHAR UNIQUE
  created_at         : TIMESTAMP WITH TIME ZONE
  updated_at         : TIMESTAMP WITH TIME ZONE
  expires_at         : TIMESTAMP WITH TIME ZONE
  approved_at        : NULLABLE TIMESTAMP WITH TIME ZONE
  executed_at        : NULLABLE TIMESTAMP WITH TIME ZONE
  delivered_at       : NULLABLE TIMESTAMP WITH TIME ZONE
  denial_reason      : NULLABLE VARCHAR
  delivery_status    : NULLABLE VARCHAR
  provider_reference : NULLABLE VARCHAR
  retry_count        : INTEGER DEFAULT 0
  provenance_id      : NULLABLE VARCHAR

Required indexes:
  - (patient_id, status) for patient query
  - (requester_id, status) for requester query
  - (idempotency_key) unique index
  - (expires_at, status) for expiration sweep
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.repositories.base import BaseRepository
from app.schemas.sharing import (
    DeliveryMethod,
    DestinationType,
    SharingAction,
    SharingStatus,
    SharingType,
)


@dataclass
class SharingRequestRecord:
    """Contract representing a sharing request entity from the database."""

    id: str
    patient_id: str
    requester_id: str
    requester_role: str
    sharing_type: SharingType
    recipient_id: str
    recipient_type: DestinationType
    resource_scopes: List[str]
    action: SharingAction = SharingAction.SHARE
    purpose: str = "CARE_DELIVERY"
    delivery_method: DeliveryMethod = DeliveryMethod.DIRECT_API
    requested_format: str = "JSON"
    destination_url: Optional[str] = None
    status: SharingStatus = SharingStatus.REQUESTED
    consent_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    denial_reason: Optional[str] = None
    delivery_status: Optional[str] = None
    provider_reference: Optional[str] = None
    retry_count: int = 0
    provenance_id: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)


class SharingRepository(BaseRepository[SharingRequestRecord]):
    """Repository managing sharing request lifecycle and query persistence."""

    def __init__(self, session: Optional[Any] = None) -> None:
        super().__init__(session=session)
        self._store: Dict[str, SharingRequestRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> id

    async def create(self, record: SharingRequestRecord) -> SharingRequestRecord:
        """Store a new sharing request record."""
        self._store[record.id] = record
        if record.idempotency_key:
            self._idempotency_index[record.idempotency_key] = record.id
        return record

    async def get_by_id(self, sharing_id: str) -> Optional[SharingRequestRecord]:
        """Fetch sharing request by identifier."""
        return self._store.get(sharing_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[SharingRequestRecord]:
        """Fetch existing request by idempotency key."""
        sharing_id = self._idempotency_index.get(idempotency_key)
        if sharing_id:
            return self._store.get(sharing_id)
        return None

    async def update(self, record: SharingRequestRecord) -> SharingRequestRecord:
        """Update an existing sharing request record."""
        record.updated_at = datetime.now(timezone.utc)
        self._store[record.id] = record
        return record

    async def list_by_patient(
        self,
        patient_id: str,
        status: Optional[SharingStatus] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[SharingRequestRecord], int]:
        """List sharing requests targeted at a specific patient."""
        records = [
            r for r in self._store.values()
            if r.patient_id == patient_id and (status is None or r.status == status)
        ]
        records.sort(key=lambda x: x.created_at, reverse=True)
        total = len(records)
        start = (page - 1) * size
        end = start + size
        return records[start:end], total

    async def list_all(
        self,
        requester_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        status: Optional[SharingStatus] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[SharingRequestRecord], int]:
        """List sharing requests with filtering and pagination."""
        records = list(self._store.values())
        if requester_id:
            records = [r for r in records if r.requester_id == requester_id]
        if patient_id:
            records = [r for r in records if r.patient_id == patient_id]
        if status:
            records = [r for r in records if r.status == status]

        records.sort(key=lambda x: x.created_at, reverse=True)
        total = len(records)
        start = (page - 1) * size
        end = start + size
        return records[start:end], total

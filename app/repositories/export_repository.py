"""Export Repository and Database Contract Definition (Phase 44).

DATABASE TEAM DEPENDENCY — PHASE 44
====================================
This repository defines the data access contract expected from the Database
Team's clinical export entities.

Required Export entity fields:
  id              : Primary Key (UUID / string)
  patient_id      : FOREIGN KEY -> users.id (patient subject)
  requester_id    : FOREIGN KEY -> users.id (actor initiating export)
  requester_role  : VARCHAR (e.g. 'PATIENT', 'CLINICIAN')
  export_scope    : VARCHAR / ENUM (matches ExportScopeType)
  format          : VARCHAR / ENUM (matches ExportFormat)
  purpose         : VARCHAR (justification for export)
  status          : VARCHAR / ENUM (matches ExportStatus)
  consent_id      : NULLABLE FOREIGN KEY -> consents.id
  idempotency_key : NULLABLE VARCHAR UNIQUE
  created_at      : TIMESTAMP WITH TIME ZONE
  expires_at      : TIMESTAMP WITH TIME ZONE
  completed_at    : NULLABLE TIMESTAMP WITH TIME ZONE
  download_url    : NULLABLE VARCHAR
  payload         : NULLABLE JSON / JSONB
  file_size_bytes : NULLABLE INTEGER
  error_message   : NULLABLE VARCHAR
  metadata        : NULLABLE JSON / JSONB
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.repositories.base import BaseRepository
from app.schemas.export import ExportFormat, ExportScopeType, ExportStatus


@dataclass
class ExportRecord:
    """Contract representing a clinical data export record."""

    id: str
    patient_id: str
    requester_id: str
    requester_role: str
    export_scope: ExportScopeType
    format: ExportFormat
    purpose: str = "CARE_CONTINUITY"
    status: ExportStatus = ExportStatus.REQUESTED
    consent_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ExportRepository(BaseRepository[ExportRecord]):
    """Repository managing clinical export lifecycle and persistence."""

    def __init__(self, session: Optional[Any] = None) -> None:
        super().__init__(session=session)
        self._store: Dict[str, ExportRecord] = {}
        self._idempotency_index: Dict[str, str] = {}

    async def create(self, record: ExportRecord) -> ExportRecord:
        """Store a new export record."""
        self._store[record.id] = record
        if record.idempotency_key:
            self._idempotency_index[record.idempotency_key] = record.id
        return record

    async def get_by_id(self, export_id: str) -> Optional[ExportRecord]:
        """Fetch an export by ID."""
        return self._store.get(export_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ExportRecord]:
        """Fetch existing export by idempotency key."""
        export_id = self._idempotency_index.get(idempotency_key)
        if export_id:
            return self._store.get(export_id)
        return None

    async def update(self, record: ExportRecord) -> ExportRecord:
        """Update an existing export record."""
        self._store[record.id] = record
        return record

    async def list_by_patient(self, patient_id: str) -> List[ExportRecord]:
        """List exports for a patient."""
        records = [r for r in self._store.values() if r.patient_id == patient_id]
        records.sort(key=lambda x: x.created_at, reverse=True)
        return records

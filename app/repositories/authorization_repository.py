"""Pre-Authorization Repository (Phase 33).

Thread-safe repository managing prior authorization requests and state.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.authorization import PreAuthorizationRecord, PreAuthorizationStatus

logger = logging.getLogger(__name__)


class AuthorizationRepository:
    """Thread-safe repository for pre-authorization requests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._auths: Dict[str, PreAuthorizationRecord] = {}
        self._sequence: int = 1000

    def _next_authorization_number(self) -> str:
        self._sequence += 1
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"AUTH-{today}-{self._sequence:04d}"

    def create(self, record: PreAuthorizationRecord) -> PreAuthorizationRecord:
        """Persist a new authorization record."""
        with self._lock:
            if not record.authorization_number:
                record.authorization_number = self._next_authorization_number()
            self._auths[record.id] = record
            return record

    def get(self, auth_id: str) -> Optional[PreAuthorizationRecord]:
        """Fetch authorization by ID."""
        with self._lock:
            return self._auths.get(auth_id)

    def get_by_number(self, auth_number: str) -> Optional[PreAuthorizationRecord]:
        """Fetch authorization by sequential number."""
        with self._lock:
            for a in self._auths.values():
                if a.authorization_number == auth_number:
                    return a
            return None

    def get_by_payer_reference(self, payer_reference: str) -> Optional[PreAuthorizationRecord]:
        """Fetch authorization by external payer reference token."""
        with self._lock:
            for a in self._auths.values():
                if a.payer_reference == payer_reference:
                    return a
            return None

    def update(self, record: PreAuthorizationRecord) -> PreAuthorizationRecord:
        """Update existing pre-authorization record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._auths[record.id] = record
            return record

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[PreAuthorizationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PreAuthorizationRecord], int]:
        """List prior authorizations for a patient."""
        with self._lock:
            records = [
                a for a in self._auths.values()
                if a.patient_id == patient_id
                and (status is None or a.status == status)
            ]
            records.sort(key=lambda r: r.created_at, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total

    def list_all(
        self,
        facility_id: Optional[str] = None,
        status: Optional[PreAuthorizationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PreAuthorizationRecord], int]:
        """Admin/Clinician query across multiple patients."""
        with self._lock:
            records = [
                a for a in self._auths.values()
                if (facility_id is None or a.facility_id == facility_id)
                and (status is None or a.status == status)
            ]
            records.sort(key=lambda r: r.created_at, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total

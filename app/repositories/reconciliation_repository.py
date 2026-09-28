import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid

from app.schemas.reconciliation import (
    ReconciliationRecord,
    ReconciliationStatus,
    ReconciliationScope,
)

class ReconciliationRepository:
    """
    Thread-safe repository for persisting and querying cross-source Clinical Reconciliation records.
    Stores multi-source comparisons, conflicts, and reviewer resolutions.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._reconciliations: Dict[str, ReconciliationRecord] = {}

    def create(self, record: ReconciliationRecord) -> ReconciliationRecord:
        with self._lock:
            if not record.id:
                record.id = f"rec_{uuid.uuid4().hex[:12]}"
            self._reconciliations[record.id] = record
            return record

    def get_by_id(self, reconciliation_id: str) -> Optional[ReconciliationRecord]:
        with self._lock:
            return self._reconciliations.get(reconciliation_id)

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[ReconciliationStatus] = None,
        scope: Optional[ReconciliationScope] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ReconciliationRecord]:
        with self._lock:
            results = [
                r for r in self._reconciliations.values()
                if r.patient_id == patient_id
            ]
            if status:
                results = [r for r in results if r.status == status]
            if scope:
                results = [r for r in results if r.scope == scope]

            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    def count_by_patient(
        self,
        patient_id: str,
        status: Optional[ReconciliationStatus] = None,
        scope: Optional[ReconciliationScope] = None,
    ) -> int:
        with self._lock:
            results = [
                r for r in self._reconciliations.values()
                if r.patient_id == patient_id
            ]
            if status:
                results = [r for r in results if r.status == status]
            if scope:
                results = [r for r in results if r.scope == scope]
            return len(results)

    def update(self, record: ReconciliationRecord) -> ReconciliationRecord:
        with self._lock:
            existing = self._reconciliations.get(record.id)
            if not existing:
                raise KeyError(f"Reconciliation record with ID {record.id} does not exist.")
            record.version += 1
            record.updated_at = datetime.now(timezone.utc)
            self._reconciliations[record.id] = record
            return record

    def clear(self):
        """Used for testing cleanups."""
        with self._lock:
            self._reconciliations.clear()

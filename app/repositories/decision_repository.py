"""Decision Repository (Phase 47).

Provides thread-safe in-memory storage and querying for clinical decisions,
human reviews, input references, idempotency, and supersession links.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.decision_review import DecisionReviewRecord
from app.schemas.decisions import DecisionRecord, DecisionStatus


class DecisionRepository:
    """Thread-safe repository for decision records and oversight history."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._decisions: Dict[str, DecisionRecord] = {}
        self._reviews: Dict[str, List[DecisionReviewRecord]] = {}
        self._patient_index: Dict[str, List[str]] = {}
        self._resource_index: Dict[Tuple[str, str], List[str]] = {}
        self._idempotency_cache: Dict[str, DecisionRecord] = {}

    def create_decision(self, record: DecisionRecord) -> DecisionRecord:
        """Persist a new clinical decision record."""
        with self._lock:
            if record.idempotency_key and record.idempotency_key in self._idempotency_cache:
                return self._idempotency_cache[record.idempotency_key]

            self._decisions[record.id] = record

            # Index by patient
            p_list = self._patient_index.setdefault(record.patient_id, [])
            p_list.append(record.id)

            # Index by resource if present
            if record.resource_type and record.resource_id:
                res_key = (record.resource_type.lower(), record.resource_id)
                r_list = self._resource_index.setdefault(res_key, [])
                r_list.append(record.id)

            if record.idempotency_key:
                self._idempotency_cache[record.idempotency_key] = record

            return record

    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        """Fetch decision by identifier."""
        with self._lock:
            return self._decisions.get(decision_id)

    def update_decision(self, record: DecisionRecord) -> DecisionRecord:
        """Update existing decision record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._decisions[record.id] = record
            return record

    def add_review(self, review: DecisionReviewRecord) -> DecisionReviewRecord:
        """Append human oversight review record to decision audit trail."""
        with self._lock:
            r_list = self._reviews.setdefault(review.decision_id, [])
            r_list.append(review)
            return review

    def get_reviews(self, decision_id: str) -> List[DecisionReviewRecord]:
        """Retrieve chronological review records for a decision."""
        with self._lock:
            return list(self._reviews.get(decision_id, []))

    def list_by_patient(self, patient_id: str, limit: int = 50) -> List[DecisionRecord]:
        """List decision records for a specific patient, newest first."""
        with self._lock:
            ids = self._patient_index.get(patient_id, [])
            records = [self._decisions[d_id] for d_id in ids if d_id in self._decisions]
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[:limit]

    def list_by_resource(self, resource_type: str, resource_id: str, limit: int = 50) -> List[DecisionRecord]:
        """List decision records associated with a specific resource."""
        with self._lock:
            key = (resource_type.lower(), resource_id)
            ids = self._resource_index.get(key, [])
            records = [self._decisions[d_id] for d_id in ids if d_id in self._decisions]
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[:limit]

    def get_by_idempotency_key(self, key: str) -> Optional[DecisionRecord]:
        """Retrieve decision record cached for an idempotency key."""
        with self._lock:
            return self._idempotency_cache.get(key)

    def supersede_decision(self, old_decision_id: str, new_decision_id: str) -> None:
        """Mark old decision as superseded by new decision without deleting history."""
        with self._lock:
            old = self._decisions.get(old_decision_id)
            if old:
                old.status = DecisionStatus.SUPERSEDED
                old.is_current = False
                old.superseded_by_id = new_decision_id
                old.updated_at = datetime.now(timezone.utc)

            new = self._decisions.get(new_decision_id)
            if new:
                new.supersedes_id = old_decision_id
                new.updated_at = datetime.now(timezone.utc)

    def clear(self) -> None:
        """Reset repository for test isolation."""
        with self._lock:
            self._decisions.clear()
            self._reviews.clear()
            self._patient_index.clear()
            self._resource_index.clear()
            self._idempotency_cache.clear()


decision_repository = DecisionRepository()

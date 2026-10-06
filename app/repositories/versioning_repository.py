"""Clinical Record Versioning Repository (Phase 46).

Provides thread-safe in-memory persistence and query operations for clinical versions,
supporting optimistic concurrency checks, idempotency, supersession pointers,
and historical version traversal.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.core.exceptions import (
    ResourceVersionNotFoundException,
    StaleResourceException,
    VersionConflictException,
)
from app.schemas.versioning import ClinicalVersionRecord, RecordTemporalMetadata, VersionType


class VersioningRepository:
    """Thread-safe version repository with atomic state progression."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Storage: (resource_type, resource_id) -> list of ClinicalVersionRecord ordered by version_number ASC
        self._records: Dict[Tuple[str, str], List[ClinicalVersionRecord]] = {}
        # Idempotency cache: idempotency_key -> ClinicalVersionRecord
        self._idempotency_cache: Dict[str, ClinicalVersionRecord] = {}

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ClinicalVersionRecord]:
        """Fetch cached version record associated with an idempotency key."""
        with self._lock:
            return self._idempotency_cache.get(idempotency_key)

    def get_current_version(self, resource_type: str, resource_id: str) -> Optional[ClinicalVersionRecord]:
        """Fetch the current (active) version record for a resource, or None if none exists."""
        with self._lock:
            key = (resource_type.lower(), resource_id)
            history = self._records.get(key)
            if not history:
                return None
            for record in reversed(history):
                if record.is_current:
                    return record
            # Fallback to last version if none flagged as current
            return history[-1] if history else None

    def get_version(
        self, resource_type: str, resource_id: str, version_number: int
    ) -> Optional[ClinicalVersionRecord]:
        """Fetch a specific historical version by version number."""
        with self._lock:
            key = (resource_type.lower(), resource_id)
            history = self._records.get(key)
            if not history:
                return None
            for record in history:
                if record.version_number == version_number:
                    return record
            return None

    def list_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        reverse: bool = True,
    ) -> Tuple[List[ClinicalVersionRecord], Optional[str], bool, int]:
        """List version history with pagination.
        
        Returns:
            (records_slice, next_cursor, has_more, total_count)
        """
        with self._lock:
            key = (resource_type.lower(), resource_id)
            history = list(self._records.get(key, []))
            total_count = len(history)

            if reverse:
                # Most recent version first
                sorted_history = sorted(history, key=lambda r: r.version_number, reverse=True)
            else:
                sorted_history = sorted(history, key=lambda r: r.version_number, reverse=False)

            # Cursor-based pagination by version_number offset
            start_idx = 0
            if cursor:
                try:
                    cursor_ver = int(cursor)
                    for i, r in enumerate(sorted_history):
                        if r.version_number == cursor_ver:
                            start_idx = i + 1
                            break
                except ValueError:
                    start_idx = 0

            slice_items = sorted_history[start_idx : start_idx + limit]
            has_more = (start_idx + limit) < len(sorted_history)
            next_cursor = str(slice_items[-1].version_number) if (has_more and slice_items) else None

            return slice_items, next_cursor, has_more, total_count

    def create_initial_version(self, record: ClinicalVersionRecord, idempotency_key: Optional[str] = None) -> ClinicalVersionRecord:
        """Create the first version (v1) of a clinical record."""
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_cache:
                return self._idempotency_cache[idempotency_key]

            key = (record.resource_type.lower(), record.resource_id)
            if key in self._records and len(self._records[key]) > 0:
                raise VersionConflictException(
                    f"Resource {record.resource_type}:{record.resource_id} already exists with version {self._records[key][-1].version_number}."
                )

            record.version_number = 1
            record.previous_version_number = None
            record.is_current = True
            self._records[key] = [record]

            if idempotency_key:
                self._idempotency_cache[idempotency_key] = record

            return record

    def append_version(
        self,
        new_record: ClinicalVersionRecord,
        expected_version: int,
        idempotency_key: Optional[str] = None,
    ) -> ClinicalVersionRecord:
        """Atomically append a new version with optimistic concurrency check.
        
        Invariants:
        1. expected_version must match current_version.version_number.
        2. Previous version is superseded (is_current=False, temporal.supersession_time=now).
        3. New version is given version_number = expected_version + 1 and is_current=True.
        4. History is strictly preserved; no prior version is mutated or erased.
        """
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_cache:
                return self._idempotency_cache[idempotency_key]

            key = (new_record.resource_type.lower(), new_record.resource_id)
            history = self._records.get(key)
            if not history or len(history) == 0:
                raise ResourceVersionNotFoundException(
                    f"Cannot append version to non-existent resource {new_record.resource_type}:{new_record.resource_id}."
                )

            current_record = self.get_current_version(new_record.resource_type, new_record.resource_id)
            if current_record is None:
                raise ResourceVersionNotFoundException(f"Active record not found for {new_record.resource_id}.")

            if current_record.version_number != expected_version:
                raise VersionConflictException(
                    f"Version conflict on {new_record.resource_type}:{new_record.resource_id}. "
                    f"Expected version {expected_version}, but current version is {current_record.version_number}."
                )

            now = datetime.now(timezone.utc)

            # Supersede current record without deleting it
            current_record.is_current = False
            current_record.temporal.supersession_time = now

            # Prepare and commit new version
            new_record.version_number = current_record.version_number + 1
            new_record.previous_version_number = current_record.version_number
            new_record.is_current = True
            new_record.created_at = now
            if not new_record.temporal.updated_time:
                new_record.temporal.updated_time = now

            history.append(new_record)

            if idempotency_key:
                self._idempotency_cache[idempotency_key] = new_record

            return new_record

    def clear(self) -> None:
        """Reset repository for unit testing."""
        with self._lock:
            self._records.clear()
            self._idempotency_cache.clear()


# Global in-memory singleton
versioning_repository = VersioningRepository()

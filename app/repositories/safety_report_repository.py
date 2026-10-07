"""Phase 53: Safety Report Repository.

Thread-safe in-memory repository for Phase 53 safety oversight reports.

DB Boundary: This repository follows the database team contract.
It does NOT create competing tables or migrations. Persistence layer
is owned by the DB teammate.
"""

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.safety_report import (
    SafetyReportRecord,
    SafetyReportLifecycleState,
    SafetyReportType,
)


class SafetyReportRepository:
    """Thread-safe repository for Phase 53 safety oversight reports."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reports: Dict[str, SafetyReportRecord] = {}
        self._org_reports: Dict[str, List[str]] = {}
        self._idempotency_map: Dict[str, str] = {}

    def save_report(self, record: SafetyReportRecord) -> SafetyReportRecord:
        """Persist or update a safety report record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._reports[record.report_id] = record

            if record.organization_id:
                org_list = self._org_reports.setdefault(record.organization_id, [])
                if record.report_id not in org_list:
                    org_list.append(record.report_id)

            if record.idempotency_key:
                self._idempotency_map[record.idempotency_key] = record.report_id

            return record

    def get_report(self, report_id: str) -> Optional[SafetyReportRecord]:
        """Retrieve safety report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def get_by_idempotency_key(self, key: str) -> Optional[SafetyReportRecord]:
        """Resolve existing report via idempotency key."""
        with self._lock:
            rid = self._idempotency_map.get(key)
            if rid:
                return self._reports.get(rid)
            return None

    def list_reports(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        report_type: Optional[SafetyReportType] = None,
        lifecycle_state: Optional[SafetyReportLifecycleState] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SafetyReportRecord]:
        """List all reports with optional filters."""
        with self._lock:
            results: List[SafetyReportRecord] = []
            
            if organization_id and organization_id in self._org_reports:
                candidate_ids = self._org_reports[organization_id]
                candidates = [self._reports[i] for i in candidate_ids]
            else:
                candidates = list(self._reports.values())
                
            for rec in candidates:
                if organization_id and rec.organization_id != organization_id:
                    continue
                if facility_id and rec.facility_id != facility_id:
                    continue
                if report_type and rec.report_type != report_type:
                    continue
                if lifecycle_state and rec.lifecycle_state != lifecycle_state:
                    continue
                results.append(rec)
                
            results.sort(key=lambda r: r.requested_at, reverse=True)
            return results[offset : offset + limit]

    def reset(self) -> None:
        """Reset repository state for test isolation."""
        with self._lock:
            self._reports.clear()
            self._org_reports.clear()
            self._idempotency_map.clear()


# Global singleton
safety_report_repository = SafetyReportRepository()

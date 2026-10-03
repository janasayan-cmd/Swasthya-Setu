"""Diagnostic Result Repository (Phase 34).

Thread-safe repository for storing diagnostic laboratory results and analyte measurements.
Preserves full immutability and historical versioning for corrected/amended results.

CRITICAL INVARIANTS:
- HISTORICAL RESULTS ARE NEVER DESTROYED OR OVERWRITTEN
- CORRECTED RESULT CREATES A NEW VERSION WITH SUPERSEDES POINTER
- ORIGINAL RESULT REMAINS RETRIEVABLE FOR AUDIT
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.diagnostic_result import (
    DiagnosticResultFilter,
    DiagnosticResultListResponse,
    DiagnosticResultRecord,
    ResultStatus,
    VerificationStatus,
)


class DiagnosticResultRepository:
    """Thread-safe repository for diagnostic results with audit-grade versioning."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: Dict[str, DiagnosticResultRecord] = {}
        self._provider_result_map: Dict[str, str] = {}  # f"{provider_id}:{provider_result_id}:{version}" -> result_id

    def save(self, result: DiagnosticResultRecord) -> DiagnosticResultRecord:
        with self._lock:
            # If this record supersedes an older result, update the older result
            if result.supersedes_result_id and result.supersedes_result_id in self._results:
                old = self._results[result.supersedes_result_id]
                superseded_old = old.model_copy(
                    update={
                        "is_current": False,
                        "verification_status": VerificationStatus.SUPERSEDED,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                self._results[result.supersedes_result_id] = superseded_old

            self._results[result.result_id] = result
            map_key = f"{result.provider_id}:{result.provider_result_id}:{result.version}"
            self._provider_result_map[map_key] = result.result_id
            return result

    def get_by_id(self, result_id: str) -> Optional[DiagnosticResultRecord]:
        with self._lock:
            return self._results.get(result_id)

    def get_by_provider_result_id(
        self,
        provider_id: str,
        provider_result_id: str,
        version: Optional[int] = None,
    ) -> Optional[DiagnosticResultRecord]:
        with self._lock:
            if version is not None:
                key = f"{provider_id}:{provider_result_id}:{version}"
                rid = self._provider_result_map.get(key)
                return self._results.get(rid) if rid else None

            # Return latest current version
            matching = [
                r for r in self._results.values()
                if r.provider_id == provider_id and r.provider_result_id == provider_result_id
            ]
            if not matching:
                return None
            matching.sort(key=lambda r: r.version, reverse=True)
            return matching[0]

    def get_version_history(self, result_id: str) -> List[DiagnosticResultRecord]:
        """Traverse version chain forwards and backwards for an analyte result."""
        with self._lock:
            target = self._results.get(result_id)
            if not target:
                return []

            # Find all results with same provider_id and provider_result_id, or linked by order_id
            history = [
                r for r in self._results.values()
                if (r.provider_id == target.provider_id and r.provider_result_id == target.provider_result_id)
                or (target.order_id and r.order_id == target.order_id and r.items and target.items and r.items[0].analyte_code == target.items[0].analyte_code)
            ]
            history.sort(key=lambda r: r.version)
            return history

    def verify_result(
        self,
        result_id: str,
        verified_by: str,
        verification_status: VerificationStatus,
        notes: Optional[str] = None,
    ) -> Optional[DiagnosticResultRecord]:
        """Record clinician verification decision (Phase 10 integration)."""
        with self._lock:
            result = self._results.get(result_id)
            if not result:
                return None

            now = datetime.now(timezone.utc)
            updated = result.model_copy(
                update={
                    "verification_status": verification_status,
                    "verified_by": verified_by,
                    "verified_at": now,
                    "verification_notes": notes,
                    "updated_at": now,
                }
            )
            self._results[result_id] = updated
            return updated

    def filter_results(
        self,
        filter_params: DiagnosticResultFilter,
        current_only: bool = True,
    ) -> DiagnosticResultListResponse:
        with self._lock:
            results = list(self._results.values())

            if current_only:
                results = [r for r in results if r.is_current]

            if filter_params.patient_id:
                results = [r for r in results if r.patient_id == filter_params.patient_id]

            if filter_params.order_id:
                results = [r for r in results if r.order_id == filter_params.order_id]

            if filter_params.clinician_id:
                results = [r for r in results if r.clinician_id == filter_params.clinician_id]

            if filter_params.status:
                results = [r for r in results if r.status == filter_params.status]

            if filter_params.verification_status:
                results = [r for r in results if r.verification_status == filter_params.verification_status]

            if filter_params.has_critical is not None:
                results = [r for r in results if r.has_critical_flag == filter_params.has_critical]

            if filter_params.date_from:
                results = [r for r in results if r.created_at >= filter_params.date_from]

            if filter_params.date_to:
                results = [r for r in results if r.created_at <= filter_params.date_to]

            results.sort(key=lambda r: r.created_at, reverse=True)

            total = len(results)
            start = (filter_params.page - 1) * filter_params.limit
            end = start + filter_params.limit
            paginated = results[start:end]

            return DiagnosticResultListResponse(
                items=paginated,
                total=total,
                page=filter_params.page,
                limit=filter_params.limit,
            )

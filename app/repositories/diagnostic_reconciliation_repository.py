"""Diagnostic Reconciliation Repository (Phase 34).

Thread-safe storage for diagnostic integrity audits and reconciliation summaries.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.schemas.diagnostic_reconciliation import ReconciliationSummary


class DiagnosticReconciliationRepository:
    """Thread-safe store for diagnostic reconciliation runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._summaries: Dict[str, ReconciliationSummary] = {}

    def save(self, summary: ReconciliationSummary) -> ReconciliationSummary:
        with self._lock:
            self._summaries[summary.reconciliation_id] = summary
            return summary

    def get_by_id(self, reconciliation_id: str) -> Optional[ReconciliationSummary]:
        with self._lock:
            return self._summaries.get(reconciliation_id)

    def list_recent(self, limit: int = 50) -> List[ReconciliationSummary]:
        with self._lock:
            items = list(self._summaries.values())
            items.sort(key=lambda s: s.reconciled_at, reverse=True)
            return items[:limit]

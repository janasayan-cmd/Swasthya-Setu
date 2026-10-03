"""Diagnostic Report Repository (Phase 34).

Thread-safe repository for storing diagnostic reports, clinical summaries, and imaging conclusions.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.diagnostic_report import (
    DiagnosticReportFilter,
    DiagnosticReportListResponse,
    DiagnosticReportRecord,
)


class DiagnosticReportRepository:
    """Thread-safe repository for diagnostic reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reports: Dict[str, DiagnosticReportRecord] = {}
        self._reports_by_number: Dict[str, str] = {}
        self._counter: int = 2000

    def generate_report_number(self) -> str:
        """Generate sequential report number."""
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        with self._lock:
            self._counter += 1
            seq = self._counter
        return f"RPT-{now_str}-{seq:04d}"

    def save(self, report: DiagnosticReportRecord) -> DiagnosticReportRecord:
        with self._lock:
            self._reports[report.report_id] = report
            self._reports_by_number[report.report_number] = report.report_id
            return report

    def get_by_id(self, report_id: str) -> Optional[DiagnosticReportRecord]:
        with self._lock:
            return self._reports.get(report_id)

    def get_by_report_number(self, report_number: str) -> Optional[DiagnosticReportRecord]:
        with self._lock:
            rid = self._reports_by_number.get(report_number)
            return self._reports.get(rid) if rid else None

    def filter_reports(self, filter_params: DiagnosticReportFilter) -> DiagnosticReportListResponse:
        with self._lock:
            results = list(self._reports.values())

            if filter_params.patient_id:
                results = [r for r in results if r.patient_id == filter_params.patient_id]

            if filter_params.order_id:
                results = [r for r in results if r.order_id == filter_params.order_id]

            if filter_params.provider_id:
                results = [r for r in results if r.provider_id == filter_params.provider_id]

            if filter_params.status:
                results = [r for r in results if r.status == filter_params.status]

            if filter_params.date_from:
                results = [r for r in results if r.reported_at >= filter_params.date_from]

            if filter_params.date_to:
                results = [r for r in results if r.reported_at <= filter_params.date_to]

            results.sort(key=lambda r: r.reported_at, reverse=True)

            total = len(results)
            start = (filter_params.page - 1) * filter_params.limit
            end = start + filter_params.limit
            paginated = results[start:end]

            return DiagnosticReportListResponse(
                items=paginated,
                total=total,
                page=filter_params.page,
                limit=filter_params.limit,
            )

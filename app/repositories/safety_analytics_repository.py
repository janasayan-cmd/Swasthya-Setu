"""Phase 61: Safety Analytics Repository.

Thread-safe repository for longitudinal safety surveillance analyses,
pattern findings, emerging risk indicators, and governed routing history.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_analytics import (
    AnalysisLifecycleState,
    RiskIndicatorLifecycleState,
    SafetyAnalysisRecord,
    SafetyRiskIndicatorFinding,
)


class SafetyAnalyticsRepository:
    """Thread-safe in-memory repository for Phase 61 safety analytics records."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._analyses: Dict[str, SafetyAnalysisRecord] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyAnalysisRecord) -> SafetyAnalysisRecord:
        """Persist or update an analysis record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._analyses[record.analysis_id] = record
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.analysis_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get(self, analysis_id: str) -> Optional[SafetyAnalysisRecord]:
        """Retrieve analysis record by ID."""
        with self._lock:
            return self._analyses.get(analysis_id)

    def list_analyses(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[AnalysisLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyAnalysisRecord]:
        """Query analysis records with tenant/facility filtering."""
        with self._lock:
            results = list(self._analyses.values())

            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.scope.facility_id == facility_id]
            if lifecycle_state:
                results = [r for r in results if r.lifecycle_state == lifecycle_state]

            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[offset : offset + limit]

    def list_review_required(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyAnalysisRecord]:
        """List analyses requiring human review."""
        with self._lock:
            results = [
                r
                for r in self._analyses.values()
                if r.requires_human_review
                or r.lifecycle_state == AnalysisLifecycleState.REVIEW_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_risk_indicators(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyRiskIndicatorFinding]:
        """List all active risk indicators across analyses."""
        with self._lock:
            indicators: List[SafetyRiskIndicatorFinding] = []
            for anl in self._analyses.values():
                if organization_id and anl.organization_id != organization_id:
                    continue
                for ind in anl.risk_indicators:
                    if ind.lifecycle_state not in (
                        RiskIndicatorLifecycleState.RESOLVED,
                        RiskIndicatorLifecycleState.REJECTED,
                        RiskIndicatorLifecycleState.SUPERSEDED,
                    ):
                        indicators.append(ind)
            return indicators

    def list_escalation_required(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyAnalysisRecord]:
        """List analyses requiring governed escalation."""
        with self._lock:
            results = [
                r
                for r in self._analyses.values()
                if r.requires_escalation
                or r.lifecycle_state == AnalysisLifecycleState.ESCALATION_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_reassessment_required(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyAnalysisRecord]:
        """List analyses requiring Phase 60 reassessment."""
        with self._lock:
            results = [
                r
                for r in self._analyses.values()
                if r.requires_reassessment
                or r.lifecycle_state == AnalysisLifecycleState.REASSESSMENT_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_reanalysis_required(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyAnalysisRecord]:
        """List analyses marked stale or needing re-execution."""
        with self._lock:
            results = [
                r
                for r in self._analyses.values()
                if r.lifecycle_state
                in (AnalysisLifecycleState.STALE, AnalysisLifecycleState.SUPERSEDED)
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def check_idempotency(
        self, idempotency_key: str, organization_id: str
    ) -> Optional[SafetyAnalysisRecord]:
        """Check if an analysis has already been executed for this idempotency key."""
        with self._lock:
            entry = self._idempotency_store.get(idempotency_key)
            if entry:
                anl_id, entry_org, _ = entry
                if entry_org == organization_id:
                    return self._analyses.get(anl_id)
            return None

    def store_idempotency(
        self, idempotency_key: str, organization_id: str, analysis_id: str
    ) -> None:
        """Store idempotency key association."""
        with self._lock:
            self._idempotency_store[idempotency_key] = (
                analysis_id,
                organization_id,
                datetime.now(timezone.utc),
            )

    def clear(self) -> None:
        """Clear all records (primarily for testing)."""
        with self._lock:
            self._analyses.clear()
            self._idempotency_store.clear()


_repository_instance: Optional[SafetyAnalyticsRepository] = None
_repo_lock = threading.Lock()


def get_safety_analytics_repository() -> SafetyAnalyticsRepository:
    """Retrieve singleton repository instance."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_lock:
            if _repository_instance is None:
                _repository_instance = SafetyAnalyticsRepository()
    return _repository_instance

"""Phase 71: Clinical Safety Governance Audit Intelligence Repository.

Provides a thread-safe repository layer for:
- Repeat finding candidates and review dispositions
- Cross-audit patterns and analytical explanations
- Systemic issue candidates and priority scores
- Corrective action recurrence tracking
- Reproducible management review reports
- Versioned analytical configurations
- Cross-phase governance referrals
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.schemas.audit_analytics_config import AnalyticsConfigRecord
from app.schemas.audit_capa_recurrence import CAPARecurrenceRecord
from app.schemas.audit_governance_report import ManagementReportRecord
from app.schemas.audit_pattern_systemic import (
    AuditPatternRecord,
    SystemicIssueCandidateRecord,
)
from app.schemas.audit_repeat_finding import RepeatFindingCandidateRecord


class GovernanceAuditIntelligenceRepository:
    """Thread-safe in-memory repository for Phase 71 audit intelligence entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._repeat_candidates: Dict[str, RepeatFindingCandidateRecord] = {}
        self._patterns: Dict[str, AuditPatternRecord] = {}
        self._systemic_candidates: Dict[str, SystemicIssueCandidateRecord] = {}
        self._capa_recurrences: Dict[str, CAPARecurrenceRecord] = {}
        self._management_reports: Dict[str, ManagementReportRecord] = {}
        self._configs: Dict[str, AnalyticsConfigRecord] = {}
        self._referrals: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Analytical Configurations
    # -------------------------------------------------------------------------

    def save_config(self, record: AnalyticsConfigRecord) -> AnalyticsConfigRecord:
        with self._lock:
            self._configs[record.configuration_id] = record
            return record

    def get_config(self, configuration_id: str) -> Optional[AnalyticsConfigRecord]:
        with self._lock:
            return self._configs.get(configuration_id)

    def get_active_config(self, organization_id: str) -> Optional[AnalyticsConfigRecord]:
        with self._lock:
            for c in reversed(list(self._configs.values())):
                if c.organization_id == organization_id and c.is_active and not c.is_deprecated:
                    return c
            return None

    def list_configs(self, organization_id: str) -> List[AnalyticsConfigRecord]:
        with self._lock:
            results = [c for c in self._configs.values() if c.organization_id == organization_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Repeat Finding Candidates
    # -------------------------------------------------------------------------

    def save_repeat_candidate(
        self, record: RepeatFindingCandidateRecord
    ) -> RepeatFindingCandidateRecord:
        with self._lock:
            self._repeat_candidates[record.candidate_id] = record
            return record

    def get_repeat_candidate(self, candidate_id: str) -> Optional[RepeatFindingCandidateRecord]:
        with self._lock:
            return self._repeat_candidates.get(candidate_id)

    def list_repeat_candidates(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
        confidence: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RepeatFindingCandidateRecord]:
        with self._lock:
            results = [
                c for c in self._repeat_candidates.values()
                if c.organization_id == organization_id
                and (facility_id is None or c.facility_id == facility_id or c.facility_id is None)
                and (status is None or c.review_status.value == status)
                and (confidence is None or c.confidence.value == confidence)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Cross-Audit Patterns
    # -------------------------------------------------------------------------

    def save_pattern(self, record: AuditPatternRecord) -> AuditPatternRecord:
        with self._lock:
            self._patterns[record.pattern_id] = record
            return record

    def get_pattern(self, pattern_id: str) -> Optional[AuditPatternRecord]:
        with self._lock:
            return self._patterns.get(pattern_id)

    def list_patterns(
        self,
        organization_id: str,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditPatternRecord]:
        with self._lock:
            results = [
                p for p in self._patterns.values()
                if p.organization_id == organization_id
                and (category is None or p.pattern_category.value == category)
                and (status is None or p.review_status.value == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Systemic Issue Candidates
    # -------------------------------------------------------------------------

    def save_systemic_candidate(
        self, record: SystemicIssueCandidateRecord
    ) -> SystemicIssueCandidateRecord:
        with self._lock:
            self._systemic_candidates[record.candidate_id] = record
            return record

    def get_systemic_candidate(
        self, candidate_id: str
    ) -> Optional[SystemicIssueCandidateRecord]:
        with self._lock:
            return self._systemic_candidates.get(candidate_id)

    def list_systemic_candidates(
        self,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SystemicIssueCandidateRecord]:
        with self._lock:
            results = [
                s for s in self._systemic_candidates.values()
                if s.organization_id == organization_id
                and (status is None or s.status.value == status)
            ]
            results.sort(key=lambda x: x.priority_score, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Corrective Action Recurrence
    # -------------------------------------------------------------------------

    def save_capa_recurrence(self, record: CAPARecurrenceRecord) -> CAPARecurrenceRecord:
        with self._lock:
            self._capa_recurrences[record.recurrence_id] = record
            return record

    def get_capa_recurrence(self, recurrence_id: str) -> Optional[CAPARecurrenceRecord]:
        with self._lock:
            return self._capa_recurrences.get(recurrence_id)

    def get_capa_recurrence_by_finding(
        self, finding_id: str
    ) -> Optional[CAPARecurrenceRecord]:
        with self._lock:
            for r in self._capa_recurrences.values():
                if r.initial_finding_id == finding_id:
                    return r
            return None

    def list_capa_recurrences(
        self,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CAPARecurrenceRecord]:
        with self._lock:
            results = [
                r for r in self._capa_recurrences.values()
                if r.organization_id == organization_id
                and (status is None or r.recurrence_status.value == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Management Reports
    # -------------------------------------------------------------------------

    def save_management_report(self, record: ManagementReportRecord) -> ManagementReportRecord:
        with self._lock:
            self._management_reports[record.report_id] = record
            return record

    def get_management_report(self, report_id: str) -> Optional[ManagementReportRecord]:
        with self._lock:
            return self._management_reports.get(report_id)

    def list_management_reports(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementReportRecord]:
        with self._lock:
            results = [
                r for r in self._management_reports.values()
                if r.organization_id == organization_id
                and (facility_id is None or r.facility_id == facility_id or r.facility_id is None)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Governance Referrals
    # -------------------------------------------------------------------------

    def save_referral(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._referrals.append(record)
            return record

    def list_referrals(
        self, organization_id: str, destination_workflow: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                r for r in self._referrals
                if r.get("organization_id") == organization_id
                and (destination_workflow is None or r.get("destination_workflow") == destination_workflow)
            ]

    # -------------------------------------------------------------------------
    # Clear Repository State
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        with self._lock:
            self._repeat_candidates.clear()
            self._patterns.clear()
            self._systemic_candidates.clear()
            self._capa_recurrences.clear()
            self._management_reports.clear()
            self._configs.clear()
            self._referrals.clear()


# Global singleton
_global_intelligence_repo = GovernanceAuditIntelligenceRepository()


def get_governance_audit_intelligence_repository() -> GovernanceAuditIntelligenceRepository:
    """Dependency provider for audit intelligence repository."""
    return _global_intelligence_repo

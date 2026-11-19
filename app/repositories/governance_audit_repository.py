"""Phase 70: Independent Clinical Safety Governance Audit Repository.

Provides a thread-safe repository layer for:
- Audit programmes and individual safety audits
- Scope definitions, versions, and change history
- Auditor assignments and independence reviews
- Criteria, evidence requests, and audit tests
- Observations, confirmed/disputed findings, and auditee responses
- Audit reports, review decisions, closures, and follow-ups
- Specialized queues and idempotency cache
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.audit_execution import (
    AuditCriterionRecord,
    AuditEvidenceRequestRecord,
    AuditTestRecord,
    EvidenceRequestStatus,
)
from app.schemas.audit_finding_response import (
    AuditeeResponseRecord,
    AuditFindingRecord,
    AuditFindingStatus,
)
from app.schemas.audit_programme import (
    AuditProgrammeRecord,
)
from app.schemas.audit_report_closure import (
    AuditReportRecord,
)
from app.schemas.audit_scope_planning import (
    AuditLifecycleStatus,
    AuditScopeRecord,
    ClinicalSafetyAuditRecord,
)
from app.schemas.auditor_assignment import (
    AuditorAssignmentRecord,
    IndependenceStatus,
)


class GovernanceAuditRepository:
    """Thread-safe in-memory repository for Phase 70 governance audit entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._programmes: Dict[str, AuditProgrammeRecord] = {}
        self._audits: Dict[str, ClinicalSafetyAuditRecord] = {}
        self._scopes: Dict[str, AuditScopeRecord] = {}  # scope_id -> record
        self._audit_scope_map: Dict[str, str] = {}  # audit_id -> scope_id
        self._assignments: Dict[str, AuditorAssignmentRecord] = {}
        self._criteria: Dict[str, AuditCriterionRecord] = {}
        self._evidence_requests: Dict[str, AuditEvidenceRequestRecord] = {}
        self._tests: Dict[str, AuditTestRecord] = {}
        self._findings: Dict[str, AuditFindingRecord] = {}
        self._responses: Dict[str, AuditeeResponseRecord] = {}
        self._reports: Dict[str, AuditReportRecord] = {}
        self._idempotency_store: Dict[str, Tuple[str, datetime]] = {}

    # -------------------------------------------------------------------------
    # Programmes
    # -------------------------------------------------------------------------

    def save_programme(self, record: AuditProgrammeRecord) -> AuditProgrammeRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._programmes[record.programme_id] = record
            return record

    def get_programme(self, programme_id: str) -> Optional[AuditProgrammeRecord]:
        with self._lock:
            return self._programmes.get(programme_id)

    def list_programmes(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditProgrammeRecord]:
        with self._lock:
            results = [
                p for p in self._programmes.values()
                if p.organization_id == organization_id
                and (facility_id is None or p.facility_id == facility_id or p.facility_id is None)
                and (status is None or p.status.value == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Audits
    # -------------------------------------------------------------------------

    def save_audit(self, record: ClinicalSafetyAuditRecord) -> ClinicalSafetyAuditRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._audits[record.audit_id] = record
            return record

    def get_audit(self, audit_id: str) -> Optional[ClinicalSafetyAuditRecord]:
        with self._lock:
            return self._audits.get(audit_id)

    def list_audits(
        self,
        organization_id: str,
        programme_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ClinicalSafetyAuditRecord]:
        with self._lock:
            results = [
                a for a in self._audits.values()
                if a.organization_id == organization_id
                and (programme_id is None or a.programme_id == programme_id)
                and (status is None or a.lifecycle_status.value == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Scope
    # -------------------------------------------------------------------------

    def save_scope(self, record: AuditScopeRecord) -> AuditScopeRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._scopes[record.scope_id] = record
            self._audit_scope_map[record.audit_id] = record.scope_id
            return record

    def get_scope(self, scope_id: str) -> Optional[AuditScopeRecord]:
        with self._lock:
            return self._scopes.get(scope_id)

    def get_scope_for_audit(self, audit_id: str) -> Optional[AuditScopeRecord]:
        with self._lock:
            scope_id = self._audit_scope_map.get(audit_id)
            return self._scopes.get(scope_id) if scope_id else None

    # -------------------------------------------------------------------------
    # Assignments
    # -------------------------------------------------------------------------

    def save_assignment(self, record: AuditorAssignmentRecord) -> AuditorAssignmentRecord:
        with self._lock:
            self._assignments[record.assignment_id] = record
            return record

    def get_assignment(self, assignment_id: str) -> Optional[AuditorAssignmentRecord]:
        with self._lock:
            return self._assignments.get(assignment_id)

    def list_assignments_for_audit(self, audit_id: str) -> List[AuditorAssignmentRecord]:
        with self._lock:
            results = [a for a in self._assignments.values() if a.audit_id == audit_id and a.is_active]
            results.sort(key=lambda x: x.assigned_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Criteria
    # -------------------------------------------------------------------------

    def save_criterion(self, record: AuditCriterionRecord) -> AuditCriterionRecord:
        with self._lock:
            self._criteria[record.criterion_id] = record
            return record

    def get_criterion(self, criterion_id: str) -> Optional[AuditCriterionRecord]:
        with self._lock:
            return self._criteria.get(criterion_id)

    def list_criteria_for_audit(self, audit_id: str) -> List[AuditCriterionRecord]:
        with self._lock:
            results = [c for c in self._criteria.values() if c.audit_id == audit_id and c.is_active]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Evidence Requests
    # -------------------------------------------------------------------------

    def save_evidence_request(
        self, record: AuditEvidenceRequestRecord
    ) -> AuditEvidenceRequestRecord:
        with self._lock:
            self._evidence_requests[record.request_id] = record
            return record

    def get_evidence_request(self, request_id: str) -> Optional[AuditEvidenceRequestRecord]:
        with self._lock:
            return self._evidence_requests.get(request_id)

    def list_evidence_requests_for_audit(
        self, audit_id: str
    ) -> List[AuditEvidenceRequestRecord]:
        with self._lock:
            results = [r for r in self._evidence_requests.values() if r.audit_id == audit_id]
            results.sort(key=lambda x: x.requested_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Tests
    # -------------------------------------------------------------------------

    def save_test(self, record: AuditTestRecord) -> AuditTestRecord:
        with self._lock:
            self._tests[record.test_id] = record
            return record

    def get_test(self, test_id: str) -> Optional[AuditTestRecord]:
        with self._lock:
            return self._tests.get(test_id)

    def list_tests_for_audit(self, audit_id: str) -> List[AuditTestRecord]:
        with self._lock:
            results = [t for t in self._tests.values() if t.audit_id == audit_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Findings
    # -------------------------------------------------------------------------

    def save_finding(self, record: AuditFindingRecord) -> AuditFindingRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._findings[record.finding_id] = record
            return record

    def get_finding(self, finding_id: str) -> Optional[AuditFindingRecord]:
        with self._lock:
            return self._findings.get(finding_id)

    def list_findings_for_audit(
        self,
        audit_id: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        is_confirmed: Optional[bool] = None,
        is_closed: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditFindingRecord]:
        with self._lock:
            results = [
                f for f in self._findings.values()
                if (audit_id is None or f.audit_id == audit_id)
                and (category is None or f.category.value == category)
                and (severity is None or f.severity.value == severity)
                and (is_confirmed is None or f.is_confirmed == is_confirmed)
                and (is_closed is None or f.is_closed == is_closed)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Auditee Responses
    # -------------------------------------------------------------------------

    def save_response(self, record: AuditeeResponseRecord) -> AuditeeResponseRecord:
        with self._lock:
            self._responses[record.response_id] = record
            return record

    def get_response(self, response_id: str) -> Optional[AuditeeResponseRecord]:
        with self._lock:
            return self._responses.get(response_id)

    def list_responses_for_finding(self, finding_id: str) -> List[AuditeeResponseRecord]:
        with self._lock:
            results = [r for r in self._responses.values() if r.finding_id == finding_id]
            results.sort(key=lambda x: x.submitted_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def save_report(self, record: AuditReportRecord) -> AuditReportRecord:
        with self._lock:
            self._reports[record.report_id] = record
            return record

    def get_report(self, report_id: str) -> Optional[AuditReportRecord]:
        with self._lock:
            return self._reports.get(report_id)

    def list_reports_for_audit(self, audit_id: str) -> List[AuditReportRecord]:
        with self._lock:
            results = [r for r in self._reports.values() if r.audit_id == audit_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Queues
    # -------------------------------------------------------------------------

    def list_review_required_queue(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[ClinicalSafetyAuditRecord]:
        """Audits in PENDING_REVIEW, REPORT_DRAFT, or with unreviewed independence/findings."""
        with self._lock:
            results: List[ClinicalSafetyAuditRecord] = []
            for a in self._audits.values():
                if (
                    a.organization_id == organization_id
                    and (facility_id is None or a.facility_id == facility_id or a.facility_id is None)
                    and a.lifecycle_status in {
                        AuditLifecycleStatus.PENDING_REVIEW,
                        AuditLifecycleStatus.PENDING_APPROVAL,
                        AuditLifecycleStatus.REPORT_DRAFT,
                    }
                ):
                    results.append(a)
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    def list_overdue_queue(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[ClinicalSafetyAuditRecord]:
        """Audits past their planned_end_date that are still open."""
        with self._lock:
            now = datetime.now(timezone.utc)
            results: List[ClinicalSafetyAuditRecord] = []
            for a in self._audits.values():
                if (
                    a.organization_id == organization_id
                    and (facility_id is None or a.facility_id == facility_id or a.facility_id is None)
                    and a.lifecycle_status not in {
                        AuditLifecycleStatus.CLOSED,
                        AuditLifecycleStatus.CANCELLED,
                    }
                    and a.planned_end_date
                    and a.planned_end_date < now
                ):
                    results.append(a)
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Idempotency & Clear
    # -------------------------------------------------------------------------

    def get_idempotent_id(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._idempotency_store.get(key)
            return entry[0] if entry else None

    def save_idempotent_id(self, key: str, entity_id: str) -> None:
        with self._lock:
            self._idempotency_store[key] = (entity_id, datetime.now(timezone.utc))

    def clear(self) -> None:
        with self._lock:
            self._programmes.clear()
            self._audits.clear()
            self._scopes.clear()
            self._audit_scope_map.clear()
            self._assignments.clear()
            self._criteria.clear()
            self._evidence_requests.clear()
            self._tests.clear()
            self._findings.clear()
            self._responses.clear()
            self._reports.clear()
            self._idempotency_store.clear()


# Global singleton
_global_audit_repo = GovernanceAuditRepository()


def get_governance_audit_repository() -> GovernanceAuditRepository:
    """Dependency provider returning singleton audit repository."""
    return _global_audit_repo

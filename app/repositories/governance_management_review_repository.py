"""Phase 72: Clinical Safety Governance Management Review Repository.

Provides a thread-safe repository layer for:
- Management review programmes and operational reviews
- Participant invitations, attendance confirmations, and decision authorities
- Agenda topics and cross-workflow consolidated inputs
- Review package compilation, locking, and reproducibility
- Meeting discussion minutes and authoritative decisions
- Follow-through commitments, progress reports, verifications, and escalations
- Executive summary review reports and lifecycle closure records
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.management_review_programme import (
    ManagementReviewProgrammeRecord,
    ReviewProgrammeStatus,
)
from app.schemas.management_review_scheduling import (
    ManagementReviewRecord,
    ManagementReviewStatus,
    ReviewParticipantRecord,
)
from app.schemas.management_review_agenda import (
    ConsolidatedInputRecord,
    ReviewAgendaItemRecord,
    ReviewPackageRecord,
)
from app.schemas.management_review_decisions import (
    CommitmentEscalationRecord,
    DiscussionRecord,
    ManagementCommitmentRecord,
    ManagementDecisionRecord,
    ManagementDecisionStatus,
    CommitmentStatus,
)
from app.schemas.management_review_reports_analytics import (
    ManagementReviewReportRecord,
    ReportReviewStatus,
)


class GovernanceManagementReviewRepository:
    """Thread-safe in-memory repository for Phase 72 management review entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._programmes: Dict[str, ManagementReviewProgrammeRecord] = {}
        self._reviews: Dict[str, ManagementReviewRecord] = {}
        self._participants: Dict[str, ReviewParticipantRecord] = {}
        self._agenda_items: Dict[str, ReviewAgendaItemRecord] = {}
        self._inputs: Dict[str, ConsolidatedInputRecord] = {}
        self._packages: Dict[str, ReviewPackageRecord] = {}
        self._discussions: Dict[str, DiscussionRecord] = {}
        self._decisions: Dict[str, ManagementDecisionRecord] = {}
        self._commitments: Dict[str, ManagementCommitmentRecord] = {}
        self._escalations: Dict[str, CommitmentEscalationRecord] = {}
        self._reports: Dict[str, ManagementReviewReportRecord] = {}

    def clear(self) -> None:
        """Clears all records from the repository (useful for tests)."""
        with self._lock:
            self._programmes.clear()
            self._reviews.clear()
            self._participants.clear()
            self._agenda_items.clear()
            self._inputs.clear()
            self._packages.clear()
            self._discussions.clear()
            self._decisions.clear()
            self._commitments.clear()
            self._escalations.clear()
            self._reports.clear()

    # -------------------------------------------------------------------------
    # Programmes
    # -------------------------------------------------------------------------

    def save_programme(
        self, record: ManagementReviewProgrammeRecord
    ) -> ManagementReviewProgrammeRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._programmes[record.programme_id] = record
            return record

    def get_programme(self, programme_id: str) -> Optional[ManagementReviewProgrammeRecord]:
        with self._lock:
            return self._programmes.get(programme_id)

    def list_programmes(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementReviewProgrammeRecord]:
        with self._lock:
            results = [
                p
                for p in self._programmes.values()
                if p.organization_id == organization_id
                and (facility_id is None or p.facility_id == facility_id or p.facility_id is None)
                and (status is None or p.status.value == status)
                and (category is None or p.category.value == category)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Reviews (Meetings)
    # -------------------------------------------------------------------------

    def save_review(self, record: ManagementReviewRecord) -> ManagementReviewRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._reviews[record.review_id] = record
            return record

    def get_review(self, review_id: str) -> Optional[ManagementReviewRecord]:
        with self._lock:
            return self._reviews.get(review_id)

    def list_reviews(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        programme_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementReviewRecord]:
        with self._lock:
            results = [
                r
                for r in self._reviews.values()
                if r.organization_id == organization_id
                and (facility_id is None or r.facility_id == facility_id or r.facility_id is None)
                and (programme_id is None or r.programme_id == programme_id)
                and (status is None or r.status.value == status)
            ]
            results.sort(key=lambda x: x.planned_date, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Participants
    # -------------------------------------------------------------------------

    def save_participant(self, record: ReviewParticipantRecord) -> ReviewParticipantRecord:
        with self._lock:
            self._participants[record.participant_id] = record
            return record

    def get_participant(self, participant_id: str) -> Optional[ReviewParticipantRecord]:
        with self._lock:
            return self._participants.get(participant_id)

    def list_participants(self, review_id: str) -> List[ReviewParticipantRecord]:
        with self._lock:
            return [p for p in self._participants.values() if p.review_id == review_id]

    def find_participant_by_user(
        self, review_id: str, user_id: str
    ) -> Optional[ReviewParticipantRecord]:
        with self._lock:
            for p in self._participants.values():
                if p.review_id == review_id and p.user_id == user_id:
                    return p
            return None

    # -------------------------------------------------------------------------
    # Agenda Items
    # -------------------------------------------------------------------------

    def save_agenda_item(self, record: ReviewAgendaItemRecord) -> ReviewAgendaItemRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._agenda_items[record.agenda_item_id] = record
            return record

    def get_agenda_item(self, agenda_item_id: str) -> Optional[ReviewAgendaItemRecord]:
        with self._lock:
            return self._agenda_items.get(agenda_item_id)

    def list_agenda_items(self, review_id: str) -> List[ReviewAgendaItemRecord]:
        with self._lock:
            items = [a for a in self._agenda_items.values() if a.review_id == review_id]
            items.sort(key=lambda x: x.order)
            return items

    def delete_agenda_item(self, agenda_item_id: str) -> bool:
        with self._lock:
            if agenda_item_id in self._agenda_items:
                del self._agenda_items[agenda_item_id]
                return True
            return False

    # -------------------------------------------------------------------------
    # Consolidated Inputs
    # -------------------------------------------------------------------------

    def save_consolidated_input(self, record: ConsolidatedInputRecord) -> ConsolidatedInputRecord:
        with self._lock:
            self._inputs[record.input_id] = record
            return record

    def get_consolidated_input(self, input_id: str) -> Optional[ConsolidatedInputRecord]:
        with self._lock:
            return self._inputs.get(input_id)

    def list_consolidated_inputs(
        self, review_id: str, source_phase: Optional[str] = None
    ) -> List[ConsolidatedInputRecord]:
        with self._lock:
            return [
                inp
                for inp in self._inputs.values()
                if inp.review_id == review_id
                and (source_phase is None or inp.source_phase == source_phase)
            ]

    # -------------------------------------------------------------------------
    # Review Packages
    # -------------------------------------------------------------------------

    def save_package(self, record: ReviewPackageRecord) -> ReviewPackageRecord:
        with self._lock:
            self._packages[record.package_id] = record
            return record

    def get_package(self, package_id: str) -> Optional[ReviewPackageRecord]:
        with self._lock:
            return self._packages.get(package_id)

    def list_packages(self, review_id: str) -> List[ReviewPackageRecord]:
        with self._lock:
            packages = [p for p in self._packages.values() if p.review_id == review_id]
            packages.sort(key=lambda x: x.version, reverse=True)
            return packages

    def get_latest_package(self, review_id: str) -> Optional[ReviewPackageRecord]:
        with self._lock:
            packages = self.list_packages(review_id)
            return packages[0] if packages else None

    # -------------------------------------------------------------------------
    # Discussions
    # -------------------------------------------------------------------------

    def save_discussion(self, record: DiscussionRecord) -> DiscussionRecord:
        with self._lock:
            self._discussions[record.discussion_id] = record
            return record

    def get_discussion(self, discussion_id: str) -> Optional[DiscussionRecord]:
        with self._lock:
            return self._discussions.get(discussion_id)

    def list_discussions(
        self, review_id: str, agenda_item_id: Optional[str] = None
    ) -> List[DiscussionRecord]:
        with self._lock:
            discussions = [
                d
                for d in self._discussions.values()
                if d.review_id == review_id
                and (agenda_item_id is None or d.agenda_item_id == agenda_item_id)
            ]
            discussions.sort(key=lambda x: x.recorded_at)
            return discussions

    # -------------------------------------------------------------------------
    # Decisions
    # -------------------------------------------------------------------------

    def save_decision(self, record: ManagementDecisionRecord) -> ManagementDecisionRecord:
        with self._lock:
            self._decisions[record.decision_id] = record
            return record

    def get_decision(self, decision_id: str) -> Optional[ManagementDecisionRecord]:
        with self._lock:
            return self._decisions.get(decision_id)

    def list_decisions(
        self,
        review_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementDecisionRecord]:
        with self._lock:
            results = [
                d
                for d in self._decisions.values()
                if (review_id is None or d.review_id == review_id)
                and (organization_id is None or d.organization_id == organization_id)
                and (status is None or d.status.value == status)
                and (category is None or d.category.value == category)
            ]
            results.sort(key=lambda x: x.decided_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Commitments
    # -------------------------------------------------------------------------

    def save_commitment(self, record: ManagementCommitmentRecord) -> ManagementCommitmentRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._commitments[record.commitment_id] = record
            return record

    def get_commitment(self, commitment_id: str) -> Optional[ManagementCommitmentRecord]:
        with self._lock:
            return self._commitments.get(commitment_id)

    def list_commitments(
        self,
        review_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        status: Optional[str] = None,
        is_overdue: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementCommitmentRecord]:
        with self._lock:
            now = datetime.now(timezone.utc)
            results = []
            for c in self._commitments.values():
                if review_id and c.review_id != review_id:
                    continue
                if decision_id and c.decision_id != decision_id:
                    continue
                if owner_id and c.responsible_owner_id != owner_id:
                    continue
                if status and c.status.value != status:
                    continue
                if is_overdue is not None:
                    c_overdue = (
                        c.due_date < now
                        and c.status not in [CommitmentStatus.VERIFIED, CommitmentStatus.CLOSED, CommitmentStatus.CANCELLED]
                    )
                    if c_overdue != is_overdue:
                        continue
                results.append(c)

            results.sort(key=lambda x: x.due_date)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Escalations
    # -------------------------------------------------------------------------

    def save_escalation(self, record: CommitmentEscalationRecord) -> CommitmentEscalationRecord:
        with self._lock:
            self._escalations[record.escalation_id] = record
            return record

    def get_escalation(self, escalation_id: str) -> Optional[CommitmentEscalationRecord]:
        with self._lock:
            return self._escalations.get(escalation_id)

    def list_escalations(
        self, commitment_id: Optional[str] = None, review_id: Optional[str] = None
    ) -> List[CommitmentEscalationRecord]:
        with self._lock:
            results = [
                e
                for e in self._escalations.values()
                if (commitment_id is None or e.commitment_id == commitment_id)
                and (review_id is None or e.review_id == review_id)
            ]
            results.sort(key=lambda x: x.escalated_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def save_report(self, record: ManagementReviewReportRecord) -> ManagementReviewReportRecord:
        with self._lock:
            self._reports[record.report_id] = record
            return record

    def get_report(self, report_id: str) -> Optional[ManagementReviewReportRecord]:
        with self._lock:
            return self._reports.get(report_id)

    def get_report_by_review(self, review_id: str) -> Optional[ManagementReviewReportRecord]:
        with self._lock:
            for r in self._reports.values():
                if r.review_id == review_id:
                    return r
            return None

    def list_reports(
        self, programme_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ManagementReviewReportRecord]:
        with self._lock:
            results = [
                r
                for r in self._reports.values()
                if (programme_id is None or r.programme_id == programme_id)
                and (status is None or r.status.value == status)
            ]
            results.sort(key=lambda x: x.prepared_at, reverse=True)
            return results


# Global singleton instance
_repository_instance: Optional[GovernanceManagementReviewRepository] = None
_repo_lock = threading.Lock()


def get_governance_management_review_repository() -> GovernanceManagementReviewRepository:
    """Provides singleton instance of the GovernanceManagementReviewRepository."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_lock:
            if _repository_instance is None:
                _repository_instance = GovernanceManagementReviewRepository()
    return _repository_instance

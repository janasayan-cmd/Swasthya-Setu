"""Phase 66: Safety Post-Closure Verification Repository.

Thread-safe repository for Phase 66 post-closure verification executions,
integrity findings, monitoring statuses, reassessments, and reopening coordinations.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_integrity_finding import (
    FindingCategory,
    FindingLifecycleState,
    IntegrityFindingRecord,
)
from app.schemas.safety_post_closure_monitoring import (
    PostClosureMonitoringStatus,
    ReassessmentRecord,
    ReopeningCoordinationRecord,
)
from app.schemas.safety_post_closure_verification import (
    PostClosureVerificationRecord,
    VerificationLifecycleState,
)


class SafetyPostClosureVerificationRepository:
    """Thread-safe in-memory repository for Phase 66 post-closure verifications."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._verifications: Dict[str, PostClosureVerificationRecord] = {}
        self._findings: Dict[str, IntegrityFindingRecord] = {}
        self._monitoring: Dict[str, PostClosureMonitoringStatus] = {}
        self._reassessments: Dict[str, ReassessmentRecord] = {}
        self._reopen_coordinations: Dict[str, ReopeningCoordinationRecord] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    # -------------------------------------------------------------------------
    # Verification Runs
    # -------------------------------------------------------------------------

    def save_verification(
        self, record: PostClosureVerificationRecord
    ) -> PostClosureVerificationRecord:
        """Persist or update a verification run record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._verifications[record.verification_id] = record
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.verification_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get_verification(self, verification_id: str) -> Optional[PostClosureVerificationRecord]:
        """Retrieve a verification run by ID."""
        with self._lock:
            return self._verifications.get(verification_id)

    def list_verifications(
        self,
        completion_id: str,
        organization_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PostClosureVerificationRecord]:
        """List verification runs for a completion workflow with pagination."""
        with self._lock:
            results = [
                v for v in self._verifications.values()
                if v.completion_id == completion_id
                and (organization_id is None or v.organization_id == organization_id)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending_verifications(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PostClosureVerificationRecord]:
        """List verification runs currently scheduled, pending, or running."""
        pending_states = {
            VerificationLifecycleState.SCHEDULED,
            VerificationLifecycleState.PENDING,
            VerificationLifecycleState.RUNNING,
            VerificationLifecycleState.REOPEN_AUTHORIZATION_PENDING,
        }
        with self._lock:
            results = [
                v for v in self._verifications.values()
                if v.organization_id == organization_id
                and (facility_id is None or v.facility_id == facility_id)
                and v.state in pending_states
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_failed_verifications(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PostClosureVerificationRecord]:
        """List verification runs that failed or encountered dependency unavailability."""
        failed_states = {
            VerificationLifecycleState.VERIFICATION_FAILED,
            VerificationLifecycleState.DEPENDENCY_UNAVAILABLE,
            VerificationLifecycleState.EVIDENCE_INVALID,
            VerificationLifecycleState.CONFLICTED,
        }
        with self._lock:
            results = [
                v for v in self._verifications.values()
                if v.organization_id == organization_id
                and (facility_id is None or v.facility_id == facility_id)
                and v.state in failed_states
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Integrity Findings
    # -------------------------------------------------------------------------

    def save_finding(self, record: IntegrityFindingRecord) -> IntegrityFindingRecord:
        """Persist or update an integrity finding."""
        with self._lock:
            self._findings[record.finding_id] = record
            return record

    def get_finding(self, finding_id: str) -> Optional[IntegrityFindingRecord]:
        """Retrieve an integrity finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def list_findings(
        self,
        completion_id: str,
        verification_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        lifecycle_state: Optional[FindingLifecycleState] = None,
        category: Optional[FindingCategory] = None,
        is_material: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntegrityFindingRecord]:
        """List findings for a completion workflow with optional filters."""
        with self._lock:
            results = [
                f for f in self._findings.values()
                if f.completion_id == completion_id
                and (verification_id is None or f.verification_id == verification_id)
                and (organization_id is None or f.organization_id == organization_id)
                and (lifecycle_state is None or f.lifecycle_state == lifecycle_state)
                and (category is None or f.category == category)
                and (is_material is None or f.is_material == is_material)
            ]
            results.sort(key=lambda x: x.detected_at, reverse=True)
            return results[offset : offset + limit]

    def list_review_required_findings(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntegrityFindingRecord]:
        """List findings currently awaiting review or action."""
        review_states = {
            FindingLifecycleState.DETECTED,
            FindingLifecycleState.UNDER_REVIEW,
            FindingLifecycleState.REASSESSMENT_REQUESTED,
            FindingLifecycleState.REOPEN_REQUESTED,
        }
        with self._lock:
            results = [
                f for f in self._findings.values()
                if f.organization_id == organization_id
                and (facility_id is None or f.facility_id == facility_id)
                and f.lifecycle_state in review_states
            ]
            results.sort(key=lambda x: x.detected_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Post-Closure Monitoring Status
    # -------------------------------------------------------------------------

    def save_monitoring_status(
        self, record: PostClosureMonitoringStatus
    ) -> PostClosureMonitoringStatus:
        """Persist or update monitoring status."""
        with self._lock:
            self._monitoring[record.completion_id] = record
            return record

    def get_monitoring_status(self, completion_id: str) -> Optional[PostClosureMonitoringStatus]:
        """Retrieve monitoring status by completion ID."""
        with self._lock:
            return self._monitoring.get(completion_id)

    # -------------------------------------------------------------------------
    # Reassessment & Reopening Coordinations
    # -------------------------------------------------------------------------

    def save_reassessment(self, record: ReassessmentRecord) -> ReassessmentRecord:
        """Persist a reassessment requirement."""
        with self._lock:
            self._reassessments[record.reassessment_id] = record
            return record

    def get_reassessment(self, reassessment_id: str) -> Optional[ReassessmentRecord]:
        """Retrieve a reassessment record by ID."""
        with self._lock:
            return self._reassessments.get(reassessment_id)

    def list_reassessments(self, completion_id: str) -> List[ReassessmentRecord]:
        """List reassessment records for a completion workflow."""
        with self._lock:
            results = [
                r for r in self._reassessments.values()
                if r.completion_id == completion_id
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    def save_reopening_coordination(
        self, record: ReopeningCoordinationRecord
    ) -> ReopeningCoordinationRecord:
        """Persist or update reopening coordination."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._reopen_coordinations[record.coordination_id] = record
            return record

    def get_reopening_coordination(
        self, coordination_id: str
    ) -> Optional[ReopeningCoordinationRecord]:
        """Retrieve reopening coordination by ID."""
        with self._lock:
            return self._reopen_coordinations.get(coordination_id)

    def list_reopening_coordinations(
        self, completion_id: str
    ) -> List[ReopeningCoordinationRecord]:
        """List reopening coordinations for a completion workflow."""
        with self._lock:
            results = [
                r for r in self._reopen_coordinations.values()
                if r.completion_id == completion_id
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Idempotency & Reset
    # -------------------------------------------------------------------------

    def get_by_idempotency_key(
        self, idempotency_key: str, organization_id: Optional[str] = None
    ) -> Optional[PostClosureVerificationRecord]:
        """Check if a verification run was already performed with this idempotency key."""
        with self._lock:
            entry = self._idempotency_store.get(idempotency_key)
            if not entry:
                return None
            verif_id, org_id, _ = entry
            if organization_id and org_id != organization_id:
                return None
            return self._verifications.get(verif_id)

    def clear(self) -> None:
        """Clear all records (used for test isolation)."""
        with self._lock:
            self._verifications.clear()
            self._findings.clear()
            self._monitoring.clear()
            self._reassessments.clear()
            self._reopen_coordinations.clear()
            self._idempotency_store.clear()


# Module-level singleton
_REPO_INSTANCE: Optional[SafetyPostClosureVerificationRepository] = None
_LOCK = threading.Lock()


def get_safety_post_closure_verification_repository() -> SafetyPostClosureVerificationRepository:
    """Retrieve or create singleton repository instance."""
    global _REPO_INSTANCE
    if _REPO_INSTANCE is None:
        with _LOCK:
            if _REPO_INSTANCE is None:
                _REPO_INSTANCE = SafetyPostClosureVerificationRepository()
    return _REPO_INSTANCE

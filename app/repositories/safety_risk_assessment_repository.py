"""Phase 62: Safety Risk Assessment Repository.

Thread-safe repository for consolidated safety risk assessments,
cross-domain correlation links, evidence reconciliations, and governed routing history.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    RiskPriority,
    SafetyRiskAssessmentRecord,
)


class SafetyRiskAssessmentRepository:
    """Thread-safe in-memory repository for Phase 62 safety risk assessments."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._assessments: Dict[str, SafetyRiskAssessmentRecord] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyRiskAssessmentRecord) -> SafetyRiskAssessmentRecord:
        """Persist or update an assessment record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._assessments[record.assessment_id] = record
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.assessment_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get(self, assessment_id: str) -> Optional[SafetyRiskAssessmentRecord]:
        """Retrieve assessment record by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def list_assessments(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[AssessmentLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskAssessmentRecord]:
        """Query assessment records with tenant/facility filtering."""
        with self._lock:
            results = list(self._assessments.values())

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
    ) -> List[SafetyRiskAssessmentRecord]:
        """List assessments requiring human review."""
        with self._lock:
            results = [
                r
                for r in self._assessments.values()
                if r.requires_human_review
                or r.lifecycle_state == AssessmentLifecycleState.REVIEW_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_high_priority(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyRiskAssessmentRecord]:
        """List assessments with high, urgent, or critical routing priority."""
        with self._lock:
            high_priorities = {
                RiskPriority.HIGH_PRIORITY_REVIEW,
                RiskPriority.URGENT_GOVERNANCE_REVIEW,
                RiskPriority.CRITICAL_ESCALATION,
            }
            results = [
                r
                for r in self._assessments.values()
                if (r.characterization and r.characterization.priority in high_priorities)
                or r.requires_escalation
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_escalation_required(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyRiskAssessmentRecord]:
        """List assessments requiring governed escalation."""
        with self._lock:
            results = [
                r
                for r in self._assessments.values()
                if r.requires_escalation
                or r.lifecycle_state == AssessmentLifecycleState.ESCALATION_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_reassessment_required(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyRiskAssessmentRecord]:
        """List assessments requiring Phase 60 signal reassessment."""
        with self._lock:
            results = [
                r
                for r in self._assessments.values()
                if r.requires_reassessment
                or r.lifecycle_state == AssessmentLifecycleState.REASSESSMENT_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_conflicted(
        self, organization_id: Optional[str] = None
    ) -> List[SafetyRiskAssessmentRecord]:
        """List assessments with unresolved evidence conflicts."""
        with self._lock:
            results = [
                r
                for r in self._assessments.values()
                if r.has_unresolved_conflicts
                or r.lifecycle_state == AssessmentLifecycleState.CONFLICTED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def check_idempotency(
        self, idempotency_key: str, organization_id: str
    ) -> Optional[SafetyRiskAssessmentRecord]:
        """Check if an assessment has already been created for this idempotency key."""
        with self._lock:
            entry = self._idempotency_store.get(idempotency_key)
            if entry:
                anl_id, entry_org, _ = entry
                if entry_org == organization_id:
                    return self._assessments.get(anl_id)
            return None

    def store_idempotency(
        self, idempotency_key: str, organization_id: str, assessment_id: str
    ) -> None:
        """Store idempotency key association."""
        with self._lock:
            self._idempotency_store[idempotency_key] = (
                assessment_id,
                organization_id,
                datetime.now(timezone.utc),
            )

    def clear(self) -> None:
        """Clear all records (primarily for testing)."""
        with self._lock:
            self._assessments.clear()
            self._idempotency_store.clear()


_assessment_repo_instance: Optional[SafetyRiskAssessmentRepository] = None
_repo_lock = threading.Lock()


def get_safety_risk_assessment_repository() -> SafetyRiskAssessmentRepository:
    """Retrieve singleton repository instance."""
    global _assessment_repo_instance
    if _assessment_repo_instance is None:
        with _repo_lock:
            if _assessment_repo_instance is None:
                _assessment_repo_instance = SafetyRiskAssessmentRepository()
    return _assessment_repo_instance

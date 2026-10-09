"""Phase 63: Safety Risk Review Repository.

Thread-safe repository for Phase 63 safety risk reviews, review packages,
evidence references, questions, dispositions, and audit histories.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_risk_review import ReviewLifecycleState, SafetyRiskReviewRecord


class SafetyRiskReviewRepository:
    """Thread-safe in-memory repository for Phase 63 safety risk reviews."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reviews: Dict[str, SafetyRiskReviewRecord] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyRiskReviewRecord) -> SafetyRiskReviewRecord:
        """Persist or update a review record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._reviews[record.review_id] = record
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.review_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get(self, review_id: str) -> Optional[SafetyRiskReviewRecord]:
        """Retrieve review record by ID."""
        with self._lock:
            return self._reviews.get(review_id)

    def get_by_assessment_id(self, assessment_id: str) -> Optional[SafetyRiskReviewRecord]:
        """Retrieve review record associated with a given Phase 62 assessment ID."""
        with self._lock:
            for review in self._reviews.values():
                if review.assessment_id == assessment_id:
                    return review
            return None

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
        organization_id: Optional[str] = None,
    ) -> Optional[SafetyRiskReviewRecord]:
        """Retrieve existing review by idempotency key."""
        with self._lock:
            entry = self._idempotency_store.get(idempotency_key)
            if not entry:
                return None
            rev_id, org_id, _ = entry
            if organization_id and org_id != organization_id:
                return None
            return self._reviews.get(rev_id)

    def list_reviews(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        state: Optional[ReviewLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """Query review records with tenant/facility and state filtering."""
        with self._lock:
            results = list(self._reviews.values())
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            if state:
                results = [r for r in results if r.state == state]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews currently pending action or review."""
        pending_states = {
            ReviewLifecycleState.CREATED,
            ReviewLifecycleState.VALIDATING,
            ReviewLifecycleState.READINESS_CHECK,
            ReviewLifecycleState.REVIEW_PENDING,
            ReviewLifecycleState.REVIEW_IN_PROGRESS,
            ReviewLifecycleState.DECISION_PENDING,
        }
        with self._lock:
            results = [
                r for r in self._reviews.values()
                if r.state in pending_states
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_review_required(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews specifically requiring human review."""
        target_states = {
            ReviewLifecycleState.READY,
            ReviewLifecycleState.REVIEW_PENDING,
            ReviewLifecycleState.REVIEW_IN_PROGRESS,
            ReviewLifecycleState.DECISION_PENDING,
        }
        with self._lock:
            results = [
                r for r in self._reviews.values()
                if r.state in target_states
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_evidence_required(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews that require additional evidence."""
        with self._lock:
            results = [
                r for r in self._reviews.values()
                if r.state == ReviewLifecycleState.EVIDENCE_REQUESTED
                or any(q.status.value in ("OPEN", "EVIDENCE_REQUESTED") for q in r.questions)
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_escalation_required(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews requiring escalation."""
        with self._lock:
            results = [
                r for r in self._reviews.values()
                if r.requires_escalation
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_reassessment_required(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskReviewRecord]:
        """List reviews requiring reassessment."""
        with self._lock:
            results = [
                r for r in self._reviews.values()
                if r.state == ReviewLifecycleState.REASSESSMENT_REQUIRED or r.requires_reassessment
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def clear(self) -> None:
        """Clear all records (used for test isolation)."""
        with self._lock:
            self._reviews.clear()
            self._idempotency_store.clear()


# Global singleton instance
_repository_instance: Optional[SafetyRiskReviewRepository] = None


def get_safety_risk_review_repository() -> SafetyRiskReviewRepository:
    """Dependency provider for singleton review repository."""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = SafetyRiskReviewRepository()
    return _repository_instance

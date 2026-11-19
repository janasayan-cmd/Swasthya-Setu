"""Phase 68: Governance Decision Assurance Repository.

Thread-safe repository for decision register records, assurance execution runs,
integrity findings, correction requests, and consistency evaluations.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.decision_assurance import (
    AssuranceLifecycleState,
    DecisionAssuranceRecord,
    GovernanceDecisionRegisterRecord,
)
from app.schemas.decision_assurance_finding import (
    AssuranceFindingRecord,
)
from app.schemas.decision_correction_coordination import (
    CorrectionRequestRecord,
    CrossWorkflowConsistencyCheckResult,
)


class GovernanceDecisionAssuranceRepository:
    """Thread-safe in-memory repository for Phase 68 decision assurance entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._decisions: Dict[str, GovernanceDecisionRegisterRecord] = {}
        self._assurance_runs: Dict[str, DecisionAssuranceRecord] = {}
        self._decision_assurance_map: Dict[str, List[str]] = {}  # decision_id -> list of assurance_id
        self._findings: Dict[str, AssuranceFindingRecord] = {}
        self._corrections: Dict[str, CorrectionRequestRecord] = {}
        self._consistency_checks: Dict[str, List[CrossWorkflowConsistencyCheckResult]] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    # -------------------------------------------------------------------------
    # Decision Register
    # -------------------------------------------------------------------------

    def save_decision_register(
        self, record: GovernanceDecisionRegisterRecord
    ) -> GovernanceDecisionRegisterRecord:
        """Save or update a registered decision reference."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._decisions[record.decision_id] = record
            return record

    def get_decision_register(self, decision_id: str) -> Optional[GovernanceDecisionRegisterRecord]:
        """Retrieve a registered decision by ID."""
        with self._lock:
            return self._decisions.get(decision_id)

    def list_decisions(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        source_phase: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceDecisionRegisterRecord]:
        """List registered decisions with optional filters and pagination."""
        with self._lock:
            results = [
                d for d in self._decisions.values()
                if d.organization_id == organization_id
                and (facility_id is None or d.facility_id == facility_id)
                and (source_phase is None or d.source_phase.value == source_phase)
            ]
            results.sort(key=lambda x: x.decided_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Decision Assurance Runs
    # -------------------------------------------------------------------------

    def save_assurance_run(self, record: DecisionAssuranceRecord) -> DecisionAssuranceRecord:
        """Save a decision assurance execution record."""
        with self._lock:
            self._assurance_runs[record.assurance_id] = record
            if record.decision_id not in self._decision_assurance_map:
                self._decision_assurance_map[record.decision_id] = []
            if record.assurance_id not in self._decision_assurance_map[record.decision_id]:
                self._decision_assurance_map[record.decision_id].append(record.assurance_id)

            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.assurance_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get_assurance_run(self, assurance_id: str) -> Optional[DecisionAssuranceRecord]:
        """Retrieve a specific assurance execution run."""
        with self._lock:
            return self._assurance_runs.get(assurance_id)

    def get_latest_assurance_for_decision(
        self, decision_id: str
    ) -> Optional[DecisionAssuranceRecord]:
        """Retrieve the most recent assurance run for a registered decision."""
        with self._lock:
            a_ids = self._decision_assurance_map.get(decision_id, [])
            if not a_ids:
                return None
            runs = [self._assurance_runs[aid] for aid in a_ids if aid in self._assurance_runs]
            runs.sort(key=lambda x: x.evaluated_at, reverse=True)
            return runs[0] if runs else None

    def list_assurance_history(self, decision_id: str) -> List[DecisionAssuranceRecord]:
        """List all historical assurance runs for a decision."""
        with self._lock:
            a_ids = self._decision_assurance_map.get(decision_id, [])
            runs = [self._assurance_runs[aid] for aid in a_ids if aid in self._assurance_runs]
            runs.sort(key=lambda x: x.evaluated_at, reverse=True)
            return runs

    # -------------------------------------------------------------------------
    # Integrity Findings
    # -------------------------------------------------------------------------

    def save_finding(self, record: AssuranceFindingRecord) -> AssuranceFindingRecord:
        """Save or update an assurance integrity finding."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._findings[record.finding_id] = record
            return record

    def get_finding(self, finding_id: str) -> Optional[AssuranceFindingRecord]:
        """Retrieve a finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def list_findings_for_decision(self, decision_id: str) -> List[AssuranceFindingRecord]:
        """List findings linked to a specific decision."""
        with self._lock:
            results = [f for f in self._findings.values() if f.decision_id == decision_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    def list_findings(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AssuranceFindingRecord]:
        """List findings across decisions with optional category and severity filters."""
        with self._lock:
            results = [
                f for f in self._findings.values()
                if (category is None or f.category.value == category)
                and (severity is None or f.severity.value == severity)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Correction Requests
    # -------------------------------------------------------------------------

    def save_correction_request(
        self, record: CorrectionRequestRecord
    ) -> CorrectionRequestRecord:
        """Save or update a correction or revocation review request."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._corrections[record.request_id] = record
            return record

    def get_correction_request(self, request_id: str) -> Optional[CorrectionRequestRecord]:
        """Retrieve a correction request by ID."""
        with self._lock:
            return self._corrections.get(request_id)

    def list_corrections_for_decision(self, decision_id: str) -> List[CorrectionRequestRecord]:
        """List correction requests recorded for a decision."""
        with self._lock:
            results = [c for c in self._corrections.values() if c.decision_id == decision_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Consistency Checks
    # -------------------------------------------------------------------------

    def save_consistency_check(
        self, record: CrossWorkflowConsistencyCheckResult
    ) -> CrossWorkflowConsistencyCheckResult:
        """Save a cross-workflow consistency check outcome."""
        with self._lock:
            if record.decision_id not in self._consistency_checks:
                self._consistency_checks[record.decision_id] = []
            self._consistency_checks[record.decision_id].append(record)
            return record

    def list_consistency_checks_for_decision(
        self, decision_id: str
    ) -> List[CrossWorkflowConsistencyCheckResult]:
        """List consistency evaluations performed for a decision."""
        with self._lock:
            return list(self._consistency_checks.get(decision_id, []))

    # -------------------------------------------------------------------------
    # Queues
    # -------------------------------------------------------------------------

    def list_review_required(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[DecisionAssuranceRecord]:
        """List latest assurance runs in REVIEW_REQUIRED or OWNER_REVIEW_PENDING."""
        with self._lock:
            results: List[DecisionAssuranceRecord] = []
            for d_id, a_ids in self._decision_assurance_map.items():
                latest = self.get_latest_assurance_for_decision(d_id)
                if (
                    latest
                    and latest.organization_id == organization_id
                    and (facility_id is None or latest.facility_id == facility_id)
                    and latest.lifecycle_state in {
                        AssuranceLifecycleState.REVIEW_REQUIRED,
                        AssuranceLifecycleState.OWNER_REVIEW_PENDING,
                        AssuranceLifecycleState.CORRECTION_REQUESTED,
                    }
                ):
                    results.append(latest)
            results.sort(key=lambda x: x.evaluated_at, reverse=True)
            return results

    def list_authorization_unverifiable(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[DecisionAssuranceRecord]:
        """List latest assurance runs with unverified or invalid historical authorization."""
        with self._lock:
            results: List[DecisionAssuranceRecord] = []
            for d_id, a_ids in self._decision_assurance_map.items():
                latest = self.get_latest_assurance_for_decision(d_id)
                if (
                    latest
                    and latest.organization_id == organization_id
                    and (facility_id is None or latest.facility_id == facility_id)
                    and latest.lifecycle_state in {
                        AssuranceLifecycleState.AUTHORIZATION_UNVERIFIABLE,
                        AssuranceLifecycleState.AUTHORIZATION_INVALID,
                    }
                ):
                    results.append(latest)
            results.sort(key=lambda x: x.evaluated_at, reverse=True)
            return results

    def list_policy_mismatch(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[DecisionAssuranceRecord]:
        """List latest assurance runs exhibiting policy version mismatches."""
        with self._lock:
            results: List[DecisionAssuranceRecord] = []
            for d_id, a_ids in self._decision_assurance_map.items():
                latest = self.get_latest_assurance_for_decision(d_id)
                if (
                    latest
                    and latest.organization_id == organization_id
                    and (facility_id is None or latest.facility_id == facility_id)
                    and latest.lifecycle_state in {
                        AssuranceLifecycleState.POLICY_MISMATCH,
                        AssuranceLifecycleState.SOURCE_VERSION_MISMATCH,
                    }
                ):
                    results.append(latest)
            results.sort(key=lambda x: x.evaluated_at, reverse=True)
            return results

    def list_decision_conflicts(
        self, organization_id: str, facility_id: Optional[str] = None
    ) -> List[DecisionAssuranceRecord]:
        """List latest assurance runs exhibiting cross-workflow decision conflicts."""
        with self._lock:
            results: List[DecisionAssuranceRecord] = []
            for d_id, a_ids in self._decision_assurance_map.items():
                latest = self.get_latest_assurance_for_decision(d_id)
                if (
                    latest
                    and latest.organization_id == organization_id
                    and (facility_id is None or latest.facility_id == facility_id)
                    and latest.lifecycle_state == AssuranceLifecycleState.DECISION_CONFLICT
                ):
                    results.append(latest)
            results.sort(key=lambda x: x.evaluated_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Idempotency
    # -------------------------------------------------------------------------

    def get_idempotent_id(self, key: str) -> Optional[str]:
        """Retrieve previously saved assurance ID for an idempotency key."""
        with self._lock:
            entry = self._idempotency_store.get(key)
            return entry[0] if entry else None

    # -------------------------------------------------------------------------
    # Cleanup for Tests
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Reset repository state between tests."""
        with self._lock:
            self._decisions.clear()
            self._assurance_runs.clear()
            self._decision_assurance_map.clear()
            self._findings.clear()
            self._corrections.clear()
            self._consistency_checks.clear()
            self._idempotency_store.clear()


# Global singleton instance
_global_decision_assurance_repo = GovernanceDecisionAssuranceRepository()


def get_governance_decision_assurance_repository() -> GovernanceDecisionAssuranceRepository:
    """Dependency provider returning singleton repository instance."""
    return _global_decision_assurance_repo

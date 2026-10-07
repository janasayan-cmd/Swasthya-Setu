"""Phase 52: Safety Assurance Repository.

Thread-safe in-memory repository for Phase 52 assurance evaluations,
evidence references, degradation records, regression records, and
bypass records.

DB Boundary: This repository follows the database team contract.
It does NOT create competing tables or migrations. Persistence layer
is owned by the DB teammate. This implementation provides the service
abstraction layer used by application services.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.schemas.safety_assurance import (
    AssuranceEvaluationRecord,
    AssuranceLifecycleState,
    BypassRecord,
    ControlAssuranceSummary,
    ControlEffectivenessState,
    DegradationRecord,
    DegradationState,
    RegressionRecord,
)


class SafetyAssuranceRepository:
    """Thread-safe repository for Phase 52 control assurance evaluation records.

    All methods follow the DB team's contract boundary.
    No SQL schema creation, competing tables, or duplicate persistence logic.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Core evaluation storage
        self._evaluations: Dict[str, AssuranceEvaluationRecord] = {}
        self._control_evaluations: Dict[str, List[str]] = {}  # control_id -> [eval_ids]
        self._org_evaluations: Dict[str, List[str]] = {}       # org_id -> [eval_ids]

        # Idempotency
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> evaluation_id

        # Degradation records
        self._degradations: Dict[str, DegradationRecord] = {}
        self._control_degradations: Dict[str, List[str]] = {}

        # Regression records
        self._regressions: Dict[str, RegressionRecord] = {}
        self._control_regressions: Dict[str, List[str]] = {}

        # Bypass records
        self._bypasses: Dict[str, BypassRecord] = {}
        self._control_bypasses: Dict[str, List[str]] = {}

    # -------------------------------------------------------------------------
    # Evaluation CRUD
    # -------------------------------------------------------------------------

    def save_evaluation(self, record: AssuranceEvaluationRecord) -> AssuranceEvaluationRecord:
        """Persist or update an assurance evaluation record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._evaluations[record.evaluation_id] = record

            # Index by control
            ctrl_list = self._control_evaluations.setdefault(record.control_id, [])
            if record.evaluation_id not in ctrl_list:
                ctrl_list.append(record.evaluation_id)

            # Index by org
            if record.organization_id:
                org_list = self._org_evaluations.setdefault(record.organization_id, [])
                if record.evaluation_id not in org_list:
                    org_list.append(record.evaluation_id)

            # Register idempotency key
            if record.idempotency_key:
                self._idempotency_map[record.idempotency_key] = record.evaluation_id

            return record

    def get_evaluation(self, evaluation_id: str) -> Optional[AssuranceEvaluationRecord]:
        """Retrieve assurance evaluation by ID."""
        with self._lock:
            return self._evaluations.get(evaluation_id)

    def get_by_idempotency_key(self, key: str) -> Optional[AssuranceEvaluationRecord]:
        """Resolve existing evaluation via idempotency key."""
        with self._lock:
            eid = self._idempotency_map.get(key)
            if eid:
                return self._evaluations.get(eid)
            return None

    def list_evaluations_for_control(
        self,
        control_id: str,
        lifecycle_state: Optional[AssuranceLifecycleState] = None,
        effectiveness_state: Optional[ControlEffectivenessState] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AssuranceEvaluationRecord]:
        """List evaluations for a given control, with optional filters."""
        with self._lock:
            ids = self._control_evaluations.get(control_id, [])
            results: List[AssuranceEvaluationRecord] = []
            for eid in ids:
                rec = self._evaluations.get(eid)
                if rec is None:
                    continue
                if lifecycle_state and rec.lifecycle_state != lifecycle_state:
                    continue
                if effectiveness_state and rec.effectiveness_state != effectiveness_state:
                    continue
                if organization_id and rec.organization_id != organization_id:
                    continue
                if facility_id and rec.facility_id != facility_id:
                    continue
                results.append(rec)
            # Sort newest first
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_evaluations(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[AssuranceLifecycleState] = None,
        effectiveness_state: Optional[ControlEffectivenessState] = None,
        bypass_detected: Optional[bool] = None,
        regression_detected: Optional[bool] = None,
        review_required: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AssuranceEvaluationRecord]:
        """List all evaluations with optional filters."""
        with self._lock:
            results: List[AssuranceEvaluationRecord] = []
            for rec in self._evaluations.values():
                if organization_id and rec.organization_id != organization_id:
                    continue
                if facility_id and rec.facility_id != facility_id:
                    continue
                if lifecycle_state and rec.lifecycle_state != lifecycle_state:
                    continue
                if effectiveness_state and rec.effectiveness_state != effectiveness_state:
                    continue
                if bypass_detected is not None and rec.bypass_detected != bypass_detected:
                    continue
                if regression_detected is not None and rec.regression_detected != regression_detected:
                    continue
                if review_required is not None and rec.review_required != review_required:
                    continue
                results.append(rec)
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]

    def get_latest_accepted_evaluation(
        self,
        control_id: str,
        control_version: str,
        organization_id: Optional[str] = None,
    ) -> Optional[AssuranceEvaluationRecord]:
        """Get the most recently accepted evaluation for a control version."""
        with self._lock:
            ids = self._control_evaluations.get(control_id, [])
            candidates: List[AssuranceEvaluationRecord] = []
            for eid in ids:
                rec = self._evaluations.get(eid)
                if rec is None:
                    continue
                if rec.control_version != control_version:
                    continue
                if rec.lifecycle_state != AssuranceLifecycleState.ASSURANCE_ACCEPTED:
                    continue
                if organization_id and rec.organization_id != organization_id:
                    continue
                candidates.append(rec)
            if not candidates:
                return None
            return max(candidates, key=lambda r: r.completed_at or r.created_at)

    # -------------------------------------------------------------------------
    # Degradation Records
    # -------------------------------------------------------------------------

    def save_degradation(self, record: DegradationRecord) -> DegradationRecord:
        """Persist a degradation detection record."""
        with self._lock:
            self._degradations[record.degradation_id] = record
            ctrl_list = self._control_degradations.setdefault(record.control_id, [])
            if record.degradation_id not in ctrl_list:
                ctrl_list.append(record.degradation_id)
            return record

    def list_degradations(
        self,
        control_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        state: Optional[DegradationState] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DegradationRecord]:
        """List degradation records with optional filters."""
        with self._lock:
            if control_id:
                ids = self._control_degradations.get(control_id, [])
                results = [self._degradations[i] for i in ids if i in self._degradations]
            else:
                results = list(self._degradations.values())

            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            if state:
                results = [r for r in results if r.degradation_state == state]
            results.sort(key=lambda r: r.detected_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Regression Records
    # -------------------------------------------------------------------------

    def save_regression(self, record: RegressionRecord) -> RegressionRecord:
        """Persist a regression detection record."""
        with self._lock:
            self._regressions[record.regression_id] = record
            ctrl_list = self._control_regressions.setdefault(record.control_id, [])
            if record.regression_id not in ctrl_list:
                ctrl_list.append(record.regression_id)
            return record

    def list_regressions(
        self,
        control_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RegressionRecord]:
        """List regression records with optional filters."""
        with self._lock:
            if control_id:
                ids = self._control_regressions.get(control_id, [])
                results = [self._regressions[i] for i in ids if i in self._regressions]
            else:
                results = list(self._regressions.values())

            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            results.sort(key=lambda r: r.detected_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Bypass Records
    # -------------------------------------------------------------------------

    def save_bypass(self, record: BypassRecord) -> BypassRecord:
        """Persist a bypass detection record."""
        with self._lock:
            self._bypasses[record.bypass_id] = record
            ctrl_list = self._control_bypasses.setdefault(record.control_id, [])
            if record.bypass_id not in ctrl_list:
                ctrl_list.append(record.bypass_id)
            return record

    def list_bypasses(
        self,
        control_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BypassRecord]:
        """List bypass detection records with optional filters."""
        with self._lock:
            if control_id:
                ids = self._control_bypasses.get(control_id, [])
                results = [self._bypasses[i] for i in ids if i in self._bypasses]
            else:
                results = list(self._bypasses.values())

            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.facility_id == facility_id]
            results.sort(key=lambda r: r.detected_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Dashboard Aggregation
    # -------------------------------------------------------------------------

    def aggregate_dashboard(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return non-PHI aggregate counts for assurance dashboard."""
        with self._lock:
            evals = list(self._evaluations.values())
            if organization_id:
                evals = [e for e in evals if e.organization_id == organization_id]
            if facility_id:
                evals = [e for e in evals if e.facility_id == facility_id]

            # Latest per control
            latest: Dict[str, AssuranceEvaluationRecord] = {}
            for e in sorted(evals, key=lambda x: x.created_at):
                latest[e.control_id] = e

            controls = list(latest.values())
            return {
                "controls_total": len(controls),
                "controls_effective": sum(
                    1 for c in controls
                    if c.effectiveness_state == ControlEffectivenessState.EFFECTIVE_OBSERVED
                ),
                "controls_partially_effective": sum(
                    1 for c in controls
                    if c.effectiveness_state == ControlEffectivenessState.PARTIALLY_EFFECTIVE
                ),
                "controls_degraded": sum(
                    1 for c in controls
                    if c.effectiveness_state == ControlEffectivenessState.DEGRADED
                ),
                "controls_failed": sum(
                    1 for c in controls
                    if c.effectiveness_state == ControlEffectivenessState.FAILED
                ),
                "controls_insufficient_evidence": sum(
                    1 for c in controls
                    if c.effectiveness_state == ControlEffectivenessState.INSUFFICIENT_EVIDENCE
                ),
                "controls_pending_review": sum(1 for c in controls if c.review_required),
                "evidence_gaps_detected": sum(1 for c in controls if c.evidence_quality.value in ("MISSING", "PARTIAL", "INSUFFICIENT")),
                "regressions_detected": sum(1 for c in controls if c.regression_detected),
                "bypasses_detected": sum(1 for c in controls if c.bypass_detected),
            }

    # -------------------------------------------------------------------------
    # Test / Reset
    # -------------------------------------------------------------------------

    def reset(self) -> None:
        """Reset repository state for test isolation."""
        with self._lock:
            self._evaluations.clear()
            self._control_evaluations.clear()
            self._org_evaluations.clear()
            self._idempotency_map.clear()
            self._degradations.clear()
            self._control_degradations.clear()
            self._regressions.clear()
            self._control_regressions.clear()
            self._bypasses.clear()
            self._control_bypasses.clear()


# Global singleton — consumed by services
safety_assurance_repository = SafetyAssuranceRepository()

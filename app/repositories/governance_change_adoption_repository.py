"""Phase 74: Governance Change Adoption & Operational Sustainability Repository.

Provides a thread-safe repository layer for:
- Change adoption registration records
- Version-controlled operational baselines
- Adoption monitoring plans
- Operational adoption evidence items
- Adoption indicators
- Implementation drift signals
- Sustainability assessments
- Operational exceptions
- Operational consequences and routing
- Adoption escalations
- Historical monitoring timeline events
- Background monitoring job results
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.schemas.governance_change_adoption_registration import (
    AdoptionRegistrationStatus,
    GovernanceChangeAdoptionRecord,
)
from app.schemas.operational_adoption_baseline import (
    BaselineApprovalStatus,
    OperationalAdoptionBaselineRecord,
)
from app.schemas.adoption_monitoring_plan import (
    AdoptionMonitoringPlanRecord,
    MonitoringPlanStatus,
)
from app.schemas.adoption_evidence_indicators import (
    AdoptionEvidenceRecord,
    AdoptionIndicatorRecord,
    EvidenceVerificationStatus,
    IndicatorOutcome,
)
from app.schemas.drift_sustainability_consequences import (
    AdoptionEscalationRecord,
    AdoptionExceptionRecord,
    AdoptionExceptionStatus,
    ConsequenceStatus,
    DriftSignalClassification,
    DriftSignalStatus,
    ImplementationDriftSignalRecord,
    OperationalConsequenceRecord,
    SustainabilityAssessmentRecord,
    SustainabilityAssessmentStatus,
)
from app.schemas.adoption_reporting import (
    BackgroundJobRunResult,
    TimelineEvent,
)


class GovernanceChangeAdoptionRepository:
    """Thread-safe in-memory repository for Phase 74 domain records."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._registrations: Dict[str, GovernanceChangeAdoptionRecord] = {}
        self._baselines: Dict[str, OperationalAdoptionBaselineRecord] = {}
        self._monitoring_plans: Dict[str, AdoptionMonitoringPlanRecord] = {}
        self._evidence: Dict[str, AdoptionEvidenceRecord] = {}
        self._indicators: Dict[str, AdoptionIndicatorRecord] = {}
        self._drift_signals: Dict[str, ImplementationDriftSignalRecord] = {}
        self._sustainability_assessments: Dict[str, SustainabilityAssessmentRecord] = {}
        self._exceptions: Dict[str, AdoptionExceptionRecord] = {}
        self._consequences: Dict[str, OperationalConsequenceRecord] = {}
        self._escalations: Dict[str, AdoptionEscalationRecord] = {}
        self._timeline_events: Dict[str, List[TimelineEvent]] = {}
        self._job_runs: List[BackgroundJobRunResult] = []

    def clear(self) -> None:
        """Clears all stored records (used primarily for test isolation)."""
        with self._lock:
            self._registrations.clear()
            self._baselines.clear()
            self._monitoring_plans.clear()
            self._evidence.clear()
            self._indicators.clear()
            self._drift_signals.clear()
            self._sustainability_assessments.clear()
            self._exceptions.clear()
            self._consequences.clear()
            self._escalations.clear()
            self._timeline_events.clear()
            self._job_runs.clear()

    # -------------------------------------------------------------------------
    # Timeline Events
    # -------------------------------------------------------------------------
    def log_timeline_event(
        self,
        registration_id: str,
        event_type: str,
        actor_id: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        with self._lock:
            event = TimelineEvent(
                event_id=f"evt_{len(self._timeline_events.get(registration_id, [])) + 1}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                actor_id=actor_id,
                summary=summary,
                details=details or {},
            )
            if registration_id not in self._timeline_events:
                self._timeline_events[registration_id] = []
            self._timeline_events[registration_id].append(event)
            return event

    def get_timeline_events(self, registration_id: str) -> List[TimelineEvent]:
        with self._lock:
            return list(self._timeline_events.get(registration_id, []))

    # -------------------------------------------------------------------------
    # Adoption Registrations
    # -------------------------------------------------------------------------
    def save_registration(self, record: GovernanceChangeAdoptionRecord) -> GovernanceChangeAdoptionRecord:
        with self._lock:
            self._registrations[record.registration_id] = record
            return record

    def get_registration(self, registration_id: str) -> Optional[GovernanceChangeAdoptionRecord]:
        with self._lock:
            return self._registrations.get(registration_id)

    def list_registrations(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[AdoptionRegistrationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceChangeAdoptionRecord]:
        with self._lock:
            results = list(self._registrations.values())
            if tenant_id:
                results = [r for r in results if r.tenant_id == tenant_id]
            if status:
                results = [r for r in results if r.status == status]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Operational Baselines
    # -------------------------------------------------------------------------
    def save_baseline(self, record: OperationalAdoptionBaselineRecord) -> OperationalAdoptionBaselineRecord:
        with self._lock:
            self._baselines[record.baseline_id] = record
            return record

    def get_baseline(self, baseline_id: str) -> Optional[OperationalAdoptionBaselineRecord]:
        with self._lock:
            return self._baselines.get(baseline_id)

    def list_baselines_for_registration(
        self, registration_id: str, tenant_id: Optional[str] = None
    ) -> List[OperationalAdoptionBaselineRecord]:
        with self._lock:
            results = [
                b for b in self._baselines.values()
                if b.registration_id == registration_id and (tenant_id is None or b.tenant_id == tenant_id)
            ]
            results.sort(key=lambda b: b.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Monitoring Plans
    # -------------------------------------------------------------------------
    def save_monitoring_plan(self, record: AdoptionMonitoringPlanRecord) -> AdoptionMonitoringPlanRecord:
        with self._lock:
            self._monitoring_plans[record.plan_id] = record
            return record

    def get_monitoring_plan(self, plan_id: str) -> Optional[AdoptionMonitoringPlanRecord]:
        with self._lock:
            return self._monitoring_plans.get(plan_id)

    def list_monitoring_plans_for_registration(
        self, registration_id: str, tenant_id: Optional[str] = None
    ) -> List[AdoptionMonitoringPlanRecord]:
        with self._lock:
            results = [
                p for p in self._monitoring_plans.values()
                if p.registration_id == registration_id and (tenant_id is None or p.tenant_id == tenant_id)
            ]
            results.sort(key=lambda p: p.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Adoption Evidence
    # -------------------------------------------------------------------------
    def save_evidence(self, record: AdoptionEvidenceRecord) -> AdoptionEvidenceRecord:
        with self._lock:
            self._evidence[record.evidence_id] = record
            return record

    def get_evidence(self, evidence_id: str) -> Optional[AdoptionEvidenceRecord]:
        with self._lock:
            return self._evidence.get(evidence_id)

    def list_evidence_for_registration(
        self,
        registration_id: str,
        tenant_id: Optional[str] = None,
        status: Optional[EvidenceVerificationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AdoptionEvidenceRecord]:
        with self._lock:
            results = [
                e for e in self._evidence.values()
                if e.registration_id == registration_id and (tenant_id is None or e.tenant_id == tenant_id)
            ]
            if status:
                results = [e for e in results if e.verification_status == status]
            results.sort(key=lambda e: e.submitted_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Adoption Indicators
    # -------------------------------------------------------------------------
    def save_indicator(self, record: AdoptionIndicatorRecord) -> AdoptionIndicatorRecord:
        with self._lock:
            self._indicators[record.indicator_id] = record
            return record

    def get_indicator(self, indicator_id: str) -> Optional[AdoptionIndicatorRecord]:
        with self._lock:
            return self._indicators.get(indicator_id)

    def list_indicators_for_registration(
        self, registration_id: str, tenant_id: Optional[str] = None
    ) -> List[AdoptionIndicatorRecord]:
        with self._lock:
            results = [
                i for i in self._indicators.values()
                if i.registration_id == registration_id and (tenant_id is None or i.tenant_id == tenant_id)
            ]
            results.sort(key=lambda i: i.created_at, reverse=False)
            return results

    # -------------------------------------------------------------------------
    # Implementation Drift Signals
    # -------------------------------------------------------------------------
    def save_drift_signal(self, record: ImplementationDriftSignalRecord) -> ImplementationDriftSignalRecord:
        with self._lock:
            self._drift_signals[record.signal_id] = record
            return record

    def get_drift_signal(self, signal_id: str) -> Optional[ImplementationDriftSignalRecord]:
        with self._lock:
            return self._drift_signals.get(signal_id)

    def list_drift_signals_for_registration(
        self,
        registration_id: str,
        tenant_id: Optional[str] = None,
        status: Optional[DriftSignalStatus] = None,
    ) -> List[ImplementationDriftSignalRecord]:
        with self._lock:
            results = [
                s for s in self._drift_signals.values()
                if s.registration_id == registration_id and (tenant_id is None or s.tenant_id == tenant_id)
            ]
            if status:
                results = [s for s in results if s.status == status]
            results.sort(key=lambda s: s.observed_at, reverse=True)
            return results

    def list_all_drift_signals(self, tenant_id: Optional[str] = None) -> List[ImplementationDriftSignalRecord]:
        with self._lock:
            results = list(self._drift_signals.values())
            if tenant_id:
                results = [s for s in results if s.tenant_id == tenant_id]
            results.sort(key=lambda s: s.observed_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Sustainability Assessments
    # -------------------------------------------------------------------------
    def save_sustainability_assessment(
        self, record: SustainabilityAssessmentRecord
    ) -> SustainabilityAssessmentRecord:
        with self._lock:
            self._sustainability_assessments[record.assessment_id] = record
            return record

    def get_sustainability_assessment(self, assessment_id: str) -> Optional[SustainabilityAssessmentRecord]:
        with self._lock:
            return self._sustainability_assessments.get(assessment_id)

    def list_sustainability_assessments_for_registration(
        self, registration_id: str, tenant_id: Optional[str] = None
    ) -> List[SustainabilityAssessmentRecord]:
        with self._lock:
            results = [
                a for a in self._sustainability_assessments.values()
                if a.registration_id == registration_id and (tenant_id is None or a.tenant_id == tenant_id)
            ]
            results.sort(key=lambda a: a.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Adoption Exceptions
    # -------------------------------------------------------------------------
    def save_exception(self, record: AdoptionExceptionRecord) -> AdoptionExceptionRecord:
        with self._lock:
            self._exceptions[record.exception_id] = record
            return record

    def get_exception(self, exception_id: str) -> Optional[AdoptionExceptionRecord]:
        with self._lock:
            return self._exceptions.get(exception_id)

    def list_exceptions_for_registration(
        self, registration_id: str, tenant_id: Optional[str] = None
    ) -> List[AdoptionExceptionRecord]:
        with self._lock:
            results = [
                e for e in self._exceptions.values()
                if e.registration_id == registration_id and (tenant_id is None or e.tenant_id == tenant_id)
            ]
            results.sort(key=lambda e: e.created_at, reverse=True)
            return results

    def list_all_exceptions(self, tenant_id: Optional[str] = None) -> List[AdoptionExceptionRecord]:
        with self._lock:
            results = list(self._exceptions.values())
            if tenant_id:
                results = [e for e in results if e.tenant_id == tenant_id]
            return results

    # -------------------------------------------------------------------------
    # Operational Consequences
    # -------------------------------------------------------------------------
    def save_consequence(self, record: OperationalConsequenceRecord) -> OperationalConsequenceRecord:
        with self._lock:
            self._consequences[record.consequence_id] = record
            return record

    def get_consequence(self, consequence_id: str) -> Optional[OperationalConsequenceRecord]:
        with self._lock:
            return self._consequences.get(consequence_id)

    def list_consequences_for_registration(
        self, registration_id: str, tenant_id: Optional[str] = None
    ) -> List[OperationalConsequenceRecord]:
        with self._lock:
            results = [
                c for c in self._consequences.values()
                if c.registration_id == registration_id and (tenant_id is None or c.tenant_id == tenant_id)
            ]
            results.sort(key=lambda c: c.reported_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Adoption Escalations
    # -------------------------------------------------------------------------
    def save_escalation(self, record: AdoptionEscalationRecord) -> AdoptionEscalationRecord:
        with self._lock:
            self._escalations[record.escalation_id] = record
            return record

    def get_escalation(self, escalation_id: str) -> Optional[AdoptionEscalationRecord]:
        with self._lock:
            return self._escalations.get(escalation_id)

    def list_escalations_for_registration(
        self, registration_id: str, tenant_id: Optional[str] = None
    ) -> List[AdoptionEscalationRecord]:
        with self._lock:
            results = [
                e for e in self._escalations.values()
                if e.registration_id == registration_id and (tenant_id is None or e.tenant_id == tenant_id)
            ]
            results.sort(key=lambda e: e.escalated_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Background Job Results
    # -------------------------------------------------------------------------
    def record_job_run(self, result: BackgroundJobRunResult) -> BackgroundJobRunResult:
        with self._lock:
            self._job_runs.append(result)
            return result

    def list_job_runs(self) -> List[BackgroundJobRunResult]:
        with self._lock:
            return list(self._job_runs)


_repo_instance: Optional[GovernanceChangeAdoptionRepository] = None
_repo_lock = threading.Lock()


def get_governance_change_adoption_repository() -> GovernanceChangeAdoptionRepository:
    """Provides singleton instance of GovernanceChangeAdoptionRepository."""
    global _repo_instance
    if _repo_instance is None:
        with _repo_lock:
            if _repo_instance is None:
                _repo_instance = GovernanceChangeAdoptionRepository()
    return _repo_instance

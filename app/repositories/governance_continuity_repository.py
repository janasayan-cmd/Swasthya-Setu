"""Phase 80: Clinical Safety Governance Strategic Resilience and Continuity In-Memory Repository.

Provides thread-safe persistence and query capabilities for:
- Critical governance capabilities inventory
- Governance continuity requirements (RTO, RPO, MTPD, MBCO)
- Governance dependency mapping and SPOFs
- Version-controlled continuity plans
- Disruption classification and tracking
- Continuity activation coordination
- Alternative operating arrangements
- Temporary governance decisions and reconciliation records
- Governance recovery monitoring and verification
- Continuity exercises and evaluations
- Resilience gap findings
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_continuity_capability import (
    CapabilityCriticalityTier,
    CapabilityInventoryStatus,
    ClinicalSafetyGovernanceCapabilityRecord,
)
from app.schemas.governance_continuity_requirement import (
    ContinuityRequirementStatus,
    GovernanceContinuityRequirementRecord,
)
from app.schemas.governance_continuity_dependency import (
    ContinuityDependencyType,
    DependencyStatus,
    GovernanceContinuityDependencyRecord,
)
from app.schemas.governance_continuity_plan import (
    ContinuityPlanStatus,
    GovernanceContinuityPlanRecord,
)
from app.schemas.governance_continuity_disruption import (
    DisruptionCategory,
    DisruptionStatus,
    GovernanceDisruptionRecord,
)
from app.schemas.governance_continuity_activation import (
    ContinuityActivationStatus,
    GovernanceContinuityActivationRecord,
)
from app.schemas.governance_continuity_arrangements import (
    AlternativeOperatingArrangementRecord,
    ArrangementVerificationStatus,
)
from app.schemas.governance_continuity_reconciliation import (
    ReconciliationStatus,
    TemporaryGovernanceDecisionRecord,
)
from app.schemas.governance_continuity_recovery import (
    GovernanceRecoveryRecord,
    RecoveryStatus,
)
from app.schemas.governance_continuity_exercises import (
    ContinuityExerciseRecord,
    ContinuityExerciseStatus,
    ContinuityExerciseType,
)
from app.schemas.governance_continuity_gaps import (
    ContinuityGapCategory,
    ContinuityGapRecord,
    ContinuityGapSeverity,
    ContinuityGapStatus,
)


class GovernanceContinuityRepository:
    """Thread-safe in-memory repository for Phase 80 governance continuity data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._capabilities: Dict[str, ClinicalSafetyGovernanceCapabilityRecord] = {}
        self._requirements: Dict[str, GovernanceContinuityRequirementRecord] = {}
        self._dependencies: Dict[str, GovernanceContinuityDependencyRecord] = {}
        self._plans: Dict[str, GovernanceContinuityPlanRecord] = {}
        self._disruptions: Dict[str, GovernanceDisruptionRecord] = {}
        self._activations: Dict[str, GovernanceContinuityActivationRecord] = {}
        self._arrangements: Dict[str, AlternativeOperatingArrangementRecord] = {}
        self._temporary_decisions: Dict[str, TemporaryGovernanceDecisionRecord] = {}
        self._recovery_records: Dict[str, GovernanceRecoveryRecord] = {}
        self._exercises: Dict[str, ContinuityExerciseRecord] = {}
        self._gaps: Dict[str, ContinuityGapRecord] = {}

    def clear(self) -> None:
        """Clears all stored records (useful for test isolation)."""
        with self._lock:
            self._capabilities.clear()
            self._requirements.clear()
            self._dependencies.clear()
            self._plans.clear()
            self._disruptions.clear()
            self._activations.clear()
            self._arrangements.clear()
            self._temporary_decisions.clear()
            self._recovery_records.clear()
            self._exercises.clear()
            self._gaps.clear()

    # -------------------------------------------------------------------------
    # 1. Capabilities
    # -------------------------------------------------------------------------

    def save_capability(
        self, record: ClinicalSafetyGovernanceCapabilityRecord
    ) -> ClinicalSafetyGovernanceCapabilityRecord:
        with self._lock:
            self._capabilities[record.capability_id] = record
            return record

    def get_capability(
        self, capability_id: str
    ) -> Optional[ClinicalSafetyGovernanceCapabilityRecord]:
        with self._lock:
            return self._capabilities.get(capability_id)

    def list_capabilities(
        self,
        tenant_id: str,
        criticality: Optional[CapabilityCriticalityTier] = None,
        status: Optional[CapabilityInventoryStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ClinicalSafetyGovernanceCapabilityRecord]:
        with self._lock:
            results = [
                c
                for c in self._capabilities.values()
                if c.tenant_id == tenant_id
                and (criticality is None or c.criticality == criticality)
                and (status is None or c.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 2. Continuity Requirements
    # -------------------------------------------------------------------------

    def save_requirement(
        self, record: GovernanceContinuityRequirementRecord
    ) -> GovernanceContinuityRequirementRecord:
        with self._lock:
            self._requirements[record.requirement_id] = record
            return record

    def get_requirement(
        self, requirement_id: str
    ) -> Optional[GovernanceContinuityRequirementRecord]:
        with self._lock:
            return self._requirements.get(requirement_id)

    def get_requirement_by_capability(
        self, tenant_id: str, capability_id: str
    ) -> Optional[GovernanceContinuityRequirementRecord]:
        with self._lock:
            for req in self._requirements.values():
                if req.tenant_id == tenant_id and req.capability_id == capability_id:
                    return req
            return None

    def list_requirements(
        self,
        tenant_id: str,
        status: Optional[ContinuityRequirementStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityRequirementRecord]:
        with self._lock:
            results = [
                r
                for r in self._requirements.values()
                if r.tenant_id == tenant_id
                and (status is None or r.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 3. Dependencies
    # -------------------------------------------------------------------------

    def save_dependency(
        self, record: GovernanceContinuityDependencyRecord
    ) -> GovernanceContinuityDependencyRecord:
        with self._lock:
            self._dependencies[record.dependency_id] = record
            return record

    def get_dependency(
        self, dependency_id: str
    ) -> Optional[GovernanceContinuityDependencyRecord]:
        with self._lock:
            return self._dependencies.get(dependency_id)

    def list_dependencies(
        self,
        tenant_id: str,
        capability_id: Optional[str] = None,
        dependency_type: Optional[ContinuityDependencyType] = None,
        status: Optional[DependencyStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityDependencyRecord]:
        with self._lock:
            results = [
                d
                for d in self._dependencies.values()
                if d.tenant_id == tenant_id
                and (capability_id is None or d.source_capability_id == capability_id)
                and (dependency_type is None or d.dependency_type == dependency_type)
                and (status is None or d.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    def list_all_dependencies(
        self, tenant_id: str
    ) -> List[GovernanceContinuityDependencyRecord]:
        with self._lock:
            return [
                d for d in self._dependencies.values() if d.tenant_id == tenant_id
            ]

    # -------------------------------------------------------------------------
    # 4. Continuity Plans
    # -------------------------------------------------------------------------

    def save_plan(
        self, record: GovernanceContinuityPlanRecord
    ) -> GovernanceContinuityPlanRecord:
        with self._lock:
            self._plans[record.plan_id] = record
            return record

    def get_plan(
        self, plan_id: str
    ) -> Optional[GovernanceContinuityPlanRecord]:
        with self._lock:
            return self._plans.get(plan_id)

    def list_plans(
        self,
        tenant_id: str,
        status: Optional[ContinuityPlanStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityPlanRecord]:
        with self._lock:
            results = [
                p
                for p in self._plans.values()
                if p.tenant_id == tenant_id
                and (status is None or p.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 5. Disruptions
    # -------------------------------------------------------------------------

    def save_disruption(
        self, record: GovernanceDisruptionRecord
    ) -> GovernanceDisruptionRecord:
        with self._lock:
            self._disruptions[record.disruption_id] = record
            return record

    def get_disruption(
        self, disruption_id: str
    ) -> Optional[GovernanceDisruptionRecord]:
        with self._lock:
            return self._disruptions.get(disruption_id)

    def list_disruptions(
        self,
        tenant_id: str,
        category: Optional[DisruptionCategory] = None,
        status: Optional[DisruptionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceDisruptionRecord]:
        with self._lock:
            results = [
                d
                for d in self._disruptions.values()
                if d.tenant_id == tenant_id
                and (category is None or d.category == category)
                and (status is None or d.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 6. Activations
    # -------------------------------------------------------------------------

    def save_activation(
        self, record: GovernanceContinuityActivationRecord
    ) -> GovernanceContinuityActivationRecord:
        with self._lock:
            self._activations[record.activation_id] = record
            return record

    def get_activation(
        self, activation_id: str
    ) -> Optional[GovernanceContinuityActivationRecord]:
        with self._lock:
            return self._activations.get(activation_id)

    def list_activations(
        self,
        tenant_id: str,
        disruption_id: Optional[str] = None,
        status: Optional[ContinuityActivationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityActivationRecord]:
        with self._lock:
            results = [
                a
                for a in self._activations.values()
                if a.tenant_id == tenant_id
                and (disruption_id is None or a.triggering_disruption_id == disruption_id)
                and (status is None or a.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 7. Alternative Arrangements
    # -------------------------------------------------------------------------

    def save_arrangement(
        self, record: AlternativeOperatingArrangementRecord
    ) -> AlternativeOperatingArrangementRecord:
        with self._lock:
            self._arrangements[record.arrangement_id] = record
            return record

    def get_arrangement(
        self, arrangement_id: str
    ) -> Optional[AlternativeOperatingArrangementRecord]:
        with self._lock:
            return self._arrangements.get(arrangement_id)

    def list_arrangements(
        self,
        tenant_id: str,
        activation_id: Optional[str] = None,
        verification_status: Optional[ArrangementVerificationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AlternativeOperatingArrangementRecord]:
        with self._lock:
            results = [
                arr
                for arr in self._arrangements.values()
                if arr.tenant_id == tenant_id
                and (activation_id is None or arr.activation_id == activation_id)
                and (verification_status is None or arr.verification_status == verification_status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 8. Temporary Decisions & Reconciliation
    # -------------------------------------------------------------------------

    def save_temporary_decision(
        self, record: TemporaryGovernanceDecisionRecord
    ) -> TemporaryGovernanceDecisionRecord:
        with self._lock:
            self._temporary_decisions[record.temporary_decision_id] = record
            return record

    def get_temporary_decision(
        self, temporary_decision_id: str
    ) -> Optional[TemporaryGovernanceDecisionRecord]:
        with self._lock:
            return self._temporary_decisions.get(temporary_decision_id)

    def list_temporary_decisions(
        self,
        tenant_id: str,
        activation_id: Optional[str] = None,
        reconciliation_status: Optional[ReconciliationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[TemporaryGovernanceDecisionRecord]:
        with self._lock:
            results = [
                d
                for d in self._temporary_decisions.values()
                if d.tenant_id == tenant_id
                and (activation_id is None or d.activation_id == activation_id)
                and (reconciliation_status is None or d.reconciliation_status == reconciliation_status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 9. Recovery Coordination
    # -------------------------------------------------------------------------

    def save_recovery_record(
        self, record: GovernanceRecoveryRecord
    ) -> GovernanceRecoveryRecord:
        with self._lock:
            self._recovery_records[record.recovery_id] = record
            return record

    def get_recovery_record(
        self, recovery_id: str
    ) -> Optional[GovernanceRecoveryRecord]:
        with self._lock:
            return self._recovery_records.get(recovery_id)

    # Aliases for flexible integration
    save_recovery = save_recovery_record
    get_recovery = get_recovery_record

    def list_recovery_records(
        self,
        tenant_id: str,
        disruption_id: Optional[str] = None,
        recovery_status: Optional[RecoveryStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceRecoveryRecord]:
        with self._lock:
            results = [
                rec
                for rec in self._recovery_records.values()
                if rec.tenant_id == tenant_id
                and (disruption_id is None or rec.disruption_id == disruption_id)
                and (recovery_status is None or rec.recovery_status == recovery_status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 10. Continuity Exercises
    # -------------------------------------------------------------------------

    def save_exercise(
        self, record: ContinuityExerciseRecord
    ) -> ContinuityExerciseRecord:
        with self._lock:
            self._exercises[record.exercise_id] = record
            return record

    def get_exercise(
        self, exercise_id: str
    ) -> Optional[ContinuityExerciseRecord]:
        with self._lock:
            return self._exercises.get(exercise_id)

    def list_exercises(
        self,
        tenant_id: str,
        exercise_type: Optional[ContinuityExerciseType] = None,
        status: Optional[ContinuityExerciseStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ContinuityExerciseRecord]:
        with self._lock:
            results = [
                ex
                for ex in self._exercises.values()
                if ex.tenant_id == tenant_id
                and (exercise_type is None or ex.exercise_type == exercise_type)
                and (status is None or ex.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 11. Continuity Gaps
    # -------------------------------------------------------------------------

    def save_gap(
        self, record: ContinuityGapRecord
    ) -> ContinuityGapRecord:
        with self._lock:
            self._gaps[record.gap_id] = record
            return record

    def get_gap(
        self, gap_id: str
    ) -> Optional[ContinuityGapRecord]:
        with self._lock:
            return self._gaps.get(gap_id)

    def list_gaps(
        self,
        tenant_id: str,
        category: Optional[ContinuityGapCategory] = None,
        severity: Optional[ContinuityGapSeverity] = None,
        status: Optional[ContinuityGapStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ContinuityGapRecord]:
        with self._lock:
            results = [
                g
                for g in self._gaps.values()
                if g.tenant_id == tenant_id
                and (category is None or g.category == category)
                and (severity is None or g.severity == severity)
                and (status is None or g.status == status)
            ]
            results.sort(key=lambda x: x.detected_at, reverse=True)
            return results[skip : skip + limit]


_governance_continuity_repo = GovernanceContinuityRepository()
governance_continuity_repository = _governance_continuity_repo


def get_governance_continuity_repository() -> GovernanceContinuityRepository:
    """Returns the singleton instance of the Governance Continuity repository."""
    return _governance_continuity_repo


"""Phase 81: Clinical Safety Governance Continuity Assurance Repository.

Provides thread-safe in-memory persistence and query capabilities for:
- Continuity assurance frameworks and dimensions
- Continuity plan validation records
- Coverage assessment records
- Exercise assurance evaluations
- Scenario assessment records
- Personnel readiness records
- Dependency resilience records
- Recovery performance assessments
- Reconciliation integrity assessments
- Independent validation programmes
- Continuity assurance findings
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_continuity_assurance_framework import (
    ContinuityAssuranceFrameworkRecord,
    FrameworkStatus,
)
from app.schemas.governance_continuity_assurance_plan import (
    ContinuityPlanValidationRecord,
    PlanValidationReviewStatus,
)
from app.schemas.governance_continuity_assurance_coverage import (
    ContinuityCoverageAssessmentRecord,
)
from app.schemas.governance_continuity_assurance_exercise import (
    ContinuityExerciseAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_scenario import (
    ContinuityScenarioAssessmentRecord,
)
from app.schemas.governance_continuity_assurance_personnel import (
    PersonnelReadinessAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_dependency import (
    DependencyResilienceAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_recovery import (
    RecoveryPerformanceAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_reconciliation import (
    ReconciliationAssuranceRecord,
)
from app.schemas.governance_continuity_assurance_programme import (
    IndependentValidationProgrammeRecord,
    ProgrammeStatus,
)
from app.schemas.governance_continuity_assurance_finding import (
    ContinuityAssuranceFindingRecord,
    FindingStatus,
)


class GovernanceContinuityAssuranceRepository:
    """Thread-safe in-memory repository for Phase 81 continuity assurance data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._frameworks: Dict[str, ContinuityAssuranceFrameworkRecord] = {}
        self._plan_validations: Dict[str, ContinuityPlanValidationRecord] = {}
        self._coverage_assessments: Dict[str, ContinuityCoverageAssessmentRecord] = {}
        self._exercise_evaluations: Dict[str, ContinuityExerciseAssuranceRecord] = {}
        self._scenario_assessments: Dict[str, ContinuityScenarioAssessmentRecord] = {}
        self._personnel_readiness: Dict[str, PersonnelReadinessAssuranceRecord] = {}
        self._dependency_assessments: Dict[str, DependencyResilienceAssuranceRecord] = {}
        self._recovery_assessments: Dict[str, RecoveryPerformanceAssuranceRecord] = {}
        self._reconciliation_assessments: Dict[str, ReconciliationAssuranceRecord] = {}
        self._validation_programmes: Dict[str, IndependentValidationProgrammeRecord] = {}
        self._findings: Dict[str, ContinuityAssuranceFindingRecord] = {}

    def clear(self) -> None:
        """Clears all stored records (for test isolation)."""
        with self._lock:
            self._frameworks.clear()
            self._plan_validations.clear()
            self._coverage_assessments.clear()
            self._exercise_evaluations.clear()
            self._scenario_assessments.clear()
            self._personnel_readiness.clear()
            self._dependency_assessments.clear()
            self._recovery_assessments.clear()
            self._reconciliation_assessments.clear()
            self._validation_programmes.clear()
            self._findings.clear()

    # --- Frameworks ---
    def save_framework(self, record: ContinuityAssuranceFrameworkRecord) -> ContinuityAssuranceFrameworkRecord:
        with self._lock:
            self._frameworks[record.framework_id] = record
            return record

    def get_framework(self, framework_id: str, tenant_id: str = "default") -> Optional[ContinuityAssuranceFrameworkRecord]:
        with self._lock:
            rec = self._frameworks.get(framework_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_frameworks(self, tenant_id: str = "default", status: Optional[FrameworkStatus] = None) -> List[ContinuityAssuranceFrameworkRecord]:
        with self._lock:
            return [
                r for r in self._frameworks.values()
                if r.tenant_id == tenant_id and (status is None or r.status == status)
            ]

    # --- Plan Validations ---
    def save_plan_validation(self, record: ContinuityPlanValidationRecord) -> ContinuityPlanValidationRecord:
        with self._lock:
            self._plan_validations[record.validation_id] = record
            return record

    def get_plan_validation(self, validation_id: str, tenant_id: str = "default") -> Optional[ContinuityPlanValidationRecord]:
        with self._lock:
            rec = self._plan_validations.get(validation_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_plan_validations(self, tenant_id: str = "default", plan_id: Optional[str] = None) -> List[ContinuityPlanValidationRecord]:
        with self._lock:
            return [
                r for r in self._plan_validations.values()
                if r.tenant_id == tenant_id and (plan_id is None or r.plan_id == plan_id)
            ]

    # --- Coverage Assessments ---
    def save_coverage_assessment(self, record: ContinuityCoverageAssessmentRecord) -> ContinuityCoverageAssessmentRecord:
        with self._lock:
            self._coverage_assessments[record.assessment_id] = record
            return record

    def get_coverage_assessment(self, assessment_id: str, tenant_id: str = "default") -> Optional[ContinuityCoverageAssessmentRecord]:
        with self._lock:
            rec = self._coverage_assessments.get(assessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_coverage_assessments(self, tenant_id: str = "default") -> List[ContinuityCoverageAssessmentRecord]:
        with self._lock:
            return [r for r in self._coverage_assessments.values() if r.tenant_id == tenant_id]

    # --- Exercise Evaluations ---
    def save_exercise_evaluation(self, record: ContinuityExerciseAssuranceRecord) -> ContinuityExerciseAssuranceRecord:
        with self._lock:
            self._exercise_evaluations[record.evaluation_id] = record
            return record

    def get_exercise_evaluation(self, evaluation_id: str, tenant_id: str = "default") -> Optional[ContinuityExerciseAssuranceRecord]:
        with self._lock:
            rec = self._exercise_evaluations.get(evaluation_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_exercise_evaluations(self, tenant_id: str = "default", exercise_id: Optional[str] = None) -> List[ContinuityExerciseAssuranceRecord]:
        with self._lock:
            return [
                r for r in self._exercise_evaluations.values()
                if r.tenant_id == tenant_id and (exercise_id is None or r.exercise_id == exercise_id)
            ]

    # --- Scenario Assessments ---
    def save_scenario_assessment(self, record: ContinuityScenarioAssessmentRecord) -> ContinuityScenarioAssessmentRecord:
        with self._lock:
            self._scenario_assessments[record.scenario_id] = record
            return record

    def get_scenario_assessment(self, scenario_id: str, tenant_id: str = "default") -> Optional[ContinuityScenarioAssessmentRecord]:
        with self._lock:
            rec = self._scenario_assessments.get(scenario_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_scenario_assessments(self, tenant_id: str = "default") -> List[ContinuityScenarioAssessmentRecord]:
        with self._lock:
            return [r for r in self._scenario_assessments.values() if r.tenant_id == tenant_id]

    # --- Personnel Readiness ---
    def save_personnel_readiness(self, record: PersonnelReadinessAssuranceRecord) -> PersonnelReadinessAssuranceRecord:
        with self._lock:
            self._personnel_readiness[record.readiness_id] = record
            return record

    def get_personnel_readiness(self, readiness_id: str, tenant_id: str = "default") -> Optional[PersonnelReadinessAssuranceRecord]:
        with self._lock:
            rec = self._personnel_readiness.get(readiness_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_personnel_readiness(self, tenant_id: str = "default", role_key: Optional[str] = None) -> List[PersonnelReadinessAssuranceRecord]:
        with self._lock:
            return [
                r for r in self._personnel_readiness.values()
                if r.tenant_id == tenant_id and (role_key is None or r.role_key == role_key)
            ]

    # --- Dependency Resilience ---
    def save_dependency_assessment(self, record: DependencyResilienceAssuranceRecord) -> DependencyResilienceAssuranceRecord:
        with self._lock:
            self._dependency_assessments[record.assessment_id] = record
            return record

    def get_dependency_assessment(self, assessment_id: str, tenant_id: str = "default") -> Optional[DependencyResilienceAssuranceRecord]:
        with self._lock:
            rec = self._dependency_assessments.get(assessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_dependency_assessments(self, tenant_id: str = "default", dependency_id: Optional[str] = None) -> List[DependencyResilienceAssuranceRecord]:
        with self._lock:
            return [
                r for r in self._dependency_assessments.values()
                if r.tenant_id == tenant_id and (dependency_id is None or r.dependency_id == dependency_id)
            ]

    # --- Recovery Performance ---
    def save_recovery_assessment(self, record: RecoveryPerformanceAssuranceRecord) -> RecoveryPerformanceAssuranceRecord:
        with self._lock:
            self._recovery_assessments[record.assessment_id] = record
            return record

    def get_recovery_assessment(self, assessment_id: str, tenant_id: str = "default") -> Optional[RecoveryPerformanceAssuranceRecord]:
        with self._lock:
            rec = self._recovery_assessments.get(assessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_recovery_assessments(self, tenant_id: str = "default", recovery_id: Optional[str] = None) -> List[RecoveryPerformanceAssuranceRecord]:
        with self._lock:
            return [
                r for r in self._recovery_assessments.values()
                if r.tenant_id == tenant_id and (recovery_id is None or r.recovery_id == recovery_id)
            ]

    # --- Reconciliation Assurance ---
    def save_reconciliation_assessment(self, record: ReconciliationAssuranceRecord) -> ReconciliationAssuranceRecord:
        with self._lock:
            self._reconciliation_assessments[record.assurance_id] = record
            return record

    def get_reconciliation_assessment(self, assurance_id: str, tenant_id: str = "default") -> Optional[ReconciliationAssuranceRecord]:
        with self._lock:
            rec = self._reconciliation_assessments.get(assurance_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_reconciliation_assessments(self, tenant_id: str = "default", activation_id: Optional[str] = None) -> List[ReconciliationAssuranceRecord]:
        with self._lock:
            return [
                r for r in self._reconciliation_assessments.values()
                if r.tenant_id == tenant_id and (activation_id is None or r.activation_id == activation_id)
            ]

    # --- Validation Programmes ---
    def save_validation_programme(self, record: IndependentValidationProgrammeRecord) -> IndependentValidationProgrammeRecord:
        with self._lock:
            self._validation_programmes[record.programme_id] = record
            return record

    def get_validation_programme(self, programme_id: str, tenant_id: str = "default") -> Optional[IndependentValidationProgrammeRecord]:
        with self._lock:
            rec = self._validation_programmes.get(programme_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_validation_programmes(self, tenant_id: str = "default", status: Optional[ProgrammeStatus] = None) -> List[IndependentValidationProgrammeRecord]:
        with self._lock:
            return [
                r for r in self._validation_programmes.values()
                if r.tenant_id == tenant_id and (status is None or r.status == status)
            ]

    # --- Findings ---
    def save_finding(self, record: ContinuityAssuranceFindingRecord) -> ContinuityAssuranceFindingRecord:
        with self._lock:
            self._findings[record.finding_id] = record
            return record

    def get_finding(self, finding_id: str, tenant_id: str = "default") -> Optional[ContinuityAssuranceFindingRecord]:
        with self._lock:
            rec = self._findings.get(finding_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_findings(self, tenant_id: str = "default", status: Optional[FindingStatus] = None) -> List[ContinuityAssuranceFindingRecord]:
        with self._lock:
            return [
                r for r in self._findings.values()
                if r.tenant_id == tenant_id and (status is None or r.status == status)
            ]


# Module-level singleton
governance_continuity_assurance_repository = GovernanceContinuityAssuranceRepository()


def get_governance_continuity_assurance_repository() -> GovernanceContinuityAssuranceRepository:
    """Returns the singleton instance of the Governance Continuity Assurance repository."""
    return governance_continuity_assurance_repository


"""Phase 73: Clinical Safety Governance Decision Implementation Repository.

Provides a thread-safe repository layer for:
- Decision intake records and validation state
- Decision implementation register
- Versioned implementation plans
- Ownership assignments and delegation history
- Gating dependencies and prerequisite evaluations
- Milestones, evidence references, and independent verification records
- Destination workflow delegation handoffs (Phases 49, 54, 55, 63, 67, 69, 70)
- Outcome and intended-result reconciliation
- Implementation exceptions and decision change-impact coordination
- Executive oversight reports
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional

from app.schemas.decision_implementation_intake import (
    DecisionIntakeRecord,
    DecisionIntakeStatus,
)
from app.schemas.decision_implementation_register import (
    DecisionImplementationRecord,
    ImplementationCategory,
    ImplementationPriority,
    ImplementationStatus,
)
from app.schemas.decision_implementation_planning import (
    ImplementationPlanRecord,
    PlanApprovalStatus,
)
from app.schemas.decision_implementation_ownership_dependencies import (
    AcceptanceStatus,
    AssignmentRole,
    DependencyStatus,
    DependencyType,
    ImplementationAssignmentRecord,
    ImplementationDependencyRecord,
)
from app.schemas.decision_implementation_milestones_evidence import (
    ImplementationEvidenceRecord,
    ImplementationMilestoneRecord,
    ImplementationVerificationRecord,
    MilestoneStatus,
    VerificationOutcome,
)
from app.schemas.decision_implementation_handoffs_outcomes import (
    DecisionChangeImpactRecord,
    DestinationWorkflow,
    HandoffStatus,
    ImplementationExceptionRecord,
    OutcomeAssessmentRecord,
    WorkflowHandoffRecord,
)
from app.schemas.decision_implementation_closure_reports import (
    ImplementationReportRecord,
)


class GovernanceDecisionImplementationRepository:
    """Thread-safe in-memory repository for Phase 73 implementation entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._intakes: Dict[str, DecisionIntakeRecord] = {}
        self._implementations: Dict[str, DecisionImplementationRecord] = {}
        self._plans: Dict[str, ImplementationPlanRecord] = {}
        self._assignments: Dict[str, ImplementationAssignmentRecord] = {}
        self._dependencies: Dict[str, ImplementationDependencyRecord] = {}
        self._milestones: Dict[str, ImplementationMilestoneRecord] = {}
        self._evidence: Dict[str, ImplementationEvidenceRecord] = {}
        self._verifications: Dict[str, ImplementationVerificationRecord] = {}
        self._handoffs: Dict[str, WorkflowHandoffRecord] = {}
        self._outcomes: Dict[str, OutcomeAssessmentRecord] = {}
        self._exceptions: Dict[str, ImplementationExceptionRecord] = {}
        self._impacts: Dict[str, DecisionChangeImpactRecord] = {}
        self._reports: Dict[str, ImplementationReportRecord] = {}

    def clear(self) -> None:
        """Clears all in-memory records (used in test isolation)."""
        with self._lock:
            self._intakes.clear()
            self._implementations.clear()
            self._plans.clear()
            self._assignments.clear()
            self._dependencies.clear()
            self._milestones.clear()
            self._evidence.clear()
            self._verifications.clear()
            self._handoffs.clear()
            self._outcomes.clear()
            self._exceptions.clear()
            self._impacts.clear()
            self._reports.clear()

    # -------------------------------------------------------------------------
    # Decision Intake
    # -------------------------------------------------------------------------

    def save_intake(self, record: DecisionIntakeRecord) -> DecisionIntakeRecord:
        with self._lock:
            self._intakes[record.intake_id] = record
            return record

    def get_intake(self, intake_id: str) -> Optional[DecisionIntakeRecord]:
        with self._lock:
            return self._intakes.get(intake_id)

    def get_intake_by_decision(self, decision_id: str) -> Optional[DecisionIntakeRecord]:
        with self._lock:
            for intake in self._intakes.values():
                if intake.decision_id == decision_id:
                    return intake
            return None

    def list_intakes(
        self,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DecisionIntakeRecord]:
        with self._lock:
            results = [
                i
                for i in self._intakes.values()
                if i.organization_id == organization_id
                and (status is None or i.intake_status.value == status)
            ]
            results.sort(key=lambda x: x.ingested_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Implementation Register
    # -------------------------------------------------------------------------

    def save_implementation(
        self, record: DecisionImplementationRecord
    ) -> DecisionImplementationRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._implementations[record.implementation_id] = record
            return record

    def get_implementation(
        self, implementation_id: str
    ) -> Optional[DecisionImplementationRecord]:
        with self._lock:
            return self._implementations.get(implementation_id)

    def get_implementation_by_decision(
        self, decision_id: str
    ) -> Optional[DecisionImplementationRecord]:
        with self._lock:
            for imp in self._implementations.values():
                if imp.decision_id == decision_id:
                    return imp
            return None

    def list_implementations(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DecisionImplementationRecord]:
        with self._lock:
            results = [
                imp
                for imp in self._implementations.values()
                if imp.organization_id == organization_id
                and (facility_id is None or imp.facility_id == facility_id or imp.facility_id is None)
                and (status is None or imp.status.value == status)
                and (category is None or imp.category.value == category)
                and (priority is None or imp.priority.value == priority)
                and (owner_id is None or imp.responsible_owner_id == owner_id or imp.accountable_lead_id == owner_id)
            ]
            results.sort(key=lambda x: x.target_completion_date)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Plans
    # -------------------------------------------------------------------------

    def save_plan(self, record: ImplementationPlanRecord) -> ImplementationPlanRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._plans[record.plan_id] = record
            return record

    def get_plan(self, plan_id: str) -> Optional[ImplementationPlanRecord]:
        with self._lock:
            return self._plans.get(plan_id)

    def get_active_plan(
        self, implementation_id: str
    ) -> Optional[ImplementationPlanRecord]:
        with self._lock:
            active_plans = [
                p
                for p in self._plans.values()
                if p.implementation_id == implementation_id and p.is_active
            ]
            if active_plans:
                active_plans.sort(key=lambda x: x.version, reverse=True)
                return active_plans[0]
            return None

    def list_plans(self, implementation_id: str) -> List[ImplementationPlanRecord]:
        with self._lock:
            plans = [p for p in self._plans.values() if p.implementation_id == implementation_id]
            plans.sort(key=lambda x: x.version, reverse=True)
            return plans

    # -------------------------------------------------------------------------
    # Ownership Assignments
    # -------------------------------------------------------------------------

    def save_assignment(
        self, record: ImplementationAssignmentRecord
    ) -> ImplementationAssignmentRecord:
        with self._lock:
            self._assignments[record.assignment_id] = record
            return record

    def get_assignment(
        self, assignment_id: str
    ) -> Optional[ImplementationAssignmentRecord]:
        with self._lock:
            return self._assignments.get(assignment_id)

    def list_assignments(
        self,
        implementation_id: str,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[ImplementationAssignmentRecord]:
        with self._lock:
            return [
                a
                for a in self._assignments.values()
                if a.implementation_id == implementation_id
                and (user_id is None or a.user_id == user_id)
                and (role is None or a.role.value == role)
            ]

    # -------------------------------------------------------------------------
    # Dependencies
    # -------------------------------------------------------------------------

    def save_dependency(
        self, record: ImplementationDependencyRecord
    ) -> ImplementationDependencyRecord:
        with self._lock:
            self._dependencies[record.dependency_id] = record
            return record

    def get_dependency(
        self, dependency_id: str
    ) -> Optional[ImplementationDependencyRecord]:
        with self._lock:
            return self._dependencies.get(dependency_id)

    def list_dependencies(
        self, implementation_id: str, status: Optional[str] = None
    ) -> List[ImplementationDependencyRecord]:
        with self._lock:
            return [
                d
                for d in self._dependencies.values()
                if d.implementation_id == implementation_id
                and (status is None or d.status.value == status)
            ]

    # -------------------------------------------------------------------------
    # Milestones
    # -------------------------------------------------------------------------

    def save_milestone(
        self, record: ImplementationMilestoneRecord
    ) -> ImplementationMilestoneRecord:
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._milestones[record.milestone_id] = record
            return record

    def get_milestone(
        self, milestone_id: str
    ) -> Optional[ImplementationMilestoneRecord]:
        with self._lock:
            return self._milestones.get(milestone_id)

    def list_milestones(
        self,
        implementation_id: Optional[str] = None,
        status: Optional[str] = None,
        is_overdue: Optional[bool] = None,
    ) -> List[ImplementationMilestoneRecord]:
        with self._lock:
            now = datetime.now(timezone.utc)
            results = []
            for m in self._milestones.values():
                if implementation_id and m.implementation_id != implementation_id:
                    continue
                if status and m.status.value != status:
                    continue
                if is_overdue is not None:
                    m_overdue = (
                        m.target_date < now
                        and m.status not in [MilestoneStatus.VERIFIED, MilestoneStatus.CANCELLED]
                    )
                    if m_overdue != is_overdue:
                        continue
                results.append(m)
            results.sort(key=lambda x: x.target_date)
            return results

    # -------------------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------------------

    def save_evidence(
        self, record: ImplementationEvidenceRecord
    ) -> ImplementationEvidenceRecord:
        with self._lock:
            self._evidence[record.evidence_id] = record
            return record

    def get_evidence(self, evidence_id: str) -> Optional[ImplementationEvidenceRecord]:
        with self._lock:
            return self._evidence.get(evidence_id)

    def list_evidence(
        self, implementation_id: str, milestone_id: Optional[str] = None
    ) -> List[ImplementationEvidenceRecord]:
        with self._lock:
            return [
                e
                for e in self._evidence.values()
                if e.implementation_id == implementation_id
                and (milestone_id is None or e.milestone_id == milestone_id)
            ]

    # -------------------------------------------------------------------------
    # Verifications
    # -------------------------------------------------------------------------

    def save_verification(
        self, record: ImplementationVerificationRecord
    ) -> ImplementationVerificationRecord:
        with self._lock:
            self._verifications[record.verification_id] = record
            return record

    def get_verification(
        self, verification_id: str
    ) -> Optional[ImplementationVerificationRecord]:
        with self._lock:
            return self._verifications.get(verification_id)

    def list_verifications(
        self, implementation_id: str, milestone_id: Optional[str] = None
    ) -> List[ImplementationVerificationRecord]:
        with self._lock:
            return [
                v
                for v in self._verifications.values()
                if v.implementation_id == implementation_id
                and (milestone_id is None or v.milestone_id == milestone_id)
            ]

    # -------------------------------------------------------------------------
    # Destination Workflow Handoffs
    # -------------------------------------------------------------------------

    def save_handoff(self, record: WorkflowHandoffRecord) -> WorkflowHandoffRecord:
        with self._lock:
            self._handoffs[record.handoff_id] = record
            return record

    def get_handoff(self, handoff_id: str) -> Optional[WorkflowHandoffRecord]:
        with self._lock:
            return self._handoffs.get(handoff_id)

    def list_handoffs(
        self,
        implementation_id: str,
        destination_workflow: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[WorkflowHandoffRecord]:
        with self._lock:
            return [
                h
                for h in self._handoffs.values()
                if h.implementation_id == implementation_id
                and (destination_workflow is None or h.destination_workflow.value == destination_workflow)
                and (status is None or h.status.value == status)
            ]

    # -------------------------------------------------------------------------
    # Outcomes
    # -------------------------------------------------------------------------

    def save_outcome(
        self, record: OutcomeAssessmentRecord
    ) -> OutcomeAssessmentRecord:
        with self._lock:
            self._outcomes[record.assessment_id] = record
            return record

    def get_outcome(self, assessment_id: str) -> Optional[OutcomeAssessmentRecord]:
        with self._lock:
            return self._outcomes.get(assessment_id)

    def get_outcome_by_implementation(
        self, implementation_id: str
    ) -> Optional[OutcomeAssessmentRecord]:
        with self._lock:
            for o in self._outcomes.values():
                if o.implementation_id == implementation_id:
                    return o
            return None

    # -------------------------------------------------------------------------
    # Exceptions
    # -------------------------------------------------------------------------

    def save_exception(
        self, record: ImplementationExceptionRecord
    ) -> ImplementationExceptionRecord:
        with self._lock:
            self._exceptions[record.exception_id] = record
            return record

    def get_exception(
        self, exception_id: str
    ) -> Optional[ImplementationExceptionRecord]:
        with self._lock:
            return self._exceptions.get(exception_id)

    def list_exceptions(
        self, implementation_id: str
    ) -> List[ImplementationExceptionRecord]:
        with self._lock:
            return [e for e in self._exceptions.values() if e.implementation_id == implementation_id]

    # -------------------------------------------------------------------------
    # Change Impacts
    # -------------------------------------------------------------------------

    def save_impact(
        self, record: DecisionChangeImpactRecord
    ) -> DecisionChangeImpactRecord:
        with self._lock:
            self._impacts[record.impact_id] = record
            return record

    def get_impact(self, impact_id: str) -> Optional[DecisionChangeImpactRecord]:
        with self._lock:
            return self._impacts.get(impact_id)

    def list_impacts(
        self, implementation_id: Optional[str] = None, decision_id: Optional[str] = None
    ) -> List[DecisionChangeImpactRecord]:
        with self._lock:
            return [
                i
                for i in self._impacts.values()
                if (implementation_id is None or i.implementation_id == implementation_id)
                and (decision_id is None or i.decision_id == decision_id)
            ]

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def save_report(
        self, record: ImplementationReportRecord
    ) -> ImplementationReportRecord:
        with self._lock:
            self._reports[record.report_id] = record
            return record

    def get_report(self, report_id: str) -> Optional[ImplementationReportRecord]:
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(self) -> List[ImplementationReportRecord]:
        with self._lock:
            reports = list(self._reports.values())
            reports.sort(key=lambda x: x.generated_at, reverse=True)
            return reports


_repo_instance: Optional[GovernanceDecisionImplementationRepository] = None
_repo_lock = threading.Lock()


def get_governance_decision_implementation_repository() -> (
    GovernanceDecisionImplementationRepository
):
    """Provides singleton instance of GovernanceDecisionImplementationRepository."""
    global _repo_instance
    if _repo_instance is None:
        with _repo_lock:
            if _repo_instance is None:
                _repo_instance = GovernanceDecisionImplementationRepository()
    return _repo_instance

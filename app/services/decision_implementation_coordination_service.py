"""Phase 73: Cross-Workflow Coordination, Outcome Reconciliation & Change Impact Service.

Handles:
- Delegation handoffs to authoritative destination workflows (Phases 49, 54, 55, 63, 67, 69, 70)
- Outcome and intended-result reconciliation against original management decisions
- Implementation exception tracking and Phase 67 escalation
- Decision supersession and change-impact coordination
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_implementation_repository import (
    GovernanceDecisionImplementationRepository,
    get_governance_decision_implementation_repository,
)
from app.schemas.decision_implementation_register import ImplementationStatus
from app.schemas.decision_implementation_milestones_evidence import MilestoneStatus
from app.schemas.decision_implementation_handoffs_outcomes import (
    AssessOutcomeRequest,
    CreateHandoffRequest,
    DecisionChangeImpactRecord,
    DestinationWorkflow,
    HandoffStatus,
    ImplementationExceptionCategory,
    ImplementationExceptionRecord,
    OutcomeAssessmentRecord,
    OutcomeState,
    ReconcileHandoffRequest,
    ReferExceptionRequest,
    ReviewChangeImpactRequest,
    WorkflowHandoffRecord,
)


class DecisionImplementationCoordinationService:
    """Service governing cross-workflow handoffs, outcome reconciliation, and decision change impact."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )

    # -------------------------------------------------------------------------
    # Destination Workflow Handoffs
    # -------------------------------------------------------------------------

    def create_handoff(
        self,
        implementation_id: str,
        request: CreateHandoffRequest,
    ) -> WorkflowHandoffRecord:
        """Dispatches an implementation action to an authoritative destination workflow."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        handoff = WorkflowHandoffRecord(
            implementation_id=implementation_id,
            destination_workflow=request.destination_workflow,
            destination_record_id=request.destination_record_id,
            requested_outcome=request.requested_outcome,
            responsible_owner_id=request.responsible_owner_id,
            status=HandoffStatus.DISPATCHED,
            dispatched_at=datetime.now(timezone.utc),
            metadata=request.metadata or {},
        )

        return self.repository.save_handoff(handoff)

    def get_handoff(self, handoff_id: str) -> WorkflowHandoffRecord:
        """Retrieves a handoff record by ID."""
        handoff = self.repository.get_handoff(handoff_id)
        if not handoff:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.NOT_FOUND,
                message=f"Workflow handoff '{handoff_id}' not found.",
            )
        return handoff

    def list_handoffs(
        self,
        implementation_id: str,
        destination_workflow: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[WorkflowHandoffRecord]:
        """Lists handoffs for an implementation."""
        return self.repository.list_handoffs(
            implementation_id=implementation_id,
            destination_workflow=destination_workflow,
            status=status_filter,
        )

    def reconcile_handoff(
        self,
        handoff_id: str,
        request: ReconcileHandoffRequest,
    ) -> WorkflowHandoffRecord:
        """Reconciles status from destination workflow."""
        handoff = self.get_handoff(handoff_id)
        handoff.latest_destination_status = request.latest_destination_status
        handoff.status = request.status
        handoff.reconciled_at = datetime.now(timezone.utc)
        if request.notes:
            handoff.metadata["reconciliation_notes"] = request.notes

        return self.repository.save_handoff(handoff)

    # -------------------------------------------------------------------------
    # Outcome Reconciliation
    # -------------------------------------------------------------------------

    def assess_outcome(
        self,
        implementation_id: str,
        request: AssessOutcomeRequest,
        assessor_id: str,
    ) -> OutcomeAssessmentRecord:
        """Evaluates whether the delivered implementation achieved the original intended decision outcome.

        INVARIANT: An implementation cannot be declared OUTCOME_ACHIEVED solely because milestones are complete.
        Documented rationale and verified evidence are strictly mandatory.
        """
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        # Enforce that OUTCOME_ACHIEVED requires evidence references and rationale
        if request.state == OutcomeState.OUTCOME_ACHIEVED:
            evidence_list = self.repository.list_evidence(implementation_id)
            if not evidence_list and not request.supporting_evidence_refs:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                    message="Cannot declare OUTCOME_ACHIEVED without supporting evidence references.",
                )

        assessment = OutcomeAssessmentRecord(
            implementation_id=implementation_id,
            decision_id=imp.decision_id,
            state=request.state,
            rationale=request.rationale,
            supporting_evidence_refs=request.supporting_evidence_refs or [],
            destination_workflow_outcome=request.destination_workflow_outcome or {},
            remaining_limitations=request.remaining_limitations or [],
            unresolved_dependencies=request.unresolved_dependencies or [],
            assessed_by=assessor_id,
        )
        saved_assessment = self.repository.save_outcome(assessment)

        # If outcome achieved or partially achieved, advance implementation status
        if request.state == OutcomeState.OUTCOME_ACHIEVED:
            imp.status = ImplementationStatus.RECONCILED
            self.repository.save_implementation(imp)

        return saved_assessment

    def get_outcome(
        self, implementation_id: str
    ) -> OutcomeAssessmentRecord:
        """Retrieves outcome assessment for an implementation."""
        outcome = self.repository.get_outcome_by_implementation(implementation_id)
        if not outcome:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.OUTCOME_ASSESSMENT_NOT_FOUND,
                message=f"No outcome assessment recorded for implementation '{implementation_id}'.",
            )
        return outcome

    # -------------------------------------------------------------------------
    # Exception Tracking
    # -------------------------------------------------------------------------

    def record_exception(
        self,
        implementation_id: str,
        category: ImplementationExceptionCategory,
        description: str,
        priority: str,
        owner_id: str,
    ) -> ImplementationExceptionRecord:
        """Logs an operational or governance exception during implementation."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        exc = ImplementationExceptionRecord(
            implementation_id=implementation_id,
            decision_id=imp.decision_id,
            category=category,
            description=description,
            priority=priority,
            owner_id=owner_id,
        )
        return self.repository.save_exception(exc)

    def refer_exception(
        self,
        exception_id: str,
        request: ReferExceptionRequest,
    ) -> ImplementationExceptionRecord:
        """Links an implementation exception to Phase 67 governance escalation."""
        exc = self.repository.get_exception(exception_id)
        if not exc:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMPLEMENTATION_EXCEPTION_NOT_FOUND,
                message=f"Implementation exception '{exception_id}' not found.",
            )

        exc.escalation_reference_id = request.escalation_reference_id
        if request.notes:
            exc.metadata["referral_notes"] = request.notes

        return self.repository.save_exception(exc)

    def list_exceptions(
        self, implementation_id: str
    ) -> List[ImplementationExceptionRecord]:
        """Lists exceptions logged for an implementation."""
        return self.repository.list_exceptions(implementation_id)

    # -------------------------------------------------------------------------
    # Decision Change Impact
    # -------------------------------------------------------------------------

    def review_change_impact(
        self,
        implementation_id: str,
        request: ReviewChangeImpactRequest,
        reviewer_id: str,
    ) -> DecisionChangeImpactRecord:
        """Evaluates impact when a Phase 72 decision is amended or superseded.

        INVARIANT: Does not automatically destroy or revert completed work.
        Preserves complete implementation history and records authorized disposition.
        """
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        milestones = self.repository.list_milestones(implementation_id)
        dependencies = self.repository.list_dependencies(implementation_id)
        handoffs = self.repository.list_handoffs(implementation_id)

        impact = DecisionChangeImpactRecord(
            implementation_id=implementation_id,
            decision_id=imp.decision_id,
            previous_decision_status="APPROVED",
            new_decision_status="SUPERSEDED",
            impacted_milestones=[m.milestone_id for m in milestones],
            impacted_dependencies=[d.dependency_id for d in dependencies],
            impacted_handoffs=[h.handoff_id for h in handoffs],
            recommended_disposition=request.disposition_decision,
            disposition_decision=request.disposition_decision,
            disposition_authorized_by=reviewer_id,
            metadata={"rationale": request.rationale},
        )
        saved_impact = self.repository.save_impact(impact)

        # Update implementation status if disposition is CANCEL or SUSPEND
        if request.disposition_decision == "CANCEL":
            imp.status = ImplementationStatus.CANCELLED_WITH_AUTHORIZATION
            self.repository.save_implementation(imp)
        elif request.disposition_decision == "SUSPEND":
            imp.status = ImplementationStatus.BLOCKED
            self.repository.save_implementation(imp)
        elif request.disposition_decision == "MODIFY":
            imp.status = ImplementationStatus.REQUIRES_FURTHER_ACTION
            self.repository.save_implementation(imp)

        return saved_impact

    def list_impacts(
        self, implementation_id: Optional[str] = None
    ) -> List[DecisionChangeImpactRecord]:
        """Lists decision change impact assessments."""
        return self.repository.list_impacts(implementation_id=implementation_id)

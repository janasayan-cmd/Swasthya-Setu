"""Phase 73: Implementation Closure, Reopening & Management Reporting Service.

Handles:
- Implementation closure readiness validation against strict gating conditions
- Controlled implementation completion and closure with follow-up tracking
- Governed reopening of closed initiatives
- Executive management reporting and aggregated implementation metrics
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
from app.schemas.decision_implementation_ownership_dependencies import DependencyStatus
from app.schemas.decision_implementation_milestones_evidence import MilestoneStatus
from app.schemas.decision_implementation_closure_reports import (
    CloseImplementationRequest,
    GenerateImplementationReportRequest,
    ImplementationClosureCheckResponse,
    ImplementationOverviewResponse,
    ImplementationReportRecord,
    ReopenImplementationRequest,
)


class DecisionImplementationClosureService:
    """Service governing implementation closure, reopening, and executive reporting."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )

    # -------------------------------------------------------------------------
    # Closure Readiness & Gating Validation
    # -------------------------------------------------------------------------

    def check_closure_readiness(
        self, implementation_id: str
    ) -> ImplementationClosureCheckResponse:
        """Evaluates whether all gating conditions for implementation closure are satisfied."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        milestones = self.repository.list_milestones(implementation_id=implementation_id)
        dependencies = self.repository.list_dependencies(implementation_id)
        evidence_list = self.repository.list_evidence(implementation_id)
        outcome = self.repository.get_outcome_by_implementation(implementation_id)
        exceptions = self.repository.list_exceptions(implementation_id)

        all_milestones_completed = (
            all(m.status in [MilestoneStatus.VERIFIED, MilestoneStatus.CANCELLED] for m in milestones)
            if milestones
            else True
        )

        dependencies_satisfied = all(
            d.status in [
                DependencyStatus.SATISFIED,
                DependencyStatus.WAIVED_WITH_AUTHORIZATION,
                DependencyStatus.NOT_APPLICABLE,
            ]
            for d in dependencies
        )

        evidence_verified = any(
            e.review_status == "ACCEPTED" for e in evidence_list
        ) if evidence_list else False

        outcome_assessed = outcome is not None

        pending_blockers = []
        if not all_milestones_completed:
            pending_blockers.append("Not all milestones have reached verified or cancelled terminal states.")
        if not dependencies_satisfied:
            pending_blockers.append("Some mandatory prerequisites/dependencies remain unsatisfied.")
        if not evidence_verified:
            pending_blockers.append("No verified/accepted implementation evidence is on record.")
        if not outcome_assessed:
            pending_blockers.append("Outcome and intended-result reconciliation assessment is missing.")

        can_close = len(pending_blockers) == 0

        return ImplementationClosureCheckResponse(
            implementation_id=implementation_id,
            can_close=can_close,
            all_milestones_completed=all_milestones_completed,
            dependencies_satisfied=dependencies_satisfied,
            evidence_verified=evidence_verified,
            outcome_assessed=outcome_assessed,
            pending_blockers=pending_blockers,
        )

    def close_implementation(
        self,
        implementation_id: str,
        request: CloseImplementationRequest,
        closer_id: str,
    ) -> None:
        """Closes an implementation initiative after verifying gating criteria."""
        readiness = self.check_closure_readiness(implementation_id)
        if not readiness.can_close:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.IMPLEMENTATION_CLOSURE_CONDITIONS_UNMET,
                message=f"Implementation cannot be closed: {'; '.join(readiness.pending_blockers)}",
            )

        imp = self.repository.get_implementation(implementation_id)
        target_status = (
            ImplementationStatus[request.closure_outcome]
            if request.closure_outcome and request.closure_outcome in ImplementationStatus.__members__
            else ImplementationStatus.CLOSED
        )
        imp.status = target_status
        imp.actual_completion_date = datetime.now(timezone.utc)
        if request.closure_notes:
            imp.metadata["closure_notes"] = request.closure_notes
        imp.metadata["closed_by"] = closer_id
        imp.metadata["closed_at"] = datetime.now(timezone.utc).isoformat()
        if request.follow_up_commitments:
            imp.metadata["follow_up_commitments"] = request.follow_up_commitments

        self.repository.save_implementation(imp)

    def reopen_implementation(
        self,
        implementation_id: str,
        request: ReopenImplementationRequest,
        reopener_id: str,
    ) -> None:
        """Reopens a completed or closed implementation for further action."""
        imp = self.repository.get_implementation(implementation_id)
        if imp.status not in [
            ImplementationStatus.CLOSED,
            ImplementationStatus.CLOSED_WITH_FOLLOW_UP,
            ImplementationStatus.CLOSED_WITH_LIMITATIONS,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot reopen implementation in status '{imp.status.value}'. Must be closed.",
            )

        imp.status = ImplementationStatus.REQUIRES_FURTHER_ACTION
        reopening_entry = {
            "reopened_by": reopener_id,
            "reopening_reason": request.reopening_reason,
            "reopened_at": datetime.now(timezone.utc).isoformat(),
        }
        reopenings = imp.metadata.setdefault("reopenings", [])
        reopenings.append(reopening_entry)

        self.repository.save_implementation(imp)

    # -------------------------------------------------------------------------
    # Management Oversight Reporting
    # -------------------------------------------------------------------------

    def get_overview(
        self, organization_id: str
    ) -> ImplementationOverviewResponse:
        """Aggregates executive metrics on decision implementations for an organization."""
        implementations = self.repository.list_implementations(organization_id=organization_id)

        status_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}
        for imp in implementations:
            status_counts[imp.status.value] = status_counts.get(imp.status.value, 0) + 1
            category_counts[imp.category.value] = category_counts.get(imp.category.value, 0) + 1

        plans = self.repository._plans.values()
        plans_awaiting = sum(
            1 for p in plans if p.approval_status.value == "SUBMITTED"
        )

        blocked_count = sum(
            1 for imp in implementations if imp.status == ImplementationStatus.BLOCKED
        )

        all_milestones = self.repository._milestones.values()
        now = datetime.now(timezone.utc)
        overdue_milestones = sum(
            1
            for m in all_milestones
            if m.target_date < now
            and m.status not in [MilestoneStatus.VERIFIED, MilestoneStatus.CANCELLED]
        )

        all_verifications = self.repository._verifications.values()
        failed_verifications = sum(
            1 for v in all_verifications if v.outcome.value == "REJECTED"
        )

        outcomes = self.repository._outcomes.values()
        outcome_counts: Dict[str, int] = {}
        for o in outcomes:
            outcome_counts[o.state.value] = outcome_counts.get(o.state.value, 0) + 1

        exceptions = self.repository._exceptions.values()

        return ImplementationOverviewResponse(
            organization_id=organization_id,
            total_implementations=len(implementations),
            implementations_by_status=status_counts,
            implementations_by_category=category_counts,
            plans_awaiting_approval_count=plans_awaiting,
            blocked_implementations_count=blocked_count,
            overdue_milestones_count=overdue_milestones,
            failed_verification_count=failed_verifications,
            outcomes_by_state=outcome_counts,
            open_exceptions_count=len(exceptions),
            data_quality_status="COMPLETE",
            known_limitations=[],
        )

    def generate_report(
        self,
        request: GenerateImplementationReportRequest,
        generator_id: str,
        organization_id: str,
    ) -> ImplementationReportRecord:
        """Compiles a formal executive oversight report."""
        overview = self.get_overview(organization_id)
        title = request.title or f"Executive Decision Implementation Report - {request.reporting_period}"
        summary = (
            request.executive_summary
            or f"Oversight summary for period {request.reporting_period}. Total initiatives: {overview.total_implementations}. Blocked: {overview.blocked_implementations_count}."
        )

        report = ImplementationReportRecord(
            report_type=request.report_type or "OVERVIEW",
            reporting_period=request.reporting_period or "Current",
            title=title,
            executive_summary=summary,
            metrics=overview.model_dump(),
            generated_by=generator_id,
        )

        return self.repository.save_report(report)

    def get_report(self, report_id: str) -> ImplementationReportRecord:
        """Retrieves a report by ID."""
        rep = self.repository.get_report(report_id)
        if not rep:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.NOT_FOUND,
                message=f"Report '{report_id}' not found.",
            )
        return rep

    def list_reports(self) -> List[ImplementationReportRecord]:
        """Lists oversight reports."""
        return self.repository.list_reports()

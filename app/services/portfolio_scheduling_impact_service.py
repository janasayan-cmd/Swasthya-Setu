"""Phase 75: Portfolio Scheduling, Impact & Resource Coordination Service.

Coordinates:
- Scheduling assessments and advisory sequencing recommendations
- Cumulative operational impact assessments across concurrent changes
- Resource dependency visibility without unsupported capacity claims
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional, Set
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_portfolio_repository import (
    GovernanceChangePortfolioRepository,
    get_governance_change_portfolio_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.portfolio_scheduling_impact import (
    CreateImpactAssessmentRequest,
    CreateResourceDependencyRequest,
    CreateScheduleAssessmentRequest,
    CumulativeImpactAssessmentRecord,
    ResourceDependencyRecord,
    ScheduleAssessmentRecord,
)


class PortfolioSchedulingImpactService:
    """Service governing scheduling coordination, cumulative operational burden, and resource visibility."""

    def __init__(
        self,
        repository: Optional[GovernanceChangePortfolioRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_portfolio_repository()

    # -------------------------------------------------------------------------
    # Scheduling Assessments
    # -------------------------------------------------------------------------
    def assess_schedule(
        self,
        portfolio_id: str,
        request: CreateScheduleAssessmentRequest,
        current_user: AuthenticatedUserContext,
    ) -> ScheduleAssessmentRecord:
        """Conducts a cross-initiative scheduling assessment."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        initiatives = self.repo.list_initiatives_for_portfolio(portfolio_id, user_tenant)
        overlaps = []
        recommendations = []

        for i in range(len(initiatives)):
            for j in range(i + 1, len(initiatives)):
                a = initiatives[i]
                b = initiatives[j]
                is_overlap = not (a.planned_target_date < b.planned_start_date or b.planned_target_date < a.planned_start_date)
                if is_overlap:
                    overlaps.append({
                        "initiative_pair": [a.initiative_id, b.initiative_id],
                        "initiative_titles": [a.title, b.title],
                        "shared_facilities": list(set(a.participating_facilities).intersection(set(b.participating_facilities))),
                        "shared_departments": list(set(a.participating_departments).intersection(set(b.participating_departments))),
                    })

        if overlaps:
            recommendations.append(
                f"Advisory: {len(overlaps)} overlapping implementation windows detected. "
                "Consider staggering go-live dates by at least 14 days to prevent operational overload."
            )
        else:
            recommendations.append("Advisory: No concurrent schedule collisions identified in current portfolio planning.")

        now = datetime.now(timezone.utc).isoformat()
        aid = f"sca_{uuid.uuid4().hex[:12]}"

        record = ScheduleAssessmentRecord(
            assessment_id=aid,
            portfolio_id=portfolio_id,
            tenant_id=user_tenant,
            assessment_date=request.assessment_date or now,
            overlapping_initiatives=overlaps,
            sequencing_recommendations=recommendations,
            assessed_by=current_user.user_id,
            created_at=now,
        )

        saved = self.repo.save_schedule_assessment(record)
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.schedule_assessed",
            actor_id=current_user.user_id,
            summary=f"Schedule assessment completed: {len(overlaps)} overlaps detected.",
            details={"assessment_id": saved.assessment_id},
        )
        return saved

    def get_schedule_assessment(
        self, assessment_id: str, current_user: AuthenticatedUserContext
    ) -> ScheduleAssessmentRecord:
        """Retrieves a schedule assessment with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        assessment = self.repo.get_schedule_assessment(assessment_id)
        if not assessment or assessment.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_SCHEDULE_ASSESSMENT_NOT_FOUND,
                message=f"Schedule assessment '{assessment_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return assessment

    def list_schedule_assessments(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[ScheduleAssessmentRecord]:
        """Lists schedule assessments for a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_schedule_assessments_for_portfolio(portfolio_id, user_tenant)

    # -------------------------------------------------------------------------
    # Cumulative Operational Impact Assessments
    # -------------------------------------------------------------------------
    def assess_cumulative_impact(
        self,
        portfolio_id: str,
        request: CreateImpactAssessmentRequest,
        current_user: AuthenticatedUserContext,
    ) -> CumulativeImpactAssessmentRecord:
        """Evaluates cumulative operational disruption across concurrent changes."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        all_initiatives = self.repo.list_initiatives_for_portfolio(portfolio_id, user_tenant)
        if request.included_initiative_ids:
            included = [i for i in all_initiatives if i.initiative_id in request.included_initiative_ids]
        else:
            included = all_initiatives

        facs: Set[str] = set()
        depts: Set[str] = set()
        for i in included:
            facs.update(i.participating_facilities)
            depts.update(i.participating_departments)

        concurrent_count = len(included)
        training_hours = float(concurrent_count * 8.0)  # estimated baseline 8h per change
        proc_updates = concurrent_count * 2

        if concurrent_count >= 5:
            risk = "ELEVATED"
        elif concurrent_count >= 3:
            risk = "HIGH"
        elif concurrent_count >= 1:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        now = datetime.now(timezone.utc).isoformat()
        cid = f"imp_{uuid.uuid4().hex[:12]}"

        record = CumulativeImpactAssessmentRecord(
            assessment_id=cid,
            portfolio_id=portfolio_id,
            tenant_id=user_tenant,
            assessment_period=request.assessment_period,
            included_initiative_ids=[i.initiative_id for i in included],
            affected_facilities=sorted(list(facs)),
            affected_departments=sorted(list(depts)),
            shared_workflows=["CLINICAL_TRIAGE", "MEDICATION_ADMINISTRATION"],
            concurrent_changes_count=concurrent_count,
            estimated_training_workload_hours=training_hours,
            procedure_update_count=proc_updates,
            disruption_risk_level=risk,
            data_coverage_percentage=100.0 if included else 0.0,
            limitations_disclosed=request.limitations_disclosed,
            assumptions_noted=request.assumptions_noted,
            assessor_id=current_user.user_id,
            created_at=now,
        )

        saved = self.repo.save_impact_assessment(record)
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.impact_assessed",
            actor_id=current_user.user_id,
            summary=f"Cumulative impact assessed for '{saved.assessment_period}': Risk Level {saved.disruption_risk_level}.",
            details={"assessment_id": saved.assessment_id, "risk": saved.disruption_risk_level},
        )
        return saved

    def get_impact_assessment(
        self, assessment_id: str, current_user: AuthenticatedUserContext
    ) -> CumulativeImpactAssessmentRecord:
        """Retrieves an impact assessment with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        assessment = self.repo.get_impact_assessment(assessment_id)
        if not assessment or assessment.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.CUMULATIVE_IMPACT_ASSESSMENT_NOT_FOUND,
                message=f"Cumulative impact assessment '{assessment_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return assessment

    def list_impact_assessments(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[CumulativeImpactAssessmentRecord]:
        """Lists impact assessments for a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_impact_assessments_for_portfolio(portfolio_id, user_tenant)

    # -------------------------------------------------------------------------
    # Resource Dependencies
    # -------------------------------------------------------------------------
    def create_resource_dependency(
        self,
        portfolio_id: str,
        request: CreateResourceDependencyRequest,
        current_user: AuthenticatedUserContext,
    ) -> ResourceDependencyRecord:
        """Registers a shared resource dependency."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        rid = f"rsd_{uuid.uuid4().hex[:12]}"

        record = ResourceDependencyRecord(
            resource_dependency_id=rid,
            portfolio_id=portfolio_id,
            tenant_id=user_tenant,
            initiative_ids=request.initiative_ids,
            resource_name=request.resource_name,
            resource_category=request.resource_category,
            capacity_status=request.capacity_status,
            notes=request.notes,
            created_by=current_user.user_id,
            created_at=now,
        )

        saved = self.repo.save_resource_dependency(record)
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.resource_dependency_created",
            actor_id=current_user.user_id,
            summary=f"Resource dependency '{saved.resource_name}' ({saved.resource_category}) registered.",
            details={"resource_dependency_id": saved.resource_dependency_id},
        )
        return saved

    def get_resource_dependency(
        self, resource_dependency_id: str, current_user: AuthenticatedUserContext
    ) -> ResourceDependencyRecord:
        """Retrieves a resource dependency with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        record = self.repo.get_resource_dependency(resource_dependency_id)
        if not record or record.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.RESOURCE_DEPENDENCY_NOT_FOUND,
                message=f"Resource dependency '{resource_dependency_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_resource_dependencies(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[ResourceDependencyRecord]:
        """Lists resource dependencies for a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_resource_dependencies_for_portfolio(portfolio_id, user_tenant)

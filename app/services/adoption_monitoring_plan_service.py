"""Phase 74: Adoption Monitoring Plan Service.

Coordinates:
- Adoption monitoring plan definition across organizational scopes
- Objectives, schedules, thresholds, and end criteria
- Plan activation and lifecycle management
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_adoption_repository import (
    GovernanceChangeAdoptionRepository,
    get_governance_change_adoption_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.adoption_monitoring_plan import (
    ActivateMonitoringPlanRequest,
    AdoptionMonitoringPlanRecord,
    CreateMonitoringPlanRequest,
    MonitoringPlanStatus,
    UpdateMonitoringPlanRequest,
)


class AdoptionMonitoringPlanService:
    """Service governing adoption monitoring plans."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def create_monitoring_plan(
        self,
        registration_id: str,
        request: CreateMonitoringPlanRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionMonitoringPlanRecord:
        """Creates a monitoring plan for an adoption initiative."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        baseline = self.repo.get_baseline(request.baseline_id)
        if not baseline or baseline.registration_id != registration_id or baseline.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.OPERATIONAL_BASELINE_NOT_FOUND,
                message=f"Referenced operational baseline '{request.baseline_id}' was not found for this registration.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        plan_id = f"amp_{uuid.uuid4().hex[:12]}"

        record = AdoptionMonitoringPlanRecord(
            plan_id=plan_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            title=request.title,
            monitoring_objectives=request.monitoring_objectives,
            organizational_scope=request.organizational_scope,
            baseline_id=request.baseline_id,
            baseline_version=baseline.version,
            monitoring_schedule_start=request.monitoring_schedule_start,
            monitoring_schedule_end=request.monitoring_schedule_end,
            monitoring_frequency=request.monitoring_frequency,
            responsible_operational_owner_id=request.responsible_operational_owner_id,
            independent_verifier_role=request.independent_verifier_role,
            escalation_thresholds=request.escalation_thresholds,
            reporting_cadence=request.reporting_cadence,
            monitoring_end_criteria=request.monitoring_end_criteria,
            known_limitations=request.known_limitations,
            status=MonitoringPlanStatus.DRAFT,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_monitoring_plan(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.monitoring_plan_created",
            actor_id=current_user.user_id,
            summary=f"Monitoring plan '{saved.title}' created (Draft).",
            details={"plan_id": saved.plan_id},
        )
        return saved

    def get_monitoring_plan(
        self, plan_id: str, current_user: AuthenticatedUserContext
    ) -> AdoptionMonitoringPlanRecord:
        """Retrieves a monitoring plan with tenant isolation."""
        plan = self.repo.get_monitoring_plan(plan_id)
        if not plan or plan.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.ADOPTION_MONITORING_PLAN_NOT_FOUND,
                message=f"Adoption monitoring plan '{plan_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return plan

    def list_monitoring_plans_for_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> List[AdoptionMonitoringPlanRecord]:
        """Lists monitoring plans for an adoption initiative."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_monitoring_plans_for_registration(registration_id, current_user.tenant_id)

    def activate_monitoring_plan(
        self,
        plan_id: str,
        request: ActivateMonitoringPlanRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionMonitoringPlanRecord:
        """Activates a monitoring plan."""
        plan = self.get_monitoring_plan(plan_id, current_user)
        if plan.status != MonitoringPlanStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_ADOPTION_MONITORING_PLAN_STATE,
                message=f"Plan cannot be activated from status '{plan.status.value}'. Must be DRAFT.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = plan.model_dump()
        updated_dict["status"] = MonitoringPlanStatus.ACTIVE
        updated_dict["activated_by"] = current_user.user_id
        updated_dict["activated_at"] = now
        updated_dict["updated_at"] = now

        saved = self.repo.save_monitoring_plan(AdoptionMonitoringPlanRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=plan.registration_id,
            event_type="governance_change_adoption.monitoring_activated",
            actor_id=current_user.user_id,
            summary=f"Monitoring plan '{saved.title}' activated.",
            details={"activation_notes": request.activation_notes},
        )
        return saved

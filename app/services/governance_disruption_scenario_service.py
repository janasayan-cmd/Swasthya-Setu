"""Phase 87: Disruption Scenario Management Service.

Coordinates the lifecycle of configurable disruption scenarios.
Separation of duties: Proposers cannot approve their own scenarios.
Hypothetical scenarios are strictly separated from live incidents.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_disruption_impact_repository import (
    GovernanceDisruptionImpactRepository,
    get_governance_disruption_impact_repository,
)
from app.schemas.governance_disruption_common import (
    DisruptionScenarioCategory,
    ScenarioReviewStatus,
)
from app.schemas.governance_disruption_scenario import (
    ApproveDisruptionScenarioRequest,
    CreateDisruptionScenarioRequest,
    DisruptionScenarioRecord,
    SubmitDisruptionScenarioRequest,
    UpdateDisruptionScenarioRequest,
)


class GovernanceDisruptionScenarioService:

    def __init__(self, repo: GovernanceDisruptionImpactRepository) -> None:
        self.repo = repo

    def create_scenario(
        self, tenant_id: str, user_id: str, request: CreateDisruptionScenarioRequest
    ) -> DisruptionScenarioRecord:
        now = datetime.utcnow()
        record = DisruptionScenarioRecord(
            scenario_id=f"scen-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            scenario_name=request.scenario_name,
            description=request.description,
            category=request.category,
            organizational_scope=request.organizational_scope,
            affected_resource_refs=request.affected_resource_refs,
            affected_capability_refs=request.affected_capability_refs,
            affected_responsibility_refs=request.affected_responsibility_refs,
            initial_disruption_conditions=request.initial_disruption_conditions,
            duration_type=request.duration_type,
            assumed_duration_hours=request.assumed_duration_hours,
            severity_assumption=request.severity_assumption,
            expected_operating_constraints=request.expected_operating_constraints,
            potential_recovery_conditions=request.potential_recovery_conditions,
            evidence_refs=request.evidence_refs,
            live_incident_ref=request.live_incident_ref,
            scenario_version="1.0",
            scenario_owner=user_id,
            review_status=ScenarioReviewStatus.DRAFT,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_scenario(record)

    def get_scenario(self, tenant_id: str, scenario_id: str) -> DisruptionScenarioRecord:
        record = self.repo.get_scenario(scenario_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.DISRUPTION_SCENARIO_NOT_FOUND,
                message=f"Disruption scenario '{scenario_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_scenarios(
        self,
        tenant_id: str,
        category: Optional[DisruptionScenarioCategory] = None,
        review_status: Optional[ScenarioReviewStatus] = None,
    ) -> List[DisruptionScenarioRecord]:
        return self.repo.list_scenarios(tenant_id, category, review_status)

    def update_scenario(
        self, tenant_id: str, scenario_id: str, user_id: str, request: UpdateDisruptionScenarioRequest
    ) -> DisruptionScenarioRecord:
        record = self.get_scenario(tenant_id, scenario_id)
        if record.review_status in (ScenarioReviewStatus.ARCHIVED, ScenarioReviewStatus.SUPERSEDED):
            raise AppException(
                code=ErrorCode.INVALID_DISRUPTION_SCENARIO_STATE,
                message=f"Cannot update scenario in '{record.review_status}' state.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        record.updated_at = datetime.utcnow()
        return self.repo.save_scenario(record)

    def submit_scenario(
        self, tenant_id: str, scenario_id: str, user_id: str, request: SubmitDisruptionScenarioRequest
    ) -> DisruptionScenarioRecord:
        record = self.get_scenario(tenant_id, scenario_id)
        if record.review_status != ScenarioReviewStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_DISRUPTION_SCENARIO_STATE,
                message="Only DRAFT scenarios can be submitted for review.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        record.review_status = ScenarioReviewStatus.SUBMITTED
        record.updated_at = datetime.utcnow()
        return self.repo.save_scenario(record)

    def approve_scenario(
        self, tenant_id: str, scenario_id: str, approver_id: str, request: ApproveDisruptionScenarioRequest
    ) -> DisruptionScenarioRecord:
        record = self.get_scenario(tenant_id, scenario_id)
        if record.created_by == approver_id:
            raise AppException(
                code=ErrorCode.DISRUPTION_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties: Scenario creator cannot approve their own scenario.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if record.review_status != ScenarioReviewStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_DISRUPTION_SCENARIO_STATE,
                message=f"Cannot approve scenario in '{record.review_status}' state. Must be SUBMITTED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        now = datetime.utcnow()
        record.review_status = ScenarioReviewStatus.APPROVED
        record.approval_ref = request.approval_ref
        record.approved_by = approver_id
        record.approved_at = now
        record.updated_at = now
        return self.repo.save_scenario(record)


_scenario_service: Optional[GovernanceDisruptionScenarioService] = None


def get_governance_disruption_scenario_service() -> GovernanceDisruptionScenarioService:
    global _scenario_service
    if _scenario_service is None:
        _scenario_service = GovernanceDisruptionScenarioService(
            get_governance_disruption_impact_repository()
        )
    return _scenario_service

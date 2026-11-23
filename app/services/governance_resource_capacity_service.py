"""Phase 86: Resource Capacity Requirements Service.

Tracks minimum operating requirements and evaluates capacity shortfalls.
Unverified capacity estimates are NEVER treated as confirmed operational capability.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_resource_capacity import (
    CapacityRequirementRecord,
    CreateCapacityRequirementRequest,
    EvaluateCapacityRequest,
)


class GovernanceResourceCapacityService:

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def create_requirement(
        self, tenant_id: str, user_id: str, request: CreateCapacityRequirementRequest
    ) -> CapacityRequirementRecord:
        resource = self.repo.get_resource(request.resource_id, tenant_id)
        if not resource:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"Resource '{request.resource_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        now = datetime.utcnow()
        record = CapacityRequirementRecord(
            requirement_id=f"cap-req-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            governance_capability_ref=request.governance_capability_ref,
            resource_id=request.resource_id,
            minimum_availability_pct=request.minimum_availability_pct,
            max_acceptable_interruption_minutes=request.max_acceptable_interruption_minutes,
            min_service_capacity_pct=request.min_service_capacity_pct,
            min_information_accessibility_pct=request.min_information_accessibility_pct,
            required_communication_capacity=request.required_communication_capacity,
            max_acceptable_dependency_concentration=request.max_acceptable_dependency_concentration,
            continuity_requirement_ref=request.continuity_requirement_ref,
            required_capacity_note=request.required_capacity_note,
            evaluation_status="NOT_EVALUATED",
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_capacity_requirement(record)

    def get_requirement(self, tenant_id: str, requirement_id: str) -> CapacityRequirementRecord:
        record = self.repo.get_capacity_requirement(requirement_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPACITY_REQUIREMENT_NOT_FOUND,
                message=f"Capacity requirement '{requirement_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_requirements(
        self,
        tenant_id: str,
        resource_id: Optional[str] = None,
        capability_ref: Optional[str] = None,
    ) -> List[CapacityRequirementRecord]:
        return self.repo.list_capacity_requirements(tenant_id, resource_id, capability_ref)

    def evaluate_capacity(
        self,
        tenant_id: str,
        requirement_id: str,
        evaluator_id: str,
        request: EvaluateCapacityRequest,
    ) -> CapacityRequirementRecord:
        record = self.get_requirement(tenant_id, requirement_id)
        now = datetime.utcnow()
        record.reported_capacity_pct = request.reported_capacity_pct
        record.verified_capacity_pct = request.verified_capacity_pct
        record.evidence_freshness_hours = request.evidence_freshness_hours
        record.applicable_scenario = request.applicable_scenario

        # Calculate shortfall (compare against verified, not reported)
        if request.verified_capacity_pct is not None:
            shortfall = record.minimum_availability_pct - request.verified_capacity_pct
            record.capacity_shortfall_pct = max(0.0, shortfall)
            if record.capacity_shortfall_pct > 0:
                record.evaluation_status = "CAPACITY_SHORTFALL_DETECTED"
            else:
                record.evaluation_status = "CAPACITY_MET"
        else:
            # Unverified estimate — never treat as confirmed
            record.evaluation_status = "UNVERIFIED_ESTIMATE_ONLY"

        record.last_evaluated_at = now
        record.updated_at = now
        return self.repo.save_capacity_requirement(record)


_capacity_service: Optional[GovernanceResourceCapacityService] = None


def get_governance_resource_capacity_service() -> GovernanceResourceCapacityService:
    global _capacity_service
    if _capacity_service is None:
        _capacity_service = GovernanceResourceCapacityService(
            get_governance_resource_dependency_repository()
        )
    return _capacity_service

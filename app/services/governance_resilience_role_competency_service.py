"""Phase 84: Role Competency Requirements Service.

Configures and governs role-specific competency requirements, mapping resilience roles
to required capabilities, proficiencies, and primary/backup criteria.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_role_competency import (
    ApproveRoleRequirementRequest,
    CreateRoleRequirementRequest,
    RoleCapabilityRequirementRecord,
    RoleRequirementStatus,
    UpdateRoleRequirementRequest,
)


class GovernanceResilienceRoleCompetencyService:
    """Service managing role-to-capability mappings and competency requirement standards."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def create_role_requirement(
        self,
        tenant_id: str,
        user_id: str,
        request: CreateRoleRequirementRequest,
    ) -> RoleCapabilityRequirementRecord:
        framework = self.repository.get_framework(request.framework_id, tenant_id)
        if not framework:
            raise AppException(
                code=ErrorCode.CAPABILITY_FRAMEWORK_NOT_FOUND,
                message=f"Capability framework '{request.framework_id}' not found.",
                status_code=404,
            )

        req_id = f"rcr-{uuid.uuid4().hex[:10]}"
        record = RoleCapabilityRequirementRecord(
            requirement_id=req_id,
            tenant_id=tenant_id,
            role_name=request.role_name,
            framework_id=request.framework_id,
            framework_version=request.framework_version,
            organizational_scope=request.organizational_scope,
            required_capabilities=request.required_capabilities,
            status=RoleRequirementStatus.DRAFT,
            created_by=user_id,
        )
        return self.repository.save_role_requirement(record)

    def get_role_requirement(
        self, tenant_id: str, requirement_id: str
    ) -> RoleCapabilityRequirementRecord:
        record = self.repository.get_role_requirement(requirement_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.ROLE_CAPABILITY_REQUIREMENT_NOT_FOUND,
                message=f"Role capability requirement '{requirement_id}' not found.",
                status_code=404,
            )
        return record

    def update_role_requirement(
        self,
        tenant_id: str,
        requirement_id: str,
        user_id: str,
        request: UpdateRoleRequirementRequest,
    ) -> RoleCapabilityRequirementRecord:
        record = self.get_role_requirement(tenant_id, requirement_id)

        if record.status == RoleRequirementStatus.SUPERSEDED:
            raise AppException(
                code=ErrorCode.INVALID_ROLE_CAPABILITY_REQUIREMENT_STATE,
                message="Cannot update a superseded role requirement.",
                status_code=400,
            )

        if request.required_capabilities is not None:
            record.required_capabilities = request.required_capabilities
        if request.organizational_scope is not None:
            record.organizational_scope = request.organizational_scope

        record.updated_at = datetime.utcnow()
        return self.repository.save_role_requirement(record)

    def approve_role_requirement(
        self,
        tenant_id: str,
        requirement_id: str,
        approver_id: str,
        request: ApproveRoleRequirementRequest,
    ) -> RoleCapabilityRequirementRecord:
        record = self.get_role_requirement(tenant_id, requirement_id)

        # Separation of duties: Creator cannot approve own role requirement
        if approver_id == record.created_by:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Creator cannot independently approve their own role capability requirement.",
                status_code=400,
            )

        record.status = RoleRequirementStatus.APPROVED
        record.approved_by = approver_id
        record.updated_at = datetime.utcnow()
        return self.repository.save_role_requirement(record)

    def list_role_requirements(
        self,
        tenant_id: str,
        role_name: Optional[str] = None,
        framework_id: Optional[str] = None,
        status: Optional[RoleRequirementStatus] = None,
    ) -> List[RoleCapabilityRequirementRecord]:
        return self.repository.list_role_requirements(
            tenant_id=tenant_id,
            role_name=role_name,
            framework_id=framework_id,
            status=status,
        )


_role_competency_service = GovernanceResilienceRoleCompetencyService()


def get_governance_resilience_role_competency_service() -> GovernanceResilienceRoleCompetencyService:
    return _role_competency_service

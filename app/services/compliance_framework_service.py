"""Phase 69: Compliance Framework & Requirement Management Service.

Coordinates:
- Registration and lifecycle management of governance frameworks
- Requirement versioning, approval, and activation
- Traceable requirement-to-control mappings
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_compliance_repository import (
    GovernanceComplianceRepository,
    get_governance_compliance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.compliance_framework import (
    ActivateRequirementRequest,
    ApproveRequirementRequest,
    ComplianceFrameworkRecord,
    ComplianceRequirementRecord,
    CreateControlMappingRequest,
    CreateFrameworkRequest,
    CreateRequirementRequest,
    FrameworkLifecycleStatus,
    RequirementControlMappingRecord,
    RequirementLifecycleStatus,
)
from app.schemas.user import AuthenticatedUserContext


class ComplianceFrameworkService:
    """Service managing compliance frameworks, requirements, and control mappings."""

    def __init__(self, repository: Optional[GovernanceComplianceRepository] = None) -> None:
        self.repository = repository or get_governance_compliance_repository()

    # -------------------------------------------------------------------------
    # Framework Operations
    # -------------------------------------------------------------------------

    def create_framework(
        self, user: AuthenticatedUserContext, payload: CreateFrameworkRequest
    ) -> ComplianceFrameworkRecord:
        """Register a new governance compliance framework."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role is not authorized to register compliance frameworks.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = ComplianceFrameworkRecord(
            name=payload.name,
            version=payload.version or "v1.0.0",
            framework_type=payload.framework_type,
            description=payload.description,
            organization_id=user.organization_id,
            facility_id=payload.facility_id or user.facility_id,
            effective_date=payload.effective_date or now,
            expiry_date=payload.expiry_date,
            lifecycle_status=FrameworkLifecycleStatus.ACTIVE,
            created_by=user.user_id,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_framework(record)

    def get_framework(
        self, user: AuthenticatedUserContext, framework_id: str
    ) -> ComplianceFrameworkRecord:
        """Retrieve a framework ensuring tenant boundary isolation."""
        framework = self.repository.get_framework(framework_id)
        if not framework:
            raise AppException(
                code=ErrorCode.COMPLIANCE_FRAMEWORK_NOT_FOUND,
                message=f"Compliance framework {framework_id} not found.",
                status_code=404,
            )
        if framework.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access compliance framework across tenant boundaries.",
                status_code=403,
            )
        return framework

    def list_frameworks(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        framework_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ComplianceFrameworkRecord]:
        """List registered frameworks within tenant scope."""
        return self.repository.list_frameworks(
            organization_id=user.organization_id,
            facility_id=facility_id,
            framework_type=framework_type,
            limit=limit,
            offset=offset,
        )

    # -------------------------------------------------------------------------
    # Requirement Operations
    # -------------------------------------------------------------------------

    def create_requirement(
        self, user: AuthenticatedUserContext, payload: CreateRequirementRequest
    ) -> ComplianceRequirementRecord:
        """Register a requirement under a framework in DRAFT status."""
        framework = self.get_framework(user, payload.framework_id)

        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create compliance requirements.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = ComplianceRequirementRecord(
            framework_id=framework.framework_id,
            framework_version=framework.version,
            requirement_code=payload.requirement_code,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            organization_id=user.organization_id,
            facility_id=payload.facility_id or framework.facility_id,
            effective_date=payload.effective_date,
            expiry_date=payload.expiry_date,
            owner_id=payload.owner_id or user.user_id,
            owner_role=payload.owner_role or user.role.value,
            related_policy_refs=payload.related_policy_refs or [],
            related_control_refs=payload.related_control_refs or [],
            expected_evidence_types=payload.expected_evidence_types or [],
            assessment_frequency=payload.assessment_frequency or "MONTHLY",
            review_requirements=payload.review_requirements,
            lifecycle_status=RequirementLifecycleStatus.DRAFT,
            version="v1.0.0",
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_requirement(record)

    def get_requirement(
        self, user: AuthenticatedUserContext, requirement_id: str
    ) -> ComplianceRequirementRecord:
        """Retrieve requirement ensuring tenant scoping."""
        req = self.repository.get_requirement(requirement_id)
        if not req:
            raise AppException(
                code=ErrorCode.COMPLIANCE_REQUIREMENT_NOT_FOUND,
                message=f"Compliance requirement {requirement_id} not found.",
                status_code=404,
            )
        if req.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access requirement across tenant boundaries.",
                status_code=403,
            )
        return req

    def list_requirements(
        self,
        user: AuthenticatedUserContext,
        framework_id: Optional[str] = None,
        category: Optional[str] = None,
        lifecycle_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ComplianceRequirementRecord]:
        """List requirements within tenant scope."""
        return self.repository.list_requirements(
            organization_id=user.organization_id,
            framework_id=framework_id,
            category=category,
            lifecycle_status=lifecycle_status,
            limit=limit,
            offset=offset,
        )

    def approve_requirement(
        self,
        user: AuthenticatedUserContext,
        requirement_id: str,
        payload: ApproveRequirementRequest,
    ) -> ComplianceRequirementRecord:
        """Approve a DRAFT or UNDER_REVIEW requirement."""
        req = self.get_requirement(user, requirement_id)

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can approve requirements.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        req.lifecycle_status = RequirementLifecycleStatus.APPROVED
        req.approved_by = user.user_id
        req.approved_at = now
        if payload.effective_date:
            req.effective_date = payload.effective_date
        req.metadata["approval_rationale"] = payload.approval_rationale

        return self.repository.save_requirement(req)

    def activate_requirement(
        self,
        user: AuthenticatedUserContext,
        requirement_id: str,
        payload: ActivateRequirementRequest,
    ) -> ComplianceRequirementRecord:
        """Activate an APPROVED requirement. Cannot activate unapproved DRAFT requirements."""
        req = self.get_requirement(user, requirement_id)

        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can activate requirements.",
                status_code=403,
            )

        if req.lifecycle_status != RequirementLifecycleStatus.APPROVED:
            raise AppException(
                code=ErrorCode.REQUIREMENT_NOT_APPROVED,
                message=f"Requirement {requirement_id} must be APPROVED before activation (current: {req.lifecycle_status.value}).",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        req.lifecycle_status = RequirementLifecycleStatus.ACTIVE
        req.activated_by = user.user_id
        req.activated_at = now
        if not req.effective_date:
            req.effective_date = now
        req.metadata["activation_rationale"] = payload.activation_rationale

        return self.repository.save_requirement(req)

    # -------------------------------------------------------------------------
    # Control Mapping Operations
    # -------------------------------------------------------------------------

    def create_control_mapping(
        self, user: AuthenticatedUserContext, payload: CreateControlMappingRequest
    ) -> RequirementControlMappingRecord:
        """Map an active requirement to an authoritative workflow control."""
        req = self.get_requirement(user, payload.requirement_id)

        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot create control mappings.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        mapping = RequirementControlMappingRecord(
            requirement_id=req.requirement_id,
            control_id=payload.control_id,
            control_name=payload.control_name,
            control_owner_phase=payload.control_owner_phase,
            control_owner_id=payload.control_owner_id,
            control_purpose=payload.control_purpose,
            verification_method=payload.verification_method or "AUTOMATED_AUDIT",
            expected_evidence=payload.expected_evidence,
            mapping_status="APPROVED",
            approved_by=user.user_id,
            approved_at=now,
            policy_version=payload.policy_version or "v1.0.0",
            rationale=payload.rationale,
            created_at=now,
            metadata=payload.metadata or {},
        )
        return self.repository.save_control_mapping(mapping)

    def list_control_mappings(
        self, user: AuthenticatedUserContext, requirement_id: str
    ) -> List[RequirementControlMappingRecord]:
        """List control mappings for a requirement."""
        self.get_requirement(user, requirement_id)
        return self.repository.list_control_mappings(requirement_id)


# Global singleton instance
_global_framework_service = ComplianceFrameworkService()


def get_compliance_framework_service() -> ComplianceFrameworkService:
    """Dependency provider for compliance framework service."""
    return _global_framework_service

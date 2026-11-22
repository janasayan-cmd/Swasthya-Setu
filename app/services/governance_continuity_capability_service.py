"""Phase 80: Critical Governance Capability Inventory Service.

Manages registration, classification, human approval, and lifecycle tracking
of critical clinical safety governance capabilities.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_capability import (
    ApproveCapabilityRequest,
    CapabilityCriticalityTier,
    CapabilityInventoryStatus,
    ClinicalSafetyGovernanceCapabilityRecord,
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
    RegisterCapabilityRequest,
    SubmitCapabilityRequest,
    UpdateCapabilityRequest,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityCapabilityService:
    """Manages critical governance capability inventory, classification, and approvals."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def register_capability(
        self,
        tenant_id: str,
        author_id: str,
        request: RegisterCapabilityRequest,
    ) -> ClinicalSafetyGovernanceCapabilityRecord:
        cap_id = f"GCC-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = ClinicalSafetyGovernanceCapabilityRecord(
            capability_id=cap_id,
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            organizational_scope=request.organizational_scope or {},
            responsible_department=request.responsible_department,
            accountable_owner_id=request.accountable_owner_id,
            supporting_roles=request.supporting_roles or [],
            related_workflow=request.related_workflow,
            criticality=request.criticality,
            continuity_requirement_id=None,
            required_supporting_systems=request.required_supporting_systems or [],
            required_integrations=request.required_integrations or [],
            required_information_sources=request.required_information_sources or [],
            minimum_operational_requirements=request.minimum_operational_requirements,
            max_acceptable_interruption_hours=request.max_acceptable_interruption_hours,
            recovery_priority=request.recovery_priority,
            status=CapabilityInventoryStatus.DRAFT,
            approved_by=None,
            approval_reference=None,
            review_date=request.review_date,
            version=1,
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_capability(record)

    def update_capability(
        self,
        tenant_id: str,
        capability_id: str,
        request: UpdateCapabilityRequest,
    ) -> ClinicalSafetyGovernanceCapabilityRecord:
        cap = self.repository.get_capability(capability_id)
        if not cap or cap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_CAPABILITY_NOT_FOUND,
                message=f"Governance capability '{capability_id}' was not found.",
                status_code=404,
            )

        if cap.status not in (CapabilityInventoryStatus.DRAFT, CapabilityInventoryStatus.SUBMITTED):
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_CAPABILITY_STATE,
                message=f"Capability '{capability_id}' cannot be modified in status '{cap.status}'.",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        updated = cap.model_copy(
            update={
                "name": request.name if request.name is not None else cap.name,
                "description": request.description if request.description is not None else cap.description,
                "responsible_department": request.responsible_department if request.responsible_department is not None else cap.responsible_department,
                "accountable_owner_id": request.accountable_owner_id if request.accountable_owner_id is not None else cap.accountable_owner_id,
                "supporting_roles": request.supporting_roles if request.supporting_roles is not None else cap.supporting_roles,
                "criticality": request.criticality if request.criticality is not None else cap.criticality,
                "minimum_operational_requirements": request.minimum_operational_requirements if request.minimum_operational_requirements is not None else cap.minimum_operational_requirements,
                "max_acceptable_interruption_hours": request.max_acceptable_interruption_hours if request.max_acceptable_interruption_hours is not None else cap.max_acceptable_interruption_hours,
                "recovery_priority": request.recovery_priority if request.recovery_priority is not None else cap.recovery_priority,
                "review_date": request.review_date if request.review_date is not None else cap.review_date,
                "updated_at": now_str,
            }
        )
        return self.repository.save_capability(updated)

    def submit_capability(
        self,
        tenant_id: str,
        author_id: str,
        capability_id: str,
        request: SubmitCapabilityRequest,
    ) -> ClinicalSafetyGovernanceCapabilityRecord:
        cap = self.repository.get_capability(capability_id)
        if not cap or cap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_CAPABILITY_NOT_FOUND,
                message=f"Governance capability '{capability_id}' was not found.",
                status_code=404,
            )

        if cap.status != CapabilityInventoryStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_CAPABILITY_STATE,
                message=f"Capability '{capability_id}' cannot be submitted from status '{cap.status}'.",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        updated = cap.model_copy(
            update={
                "status": CapabilityInventoryStatus.SUBMITTED,
                "updated_at": now_str,
            }
        )
        return self.repository.save_capability(updated)

    def approve_capability(
        self,
        tenant_id: str,
        approver_id: str,
        capability_id: str,
        request: ApproveCapabilityRequest,
    ) -> ClinicalSafetyGovernanceCapabilityRecord:
        cap = self.repository.get_capability(capability_id)
        if not cap or cap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_CAPABILITY_NOT_FOUND,
                message=f"Governance capability '{capability_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: accountable owner cannot approve their own capability classification
        if approver_id == cap.accountable_owner_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Accountable capability owners cannot approve their own capability classification.",
                status_code=403,
            )

        if cap.status != CapabilityInventoryStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_CAPABILITY_STATE,
                message=f"Capability '{capability_id}' must be in SUBMITTED status to approve (currently '{cap.status}').",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        updated = cap.model_copy(
            update={
                "status": CapabilityInventoryStatus.APPROVED,
                "approved_by": approver_id,
                "approval_reference": request.approval_reference,
                "updated_at": now_str,
            }
        )
        return self.repository.save_capability(updated)

    def get_capability(
        self,
        tenant_id: str,
        capability_id: str,
    ) -> ClinicalSafetyGovernanceCapabilityRecord:
        cap = self.repository.get_capability(capability_id)
        if not cap or cap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_CAPABILITY_NOT_FOUND,
                message=f"Governance capability '{capability_id}' was not found.",
                status_code=404,
            )
        return cap

    def list_capabilities(
        self,
        tenant_id: str,
        criticality: Optional[CapabilityCriticalityTier] = None,
        status: Optional[CapabilityInventoryStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ClinicalSafetyGovernanceCapabilityRecord]:
        return self.repository.list_capabilities(
            tenant_id=tenant_id,
            criticality=criticality,
            status=status,
            skip=skip,
            limit=limit,
        )

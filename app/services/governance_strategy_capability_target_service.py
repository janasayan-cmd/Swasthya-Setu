"""Phase 78: Governance Capability Target Service.

Manages desired future governance capability targets and links Phase 77 assessment baselines.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_capability_target import (
    CapabilityDomainEnum,
    CapabilityTargetStatus,
    CreateCapabilityTargetRequest,
    GovernanceCapabilityTargetRecord,
    UpdateCapabilityTargetRequest,
)
from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyCapabilityTargetService:
    """Manages target capability operating states."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def create_target(
        self,
        tenant_id: str,
        request: CreateCapabilityTargetRequest,
    ) -> GovernanceCapabilityTargetRecord:
        now = _get_utc_now_str()
        target = GovernanceCapabilityTargetRecord(
            target_id=f"gct-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            capability_domain=request.capability_domain,
            title=request.title,
            current_state_description=request.current_state_description,
            current_maturity_reference=request.current_maturity_reference,
            desired_future_state_description=request.desired_future_state_description,
            target_maturity_level=request.target_maturity_level,
            organizational_scope=request.organizational_scope or {},
            planned_milestone_id=request.planned_milestone_id,
            responsible_owner_id=request.responsible_owner_id,
            evidence_required=request.evidence_required or [],
            review_criteria=request.review_criteria,
            status=CapabilityTargetStatus.PROPOSED,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_capability_target(target)

    def update_target(
        self,
        tenant_id: str,
        target_id: str,
        request: UpdateCapabilityTargetRequest,
    ) -> GovernanceCapabilityTargetRecord:
        target = self.repository.get_capability_target(target_id)
        if not target or target.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_CAPABILITY_TARGET_NOT_FOUND,
                message=f"Capability target '{target_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        update_data = {}
        if request.desired_future_state_description is not None:
            update_data["desired_future_state_description"] = request.desired_future_state_description
        if request.target_maturity_level is not None:
            update_data["target_maturity_level"] = request.target_maturity_level
        if request.status is not None:
            update_data["status"] = request.status
        if request.planned_milestone_id is not None:
            update_data["planned_milestone_id"] = request.planned_milestone_id

        update_data["updated_at"] = now
        target = target.model_copy(update=update_data)
        return self.repository.save_capability_target(target)

    def get_target(
        self,
        tenant_id: str,
        target_id: str,
    ) -> GovernanceCapabilityTargetRecord:
        target = self.repository.get_capability_target(target_id)
        if not target or target.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_CAPABILITY_TARGET_NOT_FOUND,
                message=f"Capability target '{target_id}' was not found.",
                status_code=404,
            )
        return target

    def list_targets(
        self,
        tenant_id: str,
        domain: Optional[CapabilityDomainEnum] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceCapabilityTargetRecord]:
        return self.repository.list_capability_targets(
            tenant_id=tenant_id,
            domain=domain,
            skip=skip,
            limit=limit,
        )

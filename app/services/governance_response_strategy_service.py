"""
Phase 88: Governance Response Strategy Service
Handles creation, review, SoD enforcement, and lifecycle management of response strategies.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import status

from app.core.exceptions import (
    AppException,
    ErrorCode,
)
from app.repositories.governance_response_strategy_repository import (
    GovernanceResponseStrategyRepository,
    get_governance_response_strategy_repository,
)
from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    ResponseStrategyCategory,
    StrategyReviewStatus,
)
from app.schemas.governance_response_strategy import (
    ApproveResponseStrategyRequest,
    CreateResponseStrategyRequest,
    ResponseStrategyRecord,
    SubmitResponseStrategyRequest,
    UpdateResponseStrategyRequest,
)


class GovernanceResponseStrategyService:
    def __init__(self, repo: Optional[GovernanceResponseStrategyRepository] = None):
        self.repo = repo or get_governance_response_strategy_repository()

    def create_response_strategy(
        self,
        tenant_id: str,
        user_id: str,
        req: CreateResponseStrategyRequest,
    ) -> ResponseStrategyRecord:
        now = datetime.now(timezone.utc)
        record = ResponseStrategyRecord(
            strategy_id=f"strat-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            strategy_name=req.strategy_name,
            description=req.description,
            category=req.category,
            organizational_scope=req.organizational_scope,
            applicable_scenario_ids=list(req.applicable_scenario_ids),
            affected_capability_refs=list(req.affected_capability_refs),
            required_resource_refs=list(req.required_resource_refs),
            required_role_refs=list(req.required_role_refs),
            required_authorization_refs=list(req.required_authorization_refs),
            dependency_requirements=list(req.dependency_requirements),
            preconditions=list(req.preconditions),
            operational_constraints=list(req.operational_constraints),
            expected_limitations=list(req.expected_limitations),
            evidence_refs=list(req.evidence_refs),
            strategy_version="1.0",
            strategy_owner=user_id,
            review_status=StrategyReviewStatus.DRAFT,
            approval_requirements=req.approval_requirements,
            approval_ref=None,
            approved_by=None,
            approved_at=None,
            effective_start=req.effective_start,
            effective_end=req.effective_end,
            created_by=user_id,
            created_at=now,
            updated_at=now,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )
        return self.repo.create_strategy(record)

    def get_response_strategy(
        self,
        strategy_id: str,
        tenant_id: str,
    ) -> ResponseStrategyRecord:
        record = self.repo.get_strategy(strategy_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.RESPONSE_STRATEGY_NOT_FOUND,
                message=f"Response strategy '{strategy_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_response_strategies(
        self,
        tenant_id: str,
        category: Optional[ResponseStrategyCategory] = None,
        status_param: Optional[StrategyReviewStatus] = None,
        scenario_ref: Optional[str] = None,
        capability_ref: Optional[str] = None,
    ) -> List[ResponseStrategyRecord]:
        return self.repo.list_strategies(
            tenant_id=tenant_id,
            category=category,
            review_status=status_param,
            scenario_ref=scenario_ref,
            capability_ref=capability_ref,
        )

    def update_response_strategy(
        self,
        strategy_id: str,
        tenant_id: str,
        user_id: str,
        req: UpdateResponseStrategyRequest,
    ) -> ResponseStrategyRecord:
        record = self.get_response_strategy(strategy_id, tenant_id)
        if record.review_status in [StrategyReviewStatus.ARCHIVED, StrategyReviewStatus.REJECTED]:
            raise AppException(
                code=ErrorCode.INVALID_RESPONSE_STRATEGY_STATE,
                message=f"Cannot update strategy '{strategy_id}' in state '{record.review_status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        now = datetime.now(timezone.utc)
        if req.strategy_name is not None:
            record.strategy_name = req.strategy_name
        if req.description is not None:
            record.description = req.description
        if req.category is not None:
            record.category = req.category
        if req.organizational_scope is not None:
            record.organizational_scope = req.organizational_scope
        if req.applicable_scenario_ids is not None:
            record.applicable_scenario_ids = list(req.applicable_scenario_ids)
        if req.affected_capability_refs is not None:
            record.affected_capability_refs = list(req.affected_capability_refs)
        if req.required_resource_refs is not None:
            record.required_resource_refs = list(req.required_resource_refs)
        if req.required_role_refs is not None:
            record.required_role_refs = list(req.required_role_refs)
        if req.required_authorization_refs is not None:
            record.required_authorization_refs = list(req.required_authorization_refs)
        if req.dependency_requirements is not None:
            record.dependency_requirements = list(req.dependency_requirements)
        if req.preconditions is not None:
            record.preconditions = list(req.preconditions)
        if req.operational_constraints is not None:
            record.operational_constraints = list(req.operational_constraints)
        if req.expected_limitations is not None:
            record.expected_limitations = list(req.expected_limitations)
        if req.evidence_refs is not None:
            record.evidence_refs = list(req.evidence_refs)
        if req.effective_end is not None:
            record.effective_end = req.effective_end

        record.updated_at = now
        return self.repo.update_strategy(record)

    def submit_response_strategy(
        self,
        strategy_id: str,
        tenant_id: str,
        user_id: str,
        req: SubmitResponseStrategyRequest,
    ) -> ResponseStrategyRecord:
        record = self.get_response_strategy(strategy_id, tenant_id)
        if record.review_status != StrategyReviewStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_RESPONSE_STRATEGY_STATE,
                message=f"Strategy '{strategy_id}' in state '{record.review_status}' cannot be submitted for review.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        now = datetime.now(timezone.utc)
        record.review_status = StrategyReviewStatus.SUBMITTED
        record.updated_at = now
        return self.repo.update_strategy(record)

    def approve_response_strategy(
        self,
        strategy_id: str,
        tenant_id: str,
        approver_id: str,
        req: ApproveResponseStrategyRequest,
    ) -> ResponseStrategyRecord:
        record = self.get_response_strategy(strategy_id, tenant_id)
        if record.review_status != StrategyReviewStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_RESPONSE_STRATEGY_STATE,
                message=f"Strategy '{strategy_id}' must be in SUBMITTED state to be approved (current: {record.review_status}).",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        # Enforce Separation of Duties (SoD)
        if record.created_by == approver_id:
            raise AppException(
                code=ErrorCode.RESPONSE_STRATEGY_SEPARATION_OF_DUTIES_VIOLATION,
                message=f"Separation of duties violation: Proposer '{record.created_by}' cannot approve their own response strategy.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        now = datetime.now(timezone.utc)
        record.review_status = StrategyReviewStatus.APPROVED
        record.approved_by = approver_id
        record.approved_at = now
        record.approval_ref = req.approval_ref
        record.updated_at = now
        return self.repo.update_strategy(record)

    def archive_response_strategy(
        self,
        strategy_id: str,
        tenant_id: str,
        user_id: str,
    ) -> ResponseStrategyRecord:
        record = self.get_response_strategy(strategy_id, tenant_id)
        now = datetime.now(timezone.utc)
        record.review_status = StrategyReviewStatus.ARCHIVED
        record.updated_at = now
        return self.repo.update_strategy(record)


_governance_response_strategy_service: Optional[GovernanceResponseStrategyService] = None


def get_governance_response_strategy_service() -> GovernanceResponseStrategyService:
    global _governance_response_strategy_service
    if _governance_response_strategy_service is None:
        _governance_response_strategy_service = GovernanceResponseStrategyService()
    return _governance_response_strategy_service

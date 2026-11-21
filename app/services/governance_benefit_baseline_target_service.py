"""Phase 76: Benefit Baseline & Target Management Service.

Coordinates:
- Creation and versioning of measurable benefit baselines and targets
- Explicit approval workflows with separation of duties enforcement
- Historical version preservation preventing silent metric overwrites
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_benefit_assurance_repository import (
    GovernanceBenefitAssuranceRepository,
    get_governance_benefit_assurance_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_benefit_baseline_target import (
    ApproveBaselineRequest,
    ApproveTargetRequest,
    BaselineStatus,
    BenefitBaselineRecord,
    BenefitTargetRecord,
    CreateBaselineRequest,
    CreateTargetRequest,
    SubmitBaselineRequest,
    SubmitTargetRequest,
    TargetStatus,
)


class GovernanceBenefitBaselineTargetService:
    """Service governing versioned benefit baselines, targets, and approval integrity."""

    def __init__(
        self,
        repository: Optional[GovernanceBenefitAssuranceRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_benefit_assurance_repository()

    # -------------------------------------------------------------------------
    # Baselines
    # -------------------------------------------------------------------------

    def create_baseline(
        self,
        benefit_id: str,
        request: CreateBaselineRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitBaselineRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        existing = self.repo.list_baselines_for_benefit(benefit_id, user_tenant)
        new_version = (existing[0].version + 1) if existing else 1
        now = datetime.now(timezone.utc).isoformat()
        baseline_id = f"bsl_{uuid.uuid4().hex[:12]}"

        record = BenefitBaselineRecord(
            baseline_id=baseline_id,
            benefit_id=benefit_id,
            tenant_id=user_tenant,
            version=new_version,
            measurement_definition=request.measurement_definition,
            baseline_value=request.baseline_value,
            qualitative_state=request.qualitative_state,
            unit=request.unit,
            measurement_period=request.measurement_period,
            source_system=request.source_system,
            data_collection_method=request.data_collection_method,
            data_quality_requirements=request.data_quality_requirements,
            organizational_scope=request.organizational_scope,
            status=BaselineStatus.DRAFT,
            created_by=current_user.user_id,
            created_at=now,
            change_reason=request.change_reason,
        )
        return self.repo.save_baseline(record)

    def list_baselines(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[BenefitBaselineRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_baselines_for_benefit(benefit_id, user_tenant)

    def submit_baseline(
        self,
        baseline_id: str,
        request: SubmitBaselineRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitBaselineRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        baseline = self.repo.get_baseline(baseline_id)
        if not baseline or baseline.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_BASELINE_NOT_FOUND,
                message=f"Baseline '{baseline_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if baseline.status != BaselineStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_BENEFIT_BASELINE_STATE,
                message=f"Baseline is in status '{baseline.status.value}', only DRAFT baselines can be submitted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        baseline.status = BaselineStatus.SUBMITTED
        baseline.submitted_by = current_user.user_id
        baseline.submitted_at = now
        return self.repo.save_baseline(baseline)

    def approve_baseline(
        self,
        baseline_id: str,
        request: ApproveBaselineRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitBaselineRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        baseline = self.repo.get_baseline(baseline_id)
        if not baseline or baseline.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_BASELINE_NOT_FOUND,
                message=f"Baseline '{baseline_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if baseline.status != BaselineStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_BENEFIT_BASELINE_STATE,
                message=f"Baseline is in status '{baseline.status.value}', only SUBMITTED baselines can be approved.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Separation of duties: creator cannot approve
        if baseline.created_by == current_user.user_id:
            raise AppException(
                code=ErrorCode.BENEFIT_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: baseline creator cannot approve their own baseline.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Supersede existing approved baseline for this benefit
        existing = self.repo.list_baselines_for_benefit(baseline.benefit_id, user_tenant)
        for b in existing:
            if b.status == BaselineStatus.APPROVED and b.baseline_id != baseline_id:
                b.status = BaselineStatus.SUPERSEDED
                self.repo.save_baseline(b)

        now = datetime.now(timezone.utc).isoformat()
        baseline.status = BaselineStatus.APPROVED
        baseline.approved_by = current_user.user_id
        baseline.approved_at = now
        baseline.approval_reference = request.approval_reference
        baseline.approval_notes = request.approval_notes
        saved = self.repo.save_baseline(baseline)

        # Update active_baseline_id on benefit
        benefit = self.repo.get_benefit(baseline.benefit_id)
        if benefit:
            benefit.active_baseline_id = baseline_id
            benefit.updated_at = now
            self.repo.save_benefit(benefit)

        return saved

    # -------------------------------------------------------------------------
    # Targets
    # -------------------------------------------------------------------------

    def create_target(
        self,
        benefit_id: str,
        request: CreateTargetRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitTargetRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        existing = self.repo.list_targets_for_benefit(benefit_id, user_tenant)
        new_version = (existing[0].version + 1) if existing else 1
        now = datetime.now(timezone.utc).isoformat()
        target_id = f"tgt_{uuid.uuid4().hex[:12]}"

        record = BenefitTargetRecord(
            target_id=target_id,
            benefit_id=benefit_id,
            tenant_id=user_tenant,
            version=new_version,
            target_value=request.target_value,
            target_condition=request.target_condition,
            target_measurement_date=request.target_measurement_date,
            unit=request.unit,
            measurement_method=request.measurement_method,
            required_evidence=request.required_evidence,
            organizational_scope=request.organizational_scope,
            status=TargetStatus.DRAFT,
            created_by=current_user.user_id,
            created_at=now,
            review_date=request.review_date,
            change_reason=request.change_reason,
        )
        return self.repo.save_target(record)

    def list_targets(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[BenefitTargetRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_targets_for_benefit(benefit_id, user_tenant)

    def submit_target(
        self,
        target_id: str,
        request: SubmitTargetRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitTargetRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        target = self.repo.get_target(target_id)
        if not target or target.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_TARGET_NOT_FOUND,
                message=f"Target '{target_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if target.status != TargetStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_BENEFIT_TARGET_STATE,
                message=f"Target is in status '{target.status.value}', only DRAFT targets can be submitted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        target.status = TargetStatus.SUBMITTED
        target.submitted_by = current_user.user_id
        target.submitted_at = now
        return self.repo.save_target(target)

    def approve_target(
        self,
        target_id: str,
        request: ApproveTargetRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitTargetRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        target = self.repo.get_target(target_id)
        if not target or target.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_TARGET_NOT_FOUND,
                message=f"Target '{target_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if target.status != TargetStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_BENEFIT_TARGET_STATE,
                message=f"Target is in status '{target.status.value}', only SUBMITTED targets can be approved.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Separation of duties: creator cannot approve
        if target.created_by == current_user.user_id:
            raise AppException(
                code=ErrorCode.BENEFIT_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: target creator cannot approve their own target.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Supersede existing approved target for this benefit
        existing = self.repo.list_targets_for_benefit(target.benefit_id, user_tenant)
        for t in existing:
            if t.status == TargetStatus.APPROVED and t.target_id != target_id:
                t.status = TargetStatus.SUPERSEDED
                self.repo.save_target(t)

        now = datetime.now(timezone.utc).isoformat()
        target.status = TargetStatus.APPROVED
        target.approved_by = current_user.user_id
        target.approved_at = now
        target.approval_reference = request.approval_reference
        target.approval_notes = request.approval_notes
        saved = self.repo.save_target(target)

        # Update active_target_id on benefit
        benefit = self.repo.get_benefit(target.benefit_id)
        if benefit:
            benefit.active_target_id = target_id
            benefit.updated_at = now
            self.repo.save_benefit(benefit)

        return saved

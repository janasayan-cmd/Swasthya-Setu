"""Phase 81: Continuity Assurance Framework Service.

Manages creation, revision, submission, and approval of version-controlled
continuity assurance frameworks.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_framework import (
    AssuranceDimension,
    ContinuityAssuranceFrameworkRecord,
    CreateContinuityAssuranceFrameworkRequest,
    DimensionCriterion,
    EvaluationMethod,
    FrameworkDimensionType,
    FrameworkStatus,
    ScoringMethod,
    UpdateContinuityAssuranceFrameworkRequest,
)


class GovernanceContinuityAssuranceFrameworkService:
    """Domain service for managing continuity assurance frameworks."""

    def __init__(self, repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository

    def create_framework(
        self,
        req: CreateContinuityAssuranceFrameworkRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityAssuranceFrameworkRecord:
        framework_id = f"GCAF-{uuid.uuid4().hex[:8].upper()}"

        dimensions = req.dimensions
        if not dimensions:
            dimensions = [
                AssuranceDimension(
                    dimension_id=f"DIM-{dim_type.value}",
                    dimension_type=dim_type,
                    name=dim_type.value.replace("_", " ").title(),
                    description=f"Assessment of {dim_type.value.lower()}",
                    evaluation_method=EvaluationMethod.DOCUMENTARY_REVIEW,
                    scoring_method=req.scoring_method,
                    criteria=[
                        DimensionCriterion(
                            criterion_id=f"CRIT-{dim_type.value}-1",
                            name=f"{dim_type.value} baseline validation",
                            description=f"Evidence of {dim_type.value.lower()} documented and approved",
                            required_evidence_type="GOVERNANCE_ARTIFACT",
                        )
                    ],
                )
                for dim_type in FrameworkDimensionType
            ]

        record = ContinuityAssuranceFrameworkRecord(
            framework_id=framework_id,
            framework_name=req.framework_name,
            description=req.description,
            version=1,
            status=FrameworkStatus.DRAFT,
            organizational_scope=req.organizational_scope,
            dimensions=dimensions,
            effective_date=req.effective_date,
            review_date=req.review_date,
            scoring_method=req.scoring_method,
            created_by=actor_id,
            created_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_framework(record)

    def update_framework(
        self,
        framework_id: str,
        req: UpdateContinuityAssuranceFrameworkRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityAssuranceFrameworkRecord:
        rec = self.repo.get_framework(framework_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework {framework_id} not found",
                status_code=404,
            )
        if rec.status != FrameworkStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_CONTINUITY_ASSURANCE_FRAMEWORK_STATE,
                message=f"Framework {framework_id} is in status {rec.status} and cannot be modified",
                status_code=400,
            )

        if req.framework_name is not None:
            rec.framework_name = req.framework_name
        if req.description is not None:
            rec.description = req.description
        if req.dimensions is not None:
            rec.dimensions = req.dimensions
        if req.review_date is not None:
            rec.review_date = req.review_date
        if req.scoring_method is not None:
            rec.scoring_method = req.scoring_method

        return self.repo.save_framework(rec)

    def submit_framework(
        self,
        framework_id: str,
        actor_id: str,
        notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> ContinuityAssuranceFrameworkRecord:
        rec = self.repo.get_framework(framework_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework {framework_id} not found",
                status_code=404,
            )
        if rec.status != FrameworkStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_CONTINUITY_ASSURANCE_FRAMEWORK_STATE,
                message=f"Framework {framework_id} is not in DRAFT status",
                status_code=400,
            )

        rec.status = FrameworkStatus.SUBMITTED
        rec.submitted_by = actor_id
        rec.submitted_at = datetime.utcnow()
        return self.repo.save_framework(rec)

    def approve_framework(
        self,
        framework_id: str,
        actor_id: str,
        notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> ContinuityAssuranceFrameworkRecord:
        rec = self.repo.get_framework(framework_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework {framework_id} not found",
                status_code=404,
            )
        if rec.status != FrameworkStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_CONTINUITY_ASSURANCE_FRAMEWORK_STATE,
                message=f"Framework {framework_id} must be in SUBMITTED status to approve",
                status_code=400,
            )
        # Separation of duties: creator/submitter cannot approve
        if rec.created_by == actor_id or rec.submitted_by == actor_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Creator/submitter cannot approve their own continuity assurance framework",
                status_code=400,
            )

        rec.status = FrameworkStatus.APPROVED
        rec.approved_by = actor_id
        rec.approved_at = datetime.utcnow()
        rec.approval_notes = notes
        return self.repo.save_framework(rec)

    def get_framework(self, framework_id: str, tenant_id: str = "default") -> ContinuityAssuranceFrameworkRecord:
        rec = self.repo.get_framework(framework_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework {framework_id} not found",
                status_code=404,
            )
        return rec

    def list_frameworks(
        self,
        tenant_id: str = "default",
        status: Optional[FrameworkStatus] = None,
    ) -> List[ContinuityAssuranceFrameworkRecord]:
        return self.repo.list_frameworks(tenant_id, status)


# Module-level instance
governance_continuity_assurance_framework_service = GovernanceContinuityAssuranceFrameworkService()

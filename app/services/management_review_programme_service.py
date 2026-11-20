"""Phase 72: Clinical Safety Governance Management Review Programme Service.

Handles:
- Review programme definition, updates, and activation
- Programme governance review and authorization
- Querying and filtering programmes by organization and facility
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_management_review_repository import (
    GovernanceManagementReviewRepository,
    get_governance_management_review_repository,
)
from app.schemas.management_review_programme import (
    ApproveReviewProgrammeRequest,
    CreateReviewProgrammeRequest,
    ManagementReviewProgrammeRecord,
    ReviewProgrammeStatus,
    UpdateReviewProgrammeRequest,
)


class ManagementReviewProgrammeService:
    """Service governing management review programmes."""

    def __init__(
        self, repository: Optional[GovernanceManagementReviewRepository] = None
    ) -> None:
        self.repository = repository or get_governance_management_review_repository()

    def create_programme(
        self,
        request: CreateReviewProgrammeRequest,
        creator_id: str,
        creator_role: str,
        organization_id: str,
    ) -> ManagementReviewProgrammeRecord:
        """Establishes a new management review programme."""
        record = ManagementReviewProgrammeRecord(
            name=request.name,
            description=request.description,
            objectives=request.objectives or [],
            category=request.category,
            frequency=request.frequency,
            status=ReviewProgrammeStatus.DRAFT,
            responsible_owner_id=creator_id,
            responsible_owner_role=creator_role,
            participating_units=request.participating_units or [],
            applicable_domains=request.applicable_domains or [],
            organization_id=organization_id,
            facility_id=request.facility_id,
            created_by=creator_id,
            metadata=request.metadata or {},
        )
        return self.repository.save_programme(record)

    def get_programme(self, programme_id: str) -> ManagementReviewProgrammeRecord:
        """Retrieves an existing review programme."""
        record = self.repository.get_programme(programme_id)
        if not record:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_PROGRAMME_NOT_FOUND,
                message=f"Management review programme '{programme_id}' not found.",
            )
        return record

    def list_programmes(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementReviewProgrammeRecord]:
        """Lists programmes matching criteria."""
        return self.repository.list_programmes(
            organization_id=organization_id,
            facility_id=facility_id,
            status=status_filter,
            category=category,
            limit=limit,
            offset=offset,
        )

    def update_programme(
        self,
        programme_id: str,
        request: UpdateReviewProgrammeRequest,
        updater_id: str,
    ) -> ManagementReviewProgrammeRecord:
        """Updates review programme parameters."""
        record = self.get_programme(programme_id)
        if record.status in [ReviewProgrammeStatus.DEPRECATED]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message="Cannot update a deprecated review programme.",
            )

        if request.name is not None:
            record.name = request.name
        if request.description is not None:
            record.description = request.description
        if request.objectives is not None:
            record.objectives = request.objectives
        if request.frequency is not None:
            record.frequency = request.frequency
        if request.participating_units is not None:
            record.participating_units = request.participating_units
        if request.applicable_domains is not None:
            record.applicable_domains = request.applicable_domains
        if request.metadata is not None:
            record.metadata.update(request.metadata)

        record.updated_at = datetime.now(timezone.utc)
        return self.repository.save_programme(record)

    def approve_programme(
        self,
        programme_id: str,
        request: ApproveReviewProgrammeRequest,
        approver_id: str,
    ) -> ManagementReviewProgrammeRecord:
        """Formally approves and activates a review programme."""
        record = self.get_programme(programme_id)
        if record.status != ReviewProgrammeStatus.DRAFT:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Programme in status '{record.status.value}' cannot be approved.",
            )

        record.status = ReviewProgrammeStatus.APPROVED
        record.approved_by = approver_id
        record.approved_at = datetime.now(timezone.utc)
        record.approval_policy_ref = request.approval_policy_ref
        if request.approval_rationale:
            record.metadata["approval_rationale"] = request.approval_rationale

        return self.repository.save_programme(record)

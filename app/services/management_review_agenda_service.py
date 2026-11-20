"""Phase 72: Clinical Safety Governance Management Review Agenda & Package Service.

Handles:
- Agenda item creation, reordering, and status progression
- Cross-phase input gathering from upstream governance workflows (Phases 49-71)
- Reproducible review package compilation and version locking
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_management_review_repository import (
    GovernanceManagementReviewRepository,
    get_governance_management_review_repository,
)
from app.schemas.management_review_scheduling import ManagementReviewStatus
from app.schemas.management_review_agenda import (
    AgendaCategory,
    AgendaDiscussionStatus,
    CollectInputsRequest,
    ConsolidatedInputRecord,
    CreateAgendaItemRequest,
    GenerateReviewPackageRequest,
    ReviewAgendaItemRecord,
    ReviewPackageRecord,
    UpdateAgendaItemRequest,
)


class ManagementReviewAgendaService:
    """Service governing agenda topics, input consolidation, and review packages."""

    def __init__(
        self, repository: Optional[GovernanceManagementReviewRepository] = None
    ) -> None:
        self.repository = repository or get_governance_management_review_repository()

    # -------------------------------------------------------------------------
    # Agenda Item Management
    # -------------------------------------------------------------------------

    def create_agenda_item(
        self, review_id: str, request: CreateAgendaItemRequest
    ) -> ReviewAgendaItemRecord:
        """Adds a new topic to a review meeting's agenda."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )

        if review.status in [
            ManagementReviewStatus.COMPLETED,
            ManagementReviewStatus.CANCELLED,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_MANAGEMENT_REVIEW_STATE,
                message=f"Cannot add agenda items to review in status '{review.status.value}'.",
            )

        existing_items = self.repository.list_agenda_items(review_id)
        next_order = (
            max([item.order for item in existing_items], default=0) + 1
            if request.order is None or request.order <= 0
            else request.order
        )

        item = ReviewAgendaItemRecord(
            review_id=review_id,
            title=request.title,
            description=request.description,
            category=request.category or AgendaCategory.CLINICAL_SAFETY_PERFORMANCE,
            priority=request.priority,
            discussion_status=AgendaDiscussionStatus.PENDING,
            presenter_id=request.presenter_id,
            presenter_name=request.presenter_name,
            allocated_minutes=request.allocated_minutes or 15,
            order=next_order,
            linked_sources=request.linked_sources or [],
            metadata=request.metadata or {},
        )
        return self.repository.save_agenda_item(item)

    def get_agenda_item(self, agenda_item_id: str) -> ReviewAgendaItemRecord:
        """Retrieves a single agenda item."""
        item = self.repository.get_agenda_item(agenda_item_id)
        if not item:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.AGENDA_ITEM_NOT_FOUND,
                message=f"Agenda item '{agenda_item_id}' not found.",
            )
        return item

    def list_agenda_items(self, review_id: str) -> List[ReviewAgendaItemRecord]:
        """Lists all agenda items for a given review."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )
        return self.repository.list_agenda_items(review_id)

    def update_agenda_item(
        self, agenda_item_id: str, request: UpdateAgendaItemRequest
    ) -> ReviewAgendaItemRecord:
        """Modifies agenda topic properties or discussion progress."""
        item = self.get_agenda_item(agenda_item_id)
        if request.title is not None:
            item.title = request.title
        if request.description is not None:
            item.description = request.description
        if request.category is not None:
            item.category = request.category
        if request.priority is not None:
            item.priority = request.priority
        if request.discussion_status is not None:
            item.discussion_status = request.discussion_status
        if request.presenter_id is not None:
            item.presenter_id = request.presenter_id
        if request.presenter_name is not None:
            item.presenter_name = request.presenter_name
        if request.allocated_minutes is not None:
            item.allocated_minutes = request.allocated_minutes
        if request.order is not None:
            item.order = request.order
        if request.linked_sources is not None:
            item.linked_sources = request.linked_sources
        if request.metadata is not None:
            item.metadata.update(request.metadata)

        return self.repository.save_agenda_item(item)

    def delete_agenda_item(self, agenda_item_id: str) -> bool:
        """Deletes an agenda item."""
        self.get_agenda_item(agenda_item_id)
        return self.repository.delete_agenda_item(agenda_item_id)

    # -------------------------------------------------------------------------
    # Input Consolidation
    # -------------------------------------------------------------------------

    def collect_inputs(
        self, review_id: str, request: CollectInputsRequest, collector_id: str
    ) -> ConsolidatedInputRecord:
        """Indexes evidence / intelligence from upstream phases (e.g. Phases 49-71)."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )

        inp = ConsolidatedInputRecord(
            review_id=review_id,
            source_phase=request.source_phase,
            source_id=request.source_id,
            source_type=request.source_type,
            summary=request.summary,
            details=request.details or {},
            collected_by=collector_id,
        )
        return self.repository.save_consolidated_input(inp)

    def list_consolidated_inputs(
        self, review_id: str, source_phase: Optional[str] = None
    ) -> List[ConsolidatedInputRecord]:
        """Lists all gathered inputs for a review."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )
        return self.repository.list_consolidated_inputs(review_id, source_phase)

    # -------------------------------------------------------------------------
    # Review Package Compilation
    # -------------------------------------------------------------------------

    def generate_package(
        self,
        review_id: str,
        request: GenerateReviewPackageRequest,
        compiler_id: str,
    ) -> ReviewPackageRecord:
        """Compiles a reproducible review package from current agenda and inputs."""
        review = self.repository.get_review(review_id)
        if not review:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.MANAGEMENT_REVIEW_NOT_FOUND,
                message=f"Management review '{review_id}' not found.",
            )

        existing_packages = self.repository.list_packages(review_id)
        version = len(existing_packages) + 1

        agenda_items = self.repository.list_agenda_items(review_id)
        inputs = self.repository.list_consolidated_inputs(review_id)

        package = ReviewPackageRecord(
            review_id=review_id,
            version=version,
            package_title=request.package_title,
            executive_summary=request.executive_summary,
            agenda_item_ids=[a.agenda_item_id for a in agenda_items],
            input_ids=[i.input_id for i in inputs],
            status="LOCKED" if request.lock_package else "COMPILED",
            compiled_by=compiler_id,
            locked_at=datetime.now(timezone.utc) if request.lock_package else None,
            locked_by=compiler_id if request.lock_package else None,
            metadata=request.metadata or {},
        )
        return self.repository.save_package(package)

    def get_package(self, package_id: str) -> ReviewPackageRecord:
        """Retrieves a compiled review package."""
        package = self.repository.get_package(package_id)
        if not package:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.REVIEW_PACKAGE_NOT_FOUND,
                message=f"Review package '{package_id}' not found.",
            )
        return package

    def list_packages(self, review_id: str) -> List[ReviewPackageRecord]:
        """Lists all package versions for a review."""
        self.repository.get_review(review_id)
        return self.repository.list_packages(review_id)

    def lock_package(self, package_id: str, locker_id: str) -> ReviewPackageRecord:
        """Locks a review package against further edits."""
        pkg = self.get_package(package_id)
        pkg.status = "LOCKED"
        pkg.locked_at = datetime.now(timezone.utc)
        pkg.locked_by = locker_id
        return self.repository.save_package(pkg)

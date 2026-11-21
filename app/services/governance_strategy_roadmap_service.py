"""Phase 78: Governance Strategic Roadmap Service.

Manages version-controlled multi-year roadmaps, change provenance, separation
of duties, and material baseline revisions.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER
from app.schemas.governance_strategy_roadmap import (
    ApproveRoadmapRequest,
    CreateRoadmapRequest,
    GovernanceStrategyRoadmapRecord,
    ReviseRoadmapRequest,
    RoadmapStatus,
    RoadmapVersionChangeRecord,
    SubmitRoadmapRequest,
    UpdateRoadmapRequest,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyRoadmapService:
    """Manages multi-year governance strategic roadmaps and revisions."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def create_roadmap(
        self,
        tenant_id: str,
        owner_id: str,
        request: CreateRoadmapRequest,
    ) -> GovernanceStrategyRoadmapRecord:
        now = _get_utc_now_str()
        roadmap = GovernanceStrategyRoadmapRecord(
            roadmap_id=f"gsr-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            title=request.title,
            description=request.description,
            organizational_scope=request.organizational_scope or {},
            planning_horizon=request.planning_horizon,
            start_date=request.start_date,
            end_date=request.end_date,
            strategic_objective_ids=request.strategic_objective_ids or [],
            strategic_priority_ids=request.strategic_priority_ids or [],
            milestone_ids=[],
            resource_proposal_ids=[],
            status=RoadmapStatus.DRAFT,
            owner_id=owner_id,
            current_version=1,
            approved_version=None,
            approved_by=None,
            approval_date=None,
            approval_reference=None,
            change_history=[],
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_roadmap(roadmap)

    def update_roadmap(
        self,
        tenant_id: str,
        roadmap_id: str,
        request: UpdateRoadmapRequest,
    ) -> GovernanceStrategyRoadmapRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Strategic roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        if roadmap.status != RoadmapStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_ROADMAP_STATE,
                message=f"Roadmap in status '{roadmap.status.value}' cannot be edited directly. Approved roadmaps require formal revision.",
                status_code=400,
            )

        now = _get_utc_now_str()
        update_data = {}
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.start_date is not None:
            update_data["start_date"] = request.start_date
        if request.end_date is not None:
            update_data["end_date"] = request.end_date
        if request.strategic_objective_ids is not None:
            update_data["strategic_objective_ids"] = request.strategic_objective_ids
        if request.strategic_priority_ids is not None:
            update_data["strategic_priority_ids"] = request.strategic_priority_ids

        update_data["updated_at"] = now
        roadmap = roadmap.model_copy(update=update_data)
        return self.repository.save_roadmap(roadmap)

    def submit_roadmap(
        self,
        tenant_id: str,
        roadmap_id: str,
        request: SubmitRoadmapRequest,
    ) -> GovernanceStrategyRoadmapRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Strategic roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        if roadmap.status != RoadmapStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_ROADMAP_STATE,
                message=f"Roadmap in status '{roadmap.status.value}' cannot be submitted. Only DRAFT roadmaps can be submitted.",
                status_code=400,
            )

        now = _get_utc_now_str()
        roadmap = roadmap.model_copy(
            update={"status": RoadmapStatus.SUBMITTED, "updated_at": now}
        )
        return self.repository.save_roadmap(roadmap)

    def approve_roadmap(
        self,
        tenant_id: str,
        roadmap_id: str,
        approver_id: str,
        request: ApproveRoadmapRequest,
    ) -> GovernanceStrategyRoadmapRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Strategic roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        if roadmap.status != RoadmapStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_ROADMAP_STATE,
                message=f"Roadmap in status '{roadmap.status.value}' cannot be approved. Only SUBMITTED roadmaps can be approved.",
                status_code=400,
            )

        # Separation of duties: owner cannot approve their own roadmap
        if roadmap.owner_id == approver_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Owner cannot approve their own strategic roadmap.",
                status_code=403,
            )

        now = _get_utc_now_str()
        roadmap = roadmap.model_copy(
            update={
                "status": RoadmapStatus.APPROVED,
                "approved_version": roadmap.current_version,
                "approved_by": approver_id,
                "approval_date": now,
                "approval_reference": request.approval_reference,
                "updated_at": now,
            }
        )
        return self.repository.save_roadmap(roadmap)

    def activate_roadmap(
        self,
        tenant_id: str,
        roadmap_id: str,
    ) -> GovernanceStrategyRoadmapRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Strategic roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        if roadmap.status != RoadmapStatus.APPROVED:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_ROADMAP_STATE,
                message=f"Roadmap in status '{roadmap.status.value}' cannot be activated. Only APPROVED roadmaps can be activated.",
                status_code=400,
            )

        now = _get_utc_now_str()
        roadmap = roadmap.model_copy(
            update={"status": RoadmapStatus.ACTIVE, "updated_at": now}
        )
        return self.repository.save_roadmap(roadmap)

    def revise_roadmap(
        self,
        tenant_id: str,
        roadmap_id: str,
        reviser_id: str,
        request: ReviseRoadmapRequest,
    ) -> GovernanceStrategyRoadmapRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Strategic roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        if roadmap.status not in (RoadmapStatus.APPROVED, RoadmapStatus.ACTIVE):
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_ROADMAP_STATE,
                message=f"Roadmap in status '{roadmap.status.value}' cannot be revised. Only APPROVED or ACTIVE roadmaps can be revised.",
                status_code=400,
            )

        now = _get_utc_now_str()
        new_version = roadmap.current_version + 1

        change_entry = RoadmapVersionChangeRecord(
            change_id=f"chg-{uuid.uuid4().hex[:8]}",
            previous_version=roadmap.current_version,
            new_version=new_version,
            change_reason=request.change_reason,
            requesting_user_id=reviser_id,
            affected_objective_ids=request.affected_objective_ids or [],
            affected_milestone_ids=request.affected_milestone_ids or [],
            approval_reference=request.approval_reference,
            approved_by=reviser_id,
            timestamp=now,
        )

        history = list(roadmap.change_history)
        history.append(change_entry)

        roadmap = roadmap.model_copy(
            update={
                "current_version": new_version,
                "approved_version": new_version,
                "change_history": history,
                "updated_at": now,
            }
        )
        return self.repository.save_roadmap(roadmap)

    def get_roadmap(
        self,
        tenant_id: str,
        roadmap_id: str,
    ) -> GovernanceStrategyRoadmapRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Strategic roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )
        return roadmap

    def list_roadmaps(
        self,
        tenant_id: str,
        status: Optional[RoadmapStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyRoadmapRecord]:
        return self.repository.list_roadmaps(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
        )

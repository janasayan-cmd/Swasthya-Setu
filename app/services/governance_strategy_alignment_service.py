"""Phase 79: Strategic Alignment Analysis Service.

Provides explainable alignment analysis detecting orphan objectives,
orphan milestones, disconnected portfolios, conflicting target states,
and contradictory timelines across strategic governance roadmaps.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_alignment import (
    AlignmentFindingCategory,
    AlignmentFindingStatus,
    CreateAlignmentFindingRequest,
    ReviewAlignmentFindingRequest,
    StrategicAlignmentFindingRecord,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyAlignmentService:
    """Detects, tracks, and manages strategic alignment findings across roadmaps."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def record_alignment_finding(
        self,
        tenant_id: str,
        request: CreateAlignmentFindingRequest,
    ) -> StrategicAlignmentFindingRecord:
        finding_id = f"SAF-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = StrategicAlignmentFindingRecord(
            finding_id=finding_id,
            tenant_id=tenant_id,
            category=request.category,
            affected_roadmap_ids=request.affected_roadmap_ids,
            affected_record_references=request.affected_record_references or [],
            detection_method=request.detection_method,
            rule_version=request.rule_version,
            explanation=request.explanation,
            confidence_score=request.confidence_score,
            evidence_limitations=request.evidence_limitations or "",
            status=AlignmentFindingStatus.DETECTED,
            reviewed_by=None,
            review_notes=None,
            suggested_review_destination=request.suggested_review_destination,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            detected_at=now_str,
        )
        return self.repository.save_alignment_finding(record)

    def review_alignment_finding(
        self,
        tenant_id: str,
        reviewer_id: str,
        finding_id: str,
        request: ReviewAlignmentFindingRequest,
    ) -> StrategicAlignmentFindingRecord:
        finding = self.repository.get_alignment_finding(finding_id)
        if not finding or finding.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ALIGNMENT_FINDING_NOT_FOUND,
                message=f"Strategic alignment finding '{finding_id}' was not found.",
                status_code=404,
            )

        updated = finding.model_copy(
            update={
                "status": request.status,
                "reviewed_by": reviewer_id,
                "review_notes": request.review_notes,
            }
        )
        return self.repository.save_alignment_finding(updated)

    def get_alignment_finding(
        self,
        tenant_id: str,
        finding_id: str,
    ) -> StrategicAlignmentFindingRecord:
        finding = self.repository.get_alignment_finding(finding_id)
        if not finding or finding.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ALIGNMENT_FINDING_NOT_FOUND,
                message=f"Strategic alignment finding '{finding_id}' was not found.",
                status_code=404,
            )
        return finding

    def list_alignment_findings(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[AlignmentFindingCategory] = None,
        status: Optional[AlignmentFindingStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicAlignmentFindingRecord]:
        return self.repository.list_alignment_findings(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            category=category,
            status=status,
            skip=skip,
            limit=limit,
        )

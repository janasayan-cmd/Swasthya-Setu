"""Phase 80: Continuity Gap and Resilience Weakness Service.

Identifies continuity gaps, captures evidence limitations, and coordinates
routing to Phase 54 CAPA and Phase 63 Risk Governance.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_gaps import (
    ContinuityGapCategory,
    ContinuityGapRecord,
    ContinuityGapSeverity,
    ContinuityGapStatus,
    CreateContinuityGapRequest,
    ReferGapToCorrectiveActionRequest,
    ReviewContinuityGapRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


_VALID_ROUTING_DESTINATIONS = {
    "PHASE_54_CAPA",
    "PHASE_55_EFFECTIVENESS",
    "PHASE_63_RISK",
    "PHASE_67_ESCALATION",
    "PHASE_49_INCIDENT",
    "PHASE_72_MANAGEMENT_REVIEW",
}


class GovernanceContinuityGapsService:
    """Manages continuity gap findings, severity ranking, and corrective action routing."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_continuity_gap(
        self,
        tenant_id: str,
        request: CreateContinuityGapRequest,
    ) -> ContinuityGapRecord:
        gap_id = f"GCG-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = ContinuityGapRecord(
            gap_id=gap_id,
            tenant_id=tenant_id,
            category=request.category,
            affected_capability_ids=request.affected_capability_ids,
            detection_method=request.detection_method,
            explanation=request.explanation,
            severity=request.severity,
            recommended_action=request.recommended_action,
            status=ContinuityGapStatus.DETECTED,
            escalation_destination=request.escalation_destination,
            reviewed_by=None,
            review_notes=None,
            corrective_action_reference=None,
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            detected_at=now_str,
        )
        return self.repository.save_gap(record)

    def review_continuity_gap(
        self,
        tenant_id: str,
        reviewer_id: str,
        gap_id: str,
        request: ReviewContinuityGapRequest,
    ) -> ContinuityGapRecord:
        gap = self.repository.get_gap(gap_id)
        if not gap or gap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_GAP_NOT_FOUND,
                message=f"Continuity gap '{gap_id}' was not found.",
                status_code=404,
            )

        updated = gap.model_copy(
            update={
                "status": request.status,
                "reviewed_by": reviewer_id,
                "review_notes": request.review_notes,
            }
        )
        return self.repository.save_gap(updated)

    def refer_gap_to_corrective_action(
        self,
        tenant_id: str,
        referrer_id: str,
        gap_id: str,
        request: ReferGapToCorrectiveActionRequest,
    ) -> ContinuityGapRecord:
        gap = self.repository.get_gap(gap_id)
        if not gap or gap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_GAP_NOT_FOUND,
                message=f"Continuity gap '{gap_id}' was not found.",
                status_code=404,
            )

        dest = request.escalation_destination.strip()
        if dest not in _VALID_ROUTING_DESTINATIONS:
            raise AppException(
                code=ErrorCode.CONTINUITY_CLINICAL_SAFETY_BOUNDARY_VIOLATION,
                message=f"Invalid escalation destination '{dest}'. Must be one of {sorted(_VALID_ROUTING_DESTINATIONS)}.",
                status_code=400,
            )

        ca_ref = request.corrective_action_reference or f"CAPA-{uuid.uuid4().hex[:8].upper()}"
        notes = f"Referred by {referrer_id}: {request.routing_notes or 'Referred for corrective action follow-up'}"

        updated = gap.model_copy(
            update={
                "status": ContinuityGapStatus.ACTION_REFERRED,
                "escalation_destination": dest,
                "corrective_action_reference": ca_ref,
                "reviewed_by": referrer_id,
                "review_notes": notes,
            }
        )
        return self.repository.save_gap(updated)

    def get_gap(
        self,
        tenant_id: str,
        gap_id: str,
    ) -> ContinuityGapRecord:
        gap = self.repository.get_gap(gap_id)
        if not gap or gap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_GAP_NOT_FOUND,
                message=f"Continuity gap '{gap_id}' was not found.",
                status_code=404,
            )
        return gap

    def list_gaps(
        self,
        tenant_id: str,
        category: Optional[ContinuityGapCategory] = None,
        severity: Optional[ContinuityGapSeverity] = None,
        status: Optional[ContinuityGapStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ContinuityGapRecord]:
        return self.repository.list_gaps(
            tenant_id=tenant_id,
            category=category,
            severity=severity,
            status=status,
            skip=skip,
            limit=limit,
        )

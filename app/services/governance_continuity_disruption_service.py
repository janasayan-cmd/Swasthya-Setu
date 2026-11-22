"""Phase 80: Governance Disruption Management Service.

Registers, updates, and tracks disruptions impacting clinical safety governance operations.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_disruption import (
    CloseDisruptionRequest,
    DisruptionCategory,
    DisruptionStatus,
    GovernanceDisruptionRecord,
    RegisterDisruptionRequest,
    UpdateDisruptionRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityDisruptionService:
    """Manages governance disruption records, capability linkage, and lifecycle tracking."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def register_disruption(
        self,
        tenant_id: str,
        author_id: str,
        request: RegisterDisruptionRequest,
    ) -> GovernanceDisruptionRecord:
        dis_id = f"GDS-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = GovernanceDisruptionRecord(
            disruption_id=dis_id,
            tenant_id=tenant_id,
            category=request.category,
            description=request.description,
            affected_organizational_scope=request.affected_organizational_scope or {},
            affected_capability_ids=request.affected_capability_ids,
            source_incident_reference=request.source_incident_reference,
            detection_timestamp=request.detection_timestamp,
            reported_impact=request.reported_impact,
            evidence_references=request.evidence_references or [],
            status=DisruptionStatus.ACTIVE,
            responsible_coordinator_id=request.responsible_coordinator_id,
            escalation_destination=request.escalation_destination,
            related_plan_id=request.related_plan_id,
            recovery_status="NOT_STARTED",
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_disruption(record)

    def update_disruption(
        self,
        tenant_id: str,
        disruption_id: str,
        request: UpdateDisruptionRequest,
    ) -> GovernanceDisruptionRecord:
        dis = self.repository.get_disruption(disruption_id)
        if not dis or dis.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DISRUPTION_NOT_FOUND,
                message=f"Governance disruption '{disruption_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        updated = dis.model_copy(
            update={
                "reported_impact": request.reported_impact if request.reported_impact is not None else dis.reported_impact,
                "status": request.status if request.status is not None else dis.status,
                "responsible_coordinator_id": request.responsible_coordinator_id if request.responsible_coordinator_id is not None else dis.responsible_coordinator_id,
                "related_plan_id": request.related_plan_id if request.related_plan_id is not None else dis.related_plan_id,
                "recovery_status": request.recovery_status if request.recovery_status is not None else dis.recovery_status,
                "updated_at": now_str,
            }
        )
        return self.repository.save_disruption(updated)

    def close_disruption(
        self,
        tenant_id: str,
        closer_id: str,
        disruption_id: str,
        request: CloseDisruptionRequest,
    ) -> GovernanceDisruptionRecord:
        dis = self.repository.get_disruption(disruption_id)
        if not dis or dis.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DISRUPTION_NOT_FOUND,
                message=f"Governance disruption '{disruption_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        ev_list = list(dis.evidence_references)
        if request.verification_evidence_reference not in ev_list:
            ev_list.append(request.verification_evidence_reference)

        updated = dis.model_copy(
            update={
                "status": DisruptionStatus.CLOSED,
                "recovery_status": "CLOSED",
                "evidence_references": ev_list,
                "updated_at": now_str,
            }
        )
        return self.repository.save_disruption(updated)

    def get_disruption(
        self,
        tenant_id: str,
        disruption_id: str,
    ) -> GovernanceDisruptionRecord:
        dis = self.repository.get_disruption(disruption_id)
        if not dis or dis.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.GOVERNANCE_DISRUPTION_NOT_FOUND,
                message=f"Governance disruption '{disruption_id}' was not found.",
                status_code=404,
            )
        return dis

    def list_disruptions(
        self,
        tenant_id: str,
        category: Optional[DisruptionCategory] = None,
        status: Optional[DisruptionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceDisruptionRecord]:
        return self.repository.list_disruptions(
            tenant_id=tenant_id,
            category=category,
            status=status,
            skip=skip,
            limit=limit,
        )

"""Phase 87: Impact Remediation and Escalation Coordination Service.

Coordinates the routing of significant disruption impact findings to authoritative workflows:
Phase 63 (Risk Management), Phase 67 (Governance Escalation), Phase 49 (Incident Management),
Phase 54 (Corrective Action), Phase 72 (Management Review), Phase 80 (Continuity Planning).
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_disruption_impact_repository import (
    GovernanceDisruptionImpactRepository,
    get_governance_disruption_impact_repository,
)
from app.schemas.governance_disruption_common import (
    FollowUpDestinationWorkflow,
    FollowUpStatus,
)
from app.schemas.governance_impact_remediation import (
    AcknowledgeImpactFollowUpRequest,
    CreateImpactFollowUpRequest,
    ImpactFollowUpRecord,
    SubmitImpactFollowUpRequest,
)


class GovernanceImpactRemediationService:

    def __init__(self, repo: GovernanceDisruptionImpactRepository) -> None:
        self.repo = repo

    def create_follow_up(
        self, tenant_id: str, assessment_id: str, user_id: str, request: CreateImpactFollowUpRequest
    ) -> ImpactFollowUpRecord:
        assessment = self.repo.get_assessment(assessment_id, tenant_id)
        if not assessment:
            raise AppException(
                code=ErrorCode.DISRUPTION_IMPACT_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        now = datetime.utcnow()
        record = ImpactFollowUpRecord(
            follow_up_id=f"ifu-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            finding_reference_id=request.finding_reference_id,
            affected_capability_ref=request.affected_capability_ref,
            responsible_owner_ref=request.responsible_owner_ref,
            destination_workflow=request.destination_workflow,
            priority_severity=request.priority_severity,
            status=FollowUpStatus.PROPOSED,
            proposal_description=request.proposal_description,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_follow_up(record)

    def get_follow_up(self, tenant_id: str, follow_up_id: str) -> ImpactFollowUpRecord:
        record = self.repo.get_follow_up(follow_up_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.IMPACT_FOLLOW_UP_NOT_FOUND,
                message=f"Impact follow-up '{follow_up_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_follow_ups(
        self,
        tenant_id: str,
        assessment_id: Optional[str] = None,
        destination_workflow: Optional[FollowUpDestinationWorkflow] = None,
        status: Optional[FollowUpStatus] = None,
    ) -> List[ImpactFollowUpRecord]:
        return self.repo.list_follow_ups(tenant_id, assessment_id, destination_workflow, status)

    def submit_follow_up(
        self, tenant_id: str, follow_up_id: str, user_id: str, request: SubmitImpactFollowUpRequest
    ) -> ImpactFollowUpRecord:
        record = self.get_follow_up(tenant_id, follow_up_id)
        if record.status != FollowUpStatus.PROPOSED:
            raise AppException(
                code=ErrorCode.INVALID_IMPACT_FOLLOW_UP_STATE,
                message=f"Cannot submit follow-up in state '{record.status}'. Must be PROPOSED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        now = datetime.utcnow()
        record.status = FollowUpStatus.SUBMITTED
        record.handoff_timestamp = now
        record.updated_at = now
        return self.repo.save_follow_up(record)

    def acknowledge_follow_up(
        self, tenant_id: str, follow_up_id: str, acknowledger_id: str, request: AcknowledgeImpactFollowUpRequest
    ) -> ImpactFollowUpRecord:
        record = self.get_follow_up(tenant_id, follow_up_id)
        if record.status != FollowUpStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_IMPACT_FOLLOW_UP_STATE,
                message=f"Cannot acknowledge follow-up in state '{record.status}'. Must be SUBMITTED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        now = datetime.utcnow()
        record.status = FollowUpStatus.ACKNOWLEDGED
        record.external_workflow_reference_id = request.external_workflow_reference_id
        record.acknowledgement_timestamp = now
        record.acknowledged_by = acknowledger_id
        record.outcome_notes = request.acknowledgement_notes
        record.updated_at = now
        return self.repo.save_follow_up(record)


_remediation_service: Optional[GovernanceImpactRemediationService] = None


def get_governance_impact_remediation_service() -> GovernanceImpactRemediationService:
    global _remediation_service
    if _remediation_service is None:
        _remediation_service = GovernanceImpactRemediationService(
            get_governance_disruption_impact_repository()
        )
    return _remediation_service

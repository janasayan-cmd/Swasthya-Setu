"""Phase 85: Role Handover and Transition Coordination Service.

Coordinates structured handovers of critical governance responsibilities,
capturing open governance items, outgoing signoffs, and incoming acknowledgements.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_role_coverage_repository import (
    GovernanceRoleCoverageRepository,
    get_governance_role_coverage_repository,
)
from app.schemas.governance_role_coverage_common import (
    HandoverStatus,
)
from app.schemas.governance_role_handover import (
    AcknowledgeHandoverRequest,
    CancelHandoverRequest,
    CompleteHandoverRequest,
    InitiateHandoverRequest,
    RoleHandoverRecord,
)


class GovernanceRoleHandoverService:
    """Service for managing critical governance handovers."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def initiate_handover(
        self,
        tenant_id: str,
        user_id: str,
        request: InitiateHandoverRequest,
    ) -> RoleHandoverRecord:
        resp = self.repository.get_responsibility(request.responsibility_id, tenant_id)
        if not resp:
            raise AppException(
                code=ErrorCode.CRITICAL_RESPONSIBILITY_NOT_FOUND,
                message=f"Critical responsibility '{request.responsibility_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if user_id == request.incoming_user_id:
            raise AppException(
                code=ErrorCode.ROLE_COVERAGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Cannot initiate handover to self: incoming user must be distinct from outgoing user.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.utcnow()
        effective_from = request.effective_from or now
        record = RoleHandoverRecord(
            handover_id=f"hand-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            responsibility_id=request.responsibility_id,
            outgoing_user_id=user_id,
            incoming_user_id=request.incoming_user_id,
            handover_reason=request.handover_reason,
            effective_from=effective_from,
            expected_to=request.expected_to,
            status=HandoverStatus.PENDING_INCOMING_ACKNOWLEDGEMENT,
            open_governance_items=request.open_governance_items,
            outgoing_checklist_completed=request.outgoing_checklist_completed,
            outgoing_signoff_notes=request.outgoing_signoff_notes,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_handover(record)

    def get_handover(self, tenant_id: str, handover_id: str) -> RoleHandoverRecord:
        record = self.repository.get_handover(handover_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.HANDOVER_RECORD_NOT_FOUND,
                message=f"Handover record '{handover_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_handovers(
        self,
        tenant_id: str,
        responsibility_id: Optional[str] = None,
        user_id: Optional[str] = None,
        handover_status: Optional[HandoverStatus] = None,
    ) -> List[RoleHandoverRecord]:
        return self.repository.list_handovers(tenant_id, responsibility_id, user_id, handover_status)

    def acknowledge_handover(
        self,
        tenant_id: str,
        handover_id: str,
        user_id: str,
        request: AcknowledgeHandoverRequest,
    ) -> RoleHandoverRecord:
        record = self.get_handover(tenant_id, handover_id)
        if record.incoming_user_id != user_id:
            raise AppException(
                code=ErrorCode.ROLE_COVERAGE_ACCESS_DENIED,
                message="Only the designated incoming user can acknowledge the handover.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if record.status not in (
            HandoverStatus.INITIATED,
            HandoverStatus.PENDING_INCOMING_ACKNOWLEDGEMENT,
        ):
            raise AppException(
                code=ErrorCode.INVALID_HANDOVER_RECORD_STATE,
                message=f"Cannot acknowledge handover in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.utcnow()
        record.status = HandoverStatus.ACKNOWLEDGED
        record.incoming_acknowledged_at = now
        record.incoming_acknowledgement_notes = request.incoming_acknowledgement_notes
        record.updated_at = now
        return self.repository.save_handover(record)

    def complete_handover(
        self,
        tenant_id: str,
        handover_id: str,
        user_id: str,
        request: CompleteHandoverRequest,
    ) -> RoleHandoverRecord:
        record = self.get_handover(tenant_id, handover_id)
        if record.status != HandoverStatus.ACKNOWLEDGED:
            raise AppException(
                code=ErrorCode.INVALID_HANDOVER_RECORD_STATE,
                message=f"Cannot complete handover before incoming acknowledgement. Current state: '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.utcnow()
        record.status = HandoverStatus.COMPLETED
        record.supervisor_reviewed_by = user_id
        record.updated_at = now
        return self.repository.save_handover(record)

    def cancel_handover(
        self,
        tenant_id: str,
        handover_id: str,
        user_id: str,
        request: CancelHandoverRequest,
    ) -> RoleHandoverRecord:
        record = self.get_handover(tenant_id, handover_id)
        if record.status in (HandoverStatus.COMPLETED, HandoverStatus.CANCELLED):
            raise AppException(
                code=ErrorCode.INVALID_HANDOVER_RECORD_STATE,
                message=f"Cannot cancel handover in state '{record.status}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.utcnow()
        record.status = HandoverStatus.CANCELLED
        record.updated_at = now
        return self.repository.save_handover(record)


_handover_service: Optional[GovernanceRoleHandoverService] = None


def get_governance_role_handover_service() -> GovernanceRoleHandoverService:
    global _handover_service
    if _handover_service is None:
        _handover_service = GovernanceRoleHandoverService(
            get_governance_role_coverage_repository()
        )
    return _handover_service

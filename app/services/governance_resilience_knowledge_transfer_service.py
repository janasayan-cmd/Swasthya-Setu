"""Phase 83: Knowledge Succession and Transfer Service.

Governs formal knowledge ownership transfer between personnel, enforcing strict
separation of duties (neither departing owner nor successor can verify the transfer).
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_knowledge_repository import (
    GovernanceResilienceKnowledgeRepository,
    get_governance_resilience_knowledge_repository,
)
from app.schemas.governance_resilience_knowledge_transfer import (
    CompleteKnowledgeTransferRequest,
    InitiateKnowledgeTransferRequest,
    KnowledgeTransferRecord,
    TransferStatus,
    UpdateTransferChecklistRequest,
    VerifyKnowledgeTransferRequest,
)


class GovernanceResilienceKnowledgeTransferService:
    """Service managing knowledge succession, handoff checklists, and verification gates."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    def initiate_transfer(
        self,
        tenant_id: str,
        departing_owner_id: str,
        request: InitiateKnowledgeTransferRequest,
    ) -> KnowledgeTransferRecord:
        # Cannot transfer to oneself
        if departing_owner_id == request.successor_owner_id:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Cannot initiate knowledge transfer to yourself. Successor must be a distinct individual.",
                status_code=400,
            )

        # Verify all knowledge records exist and belong to tenant
        for kid in request.knowledge_ids:
            rec = self.repository.get_knowledge(kid, tenant_id)
            if not rec:
                raise AppException(
                    code=ErrorCode.RESILIENCE_KNOWLEDGE_NOT_FOUND,
                    message=f"Knowledge record '{kid}' not found for transfer.",
                    status_code=404,
                )

        transfer_id = f"trf-{uuid.uuid4().hex[:10]}"
        transfer = KnowledgeTransferRecord(
            transfer_id=transfer_id,
            tenant_id=tenant_id,
            knowledge_ids=request.knowledge_ids,
            transferring_owner_id=departing_owner_id,
            successor_owner_id=request.successor_owner_id,
            reason=request.reason,
            handoff_checklist=request.handoff_checklist or {"briefing_completed": False, "documentation_shared": False},
            status=TransferStatus.INITIATED,
        )
        return self.repository.save_transfer(transfer)

    def get_transfer(self, tenant_id: str, transfer_id: str) -> KnowledgeTransferRecord:
        transfer = self.repository.get_transfer(transfer_id, tenant_id)
        if not transfer:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_TRANSFER_NOT_FOUND,
                message=f"Knowledge transfer record '{transfer_id}' not found.",
                status_code=404,
            )
        return transfer

    def update_checklist(
        self,
        tenant_id: str,
        transfer_id: str,
        user_id: str,
        request: UpdateTransferChecklistRequest,
    ) -> KnowledgeTransferRecord:
        transfer = self.get_transfer(tenant_id, transfer_id)
        if transfer.status not in [TransferStatus.INITIATED, TransferStatus.IN_PROGRESS]:
            raise AppException(
                code=ErrorCode.INVALID_KNOWLEDGE_TRANSFER_STATE,
                message=f"Cannot update checklist for transfer in state '{transfer.status}'.",
                status_code=400,
            )

        transfer.handoff_checklist.update(request.handoff_checklist)
        transfer.status = TransferStatus.IN_PROGRESS
        return self.repository.save_transfer(transfer)

    def complete_transfer(
        self,
        tenant_id: str,
        transfer_id: str,
        user_id: str,
        request: CompleteKnowledgeTransferRequest,
    ) -> KnowledgeTransferRecord:
        transfer = self.get_transfer(tenant_id, transfer_id)
        if transfer.status not in [TransferStatus.INITIATED, TransferStatus.IN_PROGRESS]:
            raise AppException(
                code=ErrorCode.INVALID_KNOWLEDGE_TRANSFER_STATE,
                message=f"Transfer in state '{transfer.status}' cannot be completed. Must be IN_PROGRESS.",
                status_code=400,
            )

        transfer.status = TransferStatus.COMPLETED
        transfer.completed_at = datetime.utcnow()
        return self.repository.save_transfer(transfer)

    def verify_transfer(
        self,
        tenant_id: str,
        transfer_id: str,
        verifier_id: str,
        request: VerifyKnowledgeTransferRequest,
    ) -> KnowledgeTransferRecord:
        transfer = self.get_transfer(tenant_id, transfer_id)

        # Separation of duties: Neither departing owner nor successor can verify
        if verifier_id in [transfer.transferring_owner_id, transfer.successor_owner_id]:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION,
                message=(
                    "Separation of duties violation: An independent third party must verify knowledge transfer. "
                    "Neither departing owner nor successor owner may act as verifier."
                ),
                status_code=400,
            )

        if transfer.status != TransferStatus.COMPLETED:
            raise AppException(
                code=ErrorCode.INVALID_KNOWLEDGE_TRANSFER_STATE,
                message=f"Transfer must be in COMPLETED state to be verified. Current state: '{transfer.status}'.",
                status_code=400,
            )

        if request.approved:
            transfer.status = TransferStatus.VERIFIED
            transfer.verified_by = verifier_id
            transfer.verified_at = datetime.utcnow()

            # Automatically update owner_id on all transferred knowledge assets
            for kid in transfer.knowledge_ids:
                knowledge = self.repository.get_knowledge(kid, tenant_id)
                if knowledge:
                    knowledge.owner_id = transfer.successor_owner_id
                    knowledge.updated_at = datetime.utcnow()
                    self.repository.save_knowledge(knowledge)
        else:
            transfer.status = TransferStatus.REJECTED
            transfer.rejection_notes = request.notes

        return self.repository.save_transfer(transfer)

    def list_transfers(
        self,
        tenant_id: str,
        owner_id: Optional[str] = None,
        status: Optional[TransferStatus] = None,
    ) -> List[KnowledgeTransferRecord]:
        return self.repository.list_transfers(tenant_id=tenant_id, owner_id=owner_id, status=status)


_transfer_service = GovernanceResilienceKnowledgeTransferService()


def get_governance_resilience_knowledge_transfer_service() -> GovernanceResilienceKnowledgeTransferService:
    return _transfer_service

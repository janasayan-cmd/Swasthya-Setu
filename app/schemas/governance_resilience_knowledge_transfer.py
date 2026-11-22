"""Phase 83: Knowledge Succession and Transfer Schemas.

Supports formal, traceable ownership transfer of critical resilience knowledge
assets, ensuring continuity of expertise and preventing institutional amnesia.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_knowledge import (
    MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER,
)


class TransferStatus(str, Enum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class KnowledgeTransferRecord(BaseModel):
    transfer_id: str
    tenant_id: str
    knowledge_ids: List[str]
    transferring_owner_id: str
    successor_owner_id: str
    reason: str
    handoff_checklist: Dict[str, bool] = Field(default_factory=dict)
    status: TransferStatus = TransferStatus.INITIATED
    initiated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    rejection_notes: Optional[str] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class InitiateKnowledgeTransferRequest(BaseModel):
    knowledge_ids: List[str]
    successor_owner_id: str
    reason: str
    handoff_checklist: Optional[Dict[str, bool]] = None


class UpdateTransferChecklistRequest(BaseModel):
    handoff_checklist: Dict[str, bool]


class CompleteKnowledgeTransferRequest(BaseModel):
    notes: Optional[str] = None


class VerifyKnowledgeTransferRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None

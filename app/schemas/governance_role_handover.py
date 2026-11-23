"""Phase 85: Role Handover and Transition Coordination Schemas.

Coordinates structured handovers of critical governance responsibilities,
capturing references to open governance items (escalations, decisions, CAPA, risks).
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    HandoverStatus,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class OpenGovernanceItemRef(BaseModel):
    item_type: str = Field(description="SAFETY_ESCALATION, MANAGEMENT_DECISION, CAPA_ACTION, SAFETY_RISK, CONTINUITY_ACTION")
    source_phase: str = Field(description="e.g. Phase 67, Phase 72, Phase 54, Phase 63, Phase 80")
    item_reference_id: str
    summary: str
    urgency_level: str = "HIGH"
    handover_notes: Optional[str] = None


class RoleHandoverRecord(BaseModel):
    handover_id: str
    tenant_id: str
    responsibility_id: str
    outgoing_user_id: str
    incoming_user_id: str
    handover_reason: str
    effective_from: datetime = Field(default_factory=datetime.utcnow)
    expected_to: Optional[datetime] = None
    status: HandoverStatus = HandoverStatus.INITIATED
    open_governance_items: List[OpenGovernanceItemRef] = Field(default_factory=list)
    outgoing_checklist_completed: bool = False
    outgoing_signoff_notes: Optional[str] = None
    incoming_acknowledged_at: Optional[datetime] = None
    incoming_acknowledgement_notes: Optional[str] = None
    supervisor_reviewed_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class InitiateHandoverRequest(BaseModel):
    responsibility_id: str
    incoming_user_id: str
    handover_reason: str
    effective_from: Optional[datetime] = None
    expected_to: Optional[datetime] = None
    open_governance_items: List[OpenGovernanceItemRef] = Field(default_factory=list)
    outgoing_checklist_completed: bool = True
    outgoing_signoff_notes: Optional[str] = None


class AcknowledgeHandoverRequest(BaseModel):
    incoming_acknowledgement_notes: str


class CompleteHandoverRequest(BaseModel):
    completion_notes: Optional[str] = None


class CancelHandoverRequest(BaseModel):
    cancellation_reason: str

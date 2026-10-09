"""Phase 64: Clinical Safety Risk Handoff Status Schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.safety_risk_handoff import HandoffDestinationPhase, HandoffLifecycleState


class HandoffStatusResponse(BaseModel):
    """Operational status response for a safety risk handoff."""

    model_config = ConfigDict(extra="ignore")

    handoff_id: str
    state: HandoffLifecycleState
    destination_phase: HandoffDestinationPhase
    is_acknowledged: bool = False
    is_reconciled: bool = False
    outcomes_count: int = 0
    retry_count: int = 0
    max_retries: int = 3
    follow_up_status: Optional[str] = None
    blocking_reason: Optional[str] = None
    escalation_reason: Optional[str] = None
    updated_at: datetime

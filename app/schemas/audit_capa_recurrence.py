"""Phase 71: Corrective Action Recurrence Analysis Schemas.

Defines schemas for:
- Tracking recurrence of audit findings after corrective actions (Phase 54) and effectiveness reviews (Phase 55)
- Classifying implementation and verification state without overriding authoritative workflows
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CAPARecurrenceStatus(str, Enum):
    """Categorization of findings relative to linked corrective actions."""

    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    IMPLEMENTED_UNVERIFIED = "IMPLEMENTED_UNVERIFIED"
    VERIFIED_EFFECTIVENESS_UNESTABLISHED = "VERIFIED_EFFECTIVENESS_UNESTABLISHED"
    EFFECTIVENESS_FAILED = "EFFECTIVENESS_FAILED"
    RECURRENCE_CONFIRMED = "RECURRENCE_CONFIRMED"
    RECURRENCE_SUSPECTED = "RECURRENCE_SUSPECTED"
    NO_RECURRENCE_OBSERVED = "NO_RECURRENCE_OBSERVED"


class CAPARecurrenceRecord(BaseModel):
    """Domain record representing recurrence analysis for a corrective action."""

    model_config = ConfigDict(extra="ignore")

    recurrence_id: str = Field(default_factory=lambda: f"gcpr-{uuid.uuid4().hex[:12]}")
    initial_finding_id: str
    corrective_action_ref: str
    phase55_eval_ref: Optional[str] = None
    action_title: Optional[str] = None

    recurrence_status: CAPARecurrenceStatus = CAPARecurrenceStatus.NO_RECURRENCE_OBSERVED
    action_implementation_date: Optional[datetime] = None
    effectiveness_outcome: Optional[str] = None

    subsequent_related_finding_ids: List[str] = Field(default_factory=list)
    temporal_context: str
    analytical_notes: str

    organization_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

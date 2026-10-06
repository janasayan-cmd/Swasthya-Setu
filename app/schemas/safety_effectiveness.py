"""Phase 50: Corrective-Action Effectiveness Schemas.

Evaluates whether implemented corrective actions are correlated with
reduced recurrence within controlled observation windows.
Preserves uncertainty: NO_RECURRENCE_OBSERVED does NOT guarantee risk elimination.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class EffectivenessState(str, Enum):
    """Controlled analytical states for remediation effectiveness."""

    NOT_EVALUATED = "NOT_EVALUATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    PENDING_OBSERVATION = "PENDING_OBSERVATION"
    NO_RECURRENCE_OBSERVED = "NO_RECURRENCE_OBSERVED"
    RECURRENCE_OBSERVED = "RECURRENCE_OBSERVED"
    PARTIAL_IMPROVEMENT = "PARTIAL_IMPROVEMENT"
    NO_CLEAR_IMPROVEMENT = "NO_CLEAR_IMPROVEMENT"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class CorrectiveActionEffectivenessRecord(BaseModel):
    """Analytical evaluation of whether a Phase 49 corrective action prevented recurrence."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"eff-{uuid.uuid4().hex[:12]}")
    action_id: str
    incident_id: str
    state: EffectivenessState = Field(default=EffectivenessState.NOT_EVALUATED)
    observation_start: datetime
    observation_end: datetime
    pre_implementation_count: int = 0
    post_implementation_count: int = 0
    subsequent_incident_ids: List[str] = Field(default_factory=list)
    summary: str
    limitations: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

"""Phase 50: Safety Learning Candidate Patterns Schemas.

Defines pattern candidate models, detection states, and evidence references.
Distinguishes pattern candidates from confirmed root causes.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class PatternState(str, Enum):
    """Lifecycle status of an identified safety pattern candidate."""

    CANDIDATE = "CANDIDATE"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"


class SafetyPatternCandidate(BaseModel):
    """Identified recurring safety pattern candidate supported by historical evidence."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"pat-{uuid.uuid4().hex[:12]}")
    title: str
    description: str
    pattern_type: str = Field(description="e.g. PROVIDER_REPEATED_TIMEOUT, WORKFLOW_STEP_BLOCK, POLICY_CONTEXT_MISSING")
    state: PatternState = Field(default=PatternState.CANDIDATE)
    occurrence_count: int = Field(ge=1)
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list, description="List of pointers (incident_id, decision_id, etc.)")
    affected_subsystem: str
    correlation_signature: Optional[str] = None
    observation_window_start: datetime
    observation_window_end: datetime
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

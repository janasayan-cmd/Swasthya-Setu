"""Phase 64: Clinical Safety Risk Handoff Outcome Schemas.

Defines schemas for downstream destination outcomes, outcome ingestion requests,
and immutable outcome records.
Non-Negotiable Invariants:
- OUTCOME RECEIVED != OUTCOME RECONCILED
- OUTCOME RECONCILED != RISK ELIMINATED
- A malformed outcome must not update authoritative destination state.
- A missing outcome must not be interpreted as a successful outcome.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_risk_handoff import HandoffDestinationPhase


class HandoffOutcomeRecord(BaseModel):
    """Immutable record capturing an authoritative outcome reported by a destination."""

    model_config = ConfigDict(extra="ignore")

    outcome_id: str = Field(default_factory=lambda: f"otc-{uuid.uuid4().hex[:12]}")
    handoff_id: str
    destination_phase: HandoffDestinationPhase
    destination_workflow_ref: str
    outcome_type: str
    outcome_status: str
    revision: str = "v1.0.0"
    provenance: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_duplicate: bool = False
    is_conflicted: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)


class IngestOutcomeRequest(BaseModel):
    """Request payload to ingest an outcome reported by a downstream destination."""

    model_config = ConfigDict(extra="ignore")

    destination_workflow_ref: str
    outcome_type: str
    outcome_status: str
    provenance: str
    revision: Optional[str] = "v1.0.0"
    payload: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None

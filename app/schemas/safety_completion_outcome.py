"""Phase 65: Safety Completion Outcome Schemas.

Defines schemas for cross-phase destination outcome verification and reconciliation references.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class OutcomeVerificationStatus(str, Enum):
    """Status of cross-phase outcome verification."""

    UNVERIFIED = "UNVERIFIED"
    VERIFYING = "VERIFYING"
    VERIFIED_TERMINAL = "VERIFIED_TERMINAL"
    PENDING_DESTINATION = "PENDING_DESTINATION"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    DESTINATION_FAILED = "DESTINATION_FAILED"
    DESTINATION_UNAVAILABLE = "DESTINATION_UNAVAILABLE"


class CompletionOutcomeReference(BaseModel):
    """Reference to an authoritative downstream destination outcome."""

    model_config = ConfigDict(extra="ignore")

    outcome_ref_id: str = Field(default_factory=lambda: f"outref-{uuid.uuid4().hex[:12]}")
    completion_id: str
    originating_handoff_id: str
    destination_phase: str
    destination_workflow_ref: str
    authoritative_destination_status: str
    verification_status: OutcomeVerificationStatus = OutcomeVerificationStatus.UNVERIFIED

    outcome_revision: str = "v1.0.0"
    contract_version: str = "v1.0.0"
    is_terminal: bool = False
    is_reconciled: bool = False
    is_superseded: bool = False

    evidence_references: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    provenance: str = "PHASE_64_RECONCILIATION"

    outcome_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

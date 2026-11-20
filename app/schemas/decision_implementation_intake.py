"""Phase 73: Approved Management Decision Intake Schemas.

Defines schemas for:
- Ingesting approved decisions from Phase 72
- Validating authorization integrity and decision eligibility
- Quarantining or rejecting invalid, draft, or superseded decisions
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DecisionIntakeStatus(str, Enum):
    """Status of decision ingestion into Phase 73 implementation tracking."""

    INTAKE_ACCEPTED = "INTAKE_ACCEPTED"
    INTAKE_REJECTED = "INTAKE_REJECTED"
    QUARANTINED = "QUARANTINED"


class DecisionIntakeRecord(BaseModel):
    """Domain record representing an ingested decision from Phase 72."""

    model_config = ConfigDict(extra="ignore")

    intake_id: str = Field(default_factory=lambda: f"gdit-{uuid.uuid4().hex[:12]}")
    decision_id: str
    source_review_id: str
    decision_version: int = 1
    decision_title: str
    decision_category: str
    decision_rationale: str

    decided_by_id: str
    decided_by_role: str
    decided_at: datetime
    effective_date: Optional[datetime] = None

    supporting_evidence_refs: List[str] = Field(default_factory=list)
    assigned_management_owner: Optional[str] = None
    required_outcome: str
    conditions_and_limitations: List[str] = Field(default_factory=list)
    supersession_status: str = "ACTIVE"

    intake_status: DecisionIntakeStatus = DecisionIntakeStatus.INTAKE_ACCEPTED
    rejection_reason: Optional[str] = None

    organization_id: str
    facility_id: Optional[str] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingested_by: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DecisionIntakeRequest(BaseModel):
    """Request payload to ingest an approved management decision."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str
    required_outcome: str
    effective_date: Optional[datetime] = None
    assigned_management_owner: Optional[str] = None
    conditions_and_limitations: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

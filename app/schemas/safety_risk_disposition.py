"""Phase 63: Clinical Safety Risk Disposition Schemas.

Defines governed risk dispositions and disposition records.
Non-Negotiable Invariants:
- RISK DISPOSITION != CLINICAL ACTION
- RISK DISPOSITION != RISK ACCEPTANCE
- RISK REVIEW != INCIDENT INVESTIGATION
- NO_FURTHER_REVIEW_AT_THIS_TIME must NEVER be interpreted as SAFE, NO_RISK,
  RISK_ELIMINATED, RISK_ACCEPTED, or CLINICALLY_CLEAR.
- Phase 63 CANNOT independently accept risk (Phase 51 owns risk acceptance).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RiskDispositionType(str, Enum):
    """Authoritative risk disposition outcomes for Phase 63."""

    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    ADDITIONAL_EVIDENCE_REQUIRED = "ADDITIONAL_EVIDENCE_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    INCIDENT_REVIEW_REQUIRED = "INCIDENT_REVIEW_REQUIRED"
    ASSURANCE_REVIEW_REQUIRED = "ASSURANCE_REVIEW_REQUIRED"
    EFFECTIVENESS_REVIEW_REQUIRED = "EFFECTIVENESS_REVIEW_REQUIRED"
    GOVERNANCE_REVIEW_REQUIRED = "GOVERNANCE_REVIEW_REQUIRED"
    CONTROLLED_ACTION_REVIEW_REQUIRED = "CONTROLLED_ACTION_REVIEW_REQUIRED"
    SAFETY_LEARNING_REQUIRED = "SAFETY_LEARNING_REQUIRED"
    SAFETY_IMPROVEMENT_REQUIRED = "SAFETY_IMPROVEMENT_REQUIRED"
    MULTI_ROUTE = "MULTI_ROUTE"
    NO_FURTHER_REVIEW_AT_THIS_TIME = "NO_FURTHER_REVIEW_AT_THIS_TIME"
    BLOCKED = "BLOCKED"


class RiskDispositionRecord(BaseModel):
    """Immutable record capturing the governed risk disposition outcome."""

    model_config = ConfigDict(extra="ignore")

    disposition_id: str = Field(default_factory=lambda: f"disp-{uuid.uuid4().hex[:12]}")
    review_id: str
    disposition_type: RiskDispositionType
    authorized_by: str
    authorizer_role: str
    reasoning: str
    prohibited_claims_acknowledged: bool = True
    resulting_routes: List[str] = Field(default_factory=list)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecordDispositionRequest(BaseModel):
    """Request payload to record a governed risk disposition."""

    model_config = ConfigDict(extra="ignore")

    disposition_type: RiskDispositionType
    reasoning: str
    resulting_routes: Optional[List[str]] = None
    is_ai: bool = False
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DispositionResponse(BaseModel):
    """Response payload for a recorded disposition."""

    model_config = ConfigDict(extra="ignore")

    disposition_id: str
    review_id: str
    disposition_type: RiskDispositionType
    recorded_at: datetime
    message: str

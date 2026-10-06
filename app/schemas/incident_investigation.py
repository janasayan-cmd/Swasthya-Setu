"""Phase 49: Incident Investigation & Root-Cause Hypotheses Schemas.

Distinguishes hypotheses from confirmed root causes, tracking investigator
findings and preserving uncertainty throughout the safety investigation.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class RootCauseCategory(str, Enum):
    """Controlled taxonomy of candidate root causes."""

    SOFTWARE_DEFECT = "SOFTWARE_DEFECT"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    DATA_ERROR = "DATA_ERROR"
    USER_ERROR = "USER_ERROR"
    WORKFLOW_DESIGN = "WORKFLOW_DESIGN"
    INTEGRATION_FAILURE = "INTEGRATION_FAILURE"
    SECURITY_EVENT = "SECURITY_EVENT"
    UNKNOWN = "UNKNOWN"
    MULTIPLE_FACTORS = "MULTIPLE_FACTORS"


class HypothesisStatus(str, Enum):
    """Lifecycle status of an investigative root-cause hypothesis."""

    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    CONFIRMED = "CONFIRMED"


class RootCauseHypothesis(BaseModel):
    """A documented hypothesis investigated during a safety review."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"hyp-{uuid.uuid4().hex[:12]}")
    incident_id: str
    category: RootCauseCategory
    title: str
    statement: str
    status: HypothesisStatus = Field(default=HypothesisStatus.PROPOSED)
    proposed_by_id: str
    proposed_by_role: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    investigator_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestigationRecord(BaseModel):
    """Consolidated state of an incident safety investigation."""

    model_config = ConfigDict(extra="ignore")

    incident_id: str
    investigator_id: Optional[str] = None
    investigator_role: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hypotheses: List[RootCauseHypothesis] = Field(default_factory=list)
    confirmed_root_cause: Optional[str] = None
    findings_summary: Optional[str] = None
    completed_at: Optional[datetime] = None


class HypothesisCreateRequest(BaseModel):
    """Payload to propose a new root-cause hypothesis."""

    model_config = ConfigDict(extra="forbid")

    category: RootCauseCategory
    title: str
    statement: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)


class HypothesisStatusUpdateRequest(BaseModel):
    """Payload to update hypothesis validation status (e.g. SUPPORTED, REJECTED, CONFIRMED)."""

    model_config = ConfigDict(extra="forbid")

    status: HypothesisStatus
    notes: Optional[str] = None
    evidence_id: Optional[str] = None

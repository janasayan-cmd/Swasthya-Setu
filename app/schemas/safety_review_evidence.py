"""Phase 63: Clinical Safety Review Evidence Schemas.

Defines evidence sufficiency states, evidence references, and request/submission models.
Non-Negotiable Invariants:
- EVIDENCE != PROOF OF ZERO RISK
- INSUFFICIENT / UNKNOWN / CONFLICTED != SAFE
- Missing evidence must NEVER be interpreted as evidence of safety.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class EvidenceSufficiencyState(str, Enum):
    """Sufficiency classification of evidence supporting a risk review."""

    SUFFICIENT = "SUFFICIENT"
    SUFFICIENT_WITH_LIMITATIONS = "SUFFICIENT_WITH_LIMITATIONS"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class EvidenceReference(BaseModel):
    """Authoritative reference and metadata for supporting or counter-evidence."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:12]}")
    source: str
    provenance: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope: Dict[str, Any] = Field(default_factory=dict)
    version: str = "v1.0.0"
    completeness: float = Field(default=1.0, ge=0.0, le=1.0)
    consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)
    is_counter_evidence: bool = False
    limitations: List[str] = Field(default_factory=list)
    dependency_available: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RequestEvidenceRequest(BaseModel):
    """Request payload to request additional evidence for a review."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    target_source: str
    evidence_types: List[str] = Field(default_factory=list)
    question_id: Optional[str] = None
    urgency_notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class SubmitEvidenceRequest(BaseModel):
    """Request payload to attach/submit evidence for a review."""

    model_config = ConfigDict(extra="ignore")

    source: str
    provenance: str
    evidence_payload: Dict[str, Any] = Field(default_factory=dict)
    version: str = "v1.0.0"
    is_counter_evidence: bool = False
    limitations: List[str] = Field(default_factory=list)
    question_id: Optional[str] = None
    idempotency_key: Optional[str] = None

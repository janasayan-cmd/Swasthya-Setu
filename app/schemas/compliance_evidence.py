"""Phase 69: Compliance Evidence Management Schemas.

Defines schemas for:
- Traceable compliance evidence index
- Evidence validity status and classification
- Reconciliation and registration payloads
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class EvidenceValidityStatus(str, Enum):
    """Integrity and validity status of a compliance evidence item."""

    VALID = "VALID"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"
    UNVERIFIED = "UNVERIFIED"


class EvidenceCategory(str, Enum):
    """Functional origin category of supporting compliance evidence."""

    AUDIT_EVENT = "AUDIT_EVENT"
    AUTHORIZATION_DECISION = "AUTHORIZATION_DECISION"
    CONSENT_RECORD = "CONSENT_RECORD"
    DISPOSITION_RECORD = "DISPOSITION_RECORD"
    POST_CLOSURE_VERIFICATION = "POST_CLOSURE_VERIFICATION"
    DECISION_ASSURANCE = "DECISION_ASSURANCE"
    EFFECTIVENESS_REPORT = "EFFECTIVENESS_REPORT"
    CORRECTIVE_ACTION_RECORD = "CORRECTIVE_ACTION_RECORD"
    TECHNICAL_CONFIGURATION = "TECHNICAL_CONFIGURATION"
    POLICY_DOCUMENT = "POLICY_DOCUMENT"


class AccessClassification(str, Enum):
    """Confidentiality tier for compliance evidence items."""

    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class ComplianceEvidenceRecord(BaseModel):
    """Domain record representing an indexed piece of compliance evidence."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: f"gevd-{uuid.uuid4().hex[:12]}")
    requirement_id: str
    control_id: Optional[str] = None
    source_phase: str  # e.g. "PHASE_48", "PHASE_63", "PHASE_68"
    source_record_id: str
    evidence_category: EvidenceCategory
    evidence_version: str = "v1.0.0"
    effective_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance_details: Dict[str, Any] = Field(default_factory=dict)
    validity_status: EvidenceValidityStatus = EvidenceValidityStatus.VALID
    checksum: Optional[str] = None
    access_classification: AccessClassification = AccessClassification.INTERNAL
    retention_class: str = "STANDARD_7_YEARS"
    is_accessible: bool = True
    last_verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RegisterEvidenceRequest(BaseModel):
    """Request payload to index a new evidence reference against a requirement."""

    model_config = ConfigDict(extra="ignore")

    requirement_id: Optional[str] = None
    control_id: Optional[str] = None
    source_phase: str
    source_record_id: str
    evidence_category: EvidenceCategory
    evidence_version: Optional[str] = "v1.0.0"
    effective_timestamp: Optional[datetime] = None
    provenance_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    validity_status: Optional[EvidenceValidityStatus] = EvidenceValidityStatus.VALID
    checksum: Optional[str] = None
    access_classification: Optional[AccessClassification] = AccessClassification.INTERNAL
    retention_class: Optional[str] = "STANDARD_7_YEARS"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReconcileEvidenceRequest(BaseModel):
    """Request payload to reconcile evidence references across authoritative source systems."""

    model_config = ConfigDict(extra="ignore")

    reconciliation_scope: Optional[str] = "ALL_CONTROLS"
    verification_depth: Optional[str] = "STANDARD"
    include_stale: Optional[bool] = False
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

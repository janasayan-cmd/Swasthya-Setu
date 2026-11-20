"""Phase 74: Adoption Evidence & Operational Indicators Schemas.

Defines schemas and models for:
- Operational adoption evidence intake, indexing, verification, and rejection
- Configurable adoption indicators across procedural, behavioral, and operational criteria
- Strict evidence-backed indicator assessments preserving uncertainty
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.governance_change_adoption_registration import OperationalScope


class AdoptionEvidenceCategory(str, Enum):
    """Categorization of operational evidence artifacts."""
    PROCEDURE_UPDATE = "PROCEDURE_UPDATE"
    WORK_INSTRUCTION = "WORK_INSTRUCTION"
    TRAINING_COMPLETION = "TRAINING_COMPLETION"
    STAFF_COMMUNICATION = "STAFF_COMMUNICATION"
    SYSTEM_CONFIGURATION = "SYSTEM_CONFIGURATION"
    AUDIT_EVENT = "AUDIT_EVENT"
    CHECKLIST_RECORD = "CHECKLIST_RECORD"
    PROCESS_EXECUTION = "PROCESS_EXECUTION"
    DEPARTMENT_CONFIRMATION = "DEPARTMENT_CONFIRMATION"
    SUPERVISOR_VERIFICATION = "SUPERVISOR_VERIFICATION"
    ASSESSMENT_RESULT = "ASSESSMENT_RESULT"
    OTHER = "OTHER"


class EvidenceVerificationStatus(str, Enum):
    """Authoritative verification state for submitted operational evidence."""
    SUBMITTED = "SUBMITTED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class AdoptionEvidenceRecord(BaseModel):
    """Authoritative record for an operational adoption evidence item."""
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    registration_id: str
    tenant_id: str
    baseline_version: str
    title: str
    description: Optional[str] = None
    category: AdoptionEvidenceCategory
    organizational_scope: OperationalScope = Field(default_factory=OperationalScope)
    source_system: str
    source_reference: str
    collected_at: str
    submitted_at: str
    submitting_actor_id: str
    verification_status: EvidenceVerificationStatus = EvidenceVerificationStatus.SUBMITTED
    reviewer_id: Optional[str] = None
    verified_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    valid_until: Optional[str] = None
    integrity_hash: Optional[str] = None
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SubmitAdoptionEvidenceRequest(BaseModel):
    """Request payload to submit operational evidence."""
    model_config = ConfigDict(extra="forbid")

    baseline_version: str
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    category: AdoptionEvidenceCategory
    organizational_scope: OperationalScope = Field(default_factory=OperationalScope)
    source_system: str = Field(..., min_length=2)
    source_reference: str = Field(..., min_length=2)
    collected_at: str
    valid_until: Optional[str] = None
    integrity_hash: Optional[str] = None
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)


class VerifyAdoptionEvidenceRequest(BaseModel):
    """Request payload to verify submitted evidence."""
    model_config = ConfigDict(extra="forbid")

    verification_comments: Optional[str] = None


class RejectAdoptionEvidenceRequest(BaseModel):
    """Request payload to reject submitted evidence."""
    model_config = ConfigDict(extra="forbid")

    rejection_reason: str = Field(..., min_length=5)


# -----------------------------------------------------------------------------
# Adoption Indicators
# -----------------------------------------------------------------------------


class IndicatorCategory(str, Enum):
    """Domain category of adoption indicators."""
    PROCEDURAL = "PROCEDURAL"
    COMMUNICATION = "COMMUNICATION"
    TRAINING_READINESS = "TRAINING_READINESS"
    OWNERSHIP_ASSIGNMENT = "OWNERSHIP_ASSIGNMENT"
    WORKFLOW_INTEGRATION = "WORKFLOW_INTEGRATION"
    CONTROL_USAGE = "CONTROL_USAGE"
    SYSTEM_CONFIGURATION = "SYSTEM_CONFIGURATION"
    DEVIATION_RATE = "DEVIATION_RATE"
    SUSTAINABILITY = "SUSTAINABILITY"


class IndicatorOutcome(str, Enum):
    """Strictly governed outcome of an indicator assessment."""
    NOT_ASSESSED = "NOT_ASSESSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    ACHIEVED = "ACHIEVED"
    PARTIALLY_ACHIEVED = "PARTIALLY_ACHIEVED"
    NOT_ACHIEVED = "NOT_ACHIEVED"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class ConfidenceLevel(str, Enum):
    """Confidence level of the indicator assessment."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class AdoptionIndicatorRecord(BaseModel):
    """Authoritative definition and current assessment of an adoption indicator."""
    model_config = ConfigDict(extra="forbid")

    indicator_id: str
    registration_id: str
    tenant_id: str
    indicator_key: str
    title: str
    category: IndicatorCategory
    measurement_criteria: str
    target_threshold: str
    current_value: Optional[str] = None
    outcome: IndicatorOutcome = IndicatorOutcome.NOT_ASSESSED
    evidence_ids_used: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    assessed_by: Optional[str] = None
    assessed_at: Optional[str] = None
    rationale: Optional[str] = None
    limitations_noted: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CreateAdoptionIndicatorRequest(BaseModel):
    """Request payload to define an adoption indicator."""
    model_config = ConfigDict(extra="forbid")

    indicator_key: str = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=3, max_length=255)
    category: IndicatorCategory
    measurement_criteria: str = Field(..., min_length=5)
    target_threshold: str = Field(..., min_length=1)


class AssessIndicatorRequest(BaseModel):
    """Request payload to record an indicator assessment against evidence."""
    model_config = ConfigDict(extra="forbid")

    current_value: str = Field(..., min_length=1)
    outcome: IndicatorOutcome
    evidence_ids_used: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    rationale: str = Field(..., min_length=5)
    limitations_noted: List[str] = Field(default_factory=list)

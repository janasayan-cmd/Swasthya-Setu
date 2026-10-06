"""Phase 49: Clinical Safety Incident Schemas.

Defines safety signal models, controlled incident types, lifecycle statuses,
severity classifications, and incident management request/response contracts.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class IncidentType(str, Enum):
    """Controlled taxonomy of clinical safety incident types."""

    CLINICAL_SAFETY = "CLINICAL_SAFETY"
    MEDICATION_SAFETY = "MEDICATION_SAFETY"
    TRIAGE_SAFETY = "TRIAGE_SAFETY"
    AI_SAFETY = "AI_SAFETY"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    DATA_RECONCILIATION = "DATA_RECONCILIATION"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    WORKFLOW_SAFETY = "WORKFLOW_SAFETY"
    AUTHORIZATION = "AUTHORIZATION"
    CONSENT = "CONSENT"
    PRIVACY = "PRIVACY"
    SECURITY = "SECURITY"
    NOTIFICATION = "NOTIFICATION"
    INTEROPERABILITY = "INTEROPERABILITY"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    SYSTEM_FAILURE = "SYSTEM_FAILURE"
    NEAR_MISS = "NEAR_MISS"
    PATIENT_IMPACT = "PATIENT_IMPACT"


class IncidentStatus(str, Enum):
    """Explicit lifecycle statuses for safety incidents."""

    DETECTED = "DETECTED"
    TRIAGED = "TRIAGED"
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CONTAINMENT_REQUIRED = "CONTAINMENT_REQUIRED"
    CONTAINED = "CONTAINED"
    ROOT_CAUSE_REVIEW = "ROOT_CAUSE_REVIEW"
    CORRECTIVE_ACTION_REQUIRED = "CORRECTIVE_ACTION_REQUIRED"
    CORRECTIVE_ACTION_IN_PROGRESS = "CORRECTIVE_ACTION_IN_PROGRESS"
    VALIDATION = "VALIDATION"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    DISPROVEN = "DISPROVEN"
    DUPLICATE = "DUPLICATE"
    CANCELLED = "CANCELLED"
    UNRESOLVED = "UNRESOLVED"
    REOPENED = "REOPENED"


class IncidentSeverity(str, Enum):
    """Controlled assessment of potential or actual safety severity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentImpactStatus(str, Enum):
    """Impact classification preserving investigative uncertainty."""

    NO_KNOWN_IMPACT = "NO_KNOWN_IMPACT"
    POTENTIAL_IMPACT = "POTENTIAL_IMPACT"
    NEAR_MISS = "NEAR_MISS"
    CONFIRMED_IMPACT = "CONFIRMED_IMPACT"
    UNKNOWN = "UNKNOWN"


class IncidentSource(str, Enum):
    """Originating source of the safety signal or incident."""

    SYSTEM = "SYSTEM"
    CLINICIAN = "CLINICIAN"
    PATIENT = "PATIENT"
    ADMINISTRATOR = "ADMINISTRATOR"
    MONITORING = "MONITORING"
    AI_SAFETY_GATE = "AI_SAFETY_GATE"
    RULE_ENGINE = "RULE_ENGINE"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    WORKFLOW = "WORKFLOW"
    TASK = "TASK"
    ALERT = "ALERT"
    DATA_RECONCILIATION = "DATA_RECONCILIATION"


class SafetySignal(BaseModel):
    """Lightweight safety event emitted by runtime gates, providers, or workflows."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"sig-{uuid.uuid4().hex[:12]}")
    source: IncidentSource = Field(description="Originating subsystem or actor type")
    incident_type: IncidentType = Field(description="Tentative incident category")
    summary: str = Field(description="Fact-based summary of detected event. Avoids unsubstantiated blame.")
    description: Optional[str] = Field(default=None)
    severity_candidate: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)
    impact_candidate: IncidentImpactStatus = Field(default=IncidentImpactStatus.UNKNOWN)
    decision_id: Optional[str] = None
    safety_check_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    alert_id: Optional[str] = None
    patient_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_version: Optional[int] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentRecord(BaseModel):
    """Authoritative safety incident record tracking investigation and resolution."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:12]}")
    title: str
    description: str
    incident_type: IncidentType
    status: IncidentStatus = Field(default=IncidentStatus.DETECTED)
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM)
    impact_status: IncidentImpactStatus = Field(default=IncidentImpactStatus.UNKNOWN)
    source: IncidentSource = Field(default=IncidentSource.SYSTEM)
    patient_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_version: Optional[int] = None
    decision_id: Optional[str] = None
    safety_check_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    alert_id: Optional[str] = None
    provider_request_id: Optional[str] = None
    signal_ids: List[str] = Field(default_factory=list)
    assigned_investigator_id: Optional[str] = None
    assigned_investigator_role: Optional[str] = None
    containment_status: Optional[str] = None
    containment_action: Optional[str] = None
    root_cause_category: Optional[str] = None
    root_cause_confirmed: bool = False
    duplicate_of_id: Optional[str] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    contained_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    closure_reason: Optional[str] = None
    resolution_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetySignalCreateRequest(BaseModel):
    """Payload to register an internal safety signal."""

    model_config = ConfigDict(extra="forbid")

    source: IncidentSource
    incident_type: IncidentType
    summary: str
    description: Optional[str] = None
    severity_candidate: IncidentSeverity = IncidentSeverity.MEDIUM
    impact_candidate: IncidentImpactStatus = IncidentImpactStatus.UNKNOWN
    decision_id: Optional[str] = None
    safety_check_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    alert_id: Optional[str] = None
    patient_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_version: Optional[int] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentCreateRequest(BaseModel):
    """Payload to create an incident candidate directly."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    incident_type: IncidentType
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    impact_status: IncidentImpactStatus = IncidentImpactStatus.UNKNOWN
    source: IncidentSource = IncidentSource.SYSTEM
    patient_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_version: Optional[int] = None
    decision_id: Optional[str] = None
    safety_check_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    alert_id: Optional[str] = None
    signal_ids: List[str] = Field(default_factory=list)
    occurred_at: Optional[datetime] = None


class IncidentTriageRequest(BaseModel):
    """Payload for clinical/safety officer triage."""

    model_config = ConfigDict(extra="forbid")

    severity: IncidentSeverity
    impact_status: IncidentImpactStatus
    triage_notes: str
    requires_containment: bool = False


class IncidentAssignmentRequest(BaseModel):
    """Payload to assign an investigator."""

    model_config = ConfigDict(extra="forbid")

    investigator_id: str
    investigator_role: str
    assignment_notes: Optional[str] = None


class IncidentContainmentRequest(BaseModel):
    """Payload to record containment actions taken."""

    model_config = ConfigDict(extra="forbid")

    containment_action: str
    containment_type: str = Field(description="e.g. DISABLE_PROVIDER, PAUSE_WORKFLOW, REQUIRE_MANUAL_REVIEW")
    details: Dict[str, Any] = Field(default_factory=dict)


class IncidentResolutionRequest(BaseModel):
    """Payload to mark incident resolved prior to closure."""

    model_config = ConfigDict(extra="forbid")

    resolution_summary: str
    root_cause_category: Optional[str] = None
    root_cause_confirmed: bool = False


class IncidentClosureRequest(BaseModel):
    """Payload for final incident closure validation."""

    model_config = ConfigDict(extra="forbid")

    closure_reason: str
    validation_confirmed: bool = True


class IncidentReopenRequest(BaseModel):
    """Payload to reopen a previously closed/resolved incident."""

    model_config = ConfigDict(extra="forbid")

    reopen_reason: str
    new_findings: Optional[str] = None

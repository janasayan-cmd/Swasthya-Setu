"""Pydantic schemas and domain models for External Data Ingestion & Clinical Reconciliation (Phase 45).

SAFETY INVARIANTS:
- IMPORT != VERIFICATION
- IMPORT != CLINICAL TRUTH
- EXTERNAL DATA != HEALTHSETU TRUTH
- EXTERNAL DATA != DIAGNOSIS / TREATMENT / PRESCRIPTION / MEDICATION CHANGE / TRIAGE / EMERGENCY DISPATCH
- FHIR VALID != CLINICALLY VERIFIED
- SUCCESSFUL INGESTION != RECONCILIATION
- MATCHED PATIENT != VERIFIED CLINICAL DATA
- DUPLICATE CANDIDATE != CONFIRMED DUPLICATE
- CONFLICT != AUTOMATIC CORRECTION
- EXTERNAL SOURCE AUTHENTICATED != DATA VERIFIED
- AI EXTRACTION != CLINICAL VERIFICATION
- AI MATCH != PATIENT IDENTITY CONFIRMATION
- NO AUTOMATIC CLINICAL OVERWRITE
- NO SILENT MERGE
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# ENUMS
# ==============================================================================

class SourceType(str, Enum):
    """Supported conceptual external data source categories."""

    HOSPITAL = "HOSPITAL"
    CLINIC = "CLINIC"
    LABORATORY = "LABORATORY"
    DIAGNOSTIC_CENTER = "DIAGNOSTIC_CENTER"
    CLINICIAN_ORGANIZATION = "CLINICIAN_ORGANIZATION"
    HEALTHCARE_NETWORK = "HEALTHCARE_NETWORK"
    INTEROPERABILITY_PROVIDER = "INTEROPERABILITY_PROVIDER"
    PATIENT_AUTHORIZED_EXTERNAL = "PATIENT_AUTHORIZED_EXTERNAL"
    HEALTHSETU_CONNECTED_SYSTEM = "HEALTHSETU_CONNECTED_SYSTEM"
    FHIR_ENDPOINT = "FHIR_ENDPOINT"
    HL7_SOURCE = "HL7_SOURCE"
    DOCUMENT_EXCHANGE_PROVIDER = "DOCUMENT_EXCHANGE_PROVIDER"


class SourceTrustState(str, Enum):
    """External source trust and registration status."""

    REGISTERED = "REGISTERED"
    AUTHORIZED = "AUTHORIZED"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"
    REVOKED = "REVOKED"
    UNKNOWN = "UNKNOWN"


class IngestionStatus(str, Enum):
    """Authoritative lifecycle state machine for external data ingestion."""

    RECEIVED = "RECEIVED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    VALIDATING = "VALIDATING"
    ACCEPTED = "ACCEPTED"
    PROCESSING = "PROCESSING"
    MAPPED = "MAPPED"
    IDENTITY_PENDING = "IDENTITY_PENDING"
    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INTEGRATED = "INTEGRATED"

    # Terminal / Alternative states
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class DataTrustStatus(str, Enum):
    """Clinical verification and trust status of imported external data."""

    IMPORTED = "IMPORTED"
    UNVERIFIED = "UNVERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CONFLICTED = "CONFLICTED"
    CORRECTED = "CORRECTED"


class IdentityMatchOutcome(str, Enum):
    """Deterministic patient identity resolution outcomes."""

    MATCH_CONFIRMED = "MATCH_CONFIRMED"
    MATCH_CANDIDATE = "MATCH_CANDIDATE"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
    NO_MATCH = "NO_MATCH"
    CONFLICT = "CONFLICT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# ==============================================================================
# SOURCE CONTEXT
# ==============================================================================

class ExternalSourceContext(BaseModel):
    """Authoritative context representing a registered external data source."""

    model_config = ConfigDict(extra="ignore")

    source_id: str = Field(description="Unique source system code e.g. 'labcorp-east', 'epic-apollo'")
    source_type: SourceType = Field(description="Conceptual category of the source")
    source_name: str = Field(description="Human readable name of external facility/source")
    organization_id: Optional[str] = Field(default=None, description="Optional tenant organization ID")
    facility_id: Optional[str] = Field(default=None, description="Optional facility identifier")
    trust_state: SourceTrustState = Field(default=SourceTrustState.ACTIVE, description="Trust lifecycle state")
    allowed_resource_types: List[str] = Field(
        default_factory=lambda: [
            "Patient", "Observation", "Condition", "AllergyIntolerance",
            "MedicationRequest", "Medication", "DiagnosticReport",
            "DocumentReference", "CarePlan"
        ],
        description="List of clinical resource types permitted for exchange",
    )
    api_key_hash: Optional[str] = Field(default=None, description="SHA256 hash of API credential")
    shared_secret: Optional[str] = Field(default=None, description="Secret for HMAC webhook signatures")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_authorized(self) -> bool:
        """Source must be in ACTIVE or AUTHORIZED state to submit data."""
        return self.trust_state in (SourceTrustState.ACTIVE, SourceTrustState.AUTHORIZED)


# ==============================================================================
# PROVENANCE RECORD
# ==============================================================================

class IngestionProvenanceRecord(BaseModel):
    """Detailed origin and transformation provenance for ingested resources."""

    model_config = ConfigDict(extra="ignore")

    provenance_id: str = Field(default_factory=lambda: f"prov-{uuid.uuid4().hex[:12]}")
    ingestion_id: str
    source_organization: Optional[str] = None
    source_facility: Optional[str] = None
    source_system: str
    source_resource_id: str
    source_version: Optional[str] = None
    source_timestamp: Optional[datetime] = None
    received_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    transformation_version: str = Field(default="1.0")
    mapper_version: str = Field(default="FHIR_R4_V1")
    validation_result: str = Field(default="VALID")
    reconciliation_result: Optional[str] = None
    verification_state: DataTrustStatus = Field(default=DataTrustStatus.UNVERIFIED)


# ==============================================================================
# INGESTION REQUESTS & RECORDS
# ==============================================================================

class IngestionCreateRequest(BaseModel):
    """Inbound clinical data payload submission contract."""

    model_config = ConfigDict(extra="forbid")

    source_system: str = Field(min_length=1, max_length=100, description="Source system identifier")
    source_type: SourceType = Field(default=SourceType.INTEROPERABILITY_PROVIDER, description="Source category")
    source_organization_id: Optional[str] = Field(default=None, description="Source organization ID")
    source_facility_id: Optional[str] = Field(default=None, description="Source facility ID")
    resource_type: str = Field(min_length=1, max_length=60, description="Clinical resource type e.g. Observation, MedicationRequest")
    format: str = Field(default="FHIR", description="Interoperability standard ('FHIR', 'HL7')")
    format_version: Optional[str] = Field(default="R4", description="Specification version")
    external_resource_id: str = Field(min_length=1, max_length=100, description="Resource identifier in source system")
    external_patient_id: Optional[str] = Field(default=None, description="Patient identifier in external system")
    healthsetu_patient_id: Optional[str] = Field(default=None, description="HealthSetu patient ID if known")
    payload: Dict[str, Any] = Field(description="Raw external clinical resource JSON payload")
    purpose: str = Field(default="CARE_DELIVERY", description="Declared purpose for exchange")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Optional unique client idempotency key")
    api_key: Optional[str] = Field(default=None, description="Source API key for authentication")


class IngestionRecord(BaseModel):
    """Authoritative state record of an external data ingestion transaction."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str = Field(default_factory=lambda: f"ing-{uuid.uuid4().hex[:12]}")
    source_system: str
    source_type: SourceType
    source_organization_id: Optional[str] = None
    source_facility_id: Optional[str] = None
    resource_type: str
    format: str = "FHIR"
    format_version: str = "R4"
    external_resource_id: str
    external_patient_id: Optional[str] = None
    healthsetu_patient_id: Optional[str] = None
    status: IngestionStatus = IngestionStatus.RECEIVED
    verification_status: DataTrustStatus = DataTrustStatus.UNVERIFIED
    identity_outcome: Optional[IdentityMatchOutcome] = None
    reconciliation_id: Optional[str] = None
    reconciliation_status: Optional[str] = None
    raw_payload_hash: str = Field(description="SHA256 digest of original raw inbound payload")
    raw_payload_preview: Optional[Dict[str, Any]] = None
    mapped_data: Optional[Dict[str, Any]] = None
    provenance_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    quarantine_reason: Optional[str] = None
    retry_count: int = 0
    idempotency_key: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None


# ==============================================================================
# RESPONSES & ACTIONS
# ==============================================================================

class IngestionResponse(BaseModel):
    """API response envelope for ingestion transactions."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_system: str
    source_type: SourceType
    resource_type: str
    external_resource_id: str
    healthsetu_patient_id: Optional[str] = None
    status: IngestionStatus
    verification_status: DataTrustStatus
    identity_outcome: Optional[IdentityMatchOutcome] = None
    reconciliation_id: Optional[str] = None
    reconciliation_status: Optional[str] = None
    raw_payload_hash: str
    provenance_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class IngestionStatusResponse(BaseModel):
    """Lightweight lifecycle polling response model."""

    id: str
    status: IngestionStatus
    verification_status: DataTrustStatus
    identity_outcome: Optional[IdentityMatchOutcome] = None
    reconciliation_status: Optional[str] = None
    updated_at: datetime


class IngestionHistoryResponse(BaseModel):
    """Lifecycle transition and audit history response model."""

    ingestion_id: str
    history: List[Dict[str, Any]]


class IngestionListResponse(BaseModel):
    """Paginated list of ingestion records."""

    items: List[IngestionResponse]
    total: int
    page: int
    size: int


class ExternalRecordsListResponse(BaseModel):
    """External records associated with a patient."""

    patient_id: str
    records: List[IngestionResponse]
    total: int


class WebhookIngestionPayload(BaseModel):
    """Contract for inbound webhook callbacks from registered healthcare providers."""

    model_config = ConfigDict(extra="ignore")

    provider: str = Field(description="Name of provider adapter")
    event_id: str = Field(description="Unique provider event ID for replay prevention")
    event_type: str = Field(description="Provider event type e.g. 'lab.result_available'")
    timestamp: str = Field(description="ISO timestamp or unix epoch of webhook dispatch")
    signature: str = Field(description="HMAC SHA256 cryptographic signature header/field")
    nonce: str = Field(description="Cryptographic random nonce for replay protection")
    data: Dict[str, Any] = Field(description="External resource payload")


class ReconciliationResolveAction(BaseModel):
    """Action payload for clinician manual resolution of a clinical conflict."""

    model_config = ConfigDict(extra="forbid")

    resolution: str = Field(description="'ACCEPT_EXTERNAL', 'KEEP_INTERNAL', 'SUPERSEDE', 'DISCARD'")
    notes: Optional[str] = Field(default=None, description="Clinical rationale for resolution")

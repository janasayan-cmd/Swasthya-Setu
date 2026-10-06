"""Clinical Record Versioning & Temporal Contracts (Phase 46).

Defines:
- Version lifecycle types and temporal timestamp structures
- Clinical version models, change payloads, and optimistic concurrency contracts
- Invariants:
  - CURRENT STATE != COMPLETE HISTORY
  - UPDATE != OVERWRITE HISTORY
  - CORRECTION != DELETION
  - SUPERSESSION != DELETION
  - NEW VERSION != NEW CLINICAL EVENT
  - PROVENANCE != AUDIT
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class VersionType(str, Enum):
    """Semantic classification of a clinical record version transition."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    CORRECTED = "CORRECTED"
    AMENDED = "AMENDED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    RECONCILED = "RECONCILED"
    IMPORTED = "IMPORTED"
    MERGED = "MERGED"
    RESTORED = "RESTORED"


class RecordTemporalMetadata(BaseModel):
    """Multi-dimensional temporal timestamps distinguishing clinical event vs system ingestion.

    CRITICAL INVARIANT:
    These timestamps must NEVER be silently treated as interchangeable:
    - event_time: When clinical event actually occurred.
    - recorded_time: When information was entered into HealthSetu.
    - received_time: When external data was received.
    - updated_time: When the current record changed.
    - effective_time: When the state became clinically applicable.
    - expiration_time: When state stopped being clinically applicable.
    - verification_time: When clinician verification occurred.
    - supersession_time: When another version replaced this version as current.
    """

    model_config = ConfigDict(extra="ignore")

    event_time: Optional[datetime] = Field(default=None, description="Actual clinical occurrence time")
    recorded_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="HealthSetu record intake timestamp")
    received_time: Optional[datetime] = Field(default=None, description="Inbound external transmission received timestamp")
    updated_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of this version modification")
    effective_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Time when state became clinically active")
    expiration_time: Optional[datetime] = Field(default=None, description="Time when state ceased to be applicable")
    verification_time: Optional[datetime] = Field(default=None, description="Timestamp of clinical verification")
    supersession_time: Optional[datetime] = Field(default=None, description="Timestamp when replaced by newer current version")


class ClinicalVersionRecord(BaseModel):
    """Immutable snapshot of a clinical resource state at a specific version point."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str = Field(default_factory=lambda: f"ver-{uuid.uuid4().hex[:12]}", description="Unique version identifier")
    resource_id: str = Field(description="Canonical identifier of clinical entity")
    resource_type: str = Field(description="Domain resource type e.g. medication, allergy, condition, observation, document")
    patient_id: str = Field(description="Canonical HealthSetu patient ID")
    version_number: int = Field(ge=1, description="Monotonically increasing version index (1-indexed)")
    previous_version_number: Optional[int] = Field(default=None, description="Predecessor version number")
    version_type: VersionType = Field(default=VersionType.CREATED, description="Transition classification")
    is_current: bool = Field(default=True, description="True if this is the active current clinical state")
    temporal: RecordTemporalMetadata = Field(default_factory=RecordTemporalMetadata)
    state_data: Dict[str, Any] = Field(description="Clinical resource attributes at this point in time")
    actor_id: str = Field(description="User or source identifier executing the change")
    actor_role: str = Field(description="Role of actor e.g. DOCTOR, PATIENT, SYSTEM")
    actor_type: str = Field(default="CLINICIAN", description="Actor category e.g. CLINICIAN, PATIENT, SYSTEM, EXTERNAL")
    change_reason: str = Field(description="Clinical explanation justifying this modification")
    provenance_id: Optional[str] = Field(default=None, description="Reference to Phase 26/45 provenance record")
    source_system: Optional[str] = Field(default=None, description="Origin source system e.g. 'healthsetu', 'apollo-hosp'")
    source_version: Optional[str] = Field(default=None, description="Upstream source version number")
    verification_state: str = Field(default="UNVERIFIED", description="Trust status ('UNVERIFIED', 'VERIFIED', etc.)")
    is_deleted: bool = Field(default=False, description="Logical soft-deletion indicator")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VersionUpdateRequest(BaseModel):
    """Request contract for optimistic-concurrency controlled updates."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, description="Current version number expected by caller for concurrency check")
    changes: Dict[str, Any] = Field(description="Dictionary of field-level updates to apply")
    change_reason: str = Field(min_length=3, max_length=500, description="Mandatory clinical justification for change")
    event_time: Optional[datetime] = Field(default=None, description="Optional clinical occurrence time")
    effective_time: Optional[datetime] = Field(default=None, description="Optional effective start time")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Optional client idempotency key")


class VersionCorrectionRequest(BaseModel):
    """Request contract for correcting mistakes without overwriting historical version."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, description="Current version number expected by caller")
    corrected_data: Dict[str, Any] = Field(description="Accurate corrected fields")
    correction_reason: str = Field(min_length=3, max_length=500, description="Reason for correction (e.g. 'Dosage correction')")
    event_time: Optional[datetime] = Field(default=None, description="Optional clinical occurrence time")
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class VersionSupersedeRequest(BaseModel):
    """Request contract for superseding an obsolete clinical state."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, description="Current version number expected by caller")
    new_state_data: Dict[str, Any] = Field(description="New replacement clinical state")
    supersede_reason: str = Field(min_length=3, max_length=500, description="Reason for superseding prior record")
    event_time: Optional[datetime] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class VersionRestoreRequest(BaseModel):
    """Request contract to restore a historical state.

    CRITICAL INVARIANT:
    Restore DOES NOT delete intervening versions! It appends a NEW version
    whose state copies the target historical version.
    """

    model_config = ConfigDict(extra="forbid")

    target_version_number: int = Field(ge=1, description="Historical version number to restore")
    expected_current_version: int = Field(ge=1, description="Current version expected by caller")
    restore_reason: str = Field(min_length=3, max_length=500, description="Clinical justification for restoring historical state")
    idempotency_key: Optional[str] = Field(default=None, max_length=128)

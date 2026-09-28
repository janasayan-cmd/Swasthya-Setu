"""Pydantic schemas and models for Clinical Record Reconciliation (Phase 26)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid

from app.schemas.data_quality import ResolutionAction
from app.schemas.provenance import ProvenanceCategory


class ReconciliationStatus(str, Enum):
    """Lifecycle status of a clinical record reconciliation case (TRD Sec 13)."""
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE_CONFIRMED = "DUPLICATE_CONFIRMED"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"
    CORRECTED = "CORRECTED"
    SUPERSEDED = "SUPERSEDED"
    UNRESOLVED = "UNRESOLVED"
    FAILED = "FAILED"


class ReconciliationScope(str, Enum):
    """Clinical domains supported for cross-source reconciliation (TRD Sec 11, 19)."""
    ALL = "ALL"
    ALLERGIES = "ALLERGIES"
    MEDICATIONS = "MEDICATIONS"
    VITALS = "VITALS"
    CONDITIONS = "CONDITIONS"
    ENCOUNTERS = "ENCOUNTERS"
    DOCUMENTS = "DOCUMENTS"
    EXTERNAL_DATA = "EXTERNAL_DATA"
    EXTERNAL_IMPORTS = "EXTERNAL_IMPORTS"
    FULL_PATIENT_RECORD = "FULL_PATIENT_RECORD"


class ReconciliationResolutionAction(str, Enum):
    ACCEPT_CLINICIAN = "accept_clinician"
    ACCEPT_EXTERNAL = "accept_external"
    KEEP_BOTH_ANNOTATED = "keep_both_annotated"
    MARK_SUPERSEDED = "mark_superseded"
    REJECT_EXTERNAL = "reject_external"
    LEAVE_UNRESOLVED = "leave_unresolved"


class ReconciliationSourceItem(BaseModel):
    """Representation of an individual clinical record version being compared."""
    model_config = ConfigDict(extra="ignore")

    source_id: str
    source_category: ProvenanceCategory = ProvenanceCategory.CLINICIAN_ENTERED
    source_system: str = "HealthSetu"
    concept_name: str
    value: Dict[str, Any] = Field(default_factory=dict)
    is_verified: bool = False
    recorded_at: Optional[datetime] = None


class ReconciliationConflictItem(BaseModel):
    """Specific field-level divergence between records."""
    model_config = ConfigDict(extra="ignore")

    conflict_id: str = Field(default_factory=lambda: f"cnf_{uuid.uuid4().hex[:8]}")
    concept_name: str
    field_name: str
    internal_source_id: str
    internal_value: Any
    external_source_id: str
    external_value: Any
    description: str


class ReconciliationRecord(BaseModel):
    """Internal domain & persistence model for a reconciliation case."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:12]}")
    reconciliation_id: Optional[str] = None
    patient_id: str
    scope: ReconciliationScope
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    sources: List[ReconciliationSourceItem] = Field(default_factory=list)
    conflicts: List[ReconciliationConflictItem] = Field(default_factory=list)
    summary: str
    ai_assisted: bool = False
    ai_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_action: Optional[Any] = None
    resolution_notes: Optional[str] = None
    version: int = 1

    def model_post_init(self, __context: Any) -> None:
        if not self.reconciliation_id:
            self.reconciliation_id = self.id
        elif not self.id:
            self.id = self.reconciliation_id


class ReconciliationResponse(BaseModel):
    """Public presentation of a reconciliation case."""
    model_config = ConfigDict(extra="ignore")

    id: str
    reconciliation_id: Optional[str] = None
    patient_id: str
    scope: ReconciliationScope
    status: ReconciliationStatus
    sources: List[ReconciliationSourceItem] = Field(default_factory=list)
    conflicts: List[ReconciliationConflictItem] = Field(default_factory=list)
    summary: str
    ai_assisted: bool = False
    ai_summary: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_action: Optional[Any] = None
    resolution_notes: Optional[str] = None
    version: int = 1

    def model_post_init(self, __context: Any) -> None:
        if not self.reconciliation_id:
            self.reconciliation_id = self.id


class ReconciliationListResponse(BaseModel):
    """Paginated list of reconciliation cases."""
    model_config = ConfigDict(extra="ignore")

    total: int
    items: List[ReconciliationResponse]


class ReconciliationRequest(BaseModel):
    """Request to initiate cross-source comparison and reconciliation."""
    model_config = ConfigDict(extra="ignore")

    scope: ReconciliationScope = ReconciliationScope.MEDICATIONS
    external_records: List[Dict[str, Any]] = Field(default_factory=list)


class ReconciliationResolveRequest(BaseModel):
    """Human-authorized decision resolving a clinical discrepancy."""
    model_config = ConfigDict(extra="ignore")

    action: Any
    notes: Optional[str] = None
    reason: Optional[str] = None
    expected_version: Optional[int] = None
    chosen_source_item_id: Optional[str] = None
    correction_payload: Optional[Dict[str, Any]] = None

"""Pydantic schemas and models for Data Quality & Integrity (Phase 26)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class DataQualityFindingType(str, Enum):
    """Categorization of data quality anomalies (TRD Sec 15)."""
    MISSING_INFORMATION = "MISSING_INFORMATION"
    INCOMPLETE_RECORD = "INCOMPLETE_RECORD"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    CONFLICTING_INFORMATION = "CONFLICTING_INFORMATION"
    STALE_INFORMATION = "STALE_INFORMATION"
    PROVENANCE_MISSING = "PROVENANCE_MISSING"
    PROVENANCE_CONFLICT = "PROVENANCE_CONFLICT"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    EXTERNAL_DATA_CONFLICT = "EXTERNAL_DATA_CONFLICT"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


class FindingSeverity(str, Enum):
    """Severity rating for data quality findings."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Alias for backward and forward compatibility
DataQualitySeverity = FindingSeverity


class FindingStatus(str, Enum):
    """Review lifecycle status for data quality findings."""
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    UNRESOLVED = "UNRESOLVED"


# Alias
DataQualityFindingStatus = FindingStatus


class ResolutionAction(str, Enum):
    """Explicit human-authorized resolution decisions (TRD Sec 16)."""
    ACCEPT_PRIMARY = "ACCEPT_PRIMARY"
    ACCEPT_CLINICIAN_SOURCE = "ACCEPT_CLINICIAN_SOURCE"
    ACCEPT_IMPORTED = "ACCEPT_IMPORTED"
    KEEP_BOTH = "KEEP_BOTH"
    KEEP_BOTH_ANNOTATED = "KEEP_BOTH_ANNOTATED"
    MARK_SUPERSEDED = "MARK_SUPERSEDED"
    CONFIRM_DUPLICATE = "CONFIRM_DUPLICATE"
    MARK_DUPLICATE = "MARK_DUPLICATE"
    REJECT_DUPLICATE = "REJECT_DUPLICATE"
    APPLY_CORRECTION = "APPLY_CORRECTION"
    REJECT_FINDING = "REJECT_FINDING"
    LEAVE_UNRESOLVED = "LEAVE_UNRESOLVED"


# Alias
DataQualityResolutionAction = ResolutionAction


class ProvenanceReference(BaseModel):
    """Provenance context attached to clinical data and findings."""
    model_config = ConfigDict(extra="ignore")

    source: str
    source_type: str  # PATIENT_REPORTED, CLINICIAN_ENTERED, IMPORTED, DOCUMENT_EXTRACTED, AI_EXTRACTED
    system_id: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    recorded_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verification_state: str = "UNVERIFIED"
    is_external: bool = False


class DataQualityFindingCreate(BaseModel):
    """Schema for creating a new data quality finding."""
    model_config = ConfigDict(extra="ignore")

    patient_id: str
    resource_type: str
    resource_id: str
    resource_version: Optional[int] = 1
    finding_type: DataQualityFindingType
    severity: FindingSeverity = FindingSeverity.MEDIUM
    status: FindingStatus = FindingStatus.PENDING
    description: str
    rule_id: Optional[str] = None
    rule_version: Optional[str] = "1.0.0"
    source_references: List[str] = Field(default_factory=list)
    conflicting_references: List[str] = Field(default_factory=list)
    context_data: Dict[str, Any] = Field(default_factory=dict)


class DataQualityFindingRecord(BaseModel):
    """Internal domain & persistence model for a data quality finding."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"dqf_{uuid.uuid4().hex[:12]}")
    finding_id: Optional[str] = None
    patient_id: str
    resource_type: str
    resource_id: str
    resource_version: Optional[int] = 1
    finding_type: DataQualityFindingType
    status: FindingStatus = FindingStatus.PENDING
    severity: FindingSeverity = FindingSeverity.MEDIUM
    description: str
    source_references: List[str] = Field(default_factory=list)
    conflicting_references: List[str] = Field(default_factory=list)
    source_reference: Optional[ProvenanceReference] = None
    conflicting_resource_references: List[Dict[str, Any]] = Field(default_factory=list)
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    rule_version: Optional[str] = "1.0.0"
    context_data: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_action: Optional[ResolutionAction] = None
    resolution_notes: Optional[str] = None
    correction_payload: Optional[Dict[str, Any]] = None
    version: int = 1

    def model_post_init(self, __context: Any) -> None:
        if not self.finding_id:
            self.finding_id = self.id
        elif not self.id:
            self.id = self.finding_id


class DataQualityFindingResponse(BaseModel):
    """Public presentation of a data quality finding."""
    model_config = ConfigDict(extra="ignore")

    id: str
    finding_id: Optional[str] = None
    patient_id: str
    resource_type: str
    resource_id: str
    finding_type: DataQualityFindingType
    status: FindingStatus
    severity: FindingSeverity
    description: str
    source_references: List[str] = Field(default_factory=list)
    conflicting_references: List[str] = Field(default_factory=list)
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    rule_version: Optional[str] = None
    context_data: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_action: Optional[ResolutionAction] = None
    resolution_notes: Optional[str] = None
    version: int = 1

    def model_post_init(self, __context: Any) -> None:
        if not self.finding_id:
            self.finding_id = self.id


class DataQualityFindingListResponse(BaseModel):
    """Paginated list of data quality findings."""
    model_config = ConfigDict(extra="ignore")

    total: int
    items: List[DataQualityFindingResponse]
    skip: int = 0
    limit: int = 50


class DataQualityCheckRequest(BaseModel):
    """Request to initiate clinical data quality scan for a patient."""
    model_config = ConfigDict(extra="ignore")

    resource_types: Optional[List[str]] = None
    rule_types: Optional[List[DataQualityFindingType]] = None
    external_imports: List[Dict[str, Any]] = Field(default_factory=list)
    force_recheck: bool = False


class DataQualityCheckResponse(BaseModel):
    """Result summary of a data quality scan."""
    model_config = ConfigDict(extra="ignore")

    patient_id: str
    total_rules_evaluated: int
    findings_created: int
    findings: List[DataQualityFindingResponse]
    status: str  # EVALUATED, FINDINGS_DETECTED, NOT_CHECKED, REVIEW_REQUIRED
    message: str = "Data quality checks evaluated successfully."


class DataQualityReviewRequest(BaseModel):
    """Request to transition finding into IN_REVIEW status."""
    model_config = ConfigDict(extra="ignore")

    notes: Optional[str] = None


FindingReviewRequest = DataQualityReviewRequest


class DataQualityResolutionRequest(BaseModel):
    """Authorized clinician resolution decision for a data quality finding."""
    model_config = ConfigDict(extra="ignore")

    action: ResolutionAction
    expected_version: Optional[int] = Field(None, description="Optimistic concurrency version check")
    reason: Optional[str] = None
    notes: Optional[str] = None
    chosen_resource_id: Optional[str] = None


FindingResolutionRequest = DataQualityResolutionRequest

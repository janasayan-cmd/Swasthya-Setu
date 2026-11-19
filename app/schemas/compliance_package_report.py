"""Phase 69: Evidence Packages, Corrective Actions and Reporting Schemas.

Defines schemas for:
- Regulatory & governance evidence packages
- Phase 54 corrective action coordination and Phase 55 effectiveness integration
- High-level compliance and evidence completeness reporting
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PackageStatus(str, Enum):
    """Lifecycle status of an evidence package generation job."""

    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class TargetAudience(str, Enum):
    """Intended consumer for an evidence package."""

    INTERNAL_AUDIT = "INTERNAL_AUDIT"
    GOVERNANCE_COMMITTEE = "GOVERNANCE_COMMITTEE"
    REGULATORY_PREPARATION = "REGULATORY_PREPARATION"


class CorrectiveActionStatus(str, Enum):
    """Lifecycle state of a compliance corrective action routed through Phase 54."""

    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    EFFECTIVENESS_PENDING = "EFFECTIVENESS_PENDING"
    VERIFIED_EFFECTIVE = "VERIFIED_EFFECTIVE"


class ComplianceCorrectiveActionRequestRecord(BaseModel):
    """Domain model tracking a corrective action request originating from a compliance gap."""

    model_config = ConfigDict(extra="ignore")

    action_request_id: str = Field(default_factory=lambda: f"gca-{uuid.uuid4().hex[:12]}")
    finding_id: str
    requirement_id: str
    target_phase: str = "PHASE_54_CONTROLLED_ACTION"
    target_action_id: Optional[str] = None
    status: CorrectiveActionStatus = CorrectiveActionStatus.SUBMITTED
    reason: str
    required_outcome: str

    requested_by: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    phase54_action_ref: Optional[str] = None
    phase55_eval_ref: Optional[str] = None
    completion_evidence_refs: List[str] = Field(default_factory=list)
    effectiveness_outcome: Optional[str] = None
    reassessment_id: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SubmitCorrectiveActionRequest(BaseModel):
    """Request payload to initiate a Phase 54 corrective action for a compliance finding."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    required_outcome: str
    phase54_action_ref: Optional[str] = None
    phase55_effectiveness_required: Optional[bool] = True
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EvidencePackageRecord(BaseModel):
    """Domain model tracking a generated regulatory/governance evidence package."""

    model_config = ConfigDict(extra="ignore")

    package_id: str = Field(default_factory=lambda: f"gpkg-{uuid.uuid4().hex[:12]}")
    framework_id: str
    framework_version: str = "v1.0.0"
    organization_id: str
    facility_id: Optional[str] = None
    title: str
    description: str
    scope_summary: str
    target_audience: TargetAudience = TargetAudience.INTERNAL_AUDIT
    status: PackageStatus = PackageStatus.READY

    requirement_ids: List[str] = Field(default_factory=list)
    assessment_ids: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    gap_ids: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    generated_by: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    download_count: int = 0
    last_accessed_at: Optional[datetime] = None
    integrity_hash: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerateEvidencePackageRequest(BaseModel):
    """Request payload to generate a controlled evidence package."""

    model_config = ConfigDict(extra="ignore")

    framework_id: str
    title: str
    description: str
    target_audience: Optional[TargetAudience] = TargetAudience.INTERNAL_AUDIT
    requirement_ids: Optional[List[str]] = Field(default_factory=list)
    include_restricted_evidence: Optional[bool] = False
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ===========================================================================
# Aggregated Reporting Models
# ===========================================================================

class ComplianceSummaryReport(BaseModel):
    """Aggregated compliance metrics across all registered frameworks and requirements."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    total_frameworks: int
    total_requirements: int
    compliant_count: int
    compliant_with_limitations_count: int
    partially_compliant_count: int
    non_compliant_count: int
    evidence_insufficient_count: int
    active_findings_count: int
    critical_findings_count: int
    open_corrective_actions_count: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ComplianceGapReport(BaseModel):
    """Categorized summary of identified compliance gaps."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    total_gaps: int
    critical_gaps: int
    high_gaps: int
    medium_or_lower_gaps: int
    gaps_by_category: Dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ControlConformanceReport(BaseModel):
    """Summary of control mapping coverage and verification status."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    total_requirements: int
    mapped_requirements: int
    unmapped_requirements: int
    mapping_coverage_percentage: float
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceCompletenessReport(BaseModel):
    """Diagnostic report on evidence freshness, accessibility, and validity."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    total_evidence_items: int
    valid_items: int
    stale_items: int
    invalidated_items: int
    superseded_items: int
    inaccessible_items: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

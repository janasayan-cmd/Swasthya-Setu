"""Pydantic schemas and dataclasses for Phase 24 — Advanced Data Privacy & Data Governance.

Ensures strict typing and contracts for:
- Data classification and purpose definitions
- Configurable retention policies & lifecycle transitions
- Legal and organizational hold representations
- Deletion eligibility and dependency checks
- Data provenance & lineage tracking
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.core.privacy import DataClassification, DataProcessingPurpose


class RetentionStatus(str, Enum):
    """Lifecycle states for managed healthcare resources (TRD Sec 12)."""

    ACTIVE = "ACTIVE"
    RETENTION_ELIGIBLE = "RETENTION_ELIGIBLE"
    ARCHIVE_PENDING = "ARCHIVE_PENDING"
    ARCHIVED = "ARCHIVED"
    DELETION_PENDING = "DELETION_PENDING"
    DELETED = "DELETED"


class HoldType(str, Enum):
    """Legal and organizational preservation hold types (TRD Sec 17)."""

    LEGAL_HOLD = "LEGAL_HOLD"
    INVESTIGATION_HOLD = "INVESTIGATION_HOLD"
    ORGANIZATIONAL_RETENTION_HOLD = "ORGANIZATIONAL_RETENTION_HOLD"
    CLINICAL_RECORD_HOLD = "CLINICAL_RECORD_HOLD"


class RetentionBehavior(str, Enum):
    """Action to take when retention eligibility period concludes."""

    ARCHIVE = "ARCHIVE"
    KEEP_ACTIVE = "KEEP_ACTIVE"
    NONE = "NONE"


class DeletionBehavior(str, Enum):
    """Execution mode for approved resource deletion."""

    SOFT_DELETE = "SOFT_DELETE"
    PERMANENT_DELETE = "PERMANENT_DELETE"
    RESTRICTED = "RESTRICTED"


class RetentionPolicy(BaseModel):
    """Configurable data retention rule for a resource category (TRD Sec 11).
    
    Retention durations are configurable based on organizational policy;
    no legal period is hardcoded.
    """

    model_config = ConfigDict(frozen=True)

    policy_id: str
    data_type: str = Field(description="Target entity type, e.g. 'medical_document', 'triage_assessment'")
    purpose: Optional[str] = Field(default=None, description="Associated processing purpose")
    retention_period_days: Optional[int] = Field(default=None, description="Days to retain prior to eligibility")
    retention_start_event: str = Field(default="creation", description="Trigger event ('creation', 'discharge', 'last_activity')")
    archive_behavior: RetentionBehavior = Field(default=RetentionBehavior.ARCHIVE)
    deletion_behavior: DeletionBehavior = Field(default=DeletionBehavior.SOFT_DELETE)
    description: str
    is_active: bool = True


class LegalHold(BaseModel):
    """Active administrative or legal hold preventing resource deletion (TRD Sec 17)."""

    model_config = ConfigDict(frozen=True)

    hold_id: str
    resource_type: str
    resource_id: str
    patient_id: Optional[str] = None
    hold_type: HoldType
    reason: str
    placed_by: str
    placed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    expires_at: Optional[datetime] = None


class LineageStage(str, Enum):
    """Provenance lifecycle stage (TRD Sec 34)."""

    SOURCE = "SOURCE"
    TRANSFORMATION = "TRANSFORMATION"
    VERIFICATION = "VERIFICATION"
    CURRENT_STATE = "CURRENT_STATE"


class LineageRecord(BaseModel):
    """Audit-grade data transformation lineage (TRD Sec 34)."""

    model_config = ConfigDict(frozen=True)

    lineage_id: str
    patient_id: Optional[str] = None
    resource_type: str
    resource_id: str
    source_type: str
    transformation_type: Optional[str] = None
    verifier_id: Optional[str] = None
    stage: LineageStage
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PrivacyEvaluationRequest(BaseModel):
    """Request payload to test access authorization against privacy rules."""

    actor_id: str
    role: str
    patient_id: Optional[str] = None
    resource_type: str
    resource_id: str
    purpose: DataProcessingPurpose


class PrivacyEvaluationResponse(BaseModel):
    """Structured decision output from privacy governance evaluation."""

    allowed: bool
    classification: DataClassification
    purpose: DataProcessingPurpose
    reason: str
    requires_consent: bool = False
    consent_verified: bool = False


class DeletionEligibilityCheck(BaseModel):
    """Evaluation summary prior to executing any destructive deletion workflow."""

    resource_id: str
    resource_type: str
    eligible_for_deletion: bool
    retention_policy_id: Optional[str] = None
    active_holds: List[str] = Field(default_factory=list)
    dependent_records: Dict[str, int] = Field(default_factory=dict)
    reason: str


class LegalHoldCreateRequest(BaseModel):
    """Payload to place a legal or organizational hold on a resource."""

    resource_type: str
    resource_id: str
    patient_id: Optional[str] = None
    hold_type: HoldType
    reason: str
    expires_at: Optional[datetime] = None


class ControlledDeletionRequest(BaseModel):
    """Payload to request controlled deletion of a resource."""

    resource_type: str
    resource_id: str
    patient_id: Optional[str] = None
    reason: str
    force: bool = False


class DataAccessPolicyResponse(BaseModel):
    """Public data access policy and governance metadata response."""

    privacy_controls_enabled: bool
    supported_purposes: List[str]
    classifications: List[str]
    active_policies_count: int
    active_holds_count: int
    governance_framework: str = "HealthSetu Data Governance & Privacy Architecture"

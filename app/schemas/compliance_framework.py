"""Phase 69: Compliance Framework and Requirement Register Schemas.

Defines schemas for:
- Compliance frameworks (internal policies, operational procedures, regulatory frameworks, accreditation standards)
- Configurable compliance requirements and versioned lifecycle states
- Requirement-to-control mappings for end-to-end traceability
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FrameworkType(str, Enum):
    """Source classification of a governance compliance framework."""

    INTERNAL_SAFETY_POLICY = "INTERNAL_SAFETY_POLICY"
    OPERATIONAL_PROCEDURE = "OPERATIONAL_PROCEDURE"
    ORGANIZATION_GOVERNANCE = "ORGANIZATION_GOVERNANCE"
    FACILITY_REQUIREMENT = "FACILITY_REQUIREMENT"
    REGULATORY_FRAMEWORK = "REGULATORY_FRAMEWORK"
    ACCREDITATION_STANDARD = "ACCREDITATION_STANDARD"
    PRIVACY_DATA_PROTECTION = "PRIVACY_DATA_PROTECTION"
    AUDIT_RETENTION = "AUDIT_RETENTION"


class FrameworkLifecycleStatus(str, Enum):
    """Lifecycle status for a compliance framework."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"
    ARCHIVED = "ARCHIVED"


class RequirementLifecycleStatus(str, Enum):
    """Lifecycle status for a compliance requirement."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"
    ARCHIVED = "ARCHIVED"


class RequirementCategory(str, Enum):
    """Category of governance compliance requirement."""

    CLINICAL_SAFETY = "CLINICAL_SAFETY"
    PRIVACY_DATA_PROTECTION = "PRIVACY_DATA_PROTECTION"
    INFORMATION_SECURITY = "INFORMATION_SECURITY"
    RISK_GOVERNANCE = "RISK_GOVERNANCE"
    WORKFLOW_INTEGRITY = "WORKFLOW_INTEGRITY"
    AUDIT_RETENTION = "AUDIT_RETENTION"
    ACCIDENTAL_DISCLOSURE = "ACCIDENTAL_DISCLOSURE"
    OPERATIONAL_COMPLIANCE = "OPERATIONAL_COMPLIANCE"


class AssessmentFrequency(str, Enum):
    """Expected evaluation cadence for compliance requirements."""

    CONTINUOUS = "CONTINUOUS"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"
    EVENT_TRIGGERED = "EVENT_TRIGGERED"


class VerificationMethod(str, Enum):
    """Verification methodology applied to a control mapping."""

    AUTOMATED_AUDIT = "AUTOMATED_AUDIT"
    DECISION_ASSURANCE = "DECISION_ASSURANCE"
    EFFECTIVENESS_EVALUATION = "EFFECTIVENESS_EVALUATION"
    MANUAL_INSPECTION = "MANUAL_INSPECTION"
    EVIDENCE_SAMPLING = "EVIDENCE_SAMPLING"


# ===========================================================================
# Framework Models
# ===========================================================================

class ComplianceFrameworkRecord(BaseModel):
    """Domain model tracking a registered compliance framework."""

    model_config = ConfigDict(extra="ignore")

    framework_id: str = Field(default_factory=lambda: f"gfw-{uuid.uuid4().hex[:12]}")
    name: str
    version: str = "v1.0.0"
    framework_type: FrameworkType
    description: str
    organization_id: str
    facility_id: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    lifecycle_status: FrameworkLifecycleStatus = FrameworkLifecycleStatus.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateFrameworkRequest(BaseModel):
    """Request payload to register a new compliance framework."""

    model_config = ConfigDict(extra="ignore")

    name: str
    version: Optional[str] = "v1.0.0"
    framework_type: FrameworkType
    description: str
    facility_id: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ===========================================================================
# Requirement Models
# ===========================================================================

class ComplianceRequirementRecord(BaseModel):
    """Domain model tracking a specific compliance requirement within a framework."""

    model_config = ConfigDict(extra="ignore")

    requirement_id: str = Field(default_factory=lambda: f"greq-{uuid.uuid4().hex[:12]}")
    framework_id: str
    framework_version: str = "v1.0.0"
    requirement_code: str  # e.g. "REQ-CLIN-001"
    title: str
    description: str
    category: RequirementCategory
    organization_id: str
    facility_id: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    owner_id: Optional[str] = None
    owner_role: Optional[str] = None
    related_policy_refs: List[str] = Field(default_factory=list)
    related_control_refs: List[str] = Field(default_factory=list)
    expected_evidence_types: List[str] = Field(default_factory=list)
    assessment_frequency: AssessmentFrequency = AssessmentFrequency.MONTHLY
    review_requirements: Optional[str] = None
    lifecycle_status: RequirementLifecycleStatus = RequirementLifecycleStatus.DRAFT
    version: str = "v1.0.0"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    activated_by: Optional[str] = None
    activated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateRequirementRequest(BaseModel):
    """Request payload to register a requirement within an existing framework."""

    model_config = ConfigDict(extra="ignore")

    framework_id: str
    requirement_code: str
    title: str
    description: str
    category: RequirementCategory
    facility_id: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    owner_id: Optional[str] = None
    owner_role: Optional[str] = None
    related_policy_refs: Optional[List[str]] = Field(default_factory=list)
    related_control_refs: Optional[List[str]] = Field(default_factory=list)
    expected_evidence_types: Optional[List[str]] = Field(default_factory=list)
    assessment_frequency: Optional[AssessmentFrequency] = AssessmentFrequency.MONTHLY
    review_requirements: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ApproveRequirementRequest(BaseModel):
    """Request payload to approve a draft compliance requirement."""

    model_config = ConfigDict(extra="ignore")

    approval_rationale: str
    effective_date: Optional[datetime] = None


class ActivateRequirementRequest(BaseModel):
    """Request payload to activate an approved compliance requirement."""

    model_config = ConfigDict(extra="ignore")

    activation_rationale: str


# ===========================================================================
# Control Mapping Models
# ===========================================================================

class RequirementControlMappingRecord(BaseModel):
    """Domain model mapping a requirement to an authoritative workflow control."""

    model_config = ConfigDict(extra="ignore")

    mapping_id: str = Field(default_factory=lambda: f"gmap-{uuid.uuid4().hex[:12]}")
    requirement_id: str
    control_id: str
    control_name: str
    control_owner_phase: str  # e.g. "PHASE_48", "PHASE_63", "PHASE_68"
    control_owner_id: Optional[str] = None
    control_purpose: str
    verification_method: VerificationMethod = VerificationMethod.AUTOMATED_AUDIT
    expected_evidence: str
    mapping_status: str = "APPROVED"  # APPROVED, PENDING_APPROVAL, DEPRECATED
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    policy_version: str = "v1.0.0"
    rationale: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateControlMappingRequest(BaseModel):
    """Request payload to map a requirement to an authoritative control."""

    model_config = ConfigDict(extra="ignore")

    requirement_id: str
    control_id: str
    control_name: str
    control_owner_phase: str
    control_owner_id: Optional[str] = None
    control_purpose: str
    verification_method: Optional[VerificationMethod] = VerificationMethod.AUTOMATED_AUDIT
    expected_evidence: str
    policy_version: Optional[str] = "v1.0.0"
    rationale: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

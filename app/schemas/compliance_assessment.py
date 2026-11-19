"""Phase 69: Compliance Assessment Schemas.

Defines schemas for:
- 18 explicit compliance assessment statuses
- Assessment triggers and execution payloads
- Historical assessment records preserving point-in-time policy versions
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ComplianceStatus(str, Enum):
    """Controlled outcomes of a governance compliance assessment run."""

    NOT_ASSESSED = "NOT_ASSESSED"
    ASSESSMENT_PENDING = "ASSESSMENT_PENDING"
    ASSESSMENT_IN_PROGRESS = "ASSESSMENT_IN_PROGRESS"
    COMPLIANT = "COMPLIANT"
    COMPLIANT_WITH_LIMITATIONS = "COMPLIANT_WITH_LIMITATIONS"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    CONTROL_NOT_IMPLEMENTED = "CONTROL_NOT_IMPLEMENTED"
    CONTROL_IMPLEMENTATION_UNVERIFIED = "CONTROL_IMPLEMENTATION_UNVERIFIED"
    CONTROL_EFFECTIVENESS_UNVERIFIED = "CONTROL_EFFECTIVENESS_UNVERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    ASSESSMENT_FAILED = "ASSESSMENT_FAILED"
    SUPERSEDED = "SUPERSEDED"


class AssessmentType(str, Enum):
    """Trigger category for executing a compliance assessment."""

    SCHEDULED = "SCHEDULED"
    EVENT_TRIGGERED = "EVENT_TRIGGERED"
    MANUAL = "MANUAL"
    POST_CORRECTIVE_ACTION = "POST_CORRECTIVE_ACTION"
    POLICY_CHANGE = "POLICY_CHANGE"


class ComplianceAssessmentRecord(BaseModel):
    """Domain model tracking a compliance assessment run for a requirement."""

    model_config = ConfigDict(extra="ignore")

    assessment_id: str = Field(default_factory=lambda: f"gasm-{uuid.uuid4().hex[:12]}")
    framework_id: str
    framework_version: str = "v1.0.0"
    requirement_id: str
    organization_id: str
    facility_id: Optional[str] = None
    assessment_scope: str = "ORGANIZATION"  # ORGANIZATION, FACILITY, PATIENT_WORKFLOW
    assessment_type: AssessmentType = AssessmentType.MANUAL
    status: ComplianceStatus = ComplianceStatus.ASSESSMENT_PENDING

    assessed_by: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assessment_rationale: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)

    evidence_refs: List[str] = Field(default_factory=list)
    findings_count: int = 0
    critical_findings_count: int = 0

    policy_version_used: str = "v1.0.0"
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TriggerAssessmentRequest(BaseModel):
    """Request payload to initiate a compliance assessment on a requirement."""

    model_config = ConfigDict(extra="ignore")

    requirement_id: str
    assessment_scope: Optional[str] = "ORGANIZATION"
    assessment_type: Optional[AssessmentType] = AssessmentType.MANUAL
    policy_version_override: Optional[str] = None
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReassessRequest(BaseModel):
    """Request payload to reassess a requirement following corrective action or policy change."""

    model_config = ConfigDict(extra="ignore")

    reassessment_reason: str
    trigger_event: Optional[str] = None
    policy_version_override: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

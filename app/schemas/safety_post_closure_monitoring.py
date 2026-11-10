"""Phase 66: Post-Closure Monitoring & Lifecycle Reconciliation Schemas.

Defines schemas for post-closure monitoring configuration, status, reassessment requests,
and governed reopening coordination.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class MonitoringPolicyConfig(BaseModel):
    """Configuration governing post-closure verification timing, intervals, and thresholds."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    initial_verification_timing_seconds: int = 0
    reverification_interval_seconds: int = 86400  # Default 24h
    max_retry_attempts: int = 3
    dependency_timeout_seconds: int = 30
    escalation_rules: Dict[str, Any] = Field(default_factory=lambda: {
        "critical_finding_action": "REOPEN_RECOMMENDED",
        "high_finding_action": "REASSESSMENT_REQUIRED",
    })
    monitoring_end_conditions: Dict[str, Any] = Field(default_factory=lambda: {
        "max_monitoring_days": 90,
        "auto_terminate_on_reopen": True,
    })
    policy_version: str = "v1.0.0"
    manual_review_conditions: List[str] = Field(default_factory=lambda: [
        "CONFLICTED",
        "EVIDENCE_INVALID",
        "SOURCE_DISPOSITION_CHANGED",
    ])


class PostClosureMonitoringStatus(BaseModel):
    """Current post-closure monitoring operational status for a completion workflow."""

    model_config = ConfigDict(extra="ignore")

    completion_id: str
    organization_id: str
    facility_id: str
    monitoring_active: bool = True
    policy: MonitoringPolicyConfig = Field(default_factory=MonitoringPolicyConfig)

    last_verification_id: Optional[str] = None
    last_verification_state: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    next_scheduled_verification_at: Optional[datetime] = None

    open_findings_count: int = 0
    critical_findings_count: int = 0
    reassessment_required: bool = False
    reopen_recommended: bool = False
    reopened: bool = False


class ReassessmentRequest(BaseModel):
    """Request payload to initiate policy-controlled workflow reassessment."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    finding_refs: List[str] = Field(default_factory=list)
    scope_adjustments: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReassessmentRecord(BaseModel):
    """Record tracking a governed reassessment requirement."""

    model_config = ConfigDict(extra="ignore")

    reassessment_id: str = Field(default_factory=lambda: f"reassess-{uuid.uuid4().hex[:12]}")
    completion_id: str
    organization_id: str
    facility_id: str
    requested_by: str
    requested_by_role: str
    reason: str
    finding_refs: List[str] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, ACKNOWLEDGED, RESOLVED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


class ReopeningCoordinationRequest(BaseModel):
    """Request payload to initiate governed reopening of a closed completion workflow."""

    model_config = ConfigDict(extra="ignore")

    reopen_trigger: str  # e.g. "MATERIAL_NEW_OUTCOME", "INVALIDATED_OUTCOME", "CONFLICTED_EVIDENCE", "DESTINATION_WORKFLOW_REOPENED", etc.
    reason: str
    reopen_rationale: str
    finding_refs: List[str] = Field(default_factory=list)
    reassessment_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReopeningCoordinationRecord(BaseModel):
    """Record tracking governed reopening coordination and authorization."""

    model_config = ConfigDict(extra="ignore")

    coordination_id: str = Field(default_factory=lambda: f"reopen-coord-{uuid.uuid4().hex[:12]}")
    completion_id: str
    organization_id: str
    facility_id: str
    requested_by: str
    requested_by_role: str
    authorized_by: Optional[str] = None
    authorized_by_role: Optional[str] = None
    reopen_trigger: str
    reason: str
    reopen_rationale: str
    finding_refs: List[str] = Field(default_factory=list)
    authorized: bool = False
    executed: bool = False
    phase65_reopen_record: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PostClosureHistoryResponse(BaseModel):
    """Comprehensive chronological post-closure history response."""

    model_config = ConfigDict(extra="ignore")

    completion_id: str
    organization_id: str
    facility_id: str
    verifications: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    reassessments: List[Dict[str, Any]] = Field(default_factory=list)
    reopenings: List[Dict[str, Any]] = Field(default_factory=list)
    closure_preserved: Optional[Dict[str, Any]] = None

"""Phase 50: Clinical Safety Learning & Analysis Request/Result Schemas.

Defines analysis scopes, types, execution status, trend summaries,
and request/response contracts for historical safety learning.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class AnalysisType(str, Enum):
    """Controlled taxonomy of safety learning analysis types."""

    INCIDENT_TREND = "INCIDENT_TREND"
    INCIDENT_RECURRENCE = "INCIDENT_RECURRENCE"
    SAFETY_SIGNAL_TREND = "SAFETY_SIGNAL_TREND"
    NEAR_MISS_TREND = "NEAR_MISS_TREND"
    BLOCKED_ACTION_TREND = "BLOCKED_ACTION_TREND"
    PROVIDER_FAILURE_TREND = "PROVIDER_FAILURE_TREND"
    WORKFLOW_FAILURE_TREND = "WORKFLOW_FAILURE_TREND"
    SAFETY_GATE_TREND = "SAFETY_GATE_TREND"
    CORRECTIVE_ACTION_EFFECTIVENESS = "CORRECTIVE_ACTION_EFFECTIVENESS"
    REOPENED_INCIDENT_ANALYSIS = "REOPENED_INCIDENT_ANALYSIS"
    REPEATED_PATTERN_ANALYSIS = "REPEATED_PATTERN_ANALYSIS"
    CONFIGURATION_SAFETY_ANALYSIS = "CONFIGURATION_SAFETY_ANALYSIS"
    RECOMMENDATION_ANALYSIS = "RECOMMENDATION_ANALYSIS"


class AnalysisScopeType(str, Enum):
    """Explicitly controlled analysis boundaries."""

    GLOBAL_SYSTEM = "GLOBAL_SYSTEM"
    ORGANIZATION = "ORGANIZATION"
    FACILITY = "FACILITY"
    DEPARTMENT = "DEPARTMENT"
    WORKFLOW = "WORKFLOW"
    WORKFLOW_VERSION = "WORKFLOW_VERSION"
    PROVIDER = "PROVIDER"
    PROVIDER_VERSION = "PROVIDER_VERSION"
    SAFETY_POLICY = "SAFETY_POLICY"
    SAFETY_POLICY_VERSION = "SAFETY_POLICY_VERSION"
    FEATURE_FLAG = "FEATURE_FLAG"
    CONFIGURATION = "CONFIGURATION"
    DECISION_TYPE = "DECISION_TYPE"
    INCIDENT_TYPE = "INCIDENT_TYPE"
    SAFETY_SIGNAL_TYPE = "SAFETY_SIGNAL_TYPE"


class AnalysisStatus(str, Enum):
    """Execution status of a safety learning analysis job."""

    REQUESTED = "REQUESTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TrendMetric(BaseModel):
    """Structured trend metric distinguishing counts, denominators, and rates."""

    model_config = ConfigDict(extra="ignore")

    metric_name: str
    count: int = Field(ge=0, description="Raw event/incident occurrence count")
    denominator: Optional[int] = Field(default=None, ge=0, description="Eligible denominator count, if validly established")
    rate: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Calculated rate (count / denominator)")
    rate_available: bool = Field(default=False, description="Whether a valid denominator was present")
    time_window_label: Optional[str] = None


class SafetyAnalysisResult(BaseModel):
    """Authoritative result envelope for a completed safety learning analysis."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"sl-res-{uuid.uuid4().hex[:12]}")
    analysis_id: str
    analysis_type: AnalysisType
    scope_type: AnalysisScopeType
    scope_id: Optional[str] = None
    status: AnalysisStatus = Field(default=AnalysisStatus.COMPLETED)
    metrics: List[TrendMetric] = Field(default_factory=list)
    detected_pattern_ids: List[str] = Field(default_factory=list)
    generated_recommendation_ids: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    sources_included: List[str] = Field(default_factory=list)
    sources_unavailable: List[str] = Field(default_factory=list)
    is_complete: bool = True
    limitations: List[str] = Field(default_factory=list)
    version: str = Field(default="1.0")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyAnalysisJob(BaseModel):
    """Tracks asynchronous execution of a safety learning analysis job."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"sl-job-{uuid.uuid4().hex[:12]}")
    analysis_type: AnalysisType
    scope_type: AnalysisScopeType
    scope_id: Optional[str] = None
    start_time: datetime
    end_time: datetime
    requested_by_id: str
    requested_by_role: str
    organization_id: Optional[str] = None
    status: AnalysisStatus = Field(default=AnalysisStatus.REQUESTED)
    filters: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    result: Optional[SafetyAnalysisResult] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyAnalysisCreateRequest(BaseModel):
    """Payload to request a safety learning trend or recurrence analysis."""

    model_config = ConfigDict(extra="forbid")

    analysis_type: AnalysisType
    scope_type: AnalysisScopeType
    scope_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    relative_window: Optional[str] = Field(default="LAST_30_DAYS", description="LAST_24_HOURS, LAST_7_DAYS, LAST_30_DAYS, LAST_90_DAYS")
    filters: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None

"""Administrative and Operational Backoffice Schemas for HealthSetu (Phase 27).

Provides data contracts for:
- Operational system status, health, and readiness inspection
- External provider integration monitoring and non-PHI connectivity testing
- Background job inspection, retry, and cancellation
- Privacy-safe patient support search with strictly minimized identifiers
- Aggregated data quality metrics and security event summaries
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.job import JobStatus, JobType
from app.schemas.audit import AuditEventRecord


class DependencyStatus(str, Enum):
    """Operational status of internal subsystems and external providers."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


class ComponentHealth(BaseModel):
    """Health inspection for an individual subsystem or external provider."""

    name: str = Field(description="Subsystem or integration component identifier")
    category: str = Field(description="Category (core, storage, ml, terminology, safety, interop, queue)")
    status: DependencyStatus = Field(description="Normalized availability status")
    response_time_ms: Optional[float] = Field(default=None, description="Check probe duration in milliseconds")
    last_checked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: Optional[str] = Field(default=None, description="Safe operational status note (no credentials)")
    version: Optional[str] = Field(default=None, description="Component or engine version")


class SystemStatusResponse(BaseModel):
    """Overall operational status overview for administrative dashboard."""

    status: DependencyStatus = Field(description="Composite system availability")
    environment: str = Field(description="Runtime environment name")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = Field(default="1.0.0")
    components: Dict[str, ComponentHealth] = Field(description="Subsystem health statuses")


class SystemDetailedHealthResponse(BaseModel):
    """In-depth operational metrics and subsystem probes."""

    status: DependencyStatus
    uptime_seconds: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active_workers: int
    queue_backlog: int
    open_incidents: int
    components: Dict[str, ComponentHealth]


class SystemReadinessResponse(BaseModel):
    """Readiness probe indicating if the platform is able to handle traffic."""

    ready: bool
    status: DependencyStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    checks: Dict[str, bool]


class IntegrationProviderStatus(BaseModel):
    """Inspection model for a registered external provider integration."""

    name: str = Field(description="Integration identifier (e.g. ocr, fhir, medication_safety)")
    category: str = Field(description="Domain classification")
    enabled: bool = Field(description="Whether the provider is currently enabled in settings")
    status: DependencyStatus = Field(description="Current operational connectivity state")
    version: Optional[str] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    error_category: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict, description="Safe metadata (ZERO secrets)")


class IntegrationListResponse(BaseModel):
    """List of registered external provider integrations."""

    items: List[IntegrationProviderStatus]
    total: int


class IntegrationTestRequest(BaseModel):
    """Payload to request a controlled provider connectivity test."""

    test_mode: str = Field(default="synthetic_ping", description="Test protocol to run")
    timeout_seconds: float = Field(default=5.0, ge=1.0, le=15.0, description="Test execution deadline")


class IntegrationTestResponse(BaseModel):
    """Result of controlled non-PHI integration probe."""

    provider: str
    status: DependencyStatus
    latency_ms: float
    test_passed: bool
    error: Optional[str] = None
    tested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AdminJobSummary(BaseModel):
    """Minimized background job representation without raw clinical payloads."""

    id: str
    job_type: JobType
    status: JobStatus
    patient_id: Optional[str] = None
    resource_type: str
    resource_id: str
    operation_type: str
    attempt: int
    max_retries: int
    created_at: datetime
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_category: Optional[str] = None
    correlation_id: Optional[str] = None


class AdminJobListResponse(BaseModel):
    """Paginated background job listing for administrative inspection."""

    items: List[AdminJobSummary]
    total: int
    skip: int
    limit: int


class JobRetryResponse(BaseModel):
    """Outcome of an administrative job retry command."""

    job_id: str
    status: JobStatus
    attempt: int
    max_retries: int
    message: str


class JobCancelResponse(BaseModel):
    """Outcome of an administrative job cancellation command."""

    job_id: str
    status: JobStatus
    message: str


class SupportPatientItem(BaseModel):
    """Strictly minimized patient account record for authorized support lookup.
    
    INVARIANT: Contains ZERO diagnoses, medications, allergies, or clinical records.
    """

    patient_id: str = Field(description="Internal patient database reference")
    sovereign_id: str = Field(description="Public sovereign identifier (e.g. HS-PAT-8921)")
    masked_name: str = Field(description="Partially masked patient name for account verification")
    account_status: str = Field(description="Active, Disabled, or Locked status")
    city: Optional[str] = None
    registered_at: datetime
    active_consent_count: int = Field(default=0, description="Count of active clinical consents")


class SupportPatientSearchResponse(BaseModel):
    """List of minimized patient records matching support query."""

    items: List[SupportPatientItem]
    total: int


class AdminDataQualityOverview(BaseModel):
    """System-level data quality and clinical integrity statistics."""

    total_findings: int
    pending_findings: int
    in_review_findings: int
    resolved_findings: int
    rejected_findings: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    total_reconciliation_cases: int
    pending_reconciliation_cases: int


class AdminSecurityEventItem(BaseModel):
    """Sanitized administrative security log event."""

    id: str
    event_type: str
    actor_id: str
    actor_role: str
    timestamp: datetime
    severity: str
    ip_address: Optional[str] = None
    description: str


class AdminSecurityEventListResponse(BaseModel):
    """Paginated list of security audit events."""

    items: List[AdminSecurityEventItem]
    total: int
    skip: int
    limit: int


class AdminAuditListResponse(BaseModel):
    """Paginated list of administrative audit event records."""

    items: List[AuditEventRecord]
    total: int
    skip: int
    limit: int


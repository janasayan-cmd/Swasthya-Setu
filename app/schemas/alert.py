"""Pydantic schemas for Clinical Alerts, Safety Notifications & Escalation Management (Phase 35).

CORE SAFETY PRINCIPLES:
- ALERT != DIAGNOSIS
- ALERT != TRIAGE DECISION
- ALERT != TREATMENT DECISION
- ALERT != PRESCRIPTION
- ALERT != MEDICATION CHANGE
- ALERT != CLINICAL AUTHORITY
- CRITICAL RESULT != AUTOMATIC TREATMENT
- UNKNOWN STATUS != RESOLVED
- ALERT CREATED != ALERT DELIVERED != ALERT READ != ALERT ACKNOWLEDGED != CLINICAL ACTION COMPLETED
- ESCALATION != EMERGENCY DISPATCH
- AI MUST NOT BECOME THE AUTHORITY FOR CLINICAL ALERT GENERATION OR SEVERITY DERIVATION.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertCategory(str, Enum):
    """Authoritative category of clinical or operational alert."""

    CLINICAL_ALERT = "CLINICAL_ALERT"
    MEDICATION_SAFETY_ALERT = "MEDICATION_SAFETY_ALERT"
    DIAGNOSTIC_RESULT_ALERT = "DIAGNOSTIC_RESULT_ALERT"
    TRIAGE_ALERT = "TRIAGE_ALERT"
    FOLLOW_UP_ALERT = "FOLLOW_UP_ALERT"
    APPOINTMENT_ALERT = "APPOINTMENT_ALERT"
    TRANSFER_ALERT = "TRANSFER_ALERT"
    DOCUMENT_PROCESSING_ALERT = "DOCUMENT_PROCESSING_ALERT"
    DATA_QUALITY_ALERT = "DATA_QUALITY_ALERT"
    SECURITY_ALERT = "SECURITY_ALERT"
    INTEROPERABILITY_ALERT = "INTEROPERABILITY_ALERT"
    SYSTEM_ALERT = "SYSTEM_ALERT"


class AlertSeverity(str, Enum):
    """Authoritative severity levels. Must be rule- or provider-derived, never invented by AI."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Database-aligned lifecycle states for an alert."""

    CREATED = "CREATED"
    PENDING_DELIVERY = "PENDING_DELIVERY"
    DELIVERED = "DELIVERED"
    READ = "READ"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATION_PENDING = "ESCALATION_PENDING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class AlertRecipientType(str, Enum):
    """Class of authorized alert recipient."""

    RESPONSIBLE_CLINICIAN = "RESPONSIBLE_CLINICIAN"
    CARE_TEAM = "CARE_TEAM"
    FACILITY_STAFF = "FACILITY_STAFF"
    FACILITY_ESCALATION = "FACILITY_ESCALATION"
    ORGANIZATION_ESCALATION = "ORGANIZATION_ESCALATION"
    PATIENT = "PATIENT"
    ADMINISTRATOR = "ADMINISTRATOR"


class AlertRecipient(BaseModel):
    """Specific authorized recipient assigned to receive an alert."""

    model_config = ConfigDict(extra="ignore")

    recipient_id: str = Field(description="Unique identifier of recipient user or group")
    recipient_type: AlertRecipientType = Field(description="Recipient clinical/operational role classification")
    channel: str = Field(default="IN_APP", description="Delivery channel (IN_APP, EMAIL, SMS, PUSH)")
    delivered_at: Optional[datetime] = Field(default=None, description="Timestamp provider confirmed delivery")
    read_at: Optional[datetime] = Field(default=None, description="Timestamp notification was opened/read")
    status: str = Field(default="PENDING", description="Status of delivery to this recipient")


class AlertProvenance(BaseModel):
    """Immutable origin context for an alert."""

    model_config = ConfigDict(extra="ignore")

    source_system: str = Field(description="Authoritative emitting domain service (e.g. diagnostic_result_service)")
    source_event_type: str = Field(description="Authoritative domain event type")
    source_event_id: str = Field(description="Authoritative domain event UUID for deduplication")
    source_resource_type: str = Field(description="Target resource type (e.g. diagnostic_result, medication_safety)")
    source_resource_id: str = Field(description="Target resource ID")
    patient_id: Optional[str] = Field(default=None, description="Associated patient ID if clinically scoped")
    organization_id: Optional[str] = Field(default=None, description="Multi-tenant organization boundary")
    facility_id: Optional[str] = Field(default=None, description="Facility context boundary")
    policy_id: str = Field(description="Identifier of alert policy evaluated")
    policy_version: int = Field(default=1, description="Version of policy evaluated at alert creation")
    severity_source: str = Field(default="POLICY_RULE", description="Provenance of severity (e.g. RULE, PROVIDER_EXPLICIT)")
    rule_identifier: Optional[str] = Field(default=None, description="Specific rule or condition identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Evaluation timestamp")


class AlertRecord(BaseModel):
    """Complete representation of a clinical or operational alert."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique alert identifier (e.g. ALT-20261003-0001)")
    title: str = Field(description="Safe human-readable alert title")
    summary: Optional[str] = Field(default=None, description="Structured non-diagnostic alert summary")
    category: AlertCategory = Field(description="Alert category")
    severity: AlertSeverity = Field(description="Alert severity level")
    status: AlertStatus = Field(default=AlertStatus.CREATED, description="Current lifecycle state")
    patient_id: Optional[str] = Field(default=None, description="Patient identifier")
    organization_id: Optional[str] = Field(default=None, description="Tenant organization ID")
    facility_id: Optional[str] = Field(default=None, description="Facility ID")
    provenance: AlertProvenance = Field(description="Authoritative provenance and source event linkage")
    recipients: List[AlertRecipient] = Field(default_factory=list, description="Authorized resolved recipients")
    requires_acknowledgement: bool = Field(default=False, description="Flag indicating explicit acknowledgement required")
    acknowledgement_timeout_minutes: Optional[int] = Field(default=None, description="Configured timeout before escalation")
    escalation_enabled: bool = Field(default=False, description="Flag indicating automated escalation is active")
    escalation_level: int = Field(default=0, description="Current escalation tier (0: clinician, 1: team, 2: facility, 3: org)")
    escalation_deadline: Optional[datetime] = Field(default=None, description="Escalation deadline if acknowledgement pending")
    escalated_at: Optional[datetime] = Field(default=None, description="Timestamp of most recent escalation")
    acknowledged_at: Optional[datetime] = Field(default=None, description="Timestamp of explicit acknowledgement")
    acknowledged_by: Optional[str] = Field(default=None, description="User ID of acknowledging actor")
    acknowledgement_note: Optional[str] = Field(default=None, description="Optional acknowledgement note")
    resolved_at: Optional[datetime] = Field(default=None, description="Timestamp alert was marked resolved")
    resolved_by: Optional[str] = Field(default=None, description="User ID of resolving actor")
    resolution_reason: Optional[str] = Field(default=None, description="Structured resolution rationale")
    dismissed_at: Optional[datetime] = Field(default=None, description="Timestamp alert was dismissed")
    dismissed_by: Optional[str] = Field(default=None, description="User ID of dismissing actor")
    dismissal_reason: Optional[str] = Field(default=None, description="Required dismissal reason")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe auxiliary metadata without unmasked PHI")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")


class AlertCreate(BaseModel):
    """Internal model for evaluating and ingesting an alert from a domain event."""

    model_config = ConfigDict(extra="ignore")

    source_system: str
    source_event_type: str
    source_event_id: str
    source_resource_type: str
    source_resource_id: str
    patient_id: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    responsible_clinician_id: Optional[str] = None
    event_payload: Dict[str, Any] = Field(default_factory=dict)
    override_severity: Optional[AlertSeverity] = None


class AlertAcknowledgeRequest(BaseModel):
    """Payload to explicitly acknowledge an alert."""

    model_config = ConfigDict(extra="ignore")

    note: Optional[str] = Field(default=None, max_length=500, description="Optional clinician acknowledgement note")


class AlertResolveRequest(BaseModel):
    """Payload to mark an alert resolved."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=3, max_length=500, description="Mandatory reason for resolving alert")
    resolution_action_taken: Optional[str] = Field(default=None, max_length=500, description="Reference to clinical or operational action completed")


class AlertDismissRequest(BaseModel):
    """Payload to dismiss an alert."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=3, max_length=500, description="Mandatory reason for dismissing alert")


class AlertFilter(BaseModel):
    """Query filters for alert retrieval."""

    model_config = ConfigDict(extra="ignore")

    status: Optional[AlertStatus] = None
    severity: Optional[AlertSeverity] = None
    category: Optional[AlertCategory] = None
    patient_id: Optional[str] = None
    source_resource_type: Optional[str] = None
    source_resource_id: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    requires_acknowledgement: Optional[bool] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AlertListResponse(BaseModel):
    """Paginated collection of alerts."""

    model_config = ConfigDict(extra="ignore")

    items: List[AlertRecord] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    has_more: bool = Field(default=False)

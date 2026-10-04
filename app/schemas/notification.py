"""Pydantic schemas for Phase 29: Notification, Communication & Event Delivery System.

SAFETY & ARCHITECTURAL INVARIANTS:
- NOTIFICATION != CLINICAL DECISION
- NOTIFICATION != MEDICAL ADVICE
- MESSAGE DELIVERY != CLINICAL VERIFICATION
- REMINDER != PRESCRIPTION
- REMINDER != MEDICATION CHANGE
- NOTIFICATION FAILURE != CLINICAL SUCCESS
- SENT != DELIVERED
- DELIVERED != READ
- READ != CLINICAL ACTION
- TRANSFER NOTIFICATION != PATIENT TRANSFER
- TRIAGE NOTIFICATION != NEW TRIAGE
- CARE-PLAN NOTIFICATION != NEW MEDICAL ADVICE
- MEDICATION REMINDER != MEDICATION MANAGEMENT
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class NotificationChannel(str, Enum):
    """Supported delivery channels."""

    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class NotificationType(str, Enum):
    """Controlled notification taxonomy for HealthSetu."""

    DOCUMENT_PROCESSING_COMPLETED = "DOCUMENT_PROCESSING_COMPLETED"
    DOCUMENT_PROCESSING_FAILED = "DOCUMENT_PROCESSING_FAILED"
    PRESCRIPTION_PROCESSING_COMPLETED = "PRESCRIPTION_PROCESSING_COMPLETED"
    MEDICATION_NORMALIZATION_REVIEW_REQUIRED = "MEDICATION_NORMALIZATION_REVIEW_REQUIRED"
    MEDICATION_SAFETY_REVIEW_REQUIRED = "MEDICATION_SAFETY_REVIEW_REQUIRED"
    TRIAGE_RESULT_AVAILABLE = "TRIAGE_RESULT_AVAILABLE"
    SBAR_AVAILABLE = "SBAR_AVAILABLE"
    DISCHARGE_DOCUMENT_AVAILABLE = "DISCHARGE_DOCUMENT_AVAILABLE"
    CARE_PLAN_AVAILABLE = "CARE_PLAN_AVAILABLE"
    CARE_PLAN_UPDATED = "CARE_PLAN_UPDATED"
    TRANSFER_REQUEST_CREATED = "TRANSFER_REQUEST_CREATED"
    TRANSFER_STATUS_UPDATED = "TRANSFER_STATUS_UPDATED"
    INTEROPERABILITY_IMPORT_COMPLETED = "INTEROPERABILITY_IMPORT_COMPLETED"
    INTEROPERABILITY_IMPORT_FAILED = "INTEROPERABILITY_IMPORT_FAILED"
    DATA_QUALITY_REVIEW_REQUIRED = "DATA_QUALITY_REVIEW_REQUIRED"
    SECURITY_ALERT = "SECURITY_ALERT"
    ACCOUNT_SECURITY_NOTIFICATION = "ACCOUNT_SECURITY_NOTIFICATION"
    SYSTEM_NOTIFICATION = "SYSTEM_NOTIFICATION"
    ADMINISTRATIVE_NOTIFICATION = "ADMINISTRATIVE_NOTIFICATION"

    # Phase 31: Appointment & Scheduling Notifications
    APPOINTMENT_CREATED = "APPOINTMENT_CREATED"
    APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED"
    APPOINTMENT_RESCHEDULED = "APPOINTMENT_RESCHEDULED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    APPOINTMENT_CHECK_IN = "APPOINTMENT_CHECK_IN"
    APPOINTMENT_NO_SHOW = "APPOINTMENT_NO_SHOW"
    APPOINTMENT_STATUS_UPDATED = "APPOINTMENT_STATUS_UPDATED"

    # Phase 32: Billing & Payment Notifications
    PAYMENT_CREATED = "PAYMENT_CREATED"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_RECONCILIATION_REQUIRED = "PAYMENT_RECONCILIATION_REQUIRED"
    REFUND_CREATED = "REFUND_CREATED"
    REFUND_SUCCEEDED = "REFUND_SUCCEEDED"
    REFUND_FAILED = "REFUND_FAILED"
    INVOICE_ISSUED = "INVOICE_ISSUED"
    INVOICE_OVERDUE = "INVOICE_OVERDUE"
    INVOICE_PAID = "INVOICE_PAID"

    # Phase 33: Insurance, Pre-Authorization & Claim Notifications
    ELIGIBILITY_CHECK_COMPLETED = "ELIGIBILITY_CHECK_COMPLETED"
    ELIGIBILITY_CHECK_FAILED = "ELIGIBILITY_CHECK_FAILED"
    PREAUTH_REQUESTED = "PREAUTH_REQUESTED"
    PREAUTH_APPROVED = "PREAUTH_APPROVED"
    PREAUTH_DENIED = "PREAUTH_DENIED"
    CLAIM_SUBMITTED = "CLAIM_SUBMITTED"
    CLAIM_RECEIVED = "CLAIM_RECEIVED"
    CLAIM_APPROVED = "CLAIM_APPROVED"
    CLAIM_DENIED = "CLAIM_DENIED"
    CLAIM_REQUIRES_REVIEW = "CLAIM_REQUIRES_REVIEW"
    CLAIM_PAYMENT_RECEIVED = "CLAIM_PAYMENT_RECEIVED"
    CLAIM_RECONCILIATION_REQUIRED = "CLAIM_RECONCILIATION_REQUIRED"

    # Phase 34: Laboratory, Diagnostic Orders & Result Management
    DIAGNOSTIC_ORDER_CREATED = "DIAGNOSTIC_ORDER_CREATED"
    DIAGNOSTIC_ORDER_ACCEPTED = "DIAGNOSTIC_ORDER_ACCEPTED"
    DIAGNOSTIC_ORDER_FAILED = "DIAGNOSTIC_ORDER_FAILED"
    SPECIMEN_COLLECTED = "SPECIMEN_COLLECTED"
    DIAGNOSTIC_RESULT_AVAILABLE = "DIAGNOSTIC_RESULT_AVAILABLE"
    DIAGNOSTIC_RESULT_CORRECTED = "DIAGNOSTIC_RESULT_CORRECTED"
    DIAGNOSTIC_RESULT_REVIEW_REQUIRED = "DIAGNOSTIC_RESULT_REVIEW_REQUIRED"
    CRITICAL_RESULT_REVIEW_REQUIRED = "CRITICAL_RESULT_REVIEW_REQUIRED"
    DIAGNOSTIC_REPORT_AVAILABLE = "DIAGNOSTIC_REPORT_AVAILABLE"

    # Phase 35: Clinical Alerts, Safety Notifications & Escalation Management
    CLINICAL_ALERT_DISPATCHED = "CLINICAL_ALERT_DISPATCHED"
    CLINICAL_ALERT_ESCALATED = "CLINICAL_ALERT_ESCALATED"
    CLINICAL_ALERT_ACKNOWLEDGED = "CLINICAL_ALERT_ACKNOWLEDGED"
    CLINICAL_ALERT_RESOLVED = "CLINICAL_ALERT_RESOLVED"

    # Phase 36: Clinical Tasks, Work Queues & Action Management
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    TASK_OVERDUE = "TASK_OVERDUE"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_VERIFICATION_REQUIRED = "TASK_VERIFICATION_REQUIRED"

    # Phase 37: Clinical Workflow Orchestration, Order Management & Controlled Action Chains
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_APPROVAL_REQUIRED = "WORKFLOW_APPROVAL_REQUIRED"
    WORKFLOW_STEP_ASSIGNED = "WORKFLOW_STEP_ASSIGNED"
    WORKFLOW_BLOCKED = "WORKFLOW_BLOCKED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_ESCALATED = "WORKFLOW_ESCALATED"


class NotificationCategory(str, Enum):
    """Broad categorization for governance and preference management."""

    CLINICAL_WORKFLOW = "CLINICAL_WORKFLOW"
    OPERATIONAL = "OPERATIONAL"
    SECURITY = "SECURITY"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    DIAGNOSTIC = "DIAGNOSTIC"
    ALERT = "ALERT"
    TASK = "TASK"
    WORKFLOW = "WORKFLOW"


class NotificationStatus(str, Enum):
    """Database-aligned notification lifecycle states."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    RETRY_PENDING = "RETRY_PENDING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class NotificationPriority(str, Enum):
    """Delivery priority levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


def get_notification_category(notification_type: NotificationType) -> NotificationCategory:
    """Resolve category from notification type."""
    if notification_type in (
        NotificationType.SECURITY_ALERT,
        NotificationType.ACCOUNT_SECURITY_NOTIFICATION,
    ):
        return NotificationCategory.SECURITY
    if notification_type in (
        NotificationType.CARE_PLAN_AVAILABLE,
        NotificationType.CARE_PLAN_UPDATED,
        NotificationType.TRIAGE_RESULT_AVAILABLE,
        NotificationType.SBAR_AVAILABLE,
        NotificationType.MEDICATION_NORMALIZATION_REVIEW_REQUIRED,
        NotificationType.MEDICATION_SAFETY_REVIEW_REQUIRED,
        NotificationType.PRESCRIPTION_PROCESSING_COMPLETED,
    ):
        return NotificationCategory.CLINICAL_WORKFLOW
    if notification_type in (
        NotificationType.ADMINISTRATIVE_NOTIFICATION,
        NotificationType.SYSTEM_NOTIFICATION,
    ):
        return NotificationCategory.ADMINISTRATIVE
    return NotificationCategory.OPERATIONAL


class NotificationCreate(BaseModel):
    """Request payload to issue a new notification."""

    model_config = ConfigDict(extra="forbid")

    recipient_id: str = Field(..., min_length=1, max_length=128, description="Target recipient user ID")
    notification_type: NotificationType = Field(..., description="Approved notification event type")
    channels: Optional[List[NotificationChannel]] = Field(
        default=None,
        description="Target channels. If omitted, resolved automatically via recipient preferences.",
    )
    template_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Variables to interpolate into the notification template.",
    )
    resource_type: Optional[str] = Field(None, max_length=64, description="Originating domain resource type")
    resource_id: Optional[str] = Field(None, max_length=128, description="Originating domain resource ID")
    event_version: int = Field(default=1, ge=1, description="Originating event version for idempotency")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Delivery priority")
    language: Optional[str] = Field(None, max_length=10, description="Preferred language override (e.g. en, hi, bn)")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Explicit idempotency key")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational metadata (sanitized, non-PHI)")


class NotificationRead(BaseModel):
    """Full notification view model."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique notification identifier")
    recipient_id: str = Field(..., description="Recipient user identifier")
    notification_type: NotificationType = Field(..., description="Notification event type")
    category: NotificationCategory = Field(..., description="Notification category")
    priority: NotificationPriority = Field(..., description="Priority")
    status: NotificationStatus = Field(..., description="Current lifecycle state")
    title: str = Field(..., description="Localized rendered notification title")
    body: str = Field(..., description="Localized rendered notification body")
    channels: List[NotificationChannel] = Field(default_factory=list, description="Targeted delivery channels")
    resource_type: Optional[str] = Field(None, description="Linked domain resource type")
    resource_id: Optional[str] = Field(None, description="Linked domain resource ID")
    idempotency_key: str = Field(..., description="Deterministic idempotency key")
    created_at: datetime = Field(..., description="Timestamp of notification creation")
    read_at: Optional[datetime] = Field(None, description="Timestamp when marked as read")
    dismissed_at: Optional[datetime] = Field(None, description="Timestamp when dismissed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Sanitized metadata")


class NotificationListResponse(BaseModel):
    """Paginated notification response."""

    model_config = ConfigDict(from_attributes=True)

    items: List[NotificationRead] = Field(..., description="Notification items")
    total: int = Field(..., ge=0, description="Total matching notifications")
    unread_count: int = Field(default=0, ge=0, description="Count of unread notifications")
    limit: int = Field(..., ge=1, description="Page limit")
    offset: int = Field(..., ge=0, description="Page offset")


class NotificationBulkCreate(BaseModel):
    """Payload for administrative bulk notification dispatch."""

    model_config = ConfigDict(extra="forbid")

    recipient_ids: List[str] = Field(..., min_length=1, max_length=1000, description="Target recipients")
    notification_type: NotificationType = Field(..., description="Notification type")
    channels: Optional[List[NotificationChannel]] = Field(default=None, description="Channels")
    template_variables: Dict[str, Any] = Field(default_factory=dict, description="Variables")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL)
    reason: str = Field(..., min_length=5, max_length=255, description="Administrative audit reason")

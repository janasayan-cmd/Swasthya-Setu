"""Pydantic schemas for Clinical Orders (Phase 38).

CRITICAL ARCHITECTURAL & SAFETY INVARIANTS:
- ORDER != CLINICAL DECISION
- ORDER != DIAGNOSIS
- ORDER != TREATMENT
- ORDER != PRESCRIPTION
- ORDER != MEDICATION CHANGE
- ORDER CREATED != ORDER AUTHORIZED
- ORDER AUTHORIZED != ORDER TRANSMITTED
- ORDER TRANSMITTED != ORDER ACCEPTED
- ORDER ACCEPTED != ORDER PERFORMED
- ORDER PERFORMED != RESULT AVAILABLE
- RESULT AVAILABLE != RESULT VERIFIED
- RESULT VERIFIED != DIAGNOSIS
- ORDER COMPLETED != CLINICAL OUTCOME
- AI SUGGESTION != CLINICAL ORDER
- PROVIDER SUCCESS RESPONSE != CLINICAL SUCCESS
- UNKNOWN STATUS != COMPLETED
- MISSING INFORMATION != SAFE TO EXECUTE
- DATABASE REMAINS THE SOURCE OF TRUTH
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Order Types — Controlled extensible order category model (TRD Section 6)
# ---------------------------------------------------------------------------

class OrderType(str, Enum):
    """Supported clinical order type categories.

    Only types supported by the existing database/domain contract are enabled.
    Unsupported types MUST be rejected at validation time.
    """
    LAB_ORDER = "LAB_ORDER"
    IMAGING_ORDER = "IMAGING_ORDER"
    DIAGNOSTIC_ORDER = "DIAGNOSTIC_ORDER"
    REFERRAL_ORDER = "REFERRAL_ORDER"
    FOLLOW_UP_ORDER = "FOLLOW_UP_ORDER"
    PROCEDURE_ORDER = "PROCEDURE_ORDER"
    MEDICATION_ORDER = "MEDICATION_ORDER"
    OTHER_SUPPORTED_ORDER = "OTHER_SUPPORTED_ORDER"

    # Convenience values
    DIAGNOSTIC = "DIAGNOSTIC"
    MEDICATION = "MEDICATION"
    REFERRAL = "REFERRAL"
    LAB = "LAB"
    IMAGING = "IMAGING"


# Enabled order types under the current domain contract.
# Unsupported types are rejected at validation.
ENABLED_ORDER_TYPES: frozenset[OrderType] = frozenset({
    OrderType.LAB_ORDER,
    OrderType.IMAGING_ORDER,
    OrderType.DIAGNOSTIC_ORDER,
    OrderType.REFERRAL_ORDER,
    OrderType.FOLLOW_UP_ORDER,
    OrderType.PROCEDURE_ORDER,
    OrderType.MEDICATION_ORDER,
    OrderType.DIAGNOSTIC,
    OrderType.MEDICATION,
    OrderType.REFERRAL,
    OrderType.LAB,
    OrderType.IMAGING,
})


# ---------------------------------------------------------------------------
# Order Status — Lifecycle states (TRD Section 7)
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    """Controlled lifecycle statuses for clinical orders.

    IMPORTANT: These values MUST map to the actual database contract.
    Do NOT assume these exact enum values exist verbatim in the database schema.
    The implementation must validate against the actual stored values.
    """
    DRAFT = "DRAFT"
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    QUEUED = "QUEUED"
    TRANSMITTING = "TRANSMITTING"
    TRANSMITTED = "TRANSMITTED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    RESULT_PENDING = "RESULT_PENDING"
    RESULT_AVAILABLE = "RESULT_AVAILABLE"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    # Provider uncertainty states — NEVER converted to success
    TRANSMISSION_UNKNOWN = "TRANSMISSION_UNKNOWN"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RETRY_PENDING = "RETRY_PENDING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


# ---------------------------------------------------------------------------
# Order Priority
# ---------------------------------------------------------------------------

class OrderPriority(str, Enum):
    """Clinical priority for order execution turnaround."""
    ROUTINE = "ROUTINE"
    URGENT = "URGENT"
    STAT = "STAT"
    ASAP = "ASAP"


# ---------------------------------------------------------------------------
# Order Author / Provenance
# ---------------------------------------------------------------------------

class OrderProvenance(BaseModel):
    """Provenance record tracking the order's authorship and authorization chain."""

    model_config = ConfigDict(populate_by_name=True)

    ordered_by: str = Field(description="ID of the ordering clinician")
    authorized_by: Optional[str] = Field(default=None, description="ID of authorizing clinician if different")
    organization_id: str = Field(description="Ordering organization")
    facility_id: str = Field(description="Ordering facility")
    encounter_id: Optional[str] = Field(default=None, description="Associated clinical encounter")
    workflow_id: Optional[str] = Field(default=None, description="Originating workflow ID if applicable")
    source_document_id: Optional[str] = Field(
        default=None,
        description="Source document ID if order originated from document extraction. "
                    "NOTE: DOCUMENT EXTRACTION != ORDER CREATION. "
                    "An explicit authorized transition is required.",
    )
    correlation_id: str = Field(description="Internal correlation ID for tracing")
    idempotency_key: Optional[str] = Field(default=None, description="Client-provided idempotency key")


# ---------------------------------------------------------------------------
# Order Item / Line Item
# ---------------------------------------------------------------------------

class OrderItemCreate(BaseModel):
    """A single item within a clinical order (e.g., a specific test or procedure)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    item_id: Optional[str] = None
    item_type: Optional[str] = Field(default=None, description="Item type or catalog code")
    item_name: Optional[str] = Field(default=None, description="Human-readable item name")
    item_code: Optional[str] = Field(default=None, description="Standard coding (LOINC, CPT, SNOMED, etc.)")
    coding_system: Optional[str] = Field(default=None, description="Coding system identifier (LOINC, CPT, etc.)")
    instructions: Optional[str] = Field(default=None, description="Specific item-level instructions")
    quantity: int = Field(default=1, ge=1, description="Quantity or count")
    notes: Optional[str] = Field(default=None, description="Clinical notes for this item")
    name: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None


class OrderItem(BaseModel):
    """Persisted clinical order line item."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique item identifier")
    order_id: str = Field(default="", description="Parent order ID")
    item_type: Optional[str] = None
    item_name: Optional[str] = None
    item_code: Optional[str] = None
    coding_system: Optional[str] = None
    instructions: Optional[str] = None
    quantity: int = Field(default=1)
    status: OrderStatus = Field(default=OrderStatus.QUEUED)
    notes: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Order Result Linkage (TRD Section 21)
# ---------------------------------------------------------------------------

class OrderResultLink(BaseModel):
    """Link between a clinical order and an associated result.

    IMPORTANT:
    - ORDER RESULT LINKAGE != RESULT VERIFICATION
    - RESULT VERIFIED != DIAGNOSIS
    - Results linked here are NOT automatically clinically verified.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    result_id: str = Field(description="Internal result identifier")
    result_type: str = Field(description="Type of result (diagnostic_result, lab_result, imaging_result, etc.)")
    provider_result_id: Optional[str] = Field(default=None, description="External provider result identifier")
    result_status: Optional[str] = Field(default=None, description="Result status from source system")
    reference_number: Optional[str] = Field(default=None, description="Reference tracking number")
    source: Optional[str] = Field(default=None, description="Result origin source")
    verified: bool = Field(default=False, description="Whether result has been clinically verified")
    verification_actor: Optional[str] = Field(default=None, description="Actor who verified the result")
    verified_at: Optional[datetime] = None
    provenance: Optional[str] = Field(default=None, description="Source/provenance of the result")
    linked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Order Creation Request (TRD Section 8)
# ---------------------------------------------------------------------------

class OrderCreate(BaseModel):
    """Request payload to create a clinical order.

    SAFETY REQUIREMENTS:
    - Patient reference is mandatory. Cannot be inferred.
    - Ordering clinician is mandatory. Cannot be inferred from context alone.
    - Order type must be explicitly supported.
    - AI output must NOT be passed here as an authorized order without human validation.
    - Missing clinical context MUST result in rejection, not silent inference.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    patient_id: str = Field(description="Target patient identifier (MANDATORY, cannot be inferred)")
    clinician_id: Optional[str] = Field(default=None, description="Ordering clinician identifier")
    organization_id: Optional[str] = Field(default=None, description="Responsible organization")
    facility_id: Optional[str] = Field(default=None, description="Ordering or servicing facility")
    order_type: OrderType = Field(description="Type of clinical order (must be a supported type)")
    priority: OrderPriority = Field(default=OrderPriority.ROUTINE)
    encounter_id: Optional[str] = Field(default=None, description="Associated clinical encounter")
    clinical_reason: Optional[str] = Field(
        default=None,
        description="Clinical rationale for the order. NOTE: reason != diagnosis. "
                    "This is documentation of clinical indication, not a diagnostic conclusion.",
    )
    items: List[Any] = Field(
        default_factory=list,
        description="Line items for the order",
    )
    provider_id: Optional[str] = Field(
        default=None,
        description="Target external provider ID. If None, the system uses configured defaults.",
    )
    notes: Optional[str] = Field(default=None, description="Special handling instructions")
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Client-provided idempotency key to prevent duplicate submissions",
    )
    # Medication-specific safeguards (TRD Section 27)
    medication_order_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Required for MEDICATION_ORDER type: dose, route, frequency, duration. "
                    "MISSING MEDICATION DETAILS MUST NOT BE SILENTLY INFERRED.",
    )
    # Referral-specific context (TRD Section 28)
    referral_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Required for REFERRAL_ORDER type. "
                    "NOTE: REFERRAL != APPOINTMENT. REFERRAL != TRANSFER.",
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="Originating workflow ID for traceability. "
                    "NOTE: WORKFLOW != CLINICAL AUTHORITY.",
    )
    source_document_id: Optional[str] = Field(
        default=None,
        description="Source document if order was assisted by document processing. "
                    "DOCUMENT EXTRACTION != ORDER AUTHORIZATION.",
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional structured metadata")


# ---------------------------------------------------------------------------
# Order Authorization Request (TRD Section 9)
# ---------------------------------------------------------------------------

class OrderAuthorizeRequest(BaseModel):
    """Request payload for clinician authorization of a draft or pending order.

    SAFETY: Authorization is a clinical action requiring authenticated
    clinical authority. AI cannot authorize an order.
    """
    reason: Optional[str] = Field(default=None, description="Authorization rationale or notes")
    authorized_by: Optional[str] = Field(
        default=None,
        description="Authorizing clinician ID (if different from ordering clinician)",
    )


# ---------------------------------------------------------------------------
# Order Submission Request
# ---------------------------------------------------------------------------

class OrderSubmitRequest(BaseModel):
    """Request to submit an authorized order to an external provider."""
    provider_id: Optional[str] = Field(default=None, description="Override provider ID for this submission")
    force_sync: bool = Field(
        default=False,
        description="If true, attempt synchronous submission (not recommended for most orders)",
    )


# ---------------------------------------------------------------------------
# Order Cancellation Request (TRD Section 19)
# ---------------------------------------------------------------------------

class OrderCancelRequest(BaseModel):
    """Request to cancel an active clinical order.

    SAFETY:
    - CANCEL_REQUESTED != CANCELLED (until provider confirms where applicable)
    - Cancellation must be verified with the provider
    - Historical state must NOT be overwritten
    """
    reason: str = Field(
        min_length=3,
        max_length=1000,
        description="Documented reason for cancellation (required for clinical audit trail)",
    )
    notify_patient: bool = Field(default=True, description="Whether to notify the patient of cancellation")


# ---------------------------------------------------------------------------
# Order Revision Request (TRD Section 20)
# ---------------------------------------------------------------------------

class OrderReviseRequest(BaseModel):
    """Request to revise or supersede a clinical order.

    SAFETY:
    - Original order is PRESERVED (never overwritten)
    - Revision relationship is maintained with full provenance
    - REVISION != SILENT OVERWRITE
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    reason: str = Field(
        min_length=3,
        max_length=1000,
        description="Documented reason for revision (required)",
    )
    revised_priority: Optional[OrderPriority] = None
    revised_clinical_reason: Optional[str] = None
    revised_items: Optional[List[Any]] = None
    items: Optional[List[Any]] = None
    revised_notes: Optional[str] = None
    revised_medication_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="For MEDICATION_ORDER revisions. Missing fields must NOT be silently inferred.",
    )


# ---------------------------------------------------------------------------
# Order Verification Request (TRD Section 21)
# ---------------------------------------------------------------------------

class OrderVerifyRequest(BaseModel):
    """Request to clinically verify an order or its result.

    SAFETY:
    - RESULT VERIFIED != DIAGNOSIS
    - Only authorized clinicians may verify
    - AI cannot verify
    """
    verified_by: Optional[str] = Field(
        default=None,
        description="Clinician ID performing verification (defaults to authenticated user)",
    )
    notes: Optional[str] = Field(default=None, description="Verification notes")


# ---------------------------------------------------------------------------
# Order Reconciliation Request (TRD Section 33)
# ---------------------------------------------------------------------------

class OrderReconcileRequest(BaseModel):
    """Request to trigger manual or admin-initiated order reconciliation.

    SAFETY:
    - Reconciliation must compare authoritative identifiers
    - Must preserve provenance
    - Must NOT automatically create new clinical actions
    - Must create review tasks where required
    """
    reason: Optional[str] = Field(default=None, description="Reconciliation trigger reason")
    force: bool = Field(default=False, description="Force reconciliation even if not flagged")


# ---------------------------------------------------------------------------
# Provider Response Model (TRD Section 14)
# ---------------------------------------------------------------------------

class OrderProviderResponse(BaseModel):
    """Normalized provider response — provider-specific models must NOT leak into domain.

    SAFETY INVARIANTS:
    - provider-success-response != clinical-success
    - provider-failure != order-failure (may need reconciliation)
    - unknown-provider-state != completed
    - timeout != failure
    """

    model_config = ConfigDict(populate_by_name=True)

    provider_order_id: Optional[str] = Field(default=None, description="Provider-assigned order ID")
    provider_status: Optional[str] = Field(default=None, description="Raw provider status string")
    internal_status: OrderStatus = Field(
        description="Normalized internal lifecycle status mapped from provider response"
    )
    accepted: Optional[bool] = Field(
        default=None,
        description="Whether provider explicitly accepted the order. "
                    "None means unknown (provider state uncertain).",
    )
    response_code: Optional[str] = Field(default=None, description="Provider response code")
    response_message: Optional[str] = Field(default=None, description="Provider response message")
    correlation_id: Optional[str] = Field(default=None, description="Provider correlation/tracking ID")
    provider_timestamp: Optional[datetime] = None
    provider_version: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Sanitized provider metadata")


# ---------------------------------------------------------------------------
# Order Record — Authoritative representation (TRD Section 11)
# ---------------------------------------------------------------------------

class OrderRecord(BaseModel):
    """Authoritative representation of a clinical order.

    SAFETY: This record is the domain's source of truth.
    External provider data must be normalized before being reflected here.
    """

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(description="Internal unique order identifier")
    order_number: str = Field(description="Human-readable sequential order number (e.g. CLN-ORD-20261003-0001)")
    patient_id: str = Field(description="Patient this order belongs to")
    clinician_id: str = Field(description="Ordering clinician")
    organization_id: str = Field(description="Responsible organization")
    facility_id: str = Field(description="Ordering facility")
    encounter_id: Optional[str] = None
    order_type: OrderType
    status: OrderStatus = Field(default=OrderStatus.DRAFT)
    priority: OrderPriority = Field(default=OrderPriority.ROUTINE)
    clinical_reason: Optional[str] = Field(
        default=None,
        description="Clinical indication. NOTE: reason != diagnosis",
    )
    items: List[OrderItem] = Field(default_factory=list)
    result_links: List[OrderResultLink] = Field(
        default_factory=list,
        description="Linked results. NOTE: ORDER RESULT LINKAGE != RESULT VERIFICATION",
    )
    # Provider tracking
    provider_id: Optional[str] = None
    provider_order_id: Optional[str] = None
    tracking_number: Optional[str] = None
    provider_response: Optional[OrderProviderResponse] = None
    # Revision/supersession tracking
    supersedes_order_id: Optional[str] = Field(
        default=None,
        description="Order ID that this order supersedes (revision chain)",
    )
    superseded_by_order_id: Optional[str] = Field(
        default=None,
        description="Order ID that supersedes this order",
    )
    revision_reason: Optional[str] = None
    # Timestamps
    ordered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    authorized_at: Optional[datetime] = None
    authorized_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    expired_at: Optional[datetime] = None
    # Provenance
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    workflow_id: Optional[str] = None
    source_document_id: Optional[str] = None
    # Operational
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Order Filter / Search
# ---------------------------------------------------------------------------

class OrderFilter(BaseModel):
    """Filtering and pagination parameters for order search."""

    patient_id: Optional[str] = None
    clinician_id: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    encounter_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    status: Optional[OrderStatus] = None
    provider_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class OrderListResponse(BaseModel):
    """Paginated response of clinical orders."""

    items: List[OrderRecord] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)


# ---------------------------------------------------------------------------
# Order History Entry
# ---------------------------------------------------------------------------

class OrderHistoryEntry(BaseModel):
    """Single entry in the order's audit/history log."""

    model_config = ConfigDict(populate_by_name=True)

    entry_id: str
    order_id: str
    action: str = Field(description="Action that occurred (e.g., ORDER_CREATED, ORDER_AUTHORIZED)")
    previous_status: Optional[OrderStatus] = None
    new_status: Optional[OrderStatus] = None
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None
    reason: Optional[str] = None
    correlation_id: Optional[str] = None
    provider_reference: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderHistoryResponse(BaseModel):
    """Paginated order history."""

    items: List[OrderHistoryEntry] = Field(default_factory=list)
    total: int = Field(ge=0)
    order_id: str


# ---------------------------------------------------------------------------
# Order Status Response
# ---------------------------------------------------------------------------

class OrderStatusResponse(BaseModel):
    """Order status with provider state details.

    SAFETY:
    - Internal status != provider status
    - Provider status must be translated, not blindly mapped
    - Unknown states must remain unknown
    """

    order_id: str
    order_number: str
    status: OrderStatus
    provider_status: Optional[str] = Field(
        default=None,
        description="Raw provider status (informational only, not authoritative)",
    )
    internal_status_detail: Optional[str] = None
    last_updated: datetime
    result_available: bool = Field(default=False)
    verification_required: bool = Field(default=False)
    reconciliation_required: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Webhook Event (TRD Section 42)
# ---------------------------------------------------------------------------

class OrderWebhookEvent(BaseModel):
    """Incoming webhook/callback event from an external order provider.

    SAFETY:
    - Webhook events MUST be authenticated before processing
    - Replay protection MUST be applied
    - Provider must be verified
    - Order identifier must be cross-referenced
    - WEBHOOK REPLAY != ORDER STATE CHANGE
    """

    event_id: str = Field(description="Provider-assigned unique event ID (used for replay protection)")
    provider_id: str = Field(description="Provider that sent the event")
    event_type: str = Field(description="Provider event type string")
    provider_order_id: str = Field(description="Provider order identifier")
    provider_status: Optional[str] = None
    patient_reference: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class OrderWebhookResponse(BaseModel):
    """Internal result after processing a provider webhook event."""

    accepted: bool
    order_id: Optional[str] = None
    action_taken: Optional[str] = None
    reason: Optional[str] = None

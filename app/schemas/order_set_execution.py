"""Pydantic schemas for Clinical Order Set Executions (Phase 39).

CRITICAL ARCHITECTURAL CONTRACT:
- ORDER SET EXECUTION != CLINICAL AUTHORIZATION
- ORDER GENERATED FROM TEMPLATE MUST PASS THROUGH PHASE 38
- PROVENANCE (TEMPLATE ID + VERSION ID) MUST BE PRESERVED
- IDEMPOTENCY MUST BE ENFORCED VIA KEY AND CORRELATION ID
- PARTIAL FAILURES MUST BE REFLECTED FAITHFULLY — NEVER FALSELY MARKED AS COMPLETED
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.order import OrderPriority, OrderType


# ---------------------------------------------------------------------------
# Order Set Execution Status (TRD Section 19)
# ---------------------------------------------------------------------------

class OrderSetExecutionStatus(str, Enum):
    """Controlled lifecycle states for an order set execution."""
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    EXPANDING = "EXPANDING"
    PARTIALLY_CREATED = "PARTIALLY_CREATED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Batch Execution Policy (TRD Section 17)
# ---------------------------------------------------------------------------

class BatchExecutionPolicy(str, Enum):
    """Policy governing handling of child order failures during order set expansion."""
    ATOMIC = "ATOMIC"
    PARTIAL = "PARTIAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Child Order Summary
# ---------------------------------------------------------------------------

class ChildOrderExecutionSummary(BaseModel):
    """Summary of a child order generated from an order set definition."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    order_id: str
    definition_id: str
    order_type: OrderType
    requested_service: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Execution Request (TRD Section 45)
# ---------------------------------------------------------------------------

class OrderSetExecuteRequest(BaseModel):
    """Request payload to execute an order set and compose child clinical orders.

    SAFETY:
    - Caller must be an authorized human clinician.
    - AI or automated non-clinical actors CANNOT execute order sets.
    - Idempotency key is mandatory to protect against duplicate requests.
    - Missing required clinical fields must NOT be silently inferred.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    patient_id: str = Field(description="Target patient identifier (cannot be inferred)")
    version_id: Optional[str] = Field(default=None, description="Template version. If None, active approved version is resolved.")
    idempotency_key: str = Field(description="Client-provided idempotency key for deduplication")
    clinical_reason: Optional[str] = Field(default=None, description="Indication rationale for this execution")
    encounter_id: Optional[str] = Field(default=None, description="Associated clinical encounter context")
    facility_id: Optional[str] = Field(default=None, description="Target facility context")
    organization_id: Optional[str] = Field(default=None, description="Responsible organization context")
    batch_policy: Optional[BatchExecutionPolicy] = Field(
        default=None,
        description="Override batch failure policy (ATOMIC, PARTIAL, REVIEW_REQUIRED)",
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="Originating workflow ID if triggered from Phase 37 workflow",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Explicit allowed parameter overrides for the order definitions",
    )


# ---------------------------------------------------------------------------
# Order Set Execution Record
# ---------------------------------------------------------------------------

class OrderSetExecutionRecord(BaseModel):
    """Persisted authoritative record of an order set execution instance."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Execution ID")
    template_id: str
    template_code: str
    version_id: str
    version_number: int
    patient_id: str
    ordered_by: str
    authorized_by: Optional[str] = None
    organization_id: str
    facility_id: Optional[str] = None
    encounter_id: Optional[str] = None
    idempotency_key: str
    batch_policy: BatchExecutionPolicy = BatchExecutionPolicy.PARTIAL
    status: OrderSetExecutionStatus = OrderSetExecutionStatus.CREATED
    child_orders: List[ChildOrderExecutionSummary] = Field(default_factory=list)
    created_orders_count: int = 0
    failed_orders_count: int = 0
    total_orders_count: int = 0
    failure_reason: Optional[str] = None
    parameters_applied: Dict[str, Any] = Field(default_factory=dict)
    workflow_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    history: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# List / Query Responses
# ---------------------------------------------------------------------------

class OrderSetExecutionListResponse(BaseModel):
    """Paginated list of order set execution records."""

    model_config = ConfigDict(populate_by_name=True)

    items: List[OrderSetExecutionRecord] = Field(default_factory=list)
    total: int
    page: int = 1
    page_size: int = 20

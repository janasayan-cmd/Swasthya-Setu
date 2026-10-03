"""Pydantic schemas for Diagnostic Orders (Phase 34).

SAFETY & ARCHITECTURAL INVARIANTS:
- DIAGNOSTIC ORDER != DIAGNOSIS
- DIAGNOSTIC ORDER != CLINICAL INTERPRETATION
- ORDER REASON != CONFIRMED DIAGNOSIS
- REPEATED SUBMISSION MUST BE PROTECTED BY IDEMPOTENCY
- ORDERS CANNOT BE ARBITRARILY CREATED WITHOUT AUTHORIZED WORKFLOW
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.specimen import SpecimenRecord, SpecimenType


class DiagnosticOrderStatus(str, Enum):
    """Controlled lifecycle statuses for diagnostic and laboratory orders."""

    DRAFT = "DRAFT"
    REQUESTED = "REQUESTED"
    PLACED = "PLACED"
    ACCEPTED = "ACCEPTED"
    SCHEDULED = "SCHEDULED"
    SPECIMEN_PENDING = "SPECIMEN_PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class OrderPriority(str, Enum):
    """Clinical priority for diagnostic order turnaround."""

    ROUTINE = "ROUTINE"
    URGENT = "URGENT"
    STAT = "STAT"
    ASAP = "ASAP"


class DiagnosticOrderItemCreate(BaseModel):
    """Sub-item (specific test/panel) requested in an order."""

    test_id: str = Field(description="Catalog test identifier")
    test_code: Optional[str] = Field(default=None, description="Test code if known")
    test_name: Optional[str] = Field(default=None, description="Clinical test name")
    specimen_type: Optional[SpecimenType] = Field(default=None, description="Required specimen matrix")
    notes: Optional[str] = Field(default=None, description="Clinical or handling instructions")


class DiagnosticOrderItem(BaseModel):
    """Persisted diagnostic order item."""

    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(description="Unique order item ID")
    order_id: str = Field(description="Parent order ID")
    test_id: str
    test_code: str
    test_name: str
    specimen_type: Optional[SpecimenType] = None
    specimen_id: Optional[str] = None
    status: DiagnosticOrderStatus = Field(default=DiagnosticOrderStatus.REQUESTED)
    notes: Optional[str] = None


class DiagnosticOrderCreate(BaseModel):
    """Request payload to create a diagnostic order."""

    patient_id: str = Field(description="Target patient identifier")
    clinician_id: str = Field(description="Ordering clinician identifier")
    organization_id: str = Field(description="Responsible organization identifier")
    facility_id: str = Field(description="Servicing or ordering facility identifier")
    encounter_id: Optional[str] = Field(default=None, description="Associated clinical encounter identifier")
    priority: OrderPriority = Field(default=OrderPriority.ROUTINE)
    clinical_reason: Optional[str] = Field(
        default=None,
        description="Clinical rationale or indication for ordering (NOTE: Reason is NOT a diagnosis)",
    )
    items: List[DiagnosticOrderItemCreate] = Field(min_length=1, description="List of diagnostic tests requested")
    provider_id: Optional[str] = Field(default=None, description="Target laboratory/diagnostic provider")
    notes: Optional[str] = Field(default=None, description="Special instructions")
    idempotency_key: Optional[str] = Field(default=None, description="Client idempotency key")


class DiagnosticOrderUpdate(BaseModel):
    """Request payload to update an existing order before placement."""

    priority: Optional[OrderPriority] = None
    clinical_reason: Optional[str] = None
    notes: Optional[str] = None


class DiagnosticOrderCancelRequest(BaseModel):
    """Request payload to cancel an active diagnostic order."""

    reason: str = Field(min_length=3, max_length=500, description="Documented reason for cancellation")


class DiagnosticOrderStatusUpdateRequest(BaseModel):
    """Request payload to manually update or sync diagnostic order status."""

    status: DiagnosticOrderStatus
    reason: Optional[str] = None


class DiagnosticOrderRecord(BaseModel):
    """Authoritative representation of a diagnostic order."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(description="Internal unique identifier for the order")
    order_number: str = Field(description="Human-readable sequential order number (e.g. ORD-20261003-0001)")
    patient_id: str
    clinician_id: str
    organization_id: str
    facility_id: str
    encounter_id: Optional[str] = None
    status: DiagnosticOrderStatus = Field(default=DiagnosticOrderStatus.REQUESTED)
    priority: OrderPriority = Field(default=OrderPriority.ROUTINE)
    clinical_reason: Optional[str] = None
    items: List[DiagnosticOrderItem] = Field(default_factory=list)
    specimens: List[SpecimenRecord] = Field(default_factory=list)
    provider_id: Optional[str] = None
    provider_order_id: Optional[str] = None
    ordered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DiagnosticOrderFilter(BaseModel):
    """Filtering options for searching and listing orders."""

    patient_id: Optional[str] = None
    clinician_id: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    encounter_id: Optional[str] = None
    status: Optional[DiagnosticOrderStatus] = None
    provider_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class DiagnosticOrderListResponse(BaseModel):
    """Paginated response of diagnostic orders."""

    items: List[DiagnosticOrderRecord] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)

"""Pydantic schemas for Clinical Order Sets, Protocol Templates & Controlled Order Composition (Phase 39).

CRITICAL SAFETY PRINCIPLES:
- ORDER SET != CLINICAL DECISION
- ORDER SET != DIAGNOSIS
- ORDER SET != TREATMENT
- ORDER SET != PRESCRIPTION
- ORDER SET != TRIAGE
- ORDER SET != MEDICATION CHANGE
- ORDER SET != EMERGENCY DISPATCH
- PROTOCOL TEMPLATE != CLINICAL AUTHORITY
- TEMPLATE != PATIENT-SPECIFIC RECOMMENDATION
- TEMPLATE VERSION != CLINICAL TRUTH
- ORDER SET SELECTION != ORDER AUTHORIZATION
- ORDER SET EXPANSION != ORDER EXECUTION
- ORDER SET CREATION != CLINICAL APPROVAL
- TEMPLATE APPROVAL != PATIENT-SPECIFIC APPROVAL
- ORDER GENERATED FROM TEMPLATE != AUTHORIZED ORDER
- AI SUGGESTION != ORDER SET SELECTION
- AI SUGGESTION != CLINICAL AUTHORIZATION
- AI OUTPUT != PROTOCOL APPROVAL
- DATABASE REMAINS THE SOURCE OF TRUTH
- PREVIEW != EXECUTION
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.order import OrderPriority, OrderType


# ---------------------------------------------------------------------------
# Template Type (TRD Section 7)
# ---------------------------------------------------------------------------

class TemplateType(str, Enum):
    """Controlled template categories.

    Only types supported by the existing domain contract are enabled.
    Unsupported types must be rejected at validation time.
    """
    DIAGNOSTIC_ORDER_SET = "DIAGNOSTIC_ORDER_SET"
    LAB_ORDER_SET = "LAB_ORDER_SET"
    IMAGING_ORDER_SET = "IMAGING_ORDER_SET"
    REFERRAL_ORDER_SET = "REFERRAL_ORDER_SET"
    FOLLOW_UP_ORDER_SET = "FOLLOW_UP_ORDER_SET"
    DISCHARGE_ORDER_SET = "DISCHARGE_ORDER_SET"
    ORGANIZATION_PROTOCOL = "ORGANIZATION_PROTOCOL"
    FACILITY_PROTOCOL = "FACILITY_PROTOCOL"
    OTHER_SUPPORTED_TEMPLATE = "OTHER_SUPPORTED_TEMPLATE"


# ---------------------------------------------------------------------------
# Template Scope (TRD Section 8)
# ---------------------------------------------------------------------------

class TemplateScope(str, Enum):
    """Scope of template ownership and accessibility."""
    SYSTEM = "SYSTEM"
    ORGANIZATION = "ORGANIZATION"
    FACILITY = "FACILITY"
    DEPARTMENT = "DEPARTMENT"


# ---------------------------------------------------------------------------
# Template Lifecycle / Status (TRD Section 10)
# ---------------------------------------------------------------------------

class TemplateStatus(str, Enum):
    """Lifecycle states for order set templates and versions.

    INVARIANTS:
    - DRAFT != USABLE
    - APPROVED != ACTIVE
    - ACTIVE != PATIENT-SPECIFICALLY AUTHORIZED
    - DEPRECATED != INVALID FOR HISTORICAL RECORDS
    - RETIRED != DELETED HISTORY
    """
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ---------------------------------------------------------------------------
# Order Definition within a Template (TRD Section 13, 14)
# ---------------------------------------------------------------------------

class OrderDefinition(BaseModel):
    """Controlled definition of a single child order within a template.

    INVARIANTS:
    - Parameter overrides are strictly restricted to allowed fields.
    - Callers cannot mutate an order definition into an arbitrary clinical order.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    definition_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this order definition inside the template",
    )
    order_type: OrderType = Field(description="Clinical order type category")
    requested_service: str = Field(description="Requested clinical test, study, procedure, or specialty")
    priority: OrderPriority = Field(default=OrderPriority.ROUTINE, description="Default clinical priority")
    clinical_reason: Optional[str] = Field(default=None, description="Default clinical rationale")
    required_fields: List[str] = Field(
        default_factory=list,
        description="Fields that must be provided via overrides or defaults",
    )
    optional_fields: List[str] = Field(
        default_factory=list,
        description="Optional fields supported for this order definition",
    )
    allowed_parameter_overrides: List[str] = Field(
        default_factory=lambda: [
            "body_region",
            "specimen_type",
            "preferred_facility",
            "requested_date",
            "quantity",
            "duration",
            "referral_destination",
            "notes",
            "clinical_reason",
            "priority",
            "medication_order_details",
            "referral_details",
        ],
        description="List of parameter keys that are allowed to be overridden by caller",
    )
    provider_compatibility_requirements: List[str] = Field(
        default_factory=list,
        description="Required provider capabilities or supported order types",
    )
    authorization_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Authorization prerequisites (e.g. physician required)",
    )
    default_parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default values for order fields",
    )
    items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Line items for the order definition (e.g. specific lab tests or LOINC codes)",
    )


# ---------------------------------------------------------------------------
# Template Version Record (TRD Section 9, 11)
# ---------------------------------------------------------------------------

class OrderSetTemplateVersion(BaseModel):
    """Auditable immutable version of an order set template.

    INVARIANTS:
    - Historical versions must NEVER be mutated.
    - If a template changes materially, a new version is created.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    version_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this version",
    )
    template_id: str = Field(description="Parent template ID")
    version_number: int = Field(ge=1, description="Sequential version number")
    status: TemplateStatus = Field(default=TemplateStatus.DRAFT, description="Version lifecycle status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(description="Identifier of user who created this version")
    approved_by: Optional[str] = Field(default=None, description="Identifier of approving user")
    approved_at: Optional[datetime] = Field(default=None, description="Timestamp of approval")
    approval_reason: Optional[str] = Field(default=None, description="Approval justification notes")
    effective_from: Optional[datetime] = Field(default=None, description="Effective start date/time")
    effective_to: Optional[datetime] = Field(default=None, description="Expiration date/time")
    change_reason: Optional[str] = Field(default=None, description="Reason for version change")
    order_definitions: List[OrderDefinition] = Field(
        default_factory=list,
        description="Predefined order definitions included in this version",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional structured metadata")


# ---------------------------------------------------------------------------
# Order Set Template Master Record (TRD Section 6, 8)
# ---------------------------------------------------------------------------

class OrderSetTemplateRecord(BaseModel):
    """Master record representing an order set template entity with version history."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Template ID")
    code: str = Field(description="Unique business code for the template (e.g. 'SET-DIAG-CHEST-PAIN')")
    title: str = Field(description="Display title of the order set")
    description: Optional[str] = Field(default=None, description="Clinical summary and intended use")
    template_type: TemplateType = Field(description="Category of order set")
    scope: TemplateScope = Field(default=TemplateScope.ORGANIZATION, description="Scope of template ownership")
    organization_id: Optional[str] = Field(default=None, description="Owning organization ID")
    facility_id: Optional[str] = Field(default=None, description="Owning facility ID if facility-scoped")
    department_id: Optional[str] = Field(default=None, description="Owning department ID if department-scoped")
    status: TemplateStatus = Field(default=TemplateStatus.DRAFT, description="Current master template status")
    active_version_id: Optional[str] = Field(default=None, description="Currently active approved version ID")
    versions: List[OrderSetTemplateVersion] = Field(default_factory=list, description="Version history")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(description="Creator identifier")


# ---------------------------------------------------------------------------
# Administrative API Request Schemas (TRD Section 42)
# ---------------------------------------------------------------------------

class OrderSetTemplateCreate(BaseModel):
    """Payload to create a new order set template (Draft, Version 1)."""

    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(description="Unique business identifier code")
    title: str = Field(description="Human-readable title")
    description: Optional[str] = Field(default=None)
    template_type: TemplateType = Field(description="Category of template")
    scope: TemplateScope = Field(default=TemplateScope.ORGANIZATION)
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    department_id: Optional[str] = None
    order_definitions: List[OrderDefinition] = Field(
        default_factory=list,
        description="Initial order definitions for Version 1",
    )
    change_reason: Optional[str] = Field(default="Initial version creation")


class OrderSetVersionCreate(BaseModel):
    """Payload to create a new version of an existing order set template."""

    model_config = ConfigDict(populate_by_name=True)

    order_definitions: List[OrderDefinition] = Field(description="Updated list of order definitions")
    change_reason: str = Field(description="Clinical or administrative reason for creating this new version")


class OrderSetApproveRequest(BaseModel):
    """Payload to approve a specific template version."""

    model_config = ConfigDict(populate_by_name=True)

    version_id: Optional[str] = Field(
        default=None,
        description="Version ID to approve. If None, latest reviewable version is targeted.",
    )
    reason: str = Field(description="Formal clinical approval notes / rationale")
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class OrderSetActivateRequest(BaseModel):
    """Payload to activate an approved template version."""

    model_config = ConfigDict(populate_by_name=True)

    version_id: Optional[str] = Field(
        default=None,
        description="Approved version ID to activate. If None, latest approved version is activated.",
    )


class OrderSetSuspendRequest(BaseModel):
    """Payload to suspend a template or its active version."""

    model_config = ConfigDict(populate_by_name=True)

    reason: str = Field(description="Mandatory reason for emergency suspension")


class OrderSetDeprecateRequest(BaseModel):
    """Payload to deprecate a template."""

    model_config = ConfigDict(populate_by_name=True)

    reason: str = Field(description="Reason for deprecating the order set template")


# ---------------------------------------------------------------------------
# Clinical Preview API Schemas (TRD Section 43, 44)
# ---------------------------------------------------------------------------

class OrderSetPreviewRequest(BaseModel):
    """Request payload to preview order set expansion.

    PREVIEW != EXECUTION.
    Preview interprets the template, calculates overrides, and returns expected orders
    WITHOUT creating orders, executing orders, or calling external providers.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    patient_id: str = Field(description="Target patient identifier")
    version_id: Optional[str] = Field(default=None, description="Specific version to preview")
    facility_id: Optional[str] = Field(default=None, description="Servicing facility context")
    organization_id: Optional[str] = Field(default=None, description="Organization context")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Candidate parameter overrides to preview",
    )


class ExpectedChildOrderPreview(BaseModel):
    """Expected child order details in preview mode."""

    definition_id: str
    order_type: OrderType
    requested_service: str
    priority: OrderPriority
    clinical_reason: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
    applied_parameters: Dict[str, Any] = Field(default_factory=dict)
    provider_compatible: bool = True
    provider_compatibility_notes: Optional[str] = None


class OrderSetPreviewResponse(BaseModel):
    """Response payload for order set preview."""

    model_config = ConfigDict(populate_by_name=True)

    template_id: str
    template_code: str
    template_title: str
    template_type: TemplateType
    version_id: str
    version_number: int
    patient_id: str
    is_executable: bool
    expected_orders: List[ExpectedChildOrderPreview] = Field(default_factory=list)
    allowed_overrides: List[str] = Field(default_factory=list)
    applied_overrides: Dict[str, Any] = Field(default_factory=dict)
    rejected_overrides: List[str] = Field(default_factory=list)
    missing_required_fields: List[str] = Field(default_factory=list)
    validation_messages: List[str] = Field(default_factory=list)
    preview_generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Version Diff Response (TRD Section 28)
# ---------------------------------------------------------------------------

class OrderSetDiffResponse(BaseModel):
    """Informational diff between two versions of an order set template."""

    model_config = ConfigDict(populate_by_name=True)

    template_id: str
    from_version_number: int
    to_version_number: int
    added_definitions: List[Dict[str, Any]] = Field(default_factory=list)
    removed_definitions: List[Dict[str, Any]] = Field(default_factory=list)
    modified_definitions: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str

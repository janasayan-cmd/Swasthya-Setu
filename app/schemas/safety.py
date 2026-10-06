"""Phase 48: Safety Evaluation Request and Resource Status Schemas.

Exposes safety request payload, resource safety status, and re-exports core schemas.
"""

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_policy import SafetyPolicyRecord, SafetyPolicyType
from app.schemas.safety_result import SafetyCheckRecord, SafetyGateResult, SafetyStatus


class SafetyEvaluationRequest(BaseModel):
    """Client request to evaluate safety gate for an operation or decision."""

    model_config = ConfigDict(extra="ignore")

    operation: str = Field(..., description="Action or operation being evaluated (e.g. 'medication:apply', 'diagnosis:suggest')")
    decision_id: str | None = Field(default=None, description="Optional decision reference")
    patient_id: str | None = Field(default=None, description="Optional patient scope")
    resource_type: str | None = Field(default=None, description="Optional target resource type")
    resource_id: str | None = Field(default=None, description="Optional target resource ID")
    policy_type: SafetyPolicyType = Field(default=SafetyPolicyType.CLINICAL_ACTION_SAFETY, description="Target policy domain")
    context: dict[str, Any] = Field(default_factory=dict, description="Contextual parameters for evaluation")
    provider_status: str | None = Field(default=None, description="Status of external provider if applicable")
    input_data: dict[str, Any] | None = Field(default=None, description="Clinical input parameters to validate")
    
    # Client bypass parameters to detect and actively reject
    skip_safety: bool | None = Field(default=None, description="Illegal client attempt to skip safety")
    force_apply: bool | None = Field(default=None, description="Illegal client attempt to force application")
    ignore_review: bool | None = Field(default=None, description="Illegal client attempt to ignore human review")
    emergency: bool | None = Field(default=None, description="Uncontrolled client attempt to declare emergency")


class ResourceSafetyStatusResponse(BaseModel):
    """Current safety evaluation status for a clinical resource."""

    model_config = ConfigDict(extra="ignore")

    resource_type: str = Field(..., description="Type of clinical resource")
    resource_id: str = Field(..., description="Identifier of the resource")
    patient_id: str | None = Field(default=None, description="Associated patient ID")
    current_version: int | None = Field(default=None, description="Current recorded version")
    is_safe_for_action: bool = Field(..., description="Whether actions can be applied safely")
    safety_status: SafetyStatus = Field(..., description="Current safety status")
    active_conflicts: list[str] = Field(default_factory=list, description="Active conflict reasons if any")
    last_evaluated_at: datetime | None = Field(default=None, description="Timestamp of latest evaluation")
    pending_reviews_count: int = Field(default=0, description="Number of decisions awaiting clinician review")


__all__ = [
    "SafetyPolicyType",
    "SafetyPolicyRecord",
    "SafetyStatus",
    "SafetyGateResult",
    "SafetyCheckRecord",
    "SafetyEvaluationRequest",
    "ResourceSafetyStatusResponse",
]

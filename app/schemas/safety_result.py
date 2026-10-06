"""Phase 48: Safety Evaluation Result Schemas.

Defines safety statuses, evaluation outputs, and check persistence records.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_policy import SafetyPolicyType


class SafetyStatus(str, Enum):
    """Controlled safety outcome states."""

    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    RESTRICTED = "RESTRICTED"


class SafetyGateResult(BaseModel):
    """Structured response from safety-gate evaluation."""

    model_config = ConfigDict(extra="ignore")

    check_id: str = Field(..., description="Unique check identifier")
    allowed: bool = Field(..., description="Whether the operation is permitted to proceed")
    status: SafetyStatus = Field(..., description="Specific safety outcome status")
    reason_codes: list[str] = Field(default_factory=list, description="Machine-readable block or alert reasons")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking safety warnings")
    required_actions: list[str] = Field(default_factory=list, description="Actions required before operation can be allowed")
    policy_type: SafetyPolicyType | None = Field(default=None, description="Evaluated safety policy type")
    policy_version: str = Field(default="1.0.0", description="Version of the safety policy applied")
    decision_id: str | None = Field(default=None, description="Linked decision ID if applicable")
    patient_id: str | None = Field(default=None, description="Patient scope identifier")
    resource_type: str | None = Field(default=None, description="Resource type evaluated")
    resource_id: str | None = Field(default=None, description="Resource identifier evaluated")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of evaluation",
    )
    details: dict[str, Any] = Field(default_factory=dict, description="Safe metadata. Must NOT contain raw PHI.")


class SafetyCheckRecord(BaseModel):
    """Persisted record of safety check execution."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique check identifier")
    operation: str = Field(..., description="Target operation attempted")
    allowed: bool = Field(..., description="Whether allowed")
    status: SafetyStatus = Field(..., description="Safety status")
    policy_type: SafetyPolicyType = Field(..., description="Policy type evaluated")
    policy_version: str = Field(..., description="Policy version used")
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    decision_id: str | None = None
    patient_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    actor_id: str | None = None
    actor_role: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)

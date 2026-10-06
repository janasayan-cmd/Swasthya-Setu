"""Phase 48: Safety Policy Schemas.

Defines controlled policy categories, metadata, and versioning models.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SafetyPolicyType(str, Enum):
    """Controlled safety policy categories."""

    ACCESS_SAFETY = "ACCESS_SAFETY"
    CONSENT_SAFETY = "CONSENT_SAFETY"
    DATA_COMPLETENESS = "DATA_COMPLETENESS"
    DATA_FRESHNESS = "DATA_FRESHNESS"
    VERSION_SAFETY = "VERSION_SAFETY"
    PROVIDER_SAFETY = "PROVIDER_SAFETY"
    AI_SAFETY = "AI_SAFETY"
    CLINICAL_ACTION_SAFETY = "CLINICAL_ACTION_SAFETY"
    HUMAN_REVIEW_SAFETY = "HUMAN_REVIEW_SAFETY"
    CONCURRENCY_SAFETY = "CONCURRENCY_SAFETY"
    WORKFLOW_SAFETY = "WORKFLOW_SAFETY"
    EXTERNAL_DATA_SAFETY = "EXTERNAL_DATA_SAFETY"
    OUTPUT_VALIDATION = "OUTPUT_VALIDATION"
    PRIVACY_SAFETY = "PRIVACY_SAFETY"
    SECURITY_SAFETY = "SECURITY_SAFETY"


class SafetyPolicyRecord(BaseModel):
    """Versioned safety policy specification."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    policy_id: str = Field(..., description="Unique policy identifier")
    policy_type: SafetyPolicyType = Field(..., description="Category of the safety policy")
    policy_version: str = Field(default="1.0.0", description="Semantic version of policy rules")
    name: str = Field(..., description="Human-readable policy name")
    description: str = Field(..., description="Policy purpose and scope")
    mandatory_controls: list[str] = Field(default_factory=list, description="Controls that must pass")
    prohibited_actions: list[str] = Field(default_factory=list, description="Actions strictly disallowed under policy")
    fail_safe_status: str = Field(default="BLOCKED", description="Fallback status when evaluation cannot complete")
    effective_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this policy became effective",
    )
    is_active: bool = Field(default=True, description="Whether this policy is currently active")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Supplementary configuration parameters")

"""Pydantic schemas for Clinical Approval Policies (Phase 40).

CRITICAL ARCHITECTURAL CONTRACT:
- Approval policies are centralized and deterministic.
- Approval policies must be versioned.
- Safety-sensitive policies must fail closed.
- AI cannot determine whether clinical approval is required.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ApprovalPolicyRule(BaseModel):
    """Specific rule within an approval policy governing an action type."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    action_type: str = Field(description="Action or order type identifier")
    requires_approval: bool = Field(default=True, description="Whether explicit approval is mandatory")
    required_level: int = Field(default=1, ge=1, description="Required approval tier level")
    required_roles: List[str] = Field(
        default_factory=lambda: ["DOCTOR", "ADMIN", "SYSTEM_ADMIN"],
        description="List of user roles eligible to approve this action",
    )
    allow_self_approval: bool = Field(
        default=False,
        description="Whether the original requester may approve their own action",
    )
    multi_approver_count: int = Field(
        default=1,
        ge=1,
        description="Number of distinct approved decisions required",
    )
    expiration_hours: int = Field(
        default=48,
        ge=1,
        description="Validity window in hours before request expires",
    )
    allow_delegation: bool = Field(
        default=True,
        description="Whether an eligible approver may delegate this approval",
    )
    auto_escalate_hours: Optional[int] = Field(
        default=24,
        description="Hours pending review before auto-escalating",
    )

    @property
    def eligible_roles(self) -> List[str]:
        return self.required_roles

    @property
    def required_approvals_count(self) -> int:
        return self.multi_approver_count


class ApprovalPolicyRecord(BaseModel):
    """Versioned configuration-driven approval policy record."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    policy_id: str = Field(description="Unique policy identifier")
    policy_name: str = Field(description="Human-readable policy name")
    policy_version: int = Field(default=1, ge=1, description="Version number of this policy")
    rules: Dict[str, ApprovalPolicyRule] = Field(
        default_factory=dict,
        description="Map of action_type to its ApprovalPolicyRule",
    )
    default_rule: ApprovalPolicyRule = Field(
        default_factory=lambda: ApprovalPolicyRule(
            action_type="DEFAULT",
            requires_approval=True,
            required_level=1,
            allow_self_approval=False,
            multi_approver_count=1,
            expiration_hours=48,
        ),
        description="Fallback rule applied when no specific rule matches",
    )

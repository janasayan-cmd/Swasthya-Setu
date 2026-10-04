"""Pydantic schemas for Workflow Approval Gates (Phase 37).

CORE SAFETY PRINCIPLES:
- APPROVAL REQUEST != APPROVAL
- APPROVAL != CLINICAL TRUTH
- APPROVAL != DIAGNOSIS CONFIRMATION
- APPROVAL != PATIENT SAFETY CONFIRMATION
- APPROVAL != TREATMENT SUCCESS
- APPROVAL != MEDICATION SAFETY
- AI SUGGESTION != WORKFLOW AUTHORIZATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkflowApprovalDecision(str, Enum):
    """Explicit decision made by an authorized human gatekeeper."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class WorkflowApprovalRequest(BaseModel):
    """Request payload submitted by an authorized user to approve or reject a step."""

    model_config = ConfigDict(extra="forbid")

    decision: WorkflowApprovalDecision = Field(description="Decision: APPROVED or REJECTED")
    comments: Optional[str] = Field(default=None, max_length=1000, description="Optional rationale comments")
    policy_version: Optional[str] = Field(default="1.0", description="Policy version governing this approval gate")


class WorkflowApprovalRecord(BaseModel):
    """Authoritative audit record of an approval gate evaluation."""

    model_config = ConfigDict(extra="ignore")

    approval_id: str = Field(description="Unique identifier for approval record")
    workflow_id: str = Field(description="Workflow instance identifier")
    step_id: str = Field(description="Definition step identifier")
    step_instance_id: str = Field(description="Step runtime instance identifier")
    approver_id: str = Field(description="User ID of authorized approver")
    approver_role: str = Field(description="Role of approver at decision time")
    decision: WorkflowApprovalDecision = Field(description="Decision outcome")
    comments: Optional[str] = Field(default=None, description="Approver comments or rationale")
    policy_version: str = Field(default="1.0", description="Policy version applied")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when decision was submitted",
    )

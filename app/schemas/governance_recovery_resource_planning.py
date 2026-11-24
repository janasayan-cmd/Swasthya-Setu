"""Phase 88: Recovery Resource Allocation Planning Schemas.

Defines schemas for planning the resources required by recovery options.
This module produces planning proposals only and does not autonomously purchase or reserve resources.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
)


class RecoveryResourceRequirementItem(BaseModel):
    resource_id: str
    resource_name: str
    resource_category: str
    required_capacity_note: str
    availability_status: str  # AVAILABLE_VERIFIED, AVAILABLE_UNVERIFIED, DEGRADED, UNAVAILABLE, UNKNOWN
    competing_demands: List[str] = Field(default_factory=list)
    allocation_constraints: List[str] = Field(default_factory=list)
    responsible_owner_ref: str


class RecoveryResourcePlanRecord(BaseModel):
    plan_id: str
    tenant_id: str
    option_id: str
    resource_requirements: List[RecoveryResourceRequirementItem] = Field(default_factory=list)
    competing_demands_count: int = 0
    unmet_resource_requirements: List[str] = Field(default_factory=list)
    planning_status: str = "PROPOSAL"  # PROPOSAL, REVIEWED, APPROVED_FOR_HANDOFF
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class CreateRecoveryResourcePlanRequest(BaseModel):
    option_id: str
    requirements: List[RecoveryResourceRequirementItem] = Field(default_factory=list)

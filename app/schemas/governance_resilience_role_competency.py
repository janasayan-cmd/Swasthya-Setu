"""Phase 84: Role-Based Competency Requirements Schemas.

Maps organizational resilience roles to required capabilities, required proficiency levels,
and primary/backup coverage criteria without altering user identity or HR profiles.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
    ProficiencyLevel,
)


class RoleRequirementStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"


class RoleRequirementItem(BaseModel):
    capability_id: str
    required_proficiency: ProficiencyLevel = ProficiencyLevel.WORKING_KNOWLEDGE
    mandatory_for_primary: bool = True
    mandatory_for_backup: bool = True
    evidence_types: List[str] = Field(default_factory=list)


class RoleCapabilityRequirementRecord(BaseModel):
    requirement_id: str
    tenant_id: str
    role_name: str
    framework_id: str
    framework_version: int = 1
    organizational_scope: str = "GLOBAL"
    required_capabilities: List[RoleRequirementItem] = Field(default_factory=list)
    status: RoleRequirementStatus = RoleRequirementStatus.DRAFT
    created_by: str
    approved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class CreateRoleRequirementRequest(BaseModel):
    role_name: str
    framework_id: str
    framework_version: int = 1
    organizational_scope: str = "GLOBAL"
    required_capabilities: List[RoleRequirementItem] = Field(default_factory=list)


class UpdateRoleRequirementRequest(BaseModel):
    required_capabilities: Optional[List[RoleRequirementItem]] = None
    organizational_scope: Optional[str] = None


class ApproveRoleRequirementRequest(BaseModel):
    notes: Optional[str] = None

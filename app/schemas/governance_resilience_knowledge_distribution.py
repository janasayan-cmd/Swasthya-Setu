"""Phase 83: Knowledge Distribution Campaign Schemas.

Supports controlled campaign-based dissemination of validated and approved
resilience knowledge assets to targeted organizational audiences.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_knowledge import (
    MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER,
)


class AudienceType(str, Enum):
    ROLE = "ROLE"
    DEPARTMENT = "DEPARTMENT"
    FACILITY = "FACILITY"
    ORGANIZATION = "ORGANIZATION"


class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TargetAudienceSpec(BaseModel):
    audience_type: AudienceType
    audience_identifier: str
    description: Optional[str] = None


class KnowledgeDistributionCampaignRecord(BaseModel):
    campaign_id: str
    tenant_id: str
    knowledge_id: str
    knowledge_version: int = 1
    title: str
    description: Optional[str] = None
    target_audiences: List[TargetAudienceSpec] = Field(default_factory=list)
    acknowledgement_required: bool = True
    due_date: Optional[datetime] = None
    status: CampaignStatus = CampaignStatus.DRAFT
    created_by: str
    approved_by: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dispatch_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_KNOWLEDGE_DISCLAIMER)


class CreateDistributionCampaignRequest(BaseModel):
    knowledge_id: str
    title: str
    description: Optional[str] = None
    target_audiences: List[TargetAudienceSpec] = Field(default_factory=list)
    acknowledgement_required: bool = True
    due_date: Optional[datetime] = None


class ApproveDistributionCampaignRequest(BaseModel):
    approval_notes: Optional[str] = None


class DispatchDistributionCampaignRequest(BaseModel):
    dispatch_notes: Optional[str] = None
    recipient_user_ids: Optional[List[str]] = None

"""Phase 84: Capability Development and Remediation Schemas.

Coordinates targeted interventions, supervised drills, and knowledge reviews
linked to Phase 83 capability development recommendations and Phase 54 CAPA.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class CapabilityInterventionType(str, Enum):
    TARGETED_KNOWLEDGE_REVIEW = "TARGETED_KNOWLEDGE_REVIEW"
    ROLE_SPECIFIC_LEARNING = "ROLE_SPECIFIC_LEARNING"
    SUPERVISED_PRACTICAL_DEMO = "SUPERVISED_PRACTICAL_DEMO"
    RECOVERY_COORDINATION_EXERCISE = "RECOVERY_COORDINATION_EXERCISE"
    DELEGATED_AUTHORITY_PRACTICE = "DELEGATED_AUTHORITY_PRACTICE"
    EVIDENCE_RECONCILIATION_PRACTICE = "EVIDENCE_RECONCILIATION_PRACTICE"
    CROSS_FUNCTIONAL_COORDINATION = "CROSS_FUNCTIONAL_COORDINATION"
    BACKUP_ROLE_DEVELOPMENT = "BACKUP_ROLE_DEVELOPMENT"
    KNOWLEDGE_TRANSFER = "KNOWLEDGE_TRANSFER"
    REASSESSMENT = "REASSESSMENT"


class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class CapabilityDevelopmentProposalRecord(BaseModel):
    proposal_id: str
    tenant_id: str
    linked_gap_id: Optional[str] = None
    target_capability_id: str
    target_role_or_team: str
    proposed_intervention: CapabilityInterventionType
    rationalization: str
    expected_improvement: str
    assigned_owner: str
    target_completion_date: Optional[datetime] = None
    status: ProposalStatus = ProposalStatus.PROPOSED
    proposed_by: str
    approved_by: Optional[str] = None
    completion_evidence: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class ProposeDevelopmentRequest(BaseModel):
    linked_gap_id: Optional[str] = None
    target_capability_id: str
    target_role_or_team: str
    proposed_intervention: CapabilityInterventionType
    rationalization: str
    expected_improvement: str
    assigned_owner: str
    target_completion_date: Optional[datetime] = None


class ReviewDevelopmentProposalRequest(BaseModel):
    status: ProposalStatus
    review_notes: Optional[str] = None


class ApproveDevelopmentProposalRequest(BaseModel):
    approval_notes: Optional[str] = None


class CompleteDevelopmentProposalRequest(BaseModel):
    completion_evidence: str
    notes: Optional[str] = None

"""Phase 88: Response Strategy Registry Schemas.

Defines schemas for registering, updating, and reviewing proposed resilience response strategies.
A proposed strategy is an administrative proposal and must never be treated as an operational order.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    ResponseStrategyCategory,
    StrategyReviewStatus,
)


class ResponseStrategyRecord(BaseModel):
    strategy_id: str
    tenant_id: str
    strategy_name: str
    description: str
    category: ResponseStrategyCategory
    organizational_scope: str = "ORGANIZATION"
    applicable_scenario_ids: List[str] = Field(default_factory=list)
    affected_capability_refs: List[str] = Field(default_factory=list)
    required_resource_refs: List[str] = Field(default_factory=list)
    required_role_refs: List[str] = Field(default_factory=list)
    required_authorization_refs: List[str] = Field(default_factory=list)
    dependency_requirements: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    operational_constraints: List[str] = Field(default_factory=list)
    expected_limitations: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    strategy_version: str = "1.0"
    strategy_owner: str
    review_status: StrategyReviewStatus = StrategyReviewStatus.DRAFT
    approval_requirements: Optional[str] = None
    approval_ref: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class CreateResponseStrategyRequest(BaseModel):
    strategy_name: str
    description: str
    category: ResponseStrategyCategory
    organizational_scope: str = "ORGANIZATION"
    applicable_scenario_ids: List[str] = Field(default_factory=list)
    affected_capability_refs: List[str] = Field(default_factory=list)
    required_resource_refs: List[str] = Field(default_factory=list)
    required_role_refs: List[str] = Field(default_factory=list)
    required_authorization_refs: List[str] = Field(default_factory=list)
    dependency_requirements: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    operational_constraints: List[str] = Field(default_factory=list)
    expected_limitations: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    approval_requirements: Optional[str] = None
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None


class UpdateResponseStrategyRequest(BaseModel):
    strategy_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ResponseStrategyCategory] = None
    organizational_scope: Optional[str] = None
    applicable_scenario_ids: Optional[List[str]] = None
    affected_capability_refs: Optional[List[str]] = None
    required_resource_refs: Optional[List[str]] = None
    required_role_refs: Optional[List[str]] = None
    required_authorization_refs: Optional[List[str]] = None
    dependency_requirements: Optional[List[str]] = None
    preconditions: Optional[List[str]] = None
    operational_constraints: Optional[List[str]] = None
    expected_limitations: Optional[List[str]] = None
    evidence_refs: Optional[List[str]] = None
    effective_end: Optional[datetime] = None


class SubmitResponseStrategyRequest(BaseModel):
    submission_notes: Optional[str] = None


class ApproveResponseStrategyRequest(BaseModel):
    approval_ref: str
    approval_notes: Optional[str] = None

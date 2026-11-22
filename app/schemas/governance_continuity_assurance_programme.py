"""Phase 81: Independent Continuity Validation Programme Schemas.

Supports formal independent validation reviews with evaluator assignment,
independence declarations, conflict-of-interest checks, and management responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class ProgrammeStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    FINDINGS_REVIEW = "FINDINGS_REVIEW"
    REPORT_DRAFTED = "REPORT_DRAFTED"
    APPROVED = "APPROVED"
    CLOSED = "CLOSED"


class IndependenceCheckResult(str, Enum):
    INDEPENDENT_CONFIRMED = "INDEPENDENT_CONFIRMED"
    CONFLICT_OF_INTEREST_IDENTIFIED = "CONFLICT_OF_INTEREST_IDENTIFIED"
    PENDING_DECLARATION = "PENDING_DECLARATION"


class CreateValidationProgrammeRequest(BaseModel):
    programme_name: str
    scope_description: str
    objectives: List[str] = Field(default_factory=list)
    framework_version: int = 1
    target_plan_ids: List[str] = Field(default_factory=list)
    scheduled_start_date: datetime
    scheduled_end_date: datetime


class AssignEvaluatorRequest(BaseModel):
    evaluator_id: str
    evaluator_name: str
    evaluator_organization: str
    is_external_or_independent: bool = True


class RecordIndependenceDeclarationRequest(BaseModel):
    evaluator_id: str
    declaration_statement: str
    has_conflict_of_interest: bool
    conflict_details: Optional[str] = None


class SubmitEvidenceRequest(BaseModel):
    target_capability_or_plan_id: str
    evidence_description: str
    evidence_document_ref: str


class IndependentValidationProgrammeRecord(BaseModel):
    programme_id: str
    programme_name: str
    scope_description: str
    objectives: List[str] = Field(default_factory=list)
    framework_version: int
    target_plan_ids: List[str] = Field(default_factory=list)
    status: ProgrammeStatus = ProgrammeStatus.PLANNED
    assigned_evaluators: List[Dict[str, Any]] = Field(default_factory=list)
    independence_status: IndependenceCheckResult = IndependenceCheckResult.PENDING_DECLARATION
    evidence_requests: List[Dict[str, Any]] = Field(default_factory=list)
    associated_finding_ids: List[str] = Field(default_factory=list)
    final_report_ref: Optional[str] = None
    management_response: Optional[str] = None
    created_by: str
    created_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER

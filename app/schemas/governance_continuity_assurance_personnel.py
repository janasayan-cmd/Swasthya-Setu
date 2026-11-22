"""Phase 81: Personnel and Delegated Authority Readiness Schemas.

Evaluates critical role coverage, approved substitutes, and verifies delegated
authority against the authoritative authorization framework without duplicating HR data.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class ReadinessStatus(str, Enum):
    VERIFIED_READY = "VERIFIED_READY"
    CONDITIONALLY_READY = "CONDITIONALLY_READY"
    UNVERIFIED_AUTHORITY = "UNVERIFIED_AUTHORITY"
    SUBSTITUTE_MISSING = "SUBSTITUTE_MISSING"
    COMPETENCY_EVIDENCE_STALE = "COMPETENCY_EVIDENCE_STALE"
    SEPARATION_OF_DUTIES_CONFLICT = "SEPARATION_OF_DUTIES_CONFLICT"


class AssessPersonnelReadinessRequest(BaseModel):
    role_key: str
    role_name: str
    primary_owner_id: str
    approved_substitute_id: str
    organizational_scope: str = "GLOBAL"
    authority_source_doc_ref: str
    competency_evidence_ref: str
    last_exercise_participated_ref: Optional[str] = None
    notes: Optional[str] = None


class VerifyDelegatedAuthorityRequest(BaseModel):
    verified_valid: bool
    delegation_expiration_date: Optional[datetime] = None
    separation_of_duties_verified: bool
    verification_notes: Optional[str] = None


class PersonnelReadinessAssuranceRecord(BaseModel):
    readiness_id: str
    role_key: str
    role_name: str
    primary_owner_id: str
    approved_substitute_id: str
    organizational_scope: str
    authority_source_doc_ref: str
    competency_evidence_ref: str
    readiness_status: ReadinessStatus = ReadinessStatus.UNVERIFIED_AUTHORITY
    authority_verified_valid: bool = False
    delegation_expiration_date: Optional[datetime] = None
    separation_of_duties_verified: bool = False
    last_exercise_participated_ref: Optional[str] = None
    outstanding_readiness_gaps: List[str] = Field(default_factory=list)
    evaluated_by: str
    evaluated_at: datetime
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER

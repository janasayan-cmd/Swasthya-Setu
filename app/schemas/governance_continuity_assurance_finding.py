"""Phase 81: Continuity Finding Management Schemas.

Structured management of continuity assurance findings across 12 categories,
routing to Phase 54 CAPA, Phase 63 Risk, Phase 67 Exception, and Phase 70 Audit.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class ContinuityFindingCategory(str, Enum):
    MISSING_CONTINUITY_COVERAGE = "MISSING_CONTINUITY_COVERAGE"
    INCOMPLETE_CONTINUITY_PLANS = "INCOMPLETE_CONTINUITY_PLANS"
    UNVERIFIED_DELEGATED_AUTHORITY = "UNVERIFIED_DELEGATED_AUTHORITY"
    INADEQUATE_DEPENDENCY_ALTERNATIVES = "INADEQUATE_DEPENDENCY_ALTERNATIVES"
    FAILED_CONTINUITY_EXERCISE = "FAILED_CONTINUITY_EXERCISE"
    RECOVERY_TARGET_DEVIATION = "RECOVERY_TARGET_DEVIATION"
    DELAYED_RECOVERY = "DELAYED_RECOVERY"
    INCOMPLETE_EVIDENCE_RECONCILIATION = "INCOMPLETE_EVIDENCE_RECONCILIATION"
    REPEATED_EXERCISE_FAILURE = "REPEATED_EXERCISE_FAILURE"
    MISSING_RECOVERY_VERIFICATION = "MISSING_RECOVERY_VERIFICATION"
    STALE_ASSURANCE_EVIDENCE = "STALE_ASSURANCE_EVIDENCE"
    INCOMPLETE_CORRECTIVE_ACTION_FOLLOW_UP = "INCOMPLETE_CORRECTIVE_ACTION_FOLLOW_UP"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class FindingStatus(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    REFERRED_TO_CAPA = "REFERRED_TO_CAPA"
    REFERRED_TO_RISK = "REFERRED_TO_RISK"
    REFERRED_TO_AUDIT = "REFERRED_TO_AUDIT"
    REFERRED_TO_MANAGEMENT_REVIEW = "REFERRED_TO_MANAGEMENT_REVIEW"
    REMEDIATED = "REMEDIATED"
    VERIFIED_EFFECTIVE_BY_PHASE55 = "VERIFIED_EFFECTIVE_BY_PHASE55"
    CLOSED = "CLOSED"


class CreateContinuityFindingRequest(BaseModel):
    category: ContinuityFindingCategory
    severity: FindingSeverity
    title: str
    description: str
    affected_capability_id: str
    related_plan_id: Optional[str] = None
    related_plan_version: Optional[int] = None
    source_evidence_ref: str
    validation_criteria_ref: str
    detection_method: str = "INDEPENDENT_VALIDATION"
    impact_description: str
    assigned_owner: str
    recommended_action: str
    limitations: Optional[str] = None


class ReferFindingRequest(BaseModel):
    destination_workflow: str  # CAPA_PHASE54, RISK_PHASE63, AUDIT_PHASE70, REVIEW_PHASE72
    referral_reference_id: str
    referral_notes: Optional[str] = None


class CloseFindingRequest(BaseModel):
    phase55_effectiveness_ref: Optional[str] = None
    closure_rationale: str


class ContinuityAssuranceFindingRecord(BaseModel):
    finding_id: str
    category: ContinuityFindingCategory
    severity: FindingSeverity
    title: str
    description: str
    affected_capability_id: str
    related_plan_id: Optional[str] = None
    related_plan_version: Optional[int] = None
    source_evidence_ref: str
    validation_criteria_ref: str
    detection_method: str
    impact_description: str
    assigned_owner: str
    recommended_action: str
    status: FindingStatus = FindingStatus.IDENTIFIED
    destination_workflow: Optional[str] = None
    referral_reference_id: Optional[str] = None
    referral_notes: Optional[str] = None
    phase55_effectiveness_ref: Optional[str] = None
    closure_rationale: Optional[str] = None
    limitations: Optional[str] = None
    identified_by: str
    identified_at: datetime
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER

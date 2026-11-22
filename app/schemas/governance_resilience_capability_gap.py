"""Phase 84: Capability Gap Identification Schemas.

Detects evidence-based capability gaps, requires human validation, and coordinates
referral to Phase 54 CAPA, Phase 63 Risk, or Phase 83 Capability Development.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class CapabilityGapCategory(str, Enum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    EXPIRED_ASSESSMENT = "EXPIRED_ASSESSMENT"
    MISSING_PRIMARY_ROLE_COVERAGE = "MISSING_PRIMARY_ROLE_COVERAGE"
    MISSING_BACKUP_COVERAGE = "MISSING_BACKUP_COVERAGE"
    INSUFFICIENT_PRACTICAL_DEMONSTRATION = "INSUFFICIENT_PRACTICAL_DEMONSTRATION"
    REPEATED_UNSUCCESSFUL_DEMONSTRATION = "REPEATED_UNSUCCESSFUL_DEMONSTRATION"
    OUTDATED_CAPABILITY_FRAMEWORK = "OUTDATED_CAPABILITY_FRAMEWORK"
    UNVERIFIED_DELEGATED_AUTHORITY = "UNVERIFIED_DELEGATED_AUTHORITY"
    MISSING_CRITICAL_TEAM_CAPABILITY = "MISSING_CRITICAL_TEAM_CAPABILITY"
    INCOMPLETE_RECOVERY_COORDINATION_COVERAGE = "INCOMPLETE_RECOVERY_COORDINATION_COVERAGE"
    MISSING_EVIDENCE_RECONCILIATION_CAPABILITY = "MISSING_EVIDENCE_RECONCILIATION_CAPABILITY"
    NEW_ROLE_UNASSESSED = "NEW_ROLE_UNASSESSED"


class CapabilityGapSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CapabilityGapStatus(str, Enum):
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    CAPA_REFERRED = "CAPA_REFERRED"
    REMEDIATION_PLANNED = "REMEDIATION_PLANNED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CapabilityGapRecord(BaseModel):
    gap_id: str
    tenant_id: str
    category: CapabilityGapCategory
    severity: CapabilityGapSeverity = CapabilityGapSeverity.MEDIUM
    title: str
    description: str
    affected_capability_id: Optional[str] = None
    affected_role: Optional[str] = None
    affected_team_id: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list)
    status: CapabilityGapStatus = CapabilityGapStatus.DETECTED
    identified_by: str
    validated_by: Optional[str] = None
    capa_referral_id: Optional[str] = None
    risk_referral_id: Optional[str] = None
    resolution_notes: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    validated_at: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class DetectCapabilityGapRequest(BaseModel):
    category: CapabilityGapCategory
    severity: CapabilityGapSeverity = CapabilityGapSeverity.MEDIUM
    title: str
    description: str
    affected_capability_id: Optional[str] = None
    affected_role: Optional[str] = None
    affected_team_id: Optional[str] = None
    evidence_references: List[str] = Field(default_factory=list)


class ValidateCapabilityGapRequest(BaseModel):
    is_valid: bool
    validation_notes: Optional[str] = None


class DispositionCapabilityGapRequest(BaseModel):
    disposition_type: str = Field(..., description="CAPA_REFERRAL, RISK_REFERRAL, REMEDIATION_PLAN, or CLOSE")
    notes: str

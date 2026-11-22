"""Phase 81: Recovery Performance Assurance Schemas.

Evaluates actual recovery records against approved RTO, RPO, MTPD, and MBCO targets.
Distinguishes technical restoration from verified governance capability restoration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class RestorationStage(str, Enum):
    TECHNICAL_RESTORATION = "TECHNICAL_RESTORATION"
    FUNCTIONAL_RESTORATION = "FUNCTIONAL_RESTORATION"
    OPERATIONAL_RESTORATION = "OPERATIONAL_RESTORATION"
    VERIFIED_GOVERNANCE_RESTORATION = "VERIFIED_GOVERNANCE_RESTORATION"


class TargetPerformanceOutcome(str, Enum):
    MET_WITHIN_TARGET = "MET_WITHIN_TARGET"
    EXCEEDED_TARGET = "EXCEEDED_TARGET"
    SIGNIFICANT_BREACH = "SIGNIFICANT_BREACH"
    INSUFFICIENT_TIMESTAMPS = "INSUFFICIENT_TIMESTAMPS"
    TARGET_NOT_DEFINED = "TARGET_NOT_DEFINED"


class AssessRecoveryPerformanceRequest(BaseModel):
    recovery_id: str  # References Phase 80 GovernanceRecoveryRecord
    capability_id: str
    disruption_detected_at: datetime
    activation_requested_at: Optional[datetime] = None
    activation_approved_at: Optional[datetime] = None
    arrangements_established_at: Optional[datetime] = None
    technical_restored_at: Optional[datetime] = None
    operational_restored_at: Optional[datetime] = None
    governance_verified_at: Optional[datetime] = None
    reconciliation_completed_at: Optional[datetime] = None
    approved_rto_minutes: Optional[int] = None
    approved_rpo_minutes: Optional[int] = None
    approved_mtpd_minutes: Optional[int] = None
    notes: Optional[str] = None


class RecoveryPerformanceAssuranceRecord(BaseModel):
    assessment_id: str
    recovery_id: str
    capability_id: str
    disruption_detected_at: datetime
    detection_to_activation_request_minutes: Optional[float] = None
    activation_approval_duration_minutes: Optional[float] = None
    arrangement_establishment_duration_minutes: Optional[float] = None
    time_to_technical_restoration_minutes: Optional[float] = None
    time_to_operational_restoration_minutes: Optional[float] = None
    time_to_governance_verification_minutes: Optional[float] = None
    time_to_reconciliation_minutes: Optional[float] = None
    approved_rto_minutes: Optional[int] = None
    rto_outcome: TargetPerformanceOutcome = TargetPerformanceOutcome.TARGET_NOT_DEFINED
    approved_mtpd_minutes: Optional[int] = None
    mtpd_outcome: TargetPerformanceOutcome = TargetPerformanceOutcome.TARGET_NOT_DEFINED
    current_restoration_stage: RestorationStage = RestorationStage.TECHNICAL_RESTORATION
    is_governance_verified: bool = False
    deviations: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None
    evaluated_by: str
    evaluated_at: datetime
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER

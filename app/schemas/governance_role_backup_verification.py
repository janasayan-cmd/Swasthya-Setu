"""Phase 85: Backup Verification and Readiness Coordination Schemas.

Evaluates and records whether a designated backup holds verified Phase 84 competency,
valid administrative delegation references, and current operational availability.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    BackupVerificationStatus,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class BackupVerificationRecord(BaseModel):
    verification_id: str
    tenant_id: str
    coverage_id: str
    responsibility_id: str
    backup_user_id: str
    status: BackupVerificationStatus = BackupVerificationStatus.PENDING_REVIEW
    capability_verified: bool = False
    capability_assessment_ref: Optional[str] = None
    capability_assessment_date: Optional[datetime] = None
    authorization_verified: bool = False
    authorization_ref: Optional[str] = None
    authorization_expires_at: Optional[datetime] = None
    concurrent_tier1_roles_count: int = 0
    availability_confirmed: bool = True
    deficiencies: List[str] = Field(default_factory=list)
    verified_by: str
    verified_at: datetime = Field(default_factory=datetime.utcnow)
    next_verification_due: Optional[datetime] = None
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class VerifyBackupRequest(BaseModel):
    coverage_id: str
    responsibility_id: str
    backup_user_id: str
    capability_assessment_ref: Optional[str] = None
    capability_verified: bool = False
    authorization_ref: Optional[str] = None
    authorization_verified: bool = False
    authorization_expires_at: Optional[datetime] = None
    availability_confirmed: bool = True
    deficiencies: List[str] = Field(default_factory=list)
    verification_notes: Optional[str] = None


class RecheckBackupVerificationRequest(BaseModel):
    verification_notes: Optional[str] = None

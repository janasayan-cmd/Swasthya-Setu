"""Phase 85: Role-Coverage Mapping and Backup Arrangement Schemas.

Coordinates designated backups, capability links, authorization references,
and lifecycle states of governance coverage arrangements.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    BackupDesignationPrecedence,
    CoverageArrangementStatus,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class DesignatedBackupItem(BaseModel):
    backup_user_id: str
    backup_user_name: str
    precedence: BackupDesignationPrecedence = BackupDesignationPrecedence.PRIMARY_BACKUP
    capability_assessment_id: Optional[str] = None
    capability_verified: bool = False
    delegation_reference_id: Optional[str] = None
    authorization_verified: bool = False
    is_available: bool = True
    notes: Optional[str] = None


class RoleCoverageArrangementRecord(BaseModel):
    coverage_id: str
    tenant_id: str
    responsibility_id: str
    status: CoverageArrangementStatus = CoverageArrangementStatus.DRAFT
    designated_backups: List[DesignatedBackupItem] = Field(default_factory=list)
    effective_start_date: Optional[datetime] = None
    effective_end_date: Optional[datetime] = None
    activation_condition: Optional[str] = None
    created_by: str
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    activation_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class CreateCoverageArrangementRequest(BaseModel):
    responsibility_id: str
    designated_backups: List[DesignatedBackupItem] = Field(default_factory=list)
    effective_start_date: Optional[datetime] = None
    effective_end_date: Optional[datetime] = None
    activation_condition: Optional[str] = None


class UpdateCoverageArrangementRequest(BaseModel):
    designated_backups: Optional[List[DesignatedBackupItem]] = None
    effective_start_date: Optional[datetime] = None
    effective_end_date: Optional[datetime] = None
    activation_condition: Optional[str] = None


class SubmitCoverageArrangementRequest(BaseModel):
    submission_notes: Optional[str] = None


class ApproveCoverageArrangementRequest(BaseModel):
    approval_notes: Optional[str] = None


class SuspendCoverageArrangementRequest(BaseModel):
    reason: str


class CloseCoverageArrangementRequest(BaseModel):
    closure_reason: str

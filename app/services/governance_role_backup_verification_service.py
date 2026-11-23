"""Phase 85: Backup Verification and Readiness Service.

Verifies whether designated backups hold valid Phase 84 capability evidence,
active administrative delegation references, and operational availability.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_role_coverage_repository import (
    GovernanceRoleCoverageRepository,
    get_governance_role_coverage_repository,
)
from app.schemas.governance_role_coverage_common import (
    BackupVerificationStatus,
    CriticalityTier,
)
from app.schemas.governance_role_backup_verification import (
    BackupVerificationRecord,
    RecheckBackupVerificationRequest,
    VerifyBackupRequest,
)


class GovernanceRoleBackupVerificationService:
    """Service for validating designated backup capability and authorization."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def verify_backup(
        self,
        tenant_id: str,
        user_id: str,
        request: VerifyBackupRequest,
    ) -> BackupVerificationRecord:
        coverage = self.repository.get_coverage(request.coverage_id, tenant_id)
        if not coverage:
            raise AppException(
                code=ErrorCode.ROLE_COVERAGE_NOT_FOUND,
                message=f"Coverage arrangement '{request.coverage_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        responsibility = self.repository.get_responsibility(
            request.responsibility_id, tenant_id
        )
        if not responsibility:
            raise AppException(
                code=ErrorCode.CRITICAL_RESPONSIBILITY_NOT_FOUND,
                message=f"Critical responsibility '{request.responsibility_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Count concurrent Tier 1 roles this backup covers
        all_coverages = self.repository.list_coverages(tenant_id)
        concurrent_tier1 = 0
        for cov in all_coverages:
            resp = self.repository.get_responsibility(cov.responsibility_id, tenant_id)
            if resp and resp.criticality_tier == CriticalityTier.TIER_1_ESSENTIAL:
                for b in cov.designated_backups:
                    if b.backup_user_id == request.backup_user_id:
                        concurrent_tier1 += 1

        deficiencies = list(request.deficiencies)
        if not request.capability_verified:
            deficiencies.append("Missing verified Phase 84 competency assessment.")
        if not request.authorization_verified:
            deficiencies.append("Missing active administrative delegation reference.")
        if not request.availability_confirmed:
            deficiencies.append("Backup is marked temporarily unavailable.")
        if concurrent_tier1 > 3:
            deficiencies.append(f"Personnel concentration: Backup holds {concurrent_tier1} concurrent Tier 1 assignments.")

        now = datetime.utcnow()
        is_fully_verified = (
            request.capability_verified
            and request.authorization_verified
            and request.availability_confirmed
        )

        verification_status = (
            BackupVerificationStatus.VERIFIED
            if is_fully_verified
            else BackupVerificationStatus.DEFICIENT
        )

        next_due = now + timedelta(days=90)
        if request.authorization_expires_at and request.authorization_expires_at < next_due:
            next_due = request.authorization_expires_at

        record = BackupVerificationRecord(
            verification_id=f"bver-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            coverage_id=request.coverage_id,
            responsibility_id=request.responsibility_id,
            backup_user_id=request.backup_user_id,
            status=verification_status,
            capability_verified=request.capability_verified,
            capability_assessment_ref=request.capability_assessment_ref,
            capability_assessment_date=now,
            authorization_verified=request.authorization_verified,
            authorization_ref=request.authorization_ref,
            authorization_expires_at=request.authorization_expires_at,
            concurrent_tier1_roles_count=concurrent_tier1,
            availability_confirmed=request.availability_confirmed,
            deficiencies=deficiencies,
            verified_by=user_id,
            verified_at=now,
            next_verification_due=next_due,
        )
        saved = self.repository.save_backup_verification(record)

        # Update the backup item in the coverage arrangement
        updated_backups = []
        for b in coverage.designated_backups:
            if b.backup_user_id == request.backup_user_id:
                b.capability_assessment_id = request.capability_assessment_ref
                b.capability_verified = request.capability_verified
                b.delegation_reference_id = request.authorization_ref
                b.authorization_verified = request.authorization_verified
                b.is_available = request.availability_confirmed
            updated_backups.append(b)
        coverage.designated_backups = updated_backups
        coverage.updated_at = now
        self.repository.save_coverage(coverage)

        return saved

    def get_verification(
        self, tenant_id: str, verification_id: str
    ) -> BackupVerificationRecord:
        record = self.repository.get_backup_verification(verification_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.BACKUP_VERIFICATION_FAILED,
                message=f"Backup verification record '{verification_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_verifications(
        self,
        tenant_id: str,
        coverage_id: Optional[str] = None,
        verification_status: Optional[BackupVerificationStatus] = None,
    ) -> List[BackupVerificationRecord]:
        return self.repository.list_backup_verifications(tenant_id, coverage_id, verification_status)

    def recheck_verification(
        self,
        tenant_id: str,
        verification_id: str,
        user_id: str,
        request: RecheckBackupVerificationRequest,
    ) -> BackupVerificationRecord:
        record = self.get_verification(tenant_id, verification_id)
        now = datetime.utcnow()
        if record.authorization_expires_at and record.authorization_expires_at < now:
            record.status = BackupVerificationStatus.EXPIRED
            record.authorization_verified = False
            if "Authorization expired." not in record.deficiencies:
                record.deficiencies.append("Authorization expired.")
        record.verified_at = now
        record.verified_by = user_id
        return self.repository.save_backup_verification(record)


_backup_verification_service: Optional[GovernanceRoleBackupVerificationService] = None


def get_governance_role_backup_verification_service() -> GovernanceRoleBackupVerificationService:
    global _backup_verification_service
    if _backup_verification_service is None:
        _backup_verification_service = GovernanceRoleBackupVerificationService(
            get_governance_role_coverage_repository()
        )
    return _backup_verification_service

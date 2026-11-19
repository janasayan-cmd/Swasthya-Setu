"""Phase 69: Regulatory & Governance Evidence Package Service.

Coordinates:
- Controlled generation of evidence packages for internal audits and regulatory prep
- Minimal data principles enforcement (omits patient-identifiable health data)
- Manifest integrity hashing (SHA256)
- Package access auditing and retrieval
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_compliance_repository import (
    GovernanceComplianceRepository,
    get_governance_compliance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.compliance_evidence import AccessClassification
from app.schemas.compliance_package_report import (
    EvidencePackageRecord,
    GenerateEvidencePackageRequest,
    PackageStatus,
    TargetAudience,
)
from app.schemas.user import AuthenticatedUserContext


class ComplianceEvidencePackageService:
    """Service managing controlled regulatory and governance evidence packages."""

    def __init__(self, repository: Optional[GovernanceComplianceRepository] = None) -> None:
        self.repository = repository or get_governance_compliance_repository()

    def generate_package(
        self,
        user: AuthenticatedUserContext,
        payload: GenerateEvidencePackageRequest,
    ) -> EvidencePackageRecord:
        """Generate a controlled governance evidence package."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can generate evidence packages.",
                status_code=403,
            )

        framework = self.repository.get_framework(payload.framework_id)
        if not framework:
            raise AppException(
                code=ErrorCode.COMPLIANCE_FRAMEWORK_NOT_FOUND,
                message=f"Framework {payload.framework_id} not found.",
                status_code=404,
            )
        if framework.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot generate evidence package across tenant boundaries.",
                status_code=403,
            )

        # Collect requirements
        target_req_ids = payload.requirement_ids or [
            r.requirement_id
            for r in self.repository.list_requirements(
                organization_id=user.organization_id, framework_id=framework.framework_id
            )
        ]

        assessment_ids: List[str] = []
        evidence_refs: List[str] = []
        gap_ids: List[str] = []
        limitations: List[str] = []

        for req_id in target_req_ids:
            latest_asm = self.repository.get_latest_assessment_for_requirement(req_id)
            if latest_asm:
                assessment_ids.append(latest_asm.assessment_id)
                evidence_refs.extend(latest_asm.evidence_refs)
                if latest_asm.limitations:
                    limitations.extend(latest_asm.limitations)

            findings = self.repository.list_findings(requirement_id=req_id)
            gap_ids.extend([f.finding_id for f in findings if not f.is_resolved])

        # Filter out RESTRICTED evidence unless explicitly permitted
        if not payload.include_restricted_evidence:
            filtered_ev: List[str] = []
            for ev_id in evidence_refs:
                ev = self.repository.get_evidence(ev_id)
                if ev and ev.access_classification != AccessClassification.RESTRICTED:
                    filtered_ev.append(ev_id)
                elif ev and ev.access_classification == AccessClassification.RESTRICTED:
                    limitations.append(f"Evidence item {ev_id} omitted due to RESTRICTED access tier.")
            evidence_refs = filtered_ev

        now = datetime.now(timezone.utc)
        package_id = f"gpkg-{framework.framework_id[-6:]}-{int(now.timestamp())}"

        # Calculate manifest integrity hash
        manifest_payload = {
            "package_id": package_id,
            "framework_id": framework.framework_id,
            "framework_version": framework.version,
            "organization_id": user.organization_id,
            "requirement_count": len(target_req_ids),
            "evidence_count": len(evidence_refs),
            "gap_count": len(gap_ids),
            "generated_at": now.isoformat(),
        }
        manifest_bytes = json.dumps(manifest_payload, sort_keys=True).encode("utf-8")
        integrity_hash = hashlib.sha256(manifest_bytes).hexdigest()

        record = EvidencePackageRecord(
            package_id=package_id,
            framework_id=framework.framework_id,
            framework_version=framework.version,
            organization_id=user.organization_id,
            facility_id=framework.facility_id or user.facility_id,
            title=payload.title,
            description=payload.description,
            scope_summary=f"Scope: {len(target_req_ids)} requirements, {len(evidence_refs)} evidence items.",
            target_audience=payload.target_audience or TargetAudience.INTERNAL_AUDIT,
            status=PackageStatus.READY,
            requirement_ids=target_req_ids,
            assessment_ids=assessment_ids,
            evidence_refs=evidence_refs,
            gap_ids=gap_ids,
            limitations=limitations,
            generated_by=user.user_id,
            generated_at=now,
            download_count=0,
            last_accessed_at=now,
            integrity_hash=integrity_hash,
            created_at=now,
            metadata=payload.metadata or {},
        )

        return self.repository.save_evidence_package(record)

    def get_package(
        self, user: AuthenticatedUserContext, package_id: str
    ) -> EvidencePackageRecord:
        """Retrieve an evidence package and record an access audit increment."""
        pkg = self.repository.get_evidence_package(package_id)
        if not pkg:
            raise AppException(
                code=ErrorCode.EVIDENCE_PACKAGE_NOT_FOUND,
                message=f"Evidence package {package_id} not found.",
                status_code=404,
            )
        if pkg.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access evidence package across tenant boundaries.",
                status_code=403,
            )

        pkg.download_count += 1
        pkg.last_accessed_at = datetime.now(timezone.utc)
        return self.repository.save_evidence_package(pkg)

    def list_packages(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EvidencePackageRecord]:
        """List generated evidence packages within tenant scope."""
        return self.repository.list_evidence_packages(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )


# Global singleton
_global_package_service = ComplianceEvidencePackageService()


def get_compliance_evidence_package_service() -> ComplianceEvidencePackageService:
    """Dependency provider for compliance evidence package service."""
    return _global_package_service

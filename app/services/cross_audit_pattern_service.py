"""Phase 71: Cross-Audit Pattern Identification Service.

Coordinates:
- Cross-audit analytical pattern detection across facilities, controls, and workflows
- Distinction between statistical patterns and confirmed governance exceptions
- Human review and cross-phase governance referral workflow
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_intelligence_repository import (
    GovernanceAuditIntelligenceRepository,
    get_governance_audit_intelligence_repository,
)
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_finding_response import AuditFindingStatus
from app.schemas.audit_pattern_systemic import (
    AuditPatternRecord,
    PatternCategory,
    PatternReviewStatus,
    ReferPatternRequest,
    ReviewPatternRequest,
)
from app.schemas.user import AuthenticatedUserContext


class CrossAuditPatternService:
    """Service detecting cross-audit governance patterns and coordinating human review."""

    def __init__(
        self,
        audit_repo: Optional[GovernanceAuditRepository] = None,
        intel_repo: Optional[GovernanceAuditIntelligenceRepository] = None,
    ) -> None:
        self.audit_repo = audit_repo or get_governance_audit_repository()
        self.intel_repo = intel_repo or get_governance_audit_intelligence_repository()

    def detect_patterns(
        self, user: AuthenticatedUserContext, min_findings: int = 2
    ) -> List[AuditPatternRecord]:
        """Scan tenant audits and findings to identify cross-audit patterns."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot execute pattern detection.",
                status_code=403,
            )

        all_audits = self.audit_repo.list_audits(organization_id=user.organization_id)
        audit_map = {a.audit_id: a for a in all_audits}

        all_findings = self.audit_repo.list_findings_for_audit()
        tenant_findings = [
            f for f in all_findings
            if f.audit_id in audit_map and f.status != AuditFindingStatus.WITHDRAWN
        ]

        now = datetime.now(timezone.utc)
        patterns_generated: List[AuditPatternRecord] = []

        # ---------------------------------------------------------------------
        # Pattern 1: Control Weakness Concentration (same control in 2+ audits)
        # ---------------------------------------------------------------------
        findings_by_control: Dict[str, List] = defaultdict(list)
        for f in tenant_findings:
            if f.criterion_id:
                findings_by_control[f.criterion_id].append(f)

        for ctrl_id, f_list in findings_by_control.items():
            distinct_audits = list({f.audit_id for f in f_list})
            if len(distinct_audits) >= min_findings:
                distinct_facilities = list(
                    {audit_map[f.audit_id].facility_id for f in f_list if audit_map.get(f.audit_id) and audit_map[f.audit_id].facility_id}
                )
                pat = AuditPatternRecord(
                    pattern_name=f"Control Weakness Concentration: {ctrl_id}",
                    pattern_category=PatternCategory.CONTROL_WEAKNESS_CONCENTRATION,
                    related_audit_ids=distinct_audits,
                    related_finding_ids=[f.finding_id for f in f_list],
                    affected_controls=[ctrl_id],
                    affected_processes=[f.metadata.get("process", "CLINICAL_SAFETY_GOVERNANCE") for f in f_list],
                    affected_facilities=distinct_facilities,
                    matching_criteria={"criterion_id": ctrl_id, "audit_count": len(distinct_audits)},
                    time_period="LAST_12_MONTHS",
                    potential_impact="Multiple audits independently identified deficiencies in this safety control.",
                    analytical_explanation=(
                        f"Criterion/Control {ctrl_id} failed in {len(distinct_audits)} separate audits "
                        f"across {len(f_list)} individual findings."
                    ),
                    review_status=PatternReviewStatus.DETECTED,
                    organization_id=user.organization_id,
                    created_at=now,
                )
                saved = self.intel_repo.save_pattern(pat)
                patterns_generated.append(saved)

        # ---------------------------------------------------------------------
        # Pattern 2: Cross-Facility Deviation (same category in 2+ facilities)
        # ---------------------------------------------------------------------
        findings_by_cat: Dict[str, List] = defaultdict(list)
        for f in tenant_findings:
            findings_by_cat[f.category.value].append(f)

        for cat_name, f_list in findings_by_cat.items():
            facilities_set = {
                audit_map[f.audit_id].facility_id
                for f in f_list
                if audit_map.get(f.audit_id) and audit_map[f.audit_id].facility_id
            }
            if len(facilities_set) >= 2:
                distinct_audits = list({f.audit_id for f in f_list})
                pat = AuditPatternRecord(
                    pattern_name=f"Cross-Facility Governance Departure: {cat_name}",
                    pattern_category=PatternCategory.CROSS_FACILITY_DEVIATION,
                    related_audit_ids=distinct_audits,
                    related_finding_ids=[f.finding_id for f in f_list],
                    affected_controls=list({f.criterion_id for f in f_list if f.criterion_id}),
                    affected_processes=["ORGANIZATION_WIDE_GOVERNANCE"],
                    affected_facilities=list(facilities_set),
                    matching_criteria={"category": cat_name, "facility_count": len(facilities_set)},
                    time_period="LAST_12_MONTHS",
                    potential_impact="Systemic recurrence across multiple organizational sites.",
                    analytical_explanation=(
                        f"Finding category {cat_name} observed across {len(facilities_set)} facilities "
                        f"in {len(distinct_audits)} distinct audits."
                    ),
                    review_status=PatternReviewStatus.DETECTED,
                    organization_id=user.organization_id,
                    created_at=now,
                )
                saved = self.intel_repo.save_pattern(pat)
                patterns_generated.append(saved)

        return patterns_generated

    def get_pattern(
        self, user: AuthenticatedUserContext, pattern_id: str
    ) -> AuditPatternRecord:
        """Retrieve pattern ensuring tenant isolation."""
        pat = self.intel_repo.get_pattern(pattern_id)
        if not pat:
            raise AppException(
                code=ErrorCode.AUDIT_PATTERN_NOT_FOUND,
                message=f"Pattern {pattern_id} not found.",
                status_code=404,
            )
        if pat.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access pattern across tenant boundaries.",
                status_code=403,
            )
        return pat

    def list_patterns(
        self,
        user: AuthenticatedUserContext,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditPatternRecord]:
        """List patterns within tenant scope."""
        return self.intel_repo.list_patterns(
            organization_id=user.organization_id,
            category=category,
            status=status,
            limit=limit,
            offset=offset,
        )

    def review_pattern(
        self,
        user: AuthenticatedUserContext,
        pattern_id: str,
        payload: ReviewPatternRequest,
    ) -> AuditPatternRecord:
        """Record human review decision for an identified pattern."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can review patterns.",
                status_code=403,
            )

        pat = self.get_pattern(user, pattern_id)
        now = datetime.now(timezone.utc)
        pat.review_status = payload.review_status
        pat.reviewed_by = user.user_id
        pat.reviewed_at = now
        pat.review_rationale = payload.review_rationale
        return self.intel_repo.save_pattern(pat)

    def refer_pattern(
        self,
        user: AuthenticatedUserContext,
        pattern_id: str,
        payload: ReferPatternRequest,
    ) -> AuditPatternRecord:
        """Refer validated pattern to an authoritative governance workflow."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can refer patterns.",
                status_code=403,
            )

        pat = self.get_pattern(user, pattern_id)
        now = datetime.now(timezone.utc)

        referral_record = {
            "referral_id": f"gref-{now.strftime('%Y%m%d%H%M%S')}",
            "source_pattern_id": pattern_id,
            "destination_workflow": payload.destination_workflow,
            "referral_reason": payload.referral_reason,
            "requested_by": user.user_id,
            "timestamp": now.isoformat(),
            "organization_id": user.organization_id,
            "notes": payload.notes,
        }

        pat.referral_refs.append(referral_record)
        pat.review_status = PatternReviewStatus.REFERRED
        self.intel_repo.save_referral(referral_record)
        return self.intel_repo.save_pattern(pat)


# Global singleton
_global_pattern_service = CrossAuditPatternService()


def get_cross_audit_pattern_service() -> CrossAuditPatternService:
    """Dependency provider for cross-audit pattern service."""
    return _global_pattern_service

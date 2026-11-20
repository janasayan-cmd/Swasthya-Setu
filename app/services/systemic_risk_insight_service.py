"""Phase 71: Systemic Issue Candidate Identification & Scoring Service.

Coordinates:
- Analytical systemic issue candidate generation using approved configuration weights
- Deterministic priority scoring based on severity, recurrence, spread, and duration
- Human review and disposition workflow (confirm, reject, review)
- Cross-phase governance referral (Phase 54 CAPA, Phase 63 Risk, Phase 67 Escalation, Phase 49 Incident)
- Explicit non-negotiable invariant: Does not automatically declare clinical safety risk
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
from app.schemas.audit_analytics_source import DataQualityStatus
from app.schemas.audit_finding_response import AuditFindingStatus
from app.schemas.audit_pattern_systemic import (
    ConfirmSystemicCandidateRequest,
    ReferSystemicCandidateRequest,
    RejectSystemicCandidateRequest,
    ReviewSystemicCandidateRequest,
    SystemicCandidateStatus,
    SystemicIssueCandidateRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_analytics_config_service import (
    AuditAnalyticsConfigService,
    get_audit_analytics_config_service,
)


class SystemicRiskInsightService:
    """Service generating systemic issue candidates and managing review workflows."""

    def __init__(
        self,
        audit_repo: Optional[GovernanceAuditRepository] = None,
        intel_repo: Optional[GovernanceAuditIntelligenceRepository] = None,
        config_service: Optional[AuditAnalyticsConfigService] = None,
    ) -> None:
        self.audit_repo = audit_repo or get_governance_audit_repository()
        self.intel_repo = intel_repo or get_governance_audit_intelligence_repository()
        self.config_service = config_service or get_audit_analytics_config_service()

    def generate_systemic_candidates(
        self, user: AuthenticatedUserContext, min_score: float = 2.0
    ) -> List[SystemicIssueCandidateRecord]:
        """Synthesize findings, repeat issues, and patterns into systemic issue candidates."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot execute systemic issue analysis.",
                status_code=403,
            )

        config = self.config_service.get_or_create_default_config(user.organization_id)
        severity_weights = config.severity_weights or {
            "CRITICAL": 10.0,
            "URGENT": 7.0,
            "HIGH": 5.0,
            "ELEVATED": 3.0,
            "ROUTINE": 1.0,
        }

        all_audits = self.audit_repo.list_audits(organization_id=user.organization_id)
        audit_map = {a.audit_id: a for a in all_audits}

        all_findings = self.audit_repo.list_findings_for_audit()
        tenant_findings = [
            f for f in all_findings
            if f.audit_id in audit_map and f.status != AuditFindingStatus.WITHDRAWN
        ]

        # Group findings by category or common control
        grouped_findings: Dict[str, List] = defaultdict(list)
        for f in tenant_findings:
            key = f.criterion_id or f.category.value
            grouped_findings[key].append(f)

        now = datetime.now(timezone.utc)
        candidates_created: List[SystemicIssueCandidateRecord] = []

        for group_key, f_list in grouped_findings.items():
            if len(f_list) < 2:
                continue

            distinct_audits = list({f.audit_id for f in f_list})
            distinct_facilities = list(
                {
                    audit_map[f.audit_id].facility_id
                    for f in f_list
                    if audit_map.get(f.audit_id) and audit_map[f.audit_id].facility_id
                }
            )

            # Calculate deterministic priority score factors
            max_sev_score = max(severity_weights.get(f.severity.value, 1.0) for f in f_list)
            recurrence_factor = min(float(len(f_list)), 5.0) * 1.5
            facility_spread_factor = min(float(max(len(distinct_facilities), 1)), 4.0) * 1.25

            oldest_created = min(f.created_at for f in f_list)
            open_days = max((now - oldest_created).days, 1)
            duration_factor = min(float(open_days), 180.0) / 30.0

            total_priority_score = round(
                0.35 * max_sev_score
                + 0.25 * recurrence_factor
                + 0.20 * facility_spread_factor
                + 0.20 * duration_factor,
                2,
            )

            if total_priority_score >= min_score:
                score_factors = {
                    "max_severity_weight": round(max_sev_score, 2),
                    "recurrence_factor": round(recurrence_factor, 2),
                    "facility_spread_factor": round(facility_spread_factor, 2),
                    "duration_factor": round(duration_factor, 2),
                }

                controls = list({f.criterion_id for f in f_list if f.criterion_id})
                candidate = SystemicIssueCandidateRecord(
                    title=f"Potential Systemic Vulnerability: {group_key}",
                    description=(
                        f"Repeated cluster of {len(f_list)} findings across {len(distinct_audits)} audits "
                        f"with calculated priority score {total_priority_score}."
                    ),
                    status=SystemicCandidateStatus.DETECTED,
                    priority_score=total_priority_score,
                    score_factors=score_factors,
                    supporting_finding_ids=[f.finding_id for f in f_list],
                    supporting_audit_ids=distinct_audits,
                    supporting_pattern_ids=[],
                    matching_rationale=(
                        f"Identified multiple findings in group '{group_key}' across audits {distinct_audits}."
                    ),
                    scoring_methodology="DETERMINISTIC_PRIORITY_SCORE_V1",
                    configuration_version=config.version,
                    affected_controls=controls,
                    affected_processes=["CLINICAL_SAFETY_GOVERNANCE"],
                    affected_facilities=distinct_facilities,
                    data_quality_status=DataQualityStatus.COMPLETE,
                    known_limitations=[
                        "Analytical candidate only; requires clinical governance review before risk classification."
                    ],
                    organization_id=user.organization_id,
                    created_at=now,
                )
                saved = self.intel_repo.save_systemic_candidate(candidate)
                candidates_created.append(saved)

        return candidates_created

    def get_candidate(
        self, user: AuthenticatedUserContext, candidate_id: str
    ) -> SystemicIssueCandidateRecord:
        """Retrieve systemic candidate ensuring tenant isolation."""
        cand = self.intel_repo.get_systemic_candidate(candidate_id)
        if not cand:
            raise AppException(
                code=ErrorCode.SYSTEMIC_ISSUE_CANDIDATE_NOT_FOUND,
                message=f"Systemic issue candidate {candidate_id} not found.",
                status_code=404,
            )
        if cand.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access systemic candidate across tenant boundaries.",
                status_code=403,
            )
        return cand

    def list_candidates(
        self,
        user: AuthenticatedUserContext,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SystemicIssueCandidateRecord]:
        """List systemic issue candidates within tenant scope."""
        return self.intel_repo.list_systemic_candidates(
            organization_id=user.organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    def review_candidate(
        self,
        user: AuthenticatedUserContext,
        candidate_id: str,
        payload: ReviewSystemicCandidateRequest,
    ) -> SystemicIssueCandidateRecord:
        """Record human review disposition for a systemic issue candidate."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can review systemic issue candidates.",
                status_code=403,
            )

        cand = self.get_candidate(user, candidate_id)
        now = datetime.now(timezone.utc)
        cand.status = payload.status
        cand.reviewed_by = user.user_id
        cand.reviewed_at = now
        cand.review_rationale = payload.review_rationale
        return self.intel_repo.save_systemic_candidate(cand)

    def confirm_candidate(
        self,
        user: AuthenticatedUserContext,
        candidate_id: str,
        payload: ConfirmSystemicCandidateRequest,
    ) -> SystemicIssueCandidateRecord:
        """Confirm a systemic issue candidate (requires governance authority)."""
        return self.review_candidate(
            user,
            candidate_id,
            ReviewSystemicCandidateRequest(
                status=SystemicCandidateStatus.SYSTEMIC_ISSUE_CANDIDATE,
                review_rationale=payload.review_rationale,
            ),
        )

    def reject_candidate(
        self,
        user: AuthenticatedUserContext,
        candidate_id: str,
        payload: RejectSystemicCandidateRequest,
    ) -> SystemicIssueCandidateRecord:
        """Reject a systemic issue candidate with documented rationale."""
        return self.review_candidate(
            user,
            candidate_id,
            ReviewSystemicCandidateRequest(
                status=SystemicCandidateStatus.REJECTED,
                review_rationale=payload.rejection_rationale,
            ),
        )

    def refer_candidate(
        self,
        user: AuthenticatedUserContext,
        candidate_id: str,
        payload: ReferSystemicCandidateRequest,
    ) -> SystemicIssueCandidateRecord:
        """Refer validated systemic issue to authoritative governance workflows."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can refer systemic issues.",
                status_code=403,
            )

        cand = self.get_candidate(user, candidate_id)
        now = datetime.now(timezone.utc)

        referral_record = {
            "referral_id": f"gref-sys-{now.strftime('%Y%m%d%H%M%S')}",
            "source_candidate_id": candidate_id,
            "destination_workflow": payload.destination_workflow,
            "referral_reason": payload.referral_reason,
            "requested_by": user.user_id,
            "timestamp": now.isoformat(),
            "organization_id": user.organization_id,
            "notes": payload.notes,
        }

        cand.referral_refs.append(referral_record)
        cand.status = (
            SystemicCandidateStatus.REFERRED_FOR_RISK_REVIEW
            if "RISK" in payload.destination_workflow
            else SystemicCandidateStatus.ESCALATED
        )
        self.intel_repo.save_referral(referral_record)
        return self.intel_repo.save_systemic_candidate(cand)


# Global singleton
_global_systemic_service = SystemicRiskInsightService()


def get_systemic_risk_insight_service() -> SystemicRiskInsightService:
    """Dependency provider for systemic risk insight service."""
    return _global_systemic_service

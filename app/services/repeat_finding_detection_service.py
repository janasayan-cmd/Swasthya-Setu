"""Phase 71: Repeat-Finding Detection Service.

Coordinates:
- Deterministic multi-dimensional matching against historical audit findings
- Confidence tier classification (POSSIBLE_REPEAT, LIKELY_REPEAT, CONFIRMED_REPEAT)
- Human review and disposition workflow (confirm, reject, review)
- Strict preservation of underlying audit findings (no silent merges or edits)
"""

from datetime import datetime, timedelta, timezone
import re
from typing import List, Optional, Set

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
from app.schemas.audit_finding_response import AuditFindingRecord, AuditFindingStatus
from app.schemas.audit_repeat_finding import (
    CandidateReviewStatus,
    ConfirmRepeatFindingRequest,
    MatchingDimension,
    RejectRepeatFindingRequest,
    RepeatConfidence,
    RepeatFindingCandidateRecord,
    ReviewRepeatFindingRequest,
)
from app.schemas.user import AuthenticatedUserContext


class RepeatFindingDetectionService:
    """Service governing repeat finding identification and authorized human review."""

    def __init__(
        self,
        audit_repo: Optional[GovernanceAuditRepository] = None,
        intel_repo: Optional[GovernanceAuditIntelligenceRepository] = None,
    ) -> None:
        self.audit_repo = audit_repo or get_governance_audit_repository()
        self.intel_repo = intel_repo or get_governance_audit_intelligence_repository()

    @staticmethod
    def _extract_keywords(text: str) -> Set[str]:
        """Extract alphanumeric keywords, excluding short stop words."""
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        stop_words = {"this", "that", "with", "from", "have", "were", "been", "their", "there", "about", "which"}
        return {w for w in words if w not in stop_words}

    def detect_repeat_findings(
        self,
        user: AuthenticatedUserContext,
        audit_id: Optional[str] = None,
        lookback_days: int = 365,
    ) -> List[RepeatFindingCandidateRecord]:
        """Scan findings and detect potential repeat issues using deterministic matching."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot execute repeat finding detection.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=lookback_days)

        # 1. Fetch tenant audits
        all_audits = self.audit_repo.list_audits(organization_id=user.organization_id)
        audit_map = {a.audit_id: a for a in all_audits}

        # 2. Fetch tenant findings
        all_findings = self.audit_repo.list_findings_for_audit()
        tenant_findings = [
            f for f in all_findings
            if f.audit_id in audit_map and f.status != AuditFindingStatus.WITHDRAWN
        ]

        # Target findings to evaluate
        if audit_id:
            target_findings = [f for f in tenant_findings if f.audit_id == audit_id]
        else:
            target_findings = [f for f in tenant_findings if f.created_at >= cutoff]

        detected_candidates: List[RepeatFindingCandidateRecord] = []

        for target in target_findings:
            matched_historical_ids: List[str] = []
            matched_dimensions: Set[str] = set()
            max_confidence_score = 0.0
            rationale_notes: List[str] = []

            target_keywords = self._extract_keywords(f"{target.finding_statement} {target.observed_condition}")

            for candidate in tenant_findings:
                # Do not match against self or findings created after the target
                if candidate.finding_id == target.finding_id or candidate.created_at >= target.created_at:
                    continue

                score = 0.0
                dims: List[str] = []

                # Dimension 1: Same Finding Category
                if candidate.category == target.category:
                    score += 0.30
                    dims.append(MatchingDimension.CATEGORY.value)

                # Dimension 2: Same Criterion / Control Mapping
                if target.criterion_id and candidate.criterion_id and target.criterion_id == candidate.criterion_id:
                    score += 0.35
                    dims.append(MatchingDimension.CONTROL.value)

                # Dimension 3: Same Corrective Action Linkage
                if (
                    target.corrective_action_ref
                    and candidate.corrective_action_ref
                    and target.corrective_action_ref == candidate.corrective_action_ref
                ):
                    score += 0.25
                    dims.append(MatchingDimension.CORRECTIVE_ACTION_REF.value)

                # Dimension 4: Semantic Keyword Overlap
                cand_keywords = self._extract_keywords(f"{candidate.finding_statement} {candidate.observed_condition}")
                if target_keywords and cand_keywords:
                    overlap = len(target_keywords & cand_keywords) / max(len(target_keywords), len(cand_keywords))
                    if overlap >= 0.30:
                        score += 0.20
                        dims.append(MatchingDimension.SEMANTIC_SIMILARITY.value)

                if score >= 0.50:
                    matched_historical_ids.append(candidate.finding_id)
                    matched_dimensions.update(dims)
                    if score > max_confidence_score:
                        max_confidence_score = score
                    rationale_notes.append(
                        f"Matched historical finding {candidate.finding_id} on [{', '.join(dims)}] with score {score:.2f}."
                    )

            if matched_historical_ids:
                # Determine confidence tier
                if max_confidence_score >= 0.80:
                    conf = RepeatConfidence.LIKELY_REPEAT
                elif max_confidence_score >= 0.60:
                    conf = RepeatConfidence.POSSIBLE_REPEAT
                else:
                    conf = RepeatConfidence.REQUIRES_REVIEW

                parent_audit = audit_map.get(target.audit_id)
                record = RepeatFindingCandidateRecord(
                    current_finding_id=target.finding_id,
                    current_finding_statement=target.finding_statement,
                    current_audit_id=target.audit_id,
                    category=target.category.value,
                    severity=target.severity.value,
                    historical_finding_ids=matched_historical_ids,
                    matching_dimensions=list(matched_dimensions),
                    matching_rationale="; ".join(rationale_notes[:3]),
                    confidence=conf,
                    confidence_score=round(max_confidence_score, 2),
                    detection_timestamp=now,
                    detection_method="DETERMINISTIC_RULES_V1",
                    reporting_period="HISTORICAL_365D",
                    review_status=CandidateReviewStatus.PENDING_REVIEW,
                    organization_id=user.organization_id,
                    facility_id=parent_audit.facility_id if parent_audit else None,
                    created_at=now,
                )
                saved = self.intel_repo.save_repeat_candidate(record)
                detected_candidates.append(saved)

        return detected_candidates

    def get_candidate(
        self, user: AuthenticatedUserContext, candidate_id: str
    ) -> RepeatFindingCandidateRecord:
        """Retrieve repeat finding candidate ensuring tenant isolation."""
        cand = self.intel_repo.get_repeat_candidate(candidate_id)
        if not cand:
            raise AppException(
                code=ErrorCode.REPEAT_FINDING_CANDIDATE_NOT_FOUND,
                message=f"Repeat finding candidate {candidate_id} not found.",
                status_code=404,
            )
        if cand.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access repeat finding candidate across tenant boundaries.",
                status_code=403,
            )
        return cand

    def list_candidates(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        status: Optional[str] = None,
        confidence: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RepeatFindingCandidateRecord]:
        """List repeat finding candidates within tenant scope."""
        return self.intel_repo.list_repeat_candidates(
            organization_id=user.organization_id,
            facility_id=facility_id,
            status=status,
            confidence=confidence,
            limit=limit,
            offset=offset,
        )

    def review_candidate(
        self,
        user: AuthenticatedUserContext,
        candidate_id: str,
        payload: ReviewRepeatFindingRequest,
    ) -> RepeatFindingCandidateRecord:
        """Record human review disposition for a repeat finding candidate."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can review repeat finding candidates.",
                status_code=403,
            )

        cand = self.get_candidate(user, candidate_id)
        now = datetime.now(timezone.utc)
        cand.review_status = payload.review_status
        cand.reviewed_by = user.user_id
        cand.reviewed_at = now
        cand.review_rationale = payload.review_rationale

        if payload.review_status == CandidateReviewStatus.CONFIRMED:
            cand.confidence = RepeatConfidence.CONFIRMED_REPEAT
        elif payload.review_status == CandidateReviewStatus.REJECTED:
            cand.confidence = RepeatConfidence.NOT_A_REPEAT

        return self.intel_repo.save_repeat_candidate(cand)

    def confirm_candidate(
        self,
        user: AuthenticatedUserContext,
        candidate_id: str,
        payload: ConfirmRepeatFindingRequest,
    ) -> RepeatFindingCandidateRecord:
        """Formally confirm a repeat finding candidate."""
        return self.review_candidate(
            user,
            candidate_id,
            ReviewRepeatFindingRequest(
                review_status=CandidateReviewStatus.CONFIRMED,
                review_rationale=payload.review_rationale,
            ),
        )

    def reject_candidate(
        self,
        user: AuthenticatedUserContext,
        candidate_id: str,
        payload: RejectRepeatFindingRequest,
    ) -> RepeatFindingCandidateRecord:
        """Formally reject a repeat finding candidate."""
        return self.review_candidate(
            user,
            candidate_id,
            ReviewRepeatFindingRequest(
                review_status=CandidateReviewStatus.REJECTED,
                review_rationale=payload.rejection_rationale,
            ),
        )


# Global singleton
_global_repeat_service = RepeatFindingDetectionService()


def get_repeat_finding_detection_service() -> RepeatFindingDetectionService:
    """Dependency provider for repeat finding detection service."""
    return _global_repeat_service

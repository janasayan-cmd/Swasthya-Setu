"""Phase 83: Organizational Learning Gap Domain Service.

Identifies, validates, and resolves organizational resilience learning gaps,
enforcing human review validation before any referral to Phase 54 CAPA.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_knowledge_repository import (
    GovernanceResilienceKnowledgeRepository,
    get_governance_resilience_knowledge_repository,
)
from app.schemas.governance_resilience_knowledge_learning_gaps import (
    IdentifyLearningGapRequest,
    LearningGapSeverity,
    LearningGapStatus,
    LearningGapType,
    OrganizationalLearningGapRecord,
    ReferGapToCAPARequest,
    ResolveLearningGapRequest,
    ValidateLearningGapRequest,
)


class GovernanceResilienceKnowledgeGapService:
    """Service managing organizational learning gaps and Phase 54 CAPA referral governance."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    def identify_learning_gap(
        self,
        tenant_id: str,
        user_id: str,
        request: IdentifyLearningGapRequest,
    ) -> OrganizationalLearningGapRecord:
        gap_id = f"gap-{uuid.uuid4().hex[:10]}"
        gap = OrganizationalLearningGapRecord(
            gap_id=gap_id,
            tenant_id=tenant_id,
            gap_type=request.gap_type,
            severity=request.severity,
            title=request.title,
            description=request.description,
            affected_capabilities=request.affected_capabilities,
            affected_roles=request.affected_roles,
            affected_facilities=request.affected_facilities,
            source_exercise_id=request.source_exercise_id,
            source_disruption_id=request.source_disruption_id,
            identified_by=user_id,
            status=LearningGapStatus.IDENTIFIED,
        )
        return self.repository.save_learning_gap(gap)

    def get_learning_gap(self, tenant_id: str, gap_id: str) -> OrganizationalLearningGapRecord:
        gap = self.repository.get_learning_gap(gap_id, tenant_id)
        if not gap:
            raise AppException(
                code=ErrorCode.LEARNING_GAP_NOT_FOUND,
                message=f"Organizational learning gap '{gap_id}' not found.",
                status_code=404,
            )
        return gap

    def validate_learning_gap(
        self,
        tenant_id: str,
        gap_id: str,
        validator_id: str,
        request: ValidateLearningGapRequest,
    ) -> OrganizationalLearningGapRecord:
        gap = self.get_learning_gap(tenant_id, gap_id)

        # Separation of duties: Validator cannot be identifier
        if validator_id == gap.identified_by:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Identifier cannot independently validate their own organizational learning gap.",
                status_code=400,
            )

        if gap.status != LearningGapStatus.IDENTIFIED:
            raise AppException(
                code=ErrorCode.INVALID_LEARNING_GAP_STATE,
                message=f"Learning gap in state '{gap.status}' cannot be validated. Must be IDENTIFIED.",
                status_code=400,
            )

        if request.is_valid:
            gap.status = LearningGapStatus.VALIDATED
            gap.validated_by = validator_id
            gap.validated_at = datetime.utcnow()
        else:
            gap.status = LearningGapStatus.CLOSED
            gap.resolution_notes = f"Closed during validation: {request.validation_notes}"

        return self.repository.save_learning_gap(gap)

    def refer_to_capa(
        self,
        tenant_id: str,
        gap_id: str,
        user_id: str,
        request: ReferGapToCAPARequest,
    ) -> OrganizationalLearningGapRecord:
        gap = self.get_learning_gap(tenant_id, gap_id)

        # Human review validation required before referral to CAPA
        if gap.status != LearningGapStatus.VALIDATED:
            raise AppException(
                code=ErrorCode.INVALID_LEARNING_GAP_STATE,
                message=(
                    f"Learning gap must be VALIDATED prior to CAPA referral. Current state: '{gap.status}'. "
                    "Unvalidated gaps cannot trigger formal corrective action procedures."
                ),
                status_code=400,
            )

        # Create virtual referral link to Phase 54
        capa_ref_id = f"capa-ref-{uuid.uuid4().hex[:10]}"
        gap.status = LearningGapStatus.CAPA_REFERRED
        gap.capa_referral_id = capa_ref_id
        gap.resolution_notes = (
            f"Referred to Phase 54 CAPA: {request.capa_title} (Priority: {request.priority}). "
            f"Details: {request.capa_description}"
        )
        return self.repository.save_learning_gap(gap)

    def resolve_learning_gap(
        self,
        tenant_id: str,
        gap_id: str,
        user_id: str,
        request: ResolveLearningGapRequest,
    ) -> OrganizationalLearningGapRecord:
        gap = self.get_learning_gap(tenant_id, gap_id)

        if gap.status not in [LearningGapStatus.VALIDATED, LearningGapStatus.CAPA_REFERRED]:
            raise AppException(
                code=ErrorCode.INVALID_LEARNING_GAP_STATE,
                message=f"Learning gap in state '{gap.status}' cannot be marked resolved.",
                status_code=400,
            )

        gap.status = LearningGapStatus.RESOLVED
        gap.resolved_at = datetime.utcnow()
        gap.resolution_notes = request.resolution_notes
        return self.repository.save_learning_gap(gap)

    def list_learning_gaps(
        self,
        tenant_id: str,
        status: Optional[LearningGapStatus] = None,
        severity: Optional[LearningGapSeverity] = None,
        gap_type: Optional[LearningGapType] = None,
    ) -> List[OrganizationalLearningGapRecord]:
        return self.repository.list_learning_gaps(
            tenant_id=tenant_id,
            status=status,
            severity=severity,
            gap_type=gap_type,
        )


_gap_service = GovernanceResilienceKnowledgeGapService()


def get_governance_resilience_knowledge_gap_service() -> GovernanceResilienceKnowledgeGapService:
    return _gap_service

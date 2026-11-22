"""Phase 83: Knowledge Conflict Detection and Resolution Service.

Detects contradictory, overlapping, or obsolete resilience guidance and executes
controlled resolutions including superseding legacy guidance.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_knowledge_repository import (
    GovernanceResilienceKnowledgeRepository,
    get_governance_resilience_knowledge_repository,
)
from app.schemas.governance_resilience_knowledge import KnowledgeLifecycleState
from app.schemas.governance_resilience_knowledge_conflicts import (
    ConflictStatus,
    DetectKnowledgeConflictRequest,
    KnowledgeConflictRecord,
    KnowledgeConflictType,
    ResolveKnowledgeConflictRequest,
)


class GovernanceResilienceKnowledgeConflictService:
    """Service managing conflict identification, analysis, and formal resolution."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    def detect_conflict(
        self,
        tenant_id: str,
        user_id: str,
        request: DetectKnowledgeConflictRequest,
    ) -> KnowledgeConflictRecord:
        primary = self.repository.get_knowledge(request.primary_knowledge_id, tenant_id)
        if not primary:
            raise AppException(
                code=ErrorCode.RESILIENCE_KNOWLEDGE_NOT_FOUND,
                message=f"Primary knowledge record '{request.primary_knowledge_id}' not found.",
                status_code=404,
            )

        conflicting = self.repository.get_knowledge(request.conflicting_knowledge_id, tenant_id)
        if not conflicting:
            raise AppException(
                code=ErrorCode.RESILIENCE_KNOWLEDGE_NOT_FOUND,
                message=f"Conflicting knowledge record '{request.conflicting_knowledge_id}' not found.",
                status_code=404,
            )

        conflict_id = f"cnf-{uuid.uuid4().hex[:10]}"
        conflict = KnowledgeConflictRecord(
            conflict_id=conflict_id,
            tenant_id=tenant_id,
            conflict_type=request.conflict_type,
            description=request.description,
            primary_knowledge_id=request.primary_knowledge_id,
            conflicting_knowledge_id=request.conflicting_knowledge_id,
            detected_by=user_id,
            status=ConflictStatus.DETECTED,
        )
        return self.repository.save_conflict(conflict)

    def get_conflict(self, tenant_id: str, conflict_id: str) -> KnowledgeConflictRecord:
        conflict = self.repository.get_conflict(conflict_id, tenant_id)
        if not conflict:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_CONFLICT_NOT_FOUND,
                message=f"Knowledge conflict record '{conflict_id}' not found.",
                status_code=404,
            )
        return conflict

    def resolve_conflict(
        self,
        tenant_id: str,
        conflict_id: str,
        resolver_id: str,
        request: ResolveKnowledgeConflictRequest,
    ) -> KnowledgeConflictRecord:
        conflict = self.get_conflict(tenant_id, conflict_id)

        if conflict.status in [ConflictStatus.RESOLVED, ConflictStatus.DISMISSED]:
            raise AppException(
                code=ErrorCode.INVALID_KNOWLEDGE_CONFLICT_STATE,
                message=f"Conflict is already in terminal state '{conflict.status}'.",
                status_code=400,
            )

        conflict.status = ConflictStatus.RESOLVED
        conflict.resolution_strategy = request.resolution_strategy
        conflict.resolution_rationale = request.resolution_rationale
        conflict.resolved_by = resolver_id
        conflict.resolved_at = datetime.utcnow()

        # If requested, automatically mark conflicting knowledge record as superseded
        if request.supersede_conflicting:
            conflicting = self.repository.get_knowledge(conflict.conflicting_knowledge_id, tenant_id)
            if conflicting:
                conflicting.current_state = KnowledgeLifecycleState.SUPERSEDED
                conflicting.superseded_by_id = conflict.primary_knowledge_id
                conflicting.updated_at = datetime.utcnow()
                self.repository.save_knowledge(conflicting)

        return self.repository.save_conflict(conflict)

    def list_conflicts(
        self,
        tenant_id: str,
        status: Optional[ConflictStatus] = None,
        conflict_type: Optional[KnowledgeConflictType] = None,
    ) -> List[KnowledgeConflictRecord]:
        return self.repository.list_conflicts(tenant_id=tenant_id, status=status, conflict_type=conflict_type)


_conflict_service = GovernanceResilienceKnowledgeConflictService()


def get_governance_resilience_knowledge_conflict_service() -> GovernanceResilienceKnowledgeConflictService:
    return _conflict_service

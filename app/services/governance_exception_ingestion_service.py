"""Phase 67: Governance Exception Ingestion and Deduplication Service.

Provides governed ingestion of cross-workflow safety findings and exceptions,
enforcing source provenance, tenant isolation, and idempotent event deduplication.
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_escalation_repository import (
    GovernanceEscalationRepository,
    get_governance_escalation_repository,
)
from app.schemas.governance_exception import (
    ExceptionLifecycleState,
    GovernanceExceptionRecord,
    GovernancePriority,
    IngestGovernanceExceptionRequest,
)
from app.schemas.user import AuthenticatedUserContext


class GovernanceExceptionIngestionService:
    """Service handling ingestion, validation, and deduplication of governance exceptions."""

    def __init__(
        self,
        repository: Optional[GovernanceEscalationRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_escalation_repository()

    def ingest_exception(
        self,
        user: AuthenticatedUserContext,
        payload: IngestGovernanceExceptionRequest,
    ) -> GovernanceExceptionRecord:
        """Ingest a new governance exception with idempotent deduplication."""
        # 1. Deduplication check: check if identical source event & version was already ingested
        existing = self.repository.find_existing_exception(
            source_phase=payload.source_phase.value,
            source_record_id=payload.source_record_id,
            source_version=payload.source_version or "v1.0.0",
        )
        if existing:
            # Idempotently return existing record if already recorded for this tenant
            if existing.organization_id == user.organization_id:
                return existing
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot ingest exception across tenant boundaries.",
                status_code=403,
            )

        # 2. Build normalized exception record
        now = datetime.now(timezone.utc)
        record = GovernanceExceptionRecord(
            escalation_id=payload.escalation_id,
            category=payload.category,
            source_phase=payload.source_phase,
            source_record_id=payload.source_record_id,
            source_version=payload.source_version or "v1.0.0",
            organization_id=user.organization_id,
            facility_id=user.facility_id or "fac-default",
            patient_id=payload.patient_id,
            source_severity=payload.source_severity or "MEDIUM",
            governance_priority=GovernancePriority.UNCLASSIFIED,
            lifecycle_state=ExceptionLifecycleState.ACTIVE,
            title=payload.title,
            description=payload.description,
            is_material=payload.is_material,
            materiality_rationale=payload.materiality_rationale,
            policy_reference=payload.policy_reference or "gov-policy-v1",
            policy_version=payload.policy_version or "v1.0.0",
            related_workflow_ids=payload.related_workflow_ids or [],
            dependency_refs=payload.dependency_refs or [],
            evidence_refs=payload.evidence_refs or [],
            created_by=user.user_id,
            created_at=now,
            updated_at=now,
            metadata=payload.metadata or {},
        )

        # 3. Save exception
        self.repository.save_exception(record)

        # 4. If linked to an existing escalation, append to its exception list
        if payload.escalation_id:
            escalation = self.repository.get_escalation(payload.escalation_id)
            if escalation and escalation.organization_id == user.organization_id:
                if record.exception_id not in escalation.aggregated_exception_ids:
                    escalation.aggregated_exception_ids.append(record.exception_id)
                    self.repository.save_escalation(escalation)

        return record


# Global singleton
_global_ingestion_service = GovernanceExceptionIngestionService()


def get_governance_exception_ingestion_service() -> GovernanceExceptionIngestionService:
    """Dependency provider for exception ingestion service."""
    return _global_ingestion_service

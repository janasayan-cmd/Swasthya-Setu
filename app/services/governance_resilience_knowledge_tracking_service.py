"""Phase 83: Knowledge Tracking and Application Evidence Service.

Tracks user delivery, views, and formal acknowledgements of distributed resilience guidance,
and records verified evidence of practical utilization in operational continuity exercises.
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
from app.schemas.governance_resilience_knowledge_tracking import (
    AcknowledgementStatus,
    ApplicationEvidenceStatus,
    KnowledgeAcknowledgementRecord,
    KnowledgeApplicationEvidenceRecord,
    RecordAcknowledgementRequest,
    SubmitApplicationEvidenceRequest,
    VerifyApplicationEvidenceRequest,
)


class GovernanceResilienceKnowledgeTrackingService:
    """Service managing acknowledgements and practical application evidence."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceKnowledgeRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_knowledge_repository()

    # -------------------------------------------------------------------------
    # Acknowledgements
    # -------------------------------------------------------------------------

    def get_acknowledgement(self, tenant_id: str, acknowledgement_id: str) -> KnowledgeAcknowledgementRecord:
        ack = self.repository.get_acknowledgement(acknowledgement_id, tenant_id)
        if not ack:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_ACKNOWLEDGEMENT_NOT_FOUND,
                message=f"Acknowledgement record '{acknowledgement_id}' not found.",
                status_code=404,
            )
        return ack

    def record_acknowledgement(
        self,
        tenant_id: str,
        acknowledgement_id: str,
        user_id: str,
        request: RecordAcknowledgementRequest,
    ) -> KnowledgeAcknowledgementRecord:
        ack = self.get_acknowledgement(tenant_id, acknowledgement_id)

        if request.status == AcknowledgementStatus.VIEWED:
            ack.status = AcknowledgementStatus.VIEWED
            ack.viewed_at = datetime.utcnow()
        elif request.status == AcknowledgementStatus.ACKNOWLEDGED:
            ack.status = AcknowledgementStatus.ACKNOWLEDGED
            ack.acknowledged_at = datetime.utcnow()
            ack.acknowledgement_notes = request.acknowledgement_notes
        else:
            raise AppException(
                code=ErrorCode.INVALID_KNOWLEDGE_ACKNOWLEDGEMENT_STATE,
                message=f"Invalid acknowledgement target status '{request.status}'.",
                status_code=400,
            )

        return self.repository.save_acknowledgement(ack)

    def list_acknowledgements(
        self,
        tenant_id: str,
        campaign_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[AcknowledgementStatus] = None,
    ) -> List[KnowledgeAcknowledgementRecord]:
        return self.repository.list_acknowledgements(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            user_id=user_id,
            status=status,
        )

    # -------------------------------------------------------------------------
    # Application Evidence
    # -------------------------------------------------------------------------

    def submit_application_evidence(
        self,
        tenant_id: str,
        user_id: str,
        request: SubmitApplicationEvidenceRequest,
    ) -> KnowledgeApplicationEvidenceRecord:
        knowledge = self.repository.get_knowledge(request.knowledge_id, tenant_id)
        if not knowledge:
            raise AppException(
                code=ErrorCode.RESILIENCE_KNOWLEDGE_NOT_FOUND,
                message=f"Knowledge record '{request.knowledge_id}' not found.",
                status_code=404,
            )

        evidence_id = f"evd-{uuid.uuid4().hex[:10]}"
        evidence = KnowledgeApplicationEvidenceRecord(
            evidence_id=evidence_id,
            tenant_id=tenant_id,
            knowledge_id=request.knowledge_id,
            operational_context=request.operational_context,
            operational_reference_id=request.operational_reference_id,
            description=request.description,
            observed_effectiveness_rating=request.observed_effectiveness_rating,
            phase55_assessment_id=request.phase55_assessment_id,
            submitted_by=user_id,
            status=ApplicationEvidenceStatus.RECORDED,
        )
        return self.repository.save_evidence(evidence)

    def get_evidence(self, tenant_id: str, evidence_id: str) -> KnowledgeApplicationEvidenceRecord:
        evidence = self.repository.get_evidence(evidence_id, tenant_id)
        if not evidence:
            raise AppException(
                code=ErrorCode.APPLICATION_EVIDENCE_NOT_FOUND,
                message=f"Application evidence record '{evidence_id}' not found.",
                status_code=404,
            )
        return evidence

    def verify_application_evidence(
        self,
        tenant_id: str,
        evidence_id: str,
        verifier_id: str,
        request: VerifyApplicationEvidenceRequest,
    ) -> KnowledgeApplicationEvidenceRecord:
        evidence = self.get_evidence(tenant_id, evidence_id)

        # Separation of duties: Verifier cannot be submitter
        if verifier_id == evidence.submitted_by:
            raise AppException(
                code=ErrorCode.KNOWLEDGE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Submitter cannot independently verify their own application evidence.",
                status_code=400,
            )

        if evidence.status != ApplicationEvidenceStatus.RECORDED:
            raise AppException(
                code=ErrorCode.INVALID_APPLICATION_EVIDENCE_STATE,
                message=f"Evidence in status '{evidence.status}' cannot be verified.",
                status_code=400,
            )

        if request.verified:
            evidence.status = ApplicationEvidenceStatus.VERIFIED
            evidence.verified_by = verifier_id
            evidence.verified_at = datetime.utcnow()
        else:
            evidence.status = ApplicationEvidenceStatus.REJECTED
            evidence.rejection_notes = request.notes

        return self.repository.save_evidence(evidence)

    def list_evidence(
        self,
        tenant_id: str,
        knowledge_id: Optional[str] = None,
        status: Optional[ApplicationEvidenceStatus] = None,
    ) -> List[KnowledgeApplicationEvidenceRecord]:
        return self.repository.list_evidence(
            tenant_id=tenant_id,
            knowledge_id=knowledge_id,
            status=status,
        )


_tracking_service = GovernanceResilienceKnowledgeTrackingService()


def get_governance_resilience_knowledge_tracking_service() -> GovernanceResilienceKnowledgeTrackingService:
    return _tracking_service

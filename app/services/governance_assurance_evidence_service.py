"""Phase 77: Governance Assurance Evidence Service.

Handles intake, lineage tracking, positive verification, rejection, and freshness checks
for governance assurance evidence across HealthSetu phases.
"""

from datetime import datetime, timezone, timedelta
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_assurance_evidence import (
    EvidenceVerificationStatus,
    GovernanceAssuranceEvidenceRecord,
    RejectAssuranceEvidenceRequest,
    SubmitAssuranceEvidenceRequest,
    VerifyAssuranceEvidenceRequest,
)
from app.schemas.governance_maturity_assessment import AssessmentStatus
from app.schemas.governance_maturity_framework import CLINICAL_SAFETY_DISCLAIMER


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceAssuranceEvidenceService:
    """Manages evidence collection, freshness, and verification for assessments."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def submit_evidence(
        self,
        tenant_id: str,
        assessment_id: str,
        collected_by: str,
        request: SubmitAssuranceEvidenceRequest,
    ) -> GovernanceAssuranceEvidenceRecord:
        assessment = self.repository.get_assessment(assessment_id)
        if not assessment or assessment.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.MATURITY_ASSESSMENT_NOT_FOUND,
                message=f"Assessment '{assessment_id}' was not found.",
                status_code=404,
            )

        if assessment.status in (AssessmentStatus.ARCHIVED, AssessmentStatus.SUPERSEDED):
            raise AppException(
                code=ErrorCode.INVALID_MATURITY_ASSESSMENT_STATE,
                message=f"Cannot submit evidence to assessment in status '{assessment.status.value}'.",
                status_code=400,
            )

        now = _get_utc_now_str()
        freshness_ts = request.freshness_timestamp or now

        # Determine staleness: older than 180 days is flagged as stale
        is_stale = False
        try:
            parsed_freshness = datetime.fromisoformat(freshness_ts.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - parsed_freshness > timedelta(days=180):
                is_stale = True
        except Exception:
            pass

        evidence = GovernanceAssuranceEvidenceRecord(
            evidence_id=f"ev-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            dimension=request.dimension,
            criterion_id=request.criterion_id,
            source_workflow=request.source_workflow,
            source_record_id=request.source_record_id,
            title=request.title,
            description=request.description,
            artifact_uri=request.artifact_uri,
            verification_status=EvidenceVerificationStatus.PENDING_VERIFICATION,
            verified_by=None,
            verified_at=None,
            verification_notes=None,
            collected_by=collected_by,
            collected_at=now,
            freshness_timestamp=freshness_ts,
            is_stale=is_stale,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
        )
        return self.repository.save_evidence(evidence)

    def verify_evidence(
        self,
        tenant_id: str,
        evidence_id: str,
        verifier_id: str,
        request: VerifyAssuranceEvidenceRequest,
    ) -> GovernanceAssuranceEvidenceRecord:
        evidence = self.repository.get_evidence(evidence_id)
        if not evidence or evidence.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_EVIDENCE_NOT_FOUND,
                message=f"Evidence '{evidence_id}' was not found.",
                status_code=404,
            )

        if evidence.verification_status == EvidenceVerificationStatus.VERIFIED:
            return evidence

        now = _get_utc_now_str()
        evidence = evidence.model_copy(
            update={
                "verification_status": EvidenceVerificationStatus.VERIFIED,
                "verified_by": verifier_id,
                "verified_at": now,
                "verification_notes": request.verification_notes or "Evidence verified.",
            }
        )
        return self.repository.save_evidence(evidence)

    def reject_evidence(
        self,
        tenant_id: str,
        evidence_id: str,
        verifier_id: str,
        request: RejectAssuranceEvidenceRequest,
    ) -> GovernanceAssuranceEvidenceRecord:
        evidence = self.repository.get_evidence(evidence_id)
        if not evidence or evidence.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_EVIDENCE_NOT_FOUND,
                message=f"Evidence '{evidence_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        evidence = evidence.model_copy(
            update={
                "verification_status": EvidenceVerificationStatus.REJECTED,
                "verified_by": verifier_id,
                "verified_at": now,
                "verification_notes": request.rejection_reason,
            }
        )
        return self.repository.save_evidence(evidence)

    def get_evidence(
        self,
        tenant_id: str,
        evidence_id: str,
    ) -> GovernanceAssuranceEvidenceRecord:
        evidence = self.repository.get_evidence(evidence_id)
        if not evidence or evidence.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.ASSURANCE_EVIDENCE_NOT_FOUND,
                message=f"Evidence '{evidence_id}' was not found.",
                status_code=404,
            )
        return evidence

    def list_evidence_for_assessment(
        self,
        tenant_id: str,
        assessment_id: str,
        dimension: Optional[str] = None,
        criterion_id: Optional[str] = None,
    ) -> List[GovernanceAssuranceEvidenceRecord]:
        return self.repository.list_evidence_for_assessment(
            tenant_id=tenant_id,
            assessment_id=assessment_id,
            dimension=dimension,
            criterion_id=criterion_id,
        )

"""Phase 84: Capability Gap Identification and Validation Service.

Detects capability gaps, enforces human review validation, and routes referrals
to Phase 54 CAPA, Phase 63 Risk, or Phase 83 Capability Development.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_capability_gap import (
    CapabilityGapCategory,
    CapabilityGapRecord,
    CapabilityGapSeverity,
    CapabilityGapStatus,
    DetectCapabilityGapRequest,
    DispositionCapabilityGapRequest,
    ValidateCapabilityGapRequest,
)


class GovernanceResilienceCapabilityGapService:
    """Service managing evidence-based capability gaps and authorized human validation."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def detect_gap(
        self,
        tenant_id: str,
        user_id: str,
        request: DetectCapabilityGapRequest,
    ) -> CapabilityGapRecord:
        gap_id = f"cgp-{uuid.uuid4().hex[:10]}"
        record = CapabilityGapRecord(
            gap_id=gap_id,
            tenant_id=tenant_id,
            category=request.category,
            severity=request.severity,
            title=request.title,
            description=request.description,
            affected_capability_id=request.affected_capability_id,
            affected_role=request.affected_role,
            affected_team_id=request.affected_team_id,
            evidence_references=request.evidence_references,
            status=CapabilityGapStatus.DETECTED,
            identified_by=user_id,
        )
        return self.repository.save_capability_gap(record)

    def get_gap(self, tenant_id: str, gap_id: str) -> CapabilityGapRecord:
        record = self.repository.get_capability_gap(gap_id, tenant_id)
        if not record:
            raise AppException(
                code=ErrorCode.CAPABILITY_GAP_NOT_FOUND,
                message=f"Capability gap record '{gap_id}' not found.",
                status_code=404,
            )
        return record

    def validate_gap(
        self,
        tenant_id: str,
        gap_id: str,
        validator_id: str,
        request: ValidateCapabilityGapRequest,
    ) -> CapabilityGapRecord:
        record = self.get_gap(tenant_id, gap_id)

        # Separation of duties: Validator cannot be identifier
        if validator_id == record.identified_by:
            raise AppException(
                code=ErrorCode.CAPABILITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Identifier cannot independently validate their own detected capability gap.",
                status_code=400,
            )

        if record.status != CapabilityGapStatus.DETECTED:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_GAP_STATE,
                message=f"Gap in status '{record.status}' cannot be validated. Must be DETECTED.",
                status_code=400,
            )

        if request.is_valid:
            record.status = CapabilityGapStatus.VALIDATED
            record.validated_by = validator_id
            record.validated_at = datetime.utcnow()
        else:
            record.status = CapabilityGapStatus.CLOSED
            record.resolution_notes = f"Closed during validation: {request.validation_notes}"

        return self.repository.save_capability_gap(record)

    def disposition_gap(
        self,
        tenant_id: str,
        gap_id: str,
        user_id: str,
        request: DispositionCapabilityGapRequest,
    ) -> CapabilityGapRecord:
        record = self.get_gap(tenant_id, gap_id)

        # Human validation prerequisite before disposition
        if record.status != CapabilityGapStatus.VALIDATED:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_GAP_STATE,
                message=f"Capability gap must be VALIDATED prior to disposition. Current: '{record.status}'.",
                status_code=400,
            )

        disp_type = request.disposition_type.upper()
        if disp_type == "CAPA_REFERRAL":
            record.status = CapabilityGapStatus.CAPA_REFERRED
            record.capa_referral_id = f"capa-p84-{uuid.uuid4().hex[:8]}"
            record.resolution_notes = f"Referred to Phase 54 CAPA: {request.notes}"
        elif disp_type == "RISK_REFERRAL":
            record.risk_referral_id = f"risk-p84-{uuid.uuid4().hex[:8]}"
            record.resolution_notes = f"Referred to Phase 63 Risk Registry: {request.notes}"
        elif disp_type == "REMEDIATION_PLAN":
            record.status = CapabilityGapStatus.REMEDIATION_PLANNED
            record.resolution_notes = f"Remediation planned: {request.notes}"
        elif disp_type == "CLOSE":
            record.status = CapabilityGapStatus.CLOSED
            record.resolution_notes = f"Closed: {request.notes}"
        else:
            raise AppException(
                code=ErrorCode.INVALID_CAPABILITY_GAP_STATE,
                message=f"Invalid disposition type '{request.disposition_type}'.",
                status_code=400,
            )

        return self.repository.save_capability_gap(record)

    def list_gaps(
        self,
        tenant_id: str,
        category: Optional[CapabilityGapCategory] = None,
        severity: Optional[CapabilityGapSeverity] = None,
        status: Optional[CapabilityGapStatus] = None,
    ) -> List[CapabilityGapRecord]:
        return self.repository.list_capability_gaps(
            tenant_id=tenant_id,
            category=category,
            severity=severity,
            status=status,
        )


_gap_service = GovernanceResilienceCapabilityGapService()


def get_governance_resilience_capability_gap_service() -> GovernanceResilienceCapabilityGapService:
    return _gap_service

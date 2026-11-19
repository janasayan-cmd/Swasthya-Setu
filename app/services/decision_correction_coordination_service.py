"""Phase 68: Decision Correction and Revocation Review Coordination Service.

Coordinates correction and revocation review requests directed to authoritative
workflow owners without independently mutating or revoking authoritative records.

Mandatory Invariants:
1. A correction recommendation is not a correction.
2. A revocation review request is not a revocation.
3. Phase 68 must never independently erase or rewrite a decision.
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_assurance_repository import (
    GovernanceDecisionAssuranceRepository,
    get_governance_decision_assurance_repository,
)
from app.schemas.auth import UserRole
from app.schemas.decision_correction_coordination import (
    CorrectionRequestRecord,
    CorrectionRequestStatus,
    RespondCorrectionRequest,
    SubmitDecisionCorrectionRequest,
    SubmitRevocationReviewRequest,
)
from app.schemas.user import AuthenticatedUserContext


class DecisionCorrectionCoordinationService:
    """Service managing governed correction and revocation review requests."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_decision_assurance_repository()

    def submit_correction_request(
        self,
        user: AuthenticatedUserContext,
        decision_id: str,
        payload: SubmitDecisionCorrectionRequest,
    ) -> CorrectionRequestRecord:
        """Submit a formal decision correction request to the authoritative owner."""
        decision = self._get_and_check_tenant(decision_id, user)

        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.DECISION_CORRECTION_UNAUTHORIZED,
                message="Patient role is not authorized to request decision corrections.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = CorrectionRequestRecord(
            decision_id=decision_id,
            target_phase=decision.source_phase,
            target_record_id=decision.source_record_id,
            request_type="CORRECTION",
            status=CorrectionRequestStatus.SUBMITTED,
            reason=payload.reason,
            finding_refs=payload.finding_refs or [],
            requested_by=user.user_id,
            requested_at=now,
            created_at=now,
            updated_at=now,
            metadata={"suggested_correction": payload.suggested_correction},
        )

        self.repository.save_correction_request(record)
        return record

    def submit_revocation_review_request(
        self,
        user: AuthenticatedUserContext,
        decision_id: str,
        payload: SubmitRevocationReviewRequest,
    ) -> CorrectionRequestRecord:
        """Submit a revocation review request to the authoritative decision owner."""
        decision = self._get_and_check_tenant(decision_id, user)

        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.REVOCATION_REVIEW_UNAUTHORIZED,
                message="Patient role is not authorized to request decision revocation review.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record = CorrectionRequestRecord(
            decision_id=decision_id,
            target_phase=decision.source_phase,
            target_record_id=decision.source_record_id,
            request_type="REVOCATION_REVIEW",
            status=CorrectionRequestStatus.SUBMITTED,
            reason=payload.reason,
            finding_refs=payload.finding_refs or [],
            requested_by=user.user_id,
            requested_at=now,
            created_at=now,
            updated_at=now,
            metadata={"revocation_grounds": payload.revocation_grounds},
        )

        self.repository.save_correction_request(record)
        return record

    def respond_to_request(
        self,
        user: AuthenticatedUserContext,
        request_id: str,
        payload: RespondCorrectionRequest,
    ) -> CorrectionRequestRecord:
        """Authoritative owner responds to a correction or revocation review request."""
        record = self.repository.get_correction_request(request_id)
        if not record:
            raise AppException(
                code=ErrorCode.CORRECTION_REQUEST_NOT_FOUND,
                message=f"Correction request {request_id} not found.",
                status_code=404,
            )

        # Check tenant via decision
        self._get_and_check_tenant(record.decision_id, user)

        # Only clinical admin or doctor can respond
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Role not authorized to respond to decision correction requests.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        record.status = payload.status
        record.response_notes = payload.response_notes
        record.responded_by = user.user_id
        record.responded_at = now
        record.authoritative_action_taken = payload.authoritative_action_taken
        record.updated_record_version = payload.updated_record_version

        self.repository.save_correction_request(record)
        return record

    def _get_and_check_tenant(self, decision_id: str, user: AuthenticatedUserContext):
        decision = self.repository.get_decision_register(decision_id)
        if not decision:
            raise AppException(
                code=ErrorCode.DECISION_REGISTER_NOT_FOUND,
                message=f"Governance decision {decision_id} not found.",
                status_code=404,
            )
        if decision.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access decision across tenant boundaries.",
                status_code=403,
            )
        return decision


# Global singleton
_global_correction_service = DecisionCorrectionCoordinationService()


def get_decision_correction_coordination_service() -> DecisionCorrectionCoordinationService:
    """Dependency provider for correction coordination service."""
    return _global_correction_service

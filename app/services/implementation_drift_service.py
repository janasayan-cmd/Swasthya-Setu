"""Phase 74: Implementation Drift Monitoring Service.

Coordinates:
- Implementation drift signal logging against approved baselines
- Distinction between unconfirmed signals and confirmed deviations
- Human review and formal disposition workflow
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_adoption_repository import (
    GovernanceChangeAdoptionRepository,
    get_governance_change_adoption_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.drift_sustainability_consequences import (
    DisposeDriftSignalRequest,
    DriftDisposition,
    DriftSignalClassification,
    DriftSignalStatus,
    ImplementationDriftSignalRecord,
    LogDriftSignalRequest,
    ReviewDriftSignalRequest,
)


class ImplementationDriftService:
    """Service governing implementation drift detection, review, and disposition."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def log_drift_signal(
        self,
        registration_id: str,
        request: LogDriftSignalRequest,
        current_user: AuthenticatedUserContext,
    ) -> ImplementationDriftSignalRecord:
        """Logs an observed implementation drift signal against the approved baseline."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        signal_id = f"dfs_{uuid.uuid4().hex[:12]}"

        record = ImplementationDriftSignalRecord(
            signal_id=signal_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            baseline_version=request.baseline_version,
            title=request.title,
            description=request.description,
            classification=request.classification,
            source_type=request.source_type,
            observed_at=request.observed_at,
            evidence_reference=request.evidence_reference,
            operational_scope=request.operational_scope,
            status=DriftSignalStatus.OPEN,
            reviewed_by=None,
            reviewed_at=None,
            review_notes=None,
            disposition=None,
            disposed_by=None,
            disposed_at=None,
            disposition_notes=None,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_drift_signal(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.drift_detected",
            actor_id=current_user.user_id,
            summary=f"Drift signal '{saved.title}' logged (Classification: {saved.classification.value}).",
            details={"signal_id": saved.signal_id, "baseline_version": saved.baseline_version},
        )
        return saved

    def get_drift_signal(
        self, signal_id: str, current_user: AuthenticatedUserContext
    ) -> ImplementationDriftSignalRecord:
        """Retrieves a drift signal by ID with tenant isolation."""
        signal = self.repo.get_drift_signal(signal_id)
        if not signal or signal.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.IMPLEMENTATION_DRIFT_SIGNAL_NOT_FOUND,
                message=f"Implementation drift signal '{signal_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return signal

    def list_drift_signals_for_registration(
        self,
        registration_id: str,
        current_user: AuthenticatedUserContext,
        status_filter: Optional[DriftSignalStatus] = None,
    ) -> List[ImplementationDriftSignalRecord]:
        """Lists drift signals for an adoption initiative."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_drift_signals_for_registration(
            registration_id, current_user.tenant_id, status_filter
        )

    def review_drift_signal(
        self,
        signal_id: str,
        request: ReviewDriftSignalRequest,
        current_user: AuthenticatedUserContext,
    ) -> ImplementationDriftSignalRecord:
        """Records human review of a drift signal."""
        signal = self.get_drift_signal(signal_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = signal.model_dump()
        updated_dict["status"] = DriftSignalStatus.UNDER_REVIEW
        updated_dict["reviewed_by"] = current_user.user_id
        updated_dict["reviewed_at"] = now
        updated_dict["review_notes"] = request.review_notes
        updated_dict["updated_at"] = now

        saved = self.repo.save_drift_signal(ImplementationDriftSignalRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=signal.registration_id,
            event_type="governance_change_adoption.drift_reviewed",
            actor_id=current_user.user_id,
            summary=f"Drift signal '{saved.title}' reviewed by {current_user.user_id}.",
            details={"review_notes": request.review_notes},
        )
        return saved

    def dispose_drift_signal(
        self,
        signal_id: str,
        request: DisposeDriftSignalRequest,
        current_user: AuthenticatedUserContext,
    ) -> ImplementationDriftSignalRecord:
        """Records formal disposition of a reviewed drift signal."""
        signal = self.get_drift_signal(signal_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = signal.model_dump()
        updated_dict["status"] = DriftSignalStatus.DISPOSED
        updated_dict["disposition"] = request.disposition
        updated_dict["disposed_by"] = current_user.user_id
        updated_dict["disposed_at"] = now
        updated_dict["disposition_notes"] = request.disposition_notes
        updated_dict["updated_at"] = now

        saved = self.repo.save_drift_signal(ImplementationDriftSignalRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=signal.registration_id,
            event_type="governance_change_adoption.drift_disposed",
            actor_id=current_user.user_id,
            summary=f"Drift signal '{saved.title}' disposed as {saved.disposition.value}.",
            details={"disposition": saved.disposition.value, "notes": request.disposition_notes},
        )
        return saved

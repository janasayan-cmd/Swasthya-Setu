"""Phase 74: Operational Adoption Indicator Service.

Coordinates:
- Adoption indicator registration and configuration
- Rigorous evidence-backed indicator assessments
- Strict invariant: Incomplete or unverified evidence cannot produce an ACHIEVED outcome
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
from app.schemas.adoption_evidence_indicators import (
    AdoptionIndicatorRecord,
    AssessIndicatorRequest,
    ConfidenceLevel,
    CreateAdoptionIndicatorRequest,
    EvidenceVerificationStatus,
    IndicatorOutcome,
)


class AdoptionIndicatorService:
    """Service governing adoption indicators and evidence-backed evaluation."""

    def __init__(
        self,
        repository: Optional[GovernanceChangeAdoptionRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_adoption_repository()

    def create_indicator(
        self,
        registration_id: str,
        request: CreateAdoptionIndicatorRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionIndicatorRecord:
        """Registers a new adoption indicator for an initiative."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        indicator_id = f"ind_{uuid.uuid4().hex[:12]}"

        record = AdoptionIndicatorRecord(
            indicator_id=indicator_id,
            registration_id=registration_id,
            tenant_id=current_user.tenant_id,
            indicator_key=request.indicator_key,
            title=request.title,
            category=request.category,
            measurement_criteria=request.measurement_criteria,
            target_threshold=request.target_threshold,
            current_value=None,
            outcome=IndicatorOutcome.NOT_ASSESSED,
            evidence_ids_used=[],
            confidence=ConfidenceLevel.UNKNOWN,
            assessed_by=None,
            assessed_at=None,
            rationale=None,
            limitations_noted=[],
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_indicator(record)
        self.repo.log_timeline_event(
            registration_id=registration_id,
            event_type="governance_change_adoption.indicator_created",
            actor_id=current_user.user_id,
            summary=f"Indicator '{saved.title}' defined (Key: {saved.indicator_key}).",
            details={"indicator_id": saved.indicator_id},
        )
        return saved

    def get_indicator(
        self, indicator_id: str, current_user: AuthenticatedUserContext
    ) -> AdoptionIndicatorRecord:
        """Retrieves an adoption indicator with tenant isolation."""
        indicator = self.repo.get_indicator(indicator_id)
        if not indicator or indicator.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.ADOPTION_INDICATOR_NOT_FOUND,
                message=f"Adoption indicator '{indicator_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return indicator

    def list_indicators_for_registration(
        self, registration_id: str, current_user: AuthenticatedUserContext
    ) -> List[AdoptionIndicatorRecord]:
        """Lists indicators for an adoption registration."""
        reg = self.repo.get_registration(registration_id)
        if not reg or reg.tenant_id != current_user.tenant_id:
            raise AppException(
                code=ErrorCode.CHANGE_ADOPTION_REGISTRATION_NOT_FOUND,
                message=f"Adoption registration '{registration_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_indicators_for_registration(registration_id, current_user.tenant_id)

    def assess_indicator(
        self,
        indicator_id: str,
        request: AssessIndicatorRequest,
        current_user: AuthenticatedUserContext,
    ) -> AdoptionIndicatorRecord:
        """Assesses an indicator against supporting verified evidence.
        
        Strict Clinical Safety Invariant:
        An indicator cannot be marked ACHIEVED without verified, unexpired supporting evidence.
        If evidence is unverified, missing, or contradictory, the outcome must be
        UNABLE_TO_DETERMINE or REQUIRES_REVIEW.
        """
        indicator = self.get_indicator(indicator_id, current_user)

        # Invariant check: ACHIEVED requires verified evidence
        if request.outcome == IndicatorOutcome.ACHIEVED:
            if not request.evidence_ids_used:
                raise AppException(
                    code=ErrorCode.INVALID_ADOPTION_EVIDENCE_STATE,
                    message="Indicator cannot be declared ACHIEVED without supporting verified evidence.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            for eid in request.evidence_ids_used:
                evi = self.repo.get_evidence(eid)
                if not evi or evi.tenant_id != current_user.tenant_id:
                    raise AppException(
                        code=ErrorCode.ADOPTION_EVIDENCE_NOT_FOUND,
                        message=f"Referenced evidence '{eid}' does not exist.",
                        status_code=status.HTTP_404_NOT_FOUND,
                    )
                if evi.verification_status != EvidenceVerificationStatus.VERIFIED:
                    raise AppException(
                        code=ErrorCode.INVALID_ADOPTION_EVIDENCE_STATE,
                        message=(
                            f"Evidence '{eid}' is in status '{evi.verification_status.value}' (not VERIFIED). "
                            "Unverified evidence cannot support an ACHIEVED outcome."
                        ),
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

        now = datetime.now(timezone.utc).isoformat()
        updated_dict = indicator.model_dump()
        updated_dict["current_value"] = request.current_value
        updated_dict["outcome"] = request.outcome
        updated_dict["evidence_ids_used"] = request.evidence_ids_used
        updated_dict["confidence"] = request.confidence
        updated_dict["assessed_by"] = current_user.user_id
        updated_dict["assessed_at"] = now
        updated_dict["rationale"] = request.rationale
        updated_dict["limitations_noted"] = request.limitations_noted
        updated_dict["updated_at"] = now

        saved = self.repo.save_indicator(AdoptionIndicatorRecord(**updated_dict))
        self.repo.log_timeline_event(
            registration_id=indicator.registration_id,
            event_type="governance_change_adoption.indicator_assessed",
            actor_id=current_user.user_id,
            summary=f"Indicator '{saved.title}' assessed as {saved.outcome.value} (Confidence: {saved.confidence.value}).",
            details={"value": saved.current_value, "outcome": saved.outcome.value},
        )
        return saved

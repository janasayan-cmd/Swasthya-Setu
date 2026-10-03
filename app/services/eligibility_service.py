"""Insurance Eligibility Verification Service (Phase 33).

Orchestrates point-in-time eligibility checks through configured PayerProvider.
CRITICAL SAFETY INVARIANTS:
- ELIGIBILITY IS POINT-IN-TIME ONLY.
- ACTIVE COVERAGE TODAY DOES NOT GUARANTEE FUTURE COVERAGE OR CLAIM PAYMENT.
- PROVIDER FAILURE MUST NEVER RETURN ELIGIBLE.
- UNKNOWN ≠ ELIGIBLE; UNKNOWN ≠ INELIGIBLE.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    EligibilityCheckFailedException,
    EligibilityCheckNotFoundException,
    EligibilityDisabledException,
    EligibilityProviderTimeoutException,
    EligibilityUnknownException,
    InsuranceNotFoundException,
)
from app.integrations.payers.base import PayerProvider
from app.integrations.payers.providers.mock import MockPayerProvider
from app.repositories.eligibility_repository import EligibilityRepository
from app.repositories.insurance_repository import InsuranceRepository
from app.schemas.eligibility import (
    EligibilityCheckRecord,
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    EligibilityStatus,
)
from app.schemas.insurance import CoverageStatus
from app.schemas.user import AuthenticatedUserContext
from app.services.payer_authorization_service import PayerAuthorizationService

logger = logging.getLogger(__name__)


class EligibilityService:
    """Service managing insurance eligibility verification."""

    def __init__(
        self,
        insurance_repo: Optional[InsuranceRepository] = None,
        eligibility_repo: Optional[EligibilityRepository] = None,
        provider: Optional[PayerProvider] = None,
    ) -> None:
        self.insurance_repo = insurance_repo or InsuranceRepository()
        self.eligibility_repo = eligibility_repo or EligibilityRepository()
        self.provider = provider or MockPayerProvider()

    def _ensure_enabled(self) -> None:
        if not settings.INSURANCE_ENABLED or not settings.ELIGIBILITY_ENABLED:
            raise EligibilityDisabledException("Insurance eligibility verification is disabled.")

    async def verify_eligibility(
        self,
        caller: AuthenticatedUserContext,
        payload: EligibilityCheckRequest,
    ) -> EligibilityCheckResponse:
        """Conduct a real-time eligibility check via configured payer gateway."""
        self._ensure_enabled()

        coverage = self.insurance_repo.get(payload.coverage_id)
        if not coverage:
            raise InsuranceNotFoundException(f"Coverage record {payload.coverage_id} not found.")

        PayerAuthorizationService.authorize_coverage_access(caller, coverage, action="check_eligibility")

        # Invoke provider adapter
        try:
            prov_result = await self.provider.verify_eligibility(
                coverage=coverage,
                service_type=payload.service_type,
                date_of_service=payload.date_of_service,
            )
        except Exception as exc:
            logger.error(f"Payer provider failed during eligibility check: {exc}")
            raise EligibilityCheckFailedException(f"Eligibility verification failed: {exc}")

        if not prov_result.success:
            if prov_result.error_code == "TIMEOUT":
                raise EligibilityProviderTimeoutException(prov_result.error_message or "Eligibility provider timed out.")
            raise EligibilityCheckFailedException(prov_result.error_message or "Eligibility verification failed at gateway.")

        # Map provider outcome
        check_id = f"elg_{uuid.uuid4().hex[:12]}"
        record = EligibilityCheckRecord(
            id=check_id,
            patient_id=coverage.patient_id,
            coverage_id=coverage.id,
            payer_id=coverage.payer_id,
            payer_name=coverage.payer_name,
            status=prov_result.status,
            raw_provider_reference=prov_result.raw_provider_reference,
            effective_date=prov_result.effective_date,
            termination_date=prov_result.termination_date,
            plan_name=prov_result.plan_name,
            limitations=prov_result.limitations,
            warnings=prov_result.warnings,
            provider_name=self.provider.name,
            provider_version="1.0",
            raw_response=prov_result.raw_response,
        )

        # Update coverage status if authoritative response received
        if prov_result.status == EligibilityStatus.ELIGIBLE:
            if coverage.status in (CoverageStatus.UNVERIFIED, CoverageStatus.PENDING):
                coverage.status = CoverageStatus.ACTIVE
                self.insurance_repo.update(coverage)
        elif prov_result.status == EligibilityStatus.INELIGIBLE:
            if coverage.status == CoverageStatus.ACTIVE:
                coverage.status = CoverageStatus.INACTIVE
                self.insurance_repo.update(coverage)

        saved = self.eligibility_repo.create(record)
        logger.info(
            f"Eligibility verification completed: id={saved.id}, patient={saved.patient_id}, "
            f"coverage={saved.coverage_id}, status={saved.status.value}"
        )
        return saved.to_response()

    def get_eligibility_check(
        self,
        caller: AuthenticatedUserContext,
        check_id: str,
    ) -> EligibilityCheckResponse:
        """Fetch historical eligibility verification record."""
        self._ensure_enabled()
        record = self.eligibility_repo.get(check_id)
        if not record:
            raise EligibilityCheckNotFoundException(f"Eligibility check record {check_id} not found.")

        coverage = self.insurance_repo.get(record.coverage_id)
        if coverage:
            PayerAuthorizationService.authorize_coverage_access(caller, coverage, action="read")

        return record.to_response()

    def list_patient_eligibility_checks(
        self,
        caller: AuthenticatedUserContext,
        patient_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[EligibilityCheckResponse], int]:
        """List eligibility inquiries conducted for a patient."""
        self._ensure_enabled()
        records, total = self.eligibility_repo.list_by_patient(patient_id, limit=limit, offset=offset)
        return [r.to_response() for r in records], total

"""Insurance Benefit Service (Phase 33).

Orchestrates retrieval and caching of covered benefits and copays via PayerProvider.
CRITICAL SAFETY INVARIANTS:
- BENEFIT INFORMATION IS AN ESTIMATE/POLICY TERM, NOT A FINAL PAYMENT GUARANTEE.
- NO AUTONOMOUS MEDICAL COVERAGE PROMISES.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    BenefitsDisabledException,
    BenefitsNotFoundException,
    BenefitsUnavailableException,
    InsuranceNotFoundException,
)
from app.integrations.payers.base import PayerProvider
from app.integrations.payers.providers.mock import MockPayerProvider
from app.repositories.benefit_repository import BenefitRepository
from app.repositories.insurance_repository import InsuranceRepository
from app.schemas.benefits import (
    BenefitCategory,
    BenefitRecord,
    BenefitRequest,
    BenefitResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.payer_authorization_service import PayerAuthorizationService

logger = logging.getLogger(__name__)


class BenefitService:
    """Service managing insurance benefit inquiry workflows."""

    def __init__(
        self,
        insurance_repo: Optional[InsuranceRepository] = None,
        benefit_repo: Optional[BenefitRepository] = None,
        provider: Optional[PayerProvider] = None,
    ) -> None:
        self.insurance_repo = insurance_repo or InsuranceRepository()
        self.benefit_repo = benefit_repo or BenefitRepository()
        self.provider = provider or MockPayerProvider()

    def _ensure_enabled(self) -> None:
        if not settings.INSURANCE_ENABLED or not settings.BENEFITS_ENABLED:
            raise BenefitsDisabledException("Insurance benefit inquiry subsystem is disabled.")

    async def get_benefits(
        self,
        caller: AuthenticatedUserContext,
        payload: BenefitRequest,
    ) -> BenefitResponse:
        """Query covered benefits for a patient's insurance policy."""
        self._ensure_enabled()

        coverage = self.insurance_repo.get(payload.coverage_id)
        if not coverage:
            raise InsuranceNotFoundException(f"Coverage record {payload.coverage_id} not found.")

        PayerAuthorizationService.authorize_coverage_access(caller, coverage, action="view_benefits")

        try:
            prov_res = await self.provider.get_benefits(coverage, categories=payload.categories)
        except Exception as exc:
            logger.error(f"Payer provider failed during benefit retrieval: {exc}")
            raise BenefitsUnavailableException(f"Benefit information unavailable from payer: {exc}")

        if not prov_res.success:
            raise BenefitsUnavailableException(prov_res.error_message or "Benefit inquiry failed at gateway")

        benefit_id = f"bnf_{uuid.uuid4().hex[:12]}"
        record = BenefitRecord(
            id=benefit_id,
            patient_id=coverage.patient_id,
            coverage_id=coverage.id,
            payer_id=coverage.payer_id,
            payer_name=coverage.payer_name,
            benefits=prov_res.benefits,
            raw_provider_reference=prov_res.raw_provider_reference,
            limitations=prov_res.limitations,
            uncertainty_notes=prov_res.uncertainty_notes,
            raw_response=prov_res.raw_response,
        )

        saved = self.benefit_repo.create(record)
        return saved.to_response()

    def get_latest_benefits(
        self,
        caller: AuthenticatedUserContext,
        coverage_id: str,
    ) -> BenefitResponse:
        """Fetch cached latest benefit inquiry for a coverage policy."""
        self._ensure_enabled()
        coverage = self.insurance_repo.get(coverage_id)
        if not coverage:
            raise InsuranceNotFoundException(f"Coverage record {coverage_id} not found.")

        PayerAuthorizationService.authorize_coverage_access(caller, coverage, action="view_benefits")

        cached = self.benefit_repo.get_latest_for_coverage(coverage_id)
        if not cached:
            raise BenefitsNotFoundException(f"No benefit breakdown records found for coverage {coverage_id}.")

        return cached.to_response()

    def list_patient_benefits(
        self,
        caller: AuthenticatedUserContext,
        patient_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[BenefitResponse], int]:
        """List historical benefit inquiries for a patient."""
        self._ensure_enabled()
        records, total = self.benefit_repo.list_by_patient(patient_id, limit=limit, offset=offset)
        return [r.to_response() for r in records], total

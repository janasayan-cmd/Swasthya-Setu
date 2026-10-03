"""Mock Payer Provider for testing and local development (Phase 33).

Supports realistic simulation of:
- Real-time eligibility inquiries (eligible, ineligible, unknown, error)
- Comprehensive benefit coverage breakdowns
- Prior authorization submission, approval, denial, and expiration
- Claim submission, adjudication, remittance advice, and denial codes
- Automated reconciliation discrepancy detection
- Cryptographic HMAC-SHA256 webhook verification
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.integrations.payers.base import (
    ParsedPayerWebhookEvent,
    PayerProvider,
    ProviderAuthResult,
    ProviderBenefitResult,
    ProviderClaimResponseResult,
    ProviderClaimStatusResult,
    ProviderClaimSubmissionResult,
    ProviderEligibilityResult,
    ProviderHealthResult,
    ProviderReconciliationResult,
    ProviderState,
)
from app.schemas.authorization import PreAuthorizationRecord, PreAuthorizationStatus
from app.schemas.benefits import BenefitCategory, BenefitItem
from app.schemas.claim import ClaimRecord, ClaimStatus
from app.schemas.claim_response import ClaimItemAdjudication, PayerClaimAdjudication
from app.schemas.eligibility import EligibilityStatus
from app.schemas.insurance import CoverageStatus, InsuranceCoverageRecord

logger = logging.getLogger(__name__)


class MockPayerProvider(PayerProvider):
    """Configurable mock payer provider for unit, integration, and failure testing."""

    def __init__(self, webhook_secret: Optional[str] = None) -> None:
        self._webhook_secret = webhook_secret or settings.PAYER_WEBHOOK_SECRET
        self._claims: Dict[str, Dict[str, Any]] = {}
        self._authorizations: Dict[str, Dict[str, Any]] = {}
        self._simulate_timeout: bool = False
        self._simulate_failure: bool = False
        self._simulate_unknown: bool = False
        self._custom_eligibility_status: Optional[EligibilityStatus] = None
        self._custom_auth_status: Optional[PreAuthorizationStatus] = None
        self._custom_claim_status: Optional[ClaimStatus] = None

    @property
    def name(self) -> str:
        return "MOCK"

    def set_simulation(
        self,
        simulate_timeout: bool = False,
        simulate_failure: bool = False,
        simulate_unknown: bool = False,
        custom_eligibility_status: Optional[EligibilityStatus] = None,
        custom_auth_status: Optional[PreAuthorizationStatus] = None,
        custom_claim_status: Optional[ClaimStatus] = None,
    ) -> None:
        """Configure mock behavior for tests."""
        self._simulate_timeout = simulate_timeout
        self._simulate_failure = simulate_failure
        self._simulate_unknown = simulate_unknown
        self._custom_eligibility_status = custom_eligibility_status
        self._custom_auth_status = custom_auth_status
        self._custom_claim_status = custom_claim_status

    configure_behavior = set_simulation

    async def verify_eligibility(
        self,
        coverage: InsuranceCoverageRecord,
        service_type: Optional[str] = None,
        date_of_service: Optional[str] = None,
    ) -> ProviderEligibilityResult:
        if self._simulate_timeout:
            return ProviderEligibilityResult(
                success=False,
                status=EligibilityStatus.ERROR,
                error_code="TIMEOUT",
                error_message="Gateway timeout connecting to payer clearinghouse",
            )
        if self._simulate_failure:
            return ProviderEligibilityResult(
                success=False,
                status=EligibilityStatus.ERROR,
                error_code="SYSTEM_UNAVAILABLE",
                error_message="Payer eligibility service temporarily unavailable",
            )
        if self._simulate_unknown:
            return ProviderEligibilityResult(
                success=True,
                status=EligibilityStatus.UNKNOWN,
                raw_provider_reference=f"mock_elig_{uuid.uuid4().hex[:8]}",
                limitations=["Payer records pending synchronization; point-in-time state unknown"],
            )
        if self._custom_eligibility_status:
            return ProviderEligibilityResult(
                success=True,
                status=self._custom_eligibility_status,
                raw_provider_reference=f"mock_elig_{uuid.uuid4().hex[:8]}",
                effective_date=coverage.start_date,
                termination_date=coverage.end_date,
            )

        # Standard deterministic logic
        if coverage.status in (CoverageStatus.ACTIVE, CoverageStatus.UNVERIFIED):
            return ProviderEligibilityResult(
                success=True,
                status=EligibilityStatus.ELIGIBLE,
                raw_provider_reference=f"mock_elig_{uuid.uuid4().hex[:8]}",
                effective_date=coverage.start_date or "2026-01-01",
                termination_date=coverage.end_date or "2026-12-31",
                plan_name=coverage.plan_name or "Standard Comprehensive Health Cover",
                limitations=["Standard OPD copay 10%", "Room rent capped at ₹5000/day"],
            )
        else:
            return ProviderEligibilityResult(
                success=True,
                status=EligibilityStatus.INELIGIBLE,
                raw_provider_reference=f"mock_elig_{uuid.uuid4().hex[:8]}",
                effective_date=coverage.start_date,
                termination_date=coverage.end_date,
                warnings=["Policy status in payer registry is inactive or terminated"],
            )

    async def get_benefits(
        self,
        coverage: InsuranceCoverageRecord,
        categories: Optional[List[BenefitCategory]] = None,
    ) -> ProviderBenefitResult:
        if self._simulate_timeout:
            return ProviderBenefitResult(success=False, error_code="TIMEOUT", error_message="Benefit service timeout")
        if self._simulate_failure:
            return ProviderBenefitResult(success=False, error_code="FAILURE", error_message="Payer clearinghouse failure")

        items = [
            BenefitItem(
                category=BenefitCategory.CONSULTATION,
                covered=True,
                copay_in_minor_units=5000,  # ₹50.00
                coinsurance_percentage=0.0,
                deductible_in_minor_units=0,
                limitations=["Maximum 12 consultations per policy year"],
            ),
            BenefitItem(
                category=BenefitCategory.DIAGNOSTIC,
                covered=True,
                copay_in_minor_units=0,
                coinsurance_percentage=10.0,
                deductible_in_minor_units=50000,  # ₹500.00 annual
                remaining_deductible_in_minor_units=20000,
                limitations=["Prior auth required for advanced radiology (MRI/CT)"],
            ),
            BenefitItem(
                category=BenefitCategory.INPATIENT,
                covered=True,
                copay_in_minor_units=0,
                coinsurance_percentage=0.0,
                deductible_in_minor_units=100000,  # ₹1000.00
                remaining_deductible_in_minor_units=0,
                limitations=["Room rent capped at ₹5000.00 / day"],
            ),
            BenefitItem(
                category=BenefitCategory.PHARMACY,
                covered=True,
                copay_in_minor_units=2000,
                coinsurance_percentage=15.0,
                limitations=["Generic formulations preferred"],
            ),
        ]

        if categories:
            items = [item for item in items if item.category in categories]

        return ProviderBenefitResult(
            success=True,
            benefits=items,
            raw_provider_reference=f"mock_bnf_{uuid.uuid4().hex[:8]}",
            limitations=["Subject to standard pre-existing disease waiting periods"],
            uncertainty_notes="Benefit schedule subject to live adjudication at time of service",
        )

    async def submit_authorization(
        self,
        auth_record: PreAuthorizationRecord,
    ) -> ProviderAuthResult:
        if self._simulate_timeout:
            return ProviderAuthResult(
                success=False,
                status=PreAuthorizationStatus.FAILED,
                error_code="TIMEOUT",
                error_message="Gateway timeout submitting prior authorization",
            )
        if self._simulate_failure:
            return ProviderAuthResult(
                success=False,
                status=PreAuthorizationStatus.FAILED,
                error_code="REJECTED",
                error_message="Payer rejected prior authorization request",
            )

        ref = f"PA-MOCK-{uuid.uuid4().hex[:8].upper()}"
        status = self._custom_auth_status or PreAuthorizationStatus.APPROVED
        approved_amt = auth_record.estimated_amount_in_minor_units if status == PreAuthorizationStatus.APPROVED else None

        self._authorizations[ref] = {
            "status": status,
            "approved_amount": approved_amt,
            "valid_from": "2026-10-01",
            "valid_to": "2026-10-31",
            "denial_reason": "Not covered under current policy terms" if status == PreAuthorizationStatus.DENIED else None,
            "denial_code": "POL_EXCL_001" if status == PreAuthorizationStatus.DENIED else None,
        }

        return ProviderAuthResult(
            success=True,
            status=status,
            payer_reference=ref,
            approved_amount_in_minor_units=approved_amt,
            valid_from="2026-10-01",
            valid_to="2026-10-31",
            denial_reason=self._authorizations[ref]["denial_reason"],
            denial_code=self._authorizations[ref]["denial_code"],
        )

    async def get_authorization_status(
        self,
        payer_reference: str,
    ) -> ProviderAuthResult:
        if self._simulate_timeout:
            return ProviderAuthResult(success=False, status=PreAuthorizationStatus.UNKNOWN, error_code="TIMEOUT")

        record = self._authorizations.get(payer_reference)
        if not record:
            return ProviderAuthResult(
                success=False,
                status=PreAuthorizationStatus.UNKNOWN,
                error_code="NOT_FOUND",
                error_message="Prior authorization not found with payer",
            )

        return ProviderAuthResult(
            success=True,
            status=record["status"],
            payer_reference=payer_reference,
            approved_amount_in_minor_units=record.get("approved_amount"),
            valid_from=record.get("valid_from"),
            valid_to=record.get("valid_to"),
            denial_reason=record.get("denial_reason"),
            denial_code=record.get("denial_code"),
        )

    async def submit_claim(
        self,
        claim_record: ClaimRecord,
    ) -> ProviderClaimSubmissionResult:
        if self._simulate_timeout:
            return ProviderClaimSubmissionResult(
                success=False,
                provider_claim_reference="",
                status=ClaimStatus.UNKNOWN,
                error_code="TIMEOUT",
                error_message="Payer claim submission connection timed out",
            )
        if self._simulate_failure:
            return ProviderClaimSubmissionResult(
                success=False,
                provider_claim_reference="",
                status=ClaimStatus.FAILED,
                error_code="SUBMISSION_REJECTED",
                error_message="Payer clearinghouse rejected claim format",
            )
        if self._simulate_unknown:
            return ProviderClaimSubmissionResult(
                success=False,
                provider_claim_reference=f"CLM-MOCK-{uuid.uuid4().hex[:10].upper()}",
                status=ClaimStatus.UNKNOWN,
                error_code="AMBIGUOUS_STATE",
                error_message="Gateway returned ambiguous acknowledgement; reconciliation required",
            )

        ref = f"CLM-MOCK-{uuid.uuid4().hex[:10].upper()}"
        initial_status = self._custom_claim_status or ClaimStatus.SUBMITTED

        self._claims[ref] = {
            "claim_number": claim_record.claim_number,
            "status": initial_status,
            "amount": claim_record.total_amount_in_minor_units,
            "currency": claim_record.currency,
            "patient_id": claim_record.patient_id,
            "created_at": time.time(),
        }

        return ProviderClaimSubmissionResult(
            success=True,
            provider_claim_reference=ref,
            status=initial_status,
            raw_response={"clearinghouse_batch_id": f"batch_{uuid.uuid4().hex[:6]}"},
        )

    async def get_claim_status(
        self,
        provider_claim_reference: str,
    ) -> ProviderClaimStatusResult:
        if self._simulate_timeout:
            return ProviderClaimStatusResult(
                success=False,
                provider_claim_reference=provider_claim_reference,
                status=ClaimStatus.UNKNOWN,
                amount_in_minor_units=0,
                currency="INR",
                error_code="TIMEOUT",
            )

        tx = self._claims.get(provider_claim_reference)
        if not tx:
            return ProviderClaimStatusResult(
                success=False,
                provider_claim_reference=provider_claim_reference,
                status=ClaimStatus.UNKNOWN,
                amount_in_minor_units=0,
                currency="INR",
                error_code="CLAIM_NOT_FOUND",
            )

        return ProviderClaimStatusResult(
            success=True,
            provider_claim_reference=provider_claim_reference,
            status=tx["status"],
            amount_in_minor_units=tx["amount"],
            currency=tx["currency"],
        )

    async def get_claim_response(
        self,
        provider_claim_reference: str,
    ) -> ProviderClaimResponseResult:
        tx = self._claims.get(provider_claim_reference)
        if not tx:
            return ProviderClaimResponseResult(
                success=False,
                error_code="CLAIM_NOT_FOUND",
                error_message="Claim not found in clearinghouse records",
            )

        total = tx["amount"]
        # Standard mock adjudication: 80% covered by payer, 20% patient responsibility
        payer_paid = int(total * 0.8)
        patient_resp = total - payer_paid

        adjudication = PayerClaimAdjudication(
            provider_claim_reference=provider_claim_reference,
            status=ClaimStatus.APPROVED,
            approved_amount_in_minor_units=total,
            payer_paid_amount_in_minor_units=payer_paid,
            patient_responsibility_in_minor_units=patient_resp,
            copay_in_minor_units=0,
            deductible_in_minor_units=0,
            coinsurance_in_minor_units=patient_resp,
            raw_response={"adjudication_engine": "MockRulesV1"},
        )
        return ProviderClaimResponseResult(success=True, adjudication=adjudication)

    async def reconcile_claim(
        self,
        provider_claim_reference: str,
        expected_amount_in_minor_units: int,
    ) -> ProviderReconciliationResult:
        tx = self._claims.get(provider_claim_reference)
        if not tx:
            return ProviderReconciliationResult(
                matched=False,
                provider_claim_reference=provider_claim_reference,
                external_status="MISSING",
                external_amount_in_minor_units=0,
            )

        ext_amt = tx["amount"]
        ext_status = tx["status"].value if hasattr(tx["status"], "value") else str(tx["status"])
        matched = (ext_amt == expected_amount_in_minor_units)

        return ProviderReconciliationResult(
            matched=matched,
            provider_claim_reference=provider_claim_reference,
            external_status=ext_status,
            external_amount_in_minor_units=ext_amt,
        )

    async def health_check(self) -> ProviderHealthResult:
        start = time.perf_counter()
        if self._simulate_failure:
            latency = (time.perf_counter() - start) * 1000.0
            return ProviderHealthResult(
                state=ProviderState.UNAVAILABLE,
                provider_name=self.name,
                latency_ms=latency,
                message="Mock payer service configured as unavailable",
                timestamp=time.time(),
            )
        latency = (time.perf_counter() - start) * 1000.0
        return ProviderHealthResult(
            state=ProviderState.AVAILABLE,
            provider_name=self.name,
            latency_ms=latency,
            message="Mock payer clearinghouse online and responding",
            timestamp=time.time(),
        )

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        headers: Dict[str, str],
    ) -> bool:
        sig = headers.get("X-Payer-Signature") or headers.get("x-payer-signature") or headers.get("X-Signature")
        if not sig:
            return False

        secret = self._webhook_secret.encode("utf-8")
        computed = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, computed)

    def parse_webhook(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> ParsedPayerWebhookEvent:
        event_id = payload.get("event_id", f"evt_{uuid.uuid4().hex[:8]}")
        event_type = payload.get("event_type", "unknown")
        data = payload.get("data") or payload.get("payload") or {}

        merged_data = dict(data)
        if "claim_id" in payload:
            merged_data["claim_id"] = payload["claim_id"]
        if "authorization_id" in payload:
            merged_data["authorization_id"] = payload["authorization_id"]

        return ParsedPayerWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            provider_claim_reference=data.get("provider_claim_reference") or payload.get("provider_claim_reference"),
            authorization_reference=data.get("authorization_reference") or payload.get("authorization_reference"),
            status=data.get("status") or payload.get("status"),
            amount_in_minor_units=data.get("amount_in_minor_units") or data.get("paid_amount") or payload.get("amount_in_minor_units"),
            currency=data.get("currency") or payload.get("currency", "INR"),
            raw_data=merged_data,
        )

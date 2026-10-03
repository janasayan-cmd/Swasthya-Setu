"""Payer Provider Abstraction (Phase 33).

Defines the pluggable interface for insurance clearinghouses and payer portals
(e.g., National Health Authority / ABHA / PMJAY, TPA Portals, Mock Clearinghouse)
without hardcoding any specific provider into business logic.

CRITICAL SAFETY INVARIANTS:
- PROVIDER FAILURE ≠ ELIGIBLE
- PROVIDER FAILURE ≠ AUTHORIZATION APPROVED
- PROVIDER FAILURE ≠ CLAIM PAID
- UNKNOWN RESULT REQUIRES RECONCILIATION
- SECRETS/CREDENTIALS MUST COME FROM CONFIGURATION, NEVER COMMITTED TO CODE.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.schemas.authorization import PreAuthorizationRecord, PreAuthorizationStatus
from app.schemas.benefits import BenefitCategory, BenefitItem
from app.schemas.claim import ClaimRecord, ClaimStatus
from app.schemas.claim_response import PayerClaimAdjudication
from app.schemas.eligibility import EligibilityStatus
from app.schemas.insurance import InsuranceCoverageRecord


class ProviderState(str, Enum):
    """Operational health state of payer gateway."""
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProviderHealthResult:
    """Outcome of health check against payer gateway."""
    state: ProviderState
    provider_name: str
    latency_ms: float
    message: str = "Payer gateway operational"
    timestamp: float = 0.0


@dataclass
class ProviderEligibilityResult:
    """Outcome of real-time eligibility inquiry."""
    success: bool
    status: EligibilityStatus
    raw_provider_reference: Optional[str] = None
    effective_date: Optional[str] = None
    termination_date: Optional[str] = None
    plan_name: Optional[str] = None
    limitations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderBenefitResult:
    """Outcome of benefit coverage inquiry."""
    success: bool
    benefits: List[BenefitItem] = field(default_factory=list)
    raw_provider_reference: Optional[str] = None
    limitations: List[str] = field(default_factory=list)
    uncertainty_notes: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderAuthResult:
    """Outcome of prior authorization request or status check."""
    success: bool
    status: PreAuthorizationStatus
    payer_reference: Optional[str] = None
    approved_amount_in_minor_units: Optional[int] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    denial_reason: Optional[str] = None
    denial_code: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderClaimSubmissionResult:
    """Outcome of claim submission to payer gateway."""
    success: bool
    provider_claim_reference: str
    status: ClaimStatus
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderClaimStatusResult:
    """Outcome of querying external claim status."""
    success: bool
    provider_claim_reference: str
    status: ClaimStatus
    amount_in_minor_units: int
    currency: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderClaimResponseResult:
    """Outcome of fetching adjudication remittance advice / EOB."""
    success: bool
    adjudication: Optional[PayerClaimAdjudication] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderReconciliationResult:
    """Outcome of reconciling claim with payer ledger."""
    matched: bool
    provider_claim_reference: str
    external_status: str
    external_amount_in_minor_units: int
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedPayerWebhookEvent:
    """Normalized webhook payload after provider-specific parsing."""
    event_id: str
    event_type: str
    provider_claim_reference: Optional[str] = None
    authorization_reference: Optional[str] = None
    status: Optional[str] = None
    amount_in_minor_units: Optional[int] = None
    currency: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


class PayerProvider(ABC):
    """Abstract interface defining the contract for payer gateway adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name / identifier of the provider."""
        ...

    @abstractmethod
    async def verify_eligibility(
        self,
        coverage: InsuranceCoverageRecord,
        service_type: Optional[str] = None,
        date_of_service: Optional[str] = None,
    ) -> ProviderEligibilityResult:
        """Verify real-time patient insurance eligibility."""
        ...

    @abstractmethod
    async def get_benefits(
        self,
        coverage: InsuranceCoverageRecord,
        categories: Optional[List[BenefitCategory]] = None,
    ) -> ProviderBenefitResult:
        """Retrieve covered benefits, copays, deductibles, and limitations."""
        ...

    @abstractmethod
    async def submit_authorization(
        self,
        auth_record: PreAuthorizationRecord,
    ) -> ProviderAuthResult:
        """Submit pre-authorization request to payer."""
        ...

    @abstractmethod
    async def get_authorization_status(
        self,
        payer_reference: str,
    ) -> ProviderAuthResult:
        """Query current status of pre-authorization from payer."""
        ...

    @abstractmethod
    async def submit_claim(
        self,
        claim_record: ClaimRecord,
    ) -> ProviderClaimSubmissionResult:
        """Submit medical claim to payer."""
        ...

    @abstractmethod
    async def get_claim_status(
        self,
        provider_claim_reference: str,
    ) -> ProviderClaimStatusResult:
        """Query current claim adjudication status."""
        ...

    @abstractmethod
    async def get_claim_response(
        self,
        provider_claim_reference: str,
    ) -> ProviderClaimResponseResult:
        """Retrieve authoritative claim remittance advice / adjudication result."""
        ...

    @abstractmethod
    async def reconcile_claim(
        self,
        provider_claim_reference: str,
        expected_amount_in_minor_units: int,
    ) -> ProviderReconciliationResult:
        """Compare internal transaction against payer system records."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderHealthResult:
        """Perform operational heartbeat and gateway connectivity check."""
        ...

    @abstractmethod
    def verify_webhook_signature(
        self,
        raw_body: bytes,
        headers: Dict[str, str],
    ) -> bool:
        """Verify cryptographic HMAC signature of inbound webhook request."""
        ...

    @abstractmethod
    def parse_webhook(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> ParsedPayerWebhookEvent:
        """Parse raw webhook payload into standardized ParsedPayerWebhookEvent."""
        ...

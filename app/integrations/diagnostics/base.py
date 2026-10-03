"""Diagnostic & Laboratory Provider Abstraction (Phase 34).

Defines the pluggable interface for external diagnostic laboratories, hospital LIS,
and diagnostic networks without hardcoding any single provider into domain services.

CRITICAL ARCHITECTURAL & SAFETY INVARIANTS:
- PROVIDER FAILURE != SUCCESS
- UNKNOWN PROVIDER RESULT != COMPLETED RESULT
- PROVIDER RESPONSE != HEALTHSETU CLINICAL TRUTH
- MALFORMED PROVIDER RESULT -> VALIDATION_FAILED
- PROVIDER TIMEOUT -> UNKNOWN / PENDING
- NO DIRECT/INVENTED CLINICAL DIAGNOSES
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.schemas.diagnostic_order import DiagnosticOrderRecord, DiagnosticOrderStatus
from app.schemas.diagnostic_result import AbnormalFlag, ReferenceRange, ResultStatus


class ProviderState(str, Enum):
    """Operational health state of diagnostic provider gateway."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProviderHealthResult:
    """Outcome of health check against diagnostic gateway."""

    state: ProviderState
    provider_name: str
    latency_ms: float
    message: str = "Diagnostic gateway operational"
    timestamp: float = 0.0


@dataclass
class ProviderOrderSubmissionResult:
    """Outcome of submitting a diagnostic order to external lab."""

    success: bool
    status: DiagnosticOrderStatus
    provider_order_id: Optional[str] = None
    tracking_number: Optional[str] = None
    estimated_completion: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderOrderResult:
    """External lab representation of an order."""

    provider_order_id: str
    status: DiagnosticOrderStatus
    patient_reference: Optional[str] = None
    test_codes: List[str] = field(default_factory=list)
    raw_status: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ProviderOrderCancelResult:
    """Outcome of attempting to cancel an order with external lab."""

    success: bool
    status: DiagnosticOrderStatus
    message: str = "Order cancelled successfully"
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderOrderStatusResult:
    """Status synchronization result from lab provider."""

    provider_order_id: str
    status: DiagnosticOrderStatus
    raw_status: Optional[str] = None
    specimen_collected: bool = False
    results_ready: bool = False
    message: Optional[str] = None


@dataclass
class ProviderAnalyteItem:
    """Single analyte reading from provider."""

    analyte_name: str
    analyte_code: Optional[str] = None
    numeric_value: Optional[float] = None
    qualitative_value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[ReferenceRange] = None
    abnormal_flag: AbnormalFlag = AbnormalFlag.UNKNOWN
    notes: Optional[str] = None


@dataclass
class ProviderResultPayload:
    """Result payload delivered by external lab."""

    provider_result_id: str
    provider_order_id: Optional[str] = None
    external_patient_id: Optional[str] = None
    status: ResultStatus = ResultStatus.FINAL
    items: List[ProviderAnalyteItem] = field(default_factory=list)
    report_text: Optional[str] = None
    collected_at: Optional[str] = None
    resulted_at: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderReportPayload:
    """Diagnostic report payload delivered by external lab."""

    provider_report_id: str
    provider_order_id: Optional[str] = None
    external_patient_id: Optional[str] = None
    conclusion_text: Optional[str] = None
    result_ids: List[str] = field(default_factory=list)
    reported_at: Optional[str] = None
    document_url: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class DiagnosticProvider(ABC):
    """Abstract base class for diagnostic laboratory integrations."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier string for this provider adapter."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of the laboratory or network."""
        pass

    @abstractmethod
    async def search_tests(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query supported tests in provider's catalog."""
        pass

    @abstractmethod
    async def get_test(self, provider_test_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve test details from provider catalog."""
        pass

    @abstractmethod
    async def place_order(self, order: DiagnosticOrderRecord) -> ProviderOrderSubmissionResult:
        """Submit diagnostic order to external lab."""
        pass

    @abstractmethod
    async def get_order(self, provider_order_id: str) -> Optional[ProviderOrderResult]:
        """Fetch order record from provider."""
        pass

    @abstractmethod
    async def cancel_order(self, provider_order_id: str, reason: str) -> ProviderOrderCancelResult:
        """Request order cancellation with lab."""
        pass

    @abstractmethod
    async def get_order_status(self, provider_order_id: str) -> ProviderOrderStatusResult:
        """Query real-time order status from lab."""
        pass

    @abstractmethod
    async def get_results(self, provider_order_id: str) -> List[ProviderResultPayload]:
        """Retrieve available results for an order."""
        pass

    @abstractmethod
    async def get_report(self, provider_report_id: str) -> Optional[ProviderReportPayload]:
        """Retrieve diagnostic report by external ID."""
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealthResult:
        """Verify connectivity and operational status."""
        pass

    @abstractmethod
    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify cryptographic HMAC signature on incoming webhooks."""
        pass

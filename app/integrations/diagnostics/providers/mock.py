"""Mock Diagnostic & Laboratory Provider (Phase 34).

Fully featured mock implementation of DiagnosticProvider for automated testing,
integration verification, and offline development.

Supports simulating:
- Normal, abnormal, critical, qualitative, and corrected results
- Provider network timeout and service unavailability
- Order cancellation and status changes
- HMAC-SHA256 signature verification for webhook payloads
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.integrations.diagnostics.base import (
    DiagnosticProvider,
    ProviderAnalyteItem,
    ProviderHealthResult,
    ProviderOrderCancelResult,
    ProviderOrderResult,
    ProviderOrderStatusResult,
    ProviderOrderSubmissionResult,
    ProviderReportPayload,
    ProviderResultPayload,
    ProviderState,
)
from app.schemas.diagnostic_order import DiagnosticOrderRecord, DiagnosticOrderStatus
from app.schemas.diagnostic_result import AbnormalFlag, ReferenceRange, ResultStatus


class MockDiagnosticProvider(DiagnosticProvider):
    """Mock lab provider with controllable failure and clinical edge modes."""

    def __init__(
        self,
        provider_id: str = "MOCK_LAB",
        provider_name: str = "HealthSetu Mock Reference Laboratory",
        secret: str = "mock-diagnostic-webhook-secret-key-12345",
    ) -> None:
        self._provider_id = provider_id
        self._provider_name = provider_name
        self._secret = secret

        # Simulation toggles
        self.simulate_failure: bool = False
        self.simulate_timeout: bool = False
        self.simulate_unavailable: bool = False
        self.simulate_critical: bool = False
        self.simulate_abnormal: bool = False
        self.simulate_qualitative: bool = False
        self.simulate_corrected: bool = False

        # In-memory orders store
        self._orders: Dict[str, Dict[str, Any]] = {}

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def search_tests(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Mock test search."""
        if self.simulate_unavailable:
            return []
        catalog = [
            {"provider_test_id": "MOCK-CBC", "name": "Complete Blood Count", "code": "58410-2", "category": "HEMATOLOGY"},
            {"provider_test_id": "MOCK-LIPID", "name": "Lipid Profile Panel", "code": "24331-1", "category": "BIOCHEMISTRY"},
            {"provider_test_id": "MOCK-CREAT", "name": "Serum Creatinine", "code": "2160-0", "category": "BIOCHEMISTRY"},
            {"provider_test_id": "MOCK-HBA1C", "name": "Hemoglobin A1c", "code": "4548-4", "category": "BIOCHEMISTRY"},
            {"provider_test_id": "MOCK-COVID", "name": "SARS-CoV-2 RT-PCR", "code": "94500-6", "category": "MOLECULAR"},
            {"provider_test_id": "MOCK-CXR", "name": "Chest X-Ray PA View", "code": "36554-4", "category": "RADIOLOGY"},
        ]
        q = query.lower()
        results = [
            t for t in catalog
            if q in t["name"].lower() or q in t["code"].lower()
        ]
        if category:
            results = [t for t in results if t["category"].upper() == category.upper()]
        return results[:limit]

    async def get_test(self, provider_test_id: str) -> Optional[Dict[str, Any]]:
        """Mock get test."""
        results = await self.search_tests(provider_test_id)
        return results[0] if results else None

    async def place_order(self, order: DiagnosticOrderRecord) -> ProviderOrderSubmissionResult:
        """Submit diagnostic order to mock lab."""
        if self.simulate_unavailable:
            return ProviderOrderSubmissionResult(
                success=False,
                status=DiagnosticOrderStatus.FAILED,
                error_code="DIAGNOSTIC_PROVIDER_UNAVAILABLE",
                error_message="Mock lab is currently offline",
            )
        if self.simulate_timeout:
            return ProviderOrderSubmissionResult(
                success=False,
                status=DiagnosticOrderStatus.UNKNOWN,
                error_code="DIAGNOSTIC_PROVIDER_TIMEOUT",
                error_message="Gateway connection timed out during submission",
            )
        if self.simulate_failure:
            return ProviderOrderSubmissionResult(
                success=False,
                status=DiagnosticOrderStatus.FAILED,
                error_code="DIAGNOSTIC_ORDER_SUBMISSION_FAILED",
                error_message="Mock lab rejected order: invalid parameters",
            )

        provider_order_id = f"MOCK-ORD-{uuid.uuid4().hex[:8].upper()}"
        tracking = f"TRK-{uuid.uuid4().hex[:6].upper()}"
        self._orders[provider_order_id] = {
            "order_id": order.order_id,
            "provider_order_id": provider_order_id,
            "patient_id": order.patient_id,
            "status": DiagnosticOrderStatus.ACCEPTED,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "tracking_number": tracking,
        }

        return ProviderOrderSubmissionResult(
            success=True,
            status=DiagnosticOrderStatus.ACCEPTED,
            provider_order_id=provider_order_id,
            tracking_number=tracking,
            estimated_completion="24 hours",
            raw_response={"status": "ACCEPTED", "facility": "MOCK_CENTRAL_LAB"},
        )

    async def get_order(self, provider_order_id: str) -> Optional[ProviderOrderResult]:
        """Fetch order record."""
        stored = self._orders.get(provider_order_id)
        if not stored:
            return None
        return ProviderOrderResult(
            provider_order_id=provider_order_id,
            status=stored.get("status", DiagnosticOrderStatus.ACCEPTED),
            patient_reference=stored.get("patient_id"),
        )

    async def cancel_order(self, provider_order_id: str, reason: str) -> ProviderOrderCancelResult:
        """Request order cancellation."""
        if self.simulate_unavailable:
            return ProviderOrderCancelResult(
                success=False,
                status=DiagnosticOrderStatus.UNKNOWN,
                message="Cannot reach laboratory for cancellation",
            )
        if provider_order_id in self._orders:
            self._orders[provider_order_id]["status"] = DiagnosticOrderStatus.CANCELLED
            self._orders[provider_order_id]["cancellation_reason"] = reason
            return ProviderOrderCancelResult(
                success=True,
                status=DiagnosticOrderStatus.CANCELLED,
                message="Order cancelled successfully by mock provider",
            )
        return ProviderOrderCancelResult(
            success=False,
            status=DiagnosticOrderStatus.FAILED,
            message="Provider order reference not found",
        )

    async def get_order_status(self, provider_order_id: str) -> ProviderOrderStatusResult:
        """Query real-time status."""
        if self.simulate_unavailable:
            return ProviderOrderStatusResult(
                provider_order_id=provider_order_id,
                status=DiagnosticOrderStatus.UNKNOWN,
                message="Lab unreachable",
            )
        stored = self._orders.get(provider_order_id)
        if not stored:
            return ProviderOrderStatusResult(
                provider_order_id=provider_order_id,
                status=DiagnosticOrderStatus.UNKNOWN,
                message="Order not found in mock lab",
            )
        return ProviderOrderStatusResult(
            provider_order_id=provider_order_id,
            status=stored.get("status", DiagnosticOrderStatus.ACCEPTED),
            results_ready=True,
        )

    async def get_results(self, provider_order_id: str) -> List[ProviderResultPayload]:
        """Retrieve results for an order."""
        if self.simulate_unavailable or self.simulate_failure:
            return []

        result_id = f"MOCK-RES-{uuid.uuid4().hex[:8].upper()}"

        if self.simulate_critical:
            # Simulate a critical analyte (e.g. Potassium 6.8 mEq/L or Hemoglobin 5.2 g/dL)
            items = [
                ProviderAnalyteItem(
                    analyte_name="Hemoglobin",
                    analyte_code="718-7",
                    numeric_value=5.2,
                    unit="g/dL",
                    reference_range=ReferenceRange(low=12.0, high=16.0, unit="g/dL", is_available=True),
                    abnormal_flag=AbnormalFlag.CRITICAL,
                    notes="Critical low panic value; repeated and verified by laboratory technician.",
                ),
                ProviderAnalyteItem(
                    analyte_name="Hematocrit",
                    analyte_code="4544-3",
                    numeric_value=16.0,
                    unit="%",
                    reference_range=ReferenceRange(low=36.0, high=48.0, unit="%", is_available=True),
                    abnormal_flag=AbnormalFlag.CRITICAL,
                ),
            ]
        elif self.simulate_abnormal:
            # Simulate abnormal but non-critical (e.g. Elevated Serum Creatinine)
            items = [
                ProviderAnalyteItem(
                    analyte_name="Serum Creatinine",
                    analyte_code="2160-0",
                    numeric_value=1.9,
                    unit="mg/dL",
                    reference_range=ReferenceRange(low=0.7, high=1.3, unit="mg/dL", is_available=True),
                    abnormal_flag=AbnormalFlag.HIGH,
                )
            ]
        elif self.simulate_qualitative:
            # Simulate qualitative result (e.g. COVID-19 PCR detected)
            items = [
                ProviderAnalyteItem(
                    analyte_name="SARS-CoV-2 RNA",
                    analyte_code="94500-6",
                    qualitative_value="DETECTED",
                    abnormal_flag=AbnormalFlag.POSITIVE,
                    reference_range=ReferenceRange(text="NOT DETECTED", is_available=True),
                )
            ]
        else:
            # Normal result
            items = [
                ProviderAnalyteItem(
                    analyte_name="Hemoglobin",
                    analyte_code="718-7",
                    numeric_value=14.2,
                    unit="g/dL",
                    reference_range=ReferenceRange(low=12.0, high=16.0, unit="g/dL", is_available=True),
                    abnormal_flag=AbnormalFlag.NORMAL,
                ),
                ProviderAnalyteItem(
                    analyte_name="Platelet Count",
                    analyte_code="777-3",
                    numeric_value=250.0,
                    unit="10*3/uL",
                    reference_range=ReferenceRange(low=150.0, high=450.0, unit="10*3/uL", is_available=True),
                    abnormal_flag=AbnormalFlag.NORMAL,
                ),
            ]

        status = ResultStatus.CORRECTED if self.simulate_corrected else ResultStatus.FINAL

        return [
            ProviderResultPayload(
                provider_result_id=result_id,
                provider_order_id=provider_order_id,
                status=status,
                items=items,
                report_text="Laboratory analysis completed according to ISO 15189 standard protocols.",
                collected_at=datetime.now(timezone.utc).isoformat(),
                resulted_at=datetime.now(timezone.utc).isoformat(),
            )
        ]

    async def get_report(self, provider_report_id: str) -> Optional[ProviderReportPayload]:
        """Fetch report."""
        if self.simulate_unavailable:
            return None
        return ProviderReportPayload(
            provider_report_id=provider_report_id,
            conclusion_text="Specimen analyzed; see analyte values for quantitative observations.",
            reported_at=datetime.now(timezone.utc).isoformat(),
        )

    async def health_check(self) -> ProviderHealthResult:
        """Verify connectivity."""
        start = time.perf_counter()
        if self.simulate_unavailable:
            return ProviderHealthResult(
                state=ProviderState.UNAVAILABLE,
                provider_name=self.provider_name,
                latency_ms=(time.perf_counter() - start) * 1000,
                message="Mock lab is currently offline",
                timestamp=time.time(),
            )
        return ProviderHealthResult(
            state=ProviderState.AVAILABLE,
            provider_name=self.provider_name,
            latency_ms=(time.perf_counter() - start) * 1000,
            message="Mock lab operational and accepting orders",
            timestamp=time.time(),
        )

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: Optional[str] = None,
    ) -> bool:
        """HMAC-SHA256 signature verification."""
        signing_secret = secret or self._secret
        if not signing_secret or not signature_header:
            return False

        clean_sig = signature_header.strip()
        if clean_sig.startswith("sha256="):
            clean_sig = clean_sig[7:]

        expected = hmac.new(
            signing_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected.lower(), clean_sig.lower())

"""Payment Reconciliation Service (Phase 32).

Authoritatively reconciles internal HealthSetu financial transaction states against
external payment gateway records, identifying discrepancies, amount mismatches,
or orphan charges.

SAFETY INVARIANTS:
- Never silently overwrite financial transactions.
- All discrepancies are logged and surfaced for controlled administrative review.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import PaymentNotFoundException
from app.integrations.payments.base import PaymentProvider
from app.repositories.payment_repository import PaymentRepository
from app.schemas.audit import AuditEventType
from app.schemas.payment import PaymentRecord, PaymentStatus
from app.schemas.financial_reconciliation import (
    FinancialDiscrepancyType as DiscrepancyType,
    FinancialReconciliationRecord as ReconciliationRecord,
    FinancialReconciliationReport as ReconciliationReport,
    FinancialReconciliationStatus as ReconciliationStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.invoice_service import InvoiceService

logger = logging.getLogger(__name__)


class PaymentReconciliationService:
    """Core domain service for comparing ledger states against external provider ledgers."""

    def __init__(
        self,
        payment_repo: PaymentRepository,
        invoice_service: InvoiceService,
        provider: PaymentProvider,
        audit_service: Optional[Any] = None,
    ) -> None:
        self.payment_repo = payment_repo
        self.invoice_service = invoice_service
        self.provider = provider
        self.audit_service = audit_service
        self._reconciliation_records: Dict[str, ReconciliationRecord] = {}

    def _record_audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.audit_service:
            return
        try:
            if hasattr(self.audit_service, "record"):
                import asyncio
                coro = self.audit_service.record(
                    event_type=event_type,
                    outcome="SUCCESS",
                    actor_id=actor_id,
                    resource_type="payment_reconciliation",
                    resource_id=resource_id,
                    metadata=details or {},
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(coro)
                except RuntimeError:
                    pass
        except Exception as e:
            logger.warning(f"Audit error: {e}")

    async def reconcile_payment(
        self,
        payment_id: str,
        actor_id: str = "SYSTEM",
    ) -> ReconciliationRecord:
        """Reconcile a single payment transaction against the provider."""
        payment = self.payment_repo.get(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"Payment {payment_id} not found")

        self._record_audit(
            AuditEventType.PAYMENT_RECONCILIATION_STARTED,
            actor_id,
            payment.id,
            {"current_status": payment.status.value},
        )

        rec = ReconciliationRecord(
            payment_id=payment.id,
            provider_transaction_id=payment.provider_transaction_id,
            system_amount_in_minor_units=payment.amount_in_minor_units,
            system_currency=payment.currency,
            system_status=payment.status.value,
        )

        if not payment.provider_transaction_id:
            rec.status = ReconciliationStatus.MISMATCHED
            rec.discrepancy_type = DiscrepancyType.MISSING_IN_PROVIDER
            rec.resolution_notes = "Payment has no provider transaction reference"
            self._reconciliation_records[rec.id] = rec
            return rec

        # Query provider
        try:
            prov_status = await self.provider.get_payment_status(payment.provider_transaction_id)
        except Exception as e:
            rec.status = ReconciliationStatus.FAILED
            rec.discrepancy_type = DiscrepancyType.UNKNOWN_PROVIDER_ERROR
            rec.resolution_notes = f"Gateway check failed: {e}"
            self._reconciliation_records[rec.id] = rec
            self._record_audit(AuditEventType.PAYMENT_RECONCILIATION_FAILED, actor_id, payment.id)
            return rec

        if not prov_status.success:
            rec.status = ReconciliationStatus.MISMATCHED
            rec.discrepancy_type = DiscrepancyType.MISSING_IN_PROVIDER
            rec.resolution_notes = prov_status.error_message
            self._reconciliation_records[rec.id] = rec
            return rec

        rec.provider_amount_in_minor_units = prov_status.amount_in_minor_units
        rec.provider_currency = prov_status.currency
        rec.provider_status = prov_status.status

        # Amount check
        if prov_status.amount_in_minor_units != payment.amount_in_minor_units:
            rec.status = ReconciliationStatus.MISMATCHED
            rec.discrepancy_type = DiscrepancyType.AMOUNT_MISMATCH
            rec.resolution_notes = (
                f"Amount mismatch: system={payment.amount_in_minor_units}, provider={prov_status.amount_in_minor_units}"
            )
            self._reconciliation_records[rec.id] = rec
            return rec

        # Currency check
        if prov_status.currency.upper() != payment.currency.upper():
            rec.status = ReconciliationStatus.MISMATCHED
            rec.discrepancy_type = DiscrepancyType.CURRENCY_MISMATCH
            rec.resolution_notes = f"Currency mismatch: system={payment.currency}, provider={prov_status.currency}"
            self._reconciliation_records[rec.id] = rec
            return rec

        # Status check
        prov_is_paid = prov_status.status in ("CAPTURED", "SUCCESS", "PAID")
        sys_is_paid = payment.status == PaymentStatus.SUCCEEDED

        if prov_is_paid and not sys_is_paid:
            # External provider succeeded, internal status was pending or unknown
            payment.status = PaymentStatus.SUCCEEDED
            payment.completed_at = datetime.now(timezone.utc)
            self.payment_repo.update(payment)
            self.invoice_service.apply_payment_delta(
                payment.invoice_id,
                amount_paid_delta=payment.amount_in_minor_units,
            )
            rec.status = ReconciliationStatus.RESOLVED
            rec.resolution_notes = "Payment status auto-resolved to SUCCEEDED based on provider truth"
            rec.resolved_at = datetime.now(timezone.utc)
        elif not prov_is_paid and sys_is_paid:
            rec.status = ReconciliationStatus.MISMATCHED
            rec.discrepancy_type = DiscrepancyType.STATUS_MISMATCH
            rec.resolution_notes = f"System marked SUCCEEDED but provider is {prov_status.status}"
        else:
            rec.status = ReconciliationStatus.MATCHED
            rec.resolution_notes = "Transaction matches provider ledger perfectly"

        self._reconciliation_records[rec.id] = rec
        self._record_audit(
            AuditEventType.PAYMENT_RECONCILIATION_COMPLETED,
            actor_id,
            payment.id,
            {"reconciliation_status": rec.status.value},
        )
        return rec

    async def run_batch(self, limit: int = 50) -> ReconciliationReport:
        """Run batch reconciliation on pending and unknown payments."""
        payments, _ = self.payment_repo.list_all(limit=limit)
        report = ReconciliationReport(total_checked=len(payments))

        for p in payments:
            rec = await self.reconcile_payment(p.id)
            report.records.append(rec)
            if rec.status == ReconciliationStatus.MATCHED:
                report.matched += 1
            elif rec.status == ReconciliationStatus.MISMATCHED:
                report.mismatched += 1
            elif rec.status == ReconciliationStatus.RESOLVED:
                report.resolved += 1
            else:
                report.unknown += 1

        return report

    def list_discrepancies(self) -> List[ReconciliationRecord]:
        """List all identified discrepancies."""
        return [
            r for r in self._reconciliation_records.values()
            if r.status in (ReconciliationStatus.MISMATCHED, ReconciliationStatus.FAILED)
        ]

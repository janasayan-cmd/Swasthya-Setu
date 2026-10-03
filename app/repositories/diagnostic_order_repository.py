"""Diagnostic Order Repository (Phase 34).

Thread-safe repository for storing diagnostic laboratory orders, order sub-items,
and specimen tracking records.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.diagnostic_order import (
    DiagnosticOrderFilter,
    DiagnosticOrderListResponse,
    DiagnosticOrderRecord,
    DiagnosticOrderStatus,
)
from app.schemas.specimen import SpecimenRecord


class DiagnosticOrderRepository:
    """Thread-safe repository for diagnostic orders."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orders: Dict[str, DiagnosticOrderRecord] = {}
        self._orders_by_number: Dict[str, str] = {}
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> order_id
        self._counter: int = 1000

    def generate_order_number(self) -> str:
        """Generate human-readable sequential order number."""
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        with self._lock:
            self._counter += 1
            seq = self._counter
        return f"ORD-{now_str}-{seq:04d}"

    def save(self, order: DiagnosticOrderRecord) -> DiagnosticOrderRecord:
        with self._lock:
            self._orders[order.order_id] = order
            self._orders_by_number[order.order_number] = order.order_id
            if order.idempotency_key:
                self._idempotency_map[order.idempotency_key] = order.order_id
            return order

    def get_by_id(self, order_id: str) -> Optional[DiagnosticOrderRecord]:
        with self._lock:
            return self._orders.get(order_id)

    def get_by_order_number(self, order_number: str) -> Optional[DiagnosticOrderRecord]:
        with self._lock:
            oid = self._orders_by_number.get(order_number)
            return self._orders.get(oid) if oid else None

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[DiagnosticOrderRecord]:
        with self._lock:
            oid = self._idempotency_map.get(idempotency_key)
            return self._orders.get(oid) if oid else None

    def get_by_provider_order_id(self, provider_order_id: str) -> Optional[DiagnosticOrderRecord]:
        with self._lock:
            for o in self._orders.values():
                if o.provider_order_id == provider_order_id:
                    return o
            return None

    def update_status(
        self,
        order_id: str,
        new_status: DiagnosticOrderStatus,
        cancellation_reason: Optional[str] = None,
        provider_order_id: Optional[str] = None,
    ) -> Optional[DiagnosticOrderRecord]:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None

            now = datetime.now(timezone.utc)
            update_data = {
                "status": new_status,
                "updated_at": now,
            }
            if provider_order_id:
                update_data["provider_order_id"] = provider_order_id
                if not order.submitted_at:
                    update_data["submitted_at"] = now
            if new_status == DiagnosticOrderStatus.CANCELLED:
                update_data["cancelled_at"] = now
                if cancellation_reason:
                    update_data["cancellation_reason"] = cancellation_reason
            elif new_status == DiagnosticOrderStatus.COMPLETED:
                update_data["completed_at"] = now

            updated = order.model_copy(update=update_data)
            self._orders[order_id] = updated
            return updated

    def attach_specimen(self, order_id: str, specimen: SpecimenRecord) -> Optional[DiagnosticOrderRecord]:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            specs = list(order.specimens)
            # Replace existing specimen or append
            replaced = False
            for i, s in enumerate(specs):
                if s.specimen_id == specimen.specimen_id:
                    specs[i] = specimen
                    replaced = True
                    break
            if not replaced:
                specs.append(specimen)

            updated = order.model_copy(
                update={"specimens": specs, "updated_at": datetime.now(timezone.utc)}
            )
            self._orders[order_id] = updated
            return updated

    def filter_orders(self, filter_params: DiagnosticOrderFilter) -> DiagnosticOrderListResponse:
        with self._lock:
            results = list(self._orders.values())

            if filter_params.patient_id:
                results = [o for o in results if o.patient_id == filter_params.patient_id]

            if filter_params.clinician_id:
                results = [o for o in results if o.clinician_id == filter_params.clinician_id]

            if filter_params.organization_id:
                results = [o for o in results if o.organization_id == filter_params.organization_id]

            if filter_params.facility_id:
                results = [o for o in results if o.facility_id == filter_params.facility_id]

            if filter_params.encounter_id:
                results = [o for o in results if o.encounter_id == filter_params.encounter_id]

            if filter_params.status:
                results = [o for o in results if o.status == filter_params.status]

            if filter_params.provider_id:
                results = [o for o in results if o.provider_id == filter_params.provider_id]

            if filter_params.date_from:
                results = [o for o in results if o.ordered_at >= filter_params.date_from]

            if filter_params.date_to:
                results = [o for o in results if o.ordered_at <= filter_params.date_to]

            # Sort descending by ordered_at
            results.sort(key=lambda o: o.ordered_at, reverse=True)

            total = len(results)
            start = (filter_params.page - 1) * filter_params.limit
            end = start + filter_params.limit
            paginated = results[start:end]

            return DiagnosticOrderListResponse(
                items=paginated,
                total=total,
                page=filter_params.page,
                limit=filter_params.limit,
            )

"""Clinical Order Repository (Phase 38).

Thread-safe in-memory repository for clinical orders, order items,
order history, and result linkage.

ARCHITECTURAL INVARIANTS:
- This repository consumes the existing database contract.
- No clinical decision logic is implemented here.
- All state transitions are delegated to the OrderStateService.
- Historical state is NEVER silently overwritten.
- Concurrency is protected via threading.Lock.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.order import (
    OrderFilter,
    OrderHistoryEntry,
    OrderItem,
    OrderListResponse,
    OrderRecord,
    OrderResultLink,
    OrderStatus,
)


class OrderRepository:
    """Thread-safe repository for clinical orders.

    CONCURRENCY SAFETY:
    - All mutations acquire the global lock before modifying shared state.
    - State transitions enforce last-write-wins only through controlled service layer,
      never through arbitrary updates.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orders: Dict[str, OrderRecord] = {}
        self._orders_by_number: Dict[str, str] = {}
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> order_id
        self._history: Dict[str, List[OrderHistoryEntry]] = {}  # order_id -> entries
        self._counter: int = 5000

    # -----------------------------------------------------------------------
    # Order Number Generation
    # -----------------------------------------------------------------------

    def generate_order_number(self) -> str:
        """Generate a human-readable sequential clinical order number."""
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        with self._lock:
            self._counter += 1
            seq = self._counter
        return f"CLN-ORD-{now_str}-{seq:04d}"

    # -----------------------------------------------------------------------
    # Core CRUD
    # -----------------------------------------------------------------------

    def save(self, order: OrderRecord) -> OrderRecord:
        """Persist or update a clinical order record."""
        with self._lock:
            self._orders[order.order_id] = order
            self._orders_by_number[order.order_number] = order.order_id
            if order.idempotency_key:
                self._idempotency_map[order.idempotency_key] = order.order_id
            return order

    def get_by_id(self, order_id: str) -> Optional[OrderRecord]:
        """Retrieve an order by internal ID."""
        with self._lock:
            return self._orders.get(order_id)

    def get_by_order_number(self, order_number: str) -> Optional[OrderRecord]:
        """Retrieve an order by its human-readable number."""
        with self._lock:
            oid = self._orders_by_number.get(order_number)
            return self._orders.get(oid) if oid else None

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[OrderRecord]:
        """Retrieve an order by client-provided idempotency key.

        IDEMPOTENCY SAFETY: Same key must return the same order without duplicate creation.
        """
        with self._lock:
            oid = self._idempotency_map.get(idempotency_key)
            return self._orders.get(oid) if oid else None

    def get_by_provider_order_id(self, provider_order_id: str) -> Optional[OrderRecord]:
        """Retrieve an order by the external provider's order ID."""
        with self._lock:
            for order in self._orders.values():
                if order.provider_order_id == provider_order_id:
                    return order
            return None

    # -----------------------------------------------------------------------
    # Controlled Status Update (TRD Section 12)
    # -----------------------------------------------------------------------

    def update_status(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        authorized_by: Optional[str] = None,
        cancellation_reason: Optional[str] = None,
        provider_order_id: Optional[str] = None,
        superseded_by_order_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[OrderRecord]:
        """Controlled status update — never allows arbitrary mutation.

        CONCURRENCY SAFETY: Acquires lock before reading + writing.
        HISTORY SAFETY: Previous state is preserved in history before update.
        """
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None

            now = datetime.now(timezone.utc)
            update_data: Dict = {
                "status": new_status,
                "updated_at": now,
            }

            if provider_order_id and not order.provider_order_id:
                update_data["provider_order_id"] = provider_order_id

            if new_status == OrderStatus.AUTHORIZED:
                update_data["authorized_at"] = now
                if authorized_by:
                    update_data["authorized_by"] = authorized_by

            if new_status in (OrderStatus.TRANSMITTING, OrderStatus.TRANSMITTED):
                if not order.submitted_at:
                    update_data["submitted_at"] = now

            if new_status in (OrderStatus.CANCELLED, OrderStatus.CANCEL_REQUESTED):
                if new_status == OrderStatus.CANCELLED:
                    update_data["cancelled_at"] = now
                if cancellation_reason:
                    update_data["cancellation_reason"] = cancellation_reason

            if new_status == OrderStatus.COMPLETED:
                update_data["completed_at"] = now

            if new_status == OrderStatus.SUPERSEDED:
                if superseded_by_order_id:
                    update_data["superseded_by_order_id"] = superseded_by_order_id

            if new_status == OrderStatus.VERIFIED:
                update_data["verified_at"] = now
                if authorized_by:
                    update_data["verified_by"] = authorized_by

            if new_status == OrderStatus.EXPIRED:
                update_data["expired_at"] = now

            if notes:
                update_data["notes"] = notes

            updated = order.model_copy(update=update_data)
            self._orders[order_id] = updated
            return updated

    # -----------------------------------------------------------------------
    # Result Linkage (TRD Section 21)
    # -----------------------------------------------------------------------

    def attach_result_link(self, order_id: str, result_link: OrderResultLink) -> Optional[OrderRecord]:
        """Attach a result link to an order.

        SAFETY: ORDER RESULT LINKAGE != RESULT VERIFICATION.
        Results are NOT automatically verified upon linkage.
        """
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            links = list(order.result_links)
            # Deduplicate by result_id
            replaced = False
            for i, existing in enumerate(links):
                if existing.result_id == result_link.result_id:
                    links[i] = result_link
                    replaced = True
                    break
            if not replaced:
                links.append(result_link)
            updated = order.model_copy(
                update={"result_links": links, "updated_at": datetime.now(timezone.utc)}
            )
            self._orders[order_id] = updated
            return updated

    # -----------------------------------------------------------------------
    # History / Audit Trail (TRD Section 40)
    # -----------------------------------------------------------------------

    def append_history(self, entry: OrderHistoryEntry) -> None:
        """Append an immutable history entry.

        HISTORICAL SAFETY: History entries are append-only and NEVER deleted or overwritten.
        """
        with self._lock:
            if entry.order_id not in self._history:
                self._history[entry.order_id] = []
            self._history[entry.order_id].append(entry)

    def get_history(self, order_id: str) -> List[OrderHistoryEntry]:
        """Retrieve full history for an order, oldest-first."""
        with self._lock:
            return list(self._history.get(order_id, []))

    # -----------------------------------------------------------------------
    # Supersession — Revision Chain (TRD Section 20)
    # -----------------------------------------------------------------------

    def mark_superseded(
        self,
        original_order_id: str,
        superseding_order_id: str,
    ) -> Optional[OrderRecord]:
        """Mark an order as superseded by a revision.

        SAFETY: Original order is PRESERVED. Only its status is updated to SUPERSEDED.
        Historical clinical state is NOT silently overwritten.
        """
        return self.update_status(
            original_order_id,
            OrderStatus.SUPERSEDED,
            superseded_by_order_id=superseding_order_id,
        )

    # -----------------------------------------------------------------------
    # Filtering / Search (TRD Section 29)
    # -----------------------------------------------------------------------

    def filter_orders(self, filter_params: OrderFilter) -> OrderListResponse:
        """Apply filter criteria and return a paginated order list.

        AUTHORIZATION NOTE: This repository does not enforce authorization.
        Authorization must be applied by the service layer before calling this method.
        """
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
        if filter_params.order_type:
            results = [o for o in results if o.order_type == filter_params.order_type]
        if filter_params.status:
            results = [o for o in results if o.status == filter_params.status]
        if filter_params.provider_id:
            results = [o for o in results if o.provider_id == filter_params.provider_id]
        if filter_params.date_from:
            results = [o for o in results if o.ordered_at >= filter_params.date_from]
        if filter_params.date_to:
            results = [o for o in results if o.ordered_at <= filter_params.date_to]

        # Sort by ordered_at descending (newest first)
        results.sort(key=lambda o: o.ordered_at, reverse=True)

        total = len(results)
        start = (filter_params.page - 1) * filter_params.limit
        end = start + filter_params.limit
        paginated = results[start:end]

        return OrderListResponse(
            items=paginated,
            total=total,
            page=filter_params.page,
            limit=filter_params.limit,
        )

    def get_patient_orders(
        self, patient_id: str, limit: int = 20, page: int = 1
    ) -> OrderListResponse:
        """Retrieve all orders for a patient, newest first."""
        return self.filter_orders(
            OrderFilter(patient_id=patient_id, limit=limit, page=page)
        )

    def get_clinician_orders(
        self, clinician_id: str, limit: int = 20, page: int = 1
    ) -> OrderListResponse:
        """Retrieve all orders by a clinician, newest first."""
        return self.filter_orders(
            OrderFilter(clinician_id=clinician_id, limit=limit, page=page)
        )

    def get_facility_orders(
        self, facility_id: str, limit: int = 20, page: int = 1
    ) -> OrderListResponse:
        """Retrieve all orders for a facility, newest first."""
        return self.filter_orders(
            OrderFilter(facility_id=facility_id, limit=limit, page=page)
        )

    def get_organization_orders(
        self, organization_id: str, limit: int = 20, page: int = 1
    ) -> OrderListResponse:
        """Retrieve all orders for an organization, newest first."""
        return self.filter_orders(
            OrderFilter(organization_id=organization_id, limit=limit, page=page)
        )

    # -----------------------------------------------------------------------
    # Reconciliation Support (TRD Section 33)
    # -----------------------------------------------------------------------

    def get_orders_needing_reconciliation(self) -> List[OrderRecord]:
        """Return orders in uncertain states requiring reconciliation."""
        reconciliation_states = {
            OrderStatus.TRANSMISSION_UNKNOWN,
            OrderStatus.PROVIDER_UNAVAILABLE,
            OrderStatus.RETRY_PENDING,
            OrderStatus.RECONCILIATION_REQUIRED,
        }
        with self._lock:
            return [
                o for o in self._orders.values()
                if o.status in reconciliation_states
            ]

    def get_orders_pending_authorization(self) -> List[OrderRecord]:
        """Return orders awaiting authorization."""
        with self._lock:
            return [
                o for o in self._orders.values()
                if o.status == OrderStatus.PENDING_AUTHORIZATION
            ]

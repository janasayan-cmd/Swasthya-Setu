"""Clinical Approval and Review Gate Repository (Phase 40).

Thread-safe in-memory repository for approval requests, decisions,
delegations, and historical audit entries.

ARCHITECTURAL INVARIANTS:
- Consumes existing database contract without duplicating tables.
- Decisions and transition histories are append-only and immutable.
- Concurrency safety is guaranteed via threading.Lock.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.approval import (
    ApprovalDelegationRecord,
    ApprovalRecord,
    ApprovalStatus,
    ApprovalType,
)


class ApprovalRepository:
    """Thread-safe repository for approval records and delegations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._approvals: Dict[str, ApprovalRecord] = {}
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> approval_id
        self._target_map: Dict[str, str] = {}  # "{target_type}:{target_id}" -> approval_id
        self._delegations: Dict[str, ApprovalDelegationRecord] = {}

    # -----------------------------------------------------------------------
    # Approval CRUD
    # -----------------------------------------------------------------------

    def save(self, approval: ApprovalRecord) -> ApprovalRecord:
        """Persist or update an approval record."""
        with self._lock:
            self._approvals[approval.id] = approval
            if approval.idempotency_key:
                self._idempotency_map[approval.idempotency_key] = approval.id
            target_key = f"{approval.target_type}:{approval.target_id}"
            self._target_map[target_key] = approval.id
            return approval

    def get_by_id(self, approval_id: str) -> Optional[ApprovalRecord]:
        """Retrieve approval record by ID."""
        with self._lock:
            return self._approvals.get(approval_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ApprovalRecord]:
        """Retrieve approval record by idempotency key."""
        with self._lock:
            app_id = self._idempotency_map.get(idempotency_key)
            if app_id:
                return self._approvals.get(app_id)
            return None

    def get_latest_by_target(self, target_type: str, target_id: str) -> Optional[ApprovalRecord]:
        """Retrieve latest approval record for a target action."""
        with self._lock:
            target_key = f"{target_type}:{target_id}"
            app_id = self._target_map.get(target_key)
            if app_id:
                return self._approvals.get(app_id)
            return None

    def list_approvals(
        self,
        status: Optional[ApprovalStatus] = None,
        approval_type: Optional[ApprovalType] = None,
        patient_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ApprovalRecord]:
        """Query approvals matching filters."""
        with self._lock:
            records = list(self._approvals.values())

        filtered: List[ApprovalRecord] = []
        for r in records:
            if status is not None and r.status != status:
                continue
            if approval_type is not None and r.approval_type != approval_type:
                continue
            if patient_id is not None and r.patient_id != patient_id:
                continue
            if requester_id is not None and r.requester_id != requester_id:
                continue
            if organization_id is not None and r.organization_id != organization_id:
                continue
            if facility_id is not None and r.facility_id != facility_id:
                continue
            if assigned_user_id is not None and assigned_user_id not in r.assigned_reviewers:
                continue
            filtered.append(r)

        # Sort descending by creation date
        filtered.sort(key=lambda x: x.created_at, reverse=True)
        return filtered[offset : offset + limit]

    def count_approvals(
        self,
        status: Optional[ApprovalStatus] = None,
        approval_type: Optional[ApprovalType] = None,
        patient_id: Optional[str] = None,
    ) -> int:
        """Count approvals matching query filters."""
        with self._lock:
            count = 0
            for r in self._approvals.values():
                if status is not None and r.status != status:
                    continue
                if approval_type is not None and r.approval_type != approval_type:
                    continue
                if patient_id is not None and r.patient_id != patient_id:
                    continue
                count += 1
            return count

    def add_history_entry(
        self,
        approval_id: str,
        action: str,
        actor_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an immutable audit entry to the approval's history."""
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval:
                entry = {
                    "action": action,
                    "actor_id": actor_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": details or {},
                }
                approval.history.append(entry)
                approval.updated_at = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Delegations (TRD Section 28)
    # -----------------------------------------------------------------------

    def save_delegation(self, delegation: ApprovalDelegationRecord) -> ApprovalDelegationRecord:
        """Persist a review delegation."""
        with self._lock:
            self._delegations[delegation.delegation_id] = delegation
            return delegation

    def get_active_delegation(
        self,
        delegator_id: str,
        delegatee_id: str,
    ) -> Optional[ApprovalDelegationRecord]:
        """Check if an active, unexpired delegation exists between two clinicians."""
        with self._lock:
            now = datetime.now(timezone.utc)
            for d in self._delegations.values():
                if d.delegator_id == delegator_id and d.delegatee_id == delegatee_id and d.is_active:
                    if d.expires_at is None or d.expires_at > now:
                        return d
            return None

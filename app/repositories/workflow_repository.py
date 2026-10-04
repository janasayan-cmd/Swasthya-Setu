"""Thread-safe in-memory repository for Clinical Workflows, History, and Approvals (Phase 37).

Consumes existing database contracts; does not create competing database schemas or migrations.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.workflow import (
    WorkflowCategory,
    WorkflowFilter,
    WorkflowRecord,
    WorkflowStatus,
)
from app.schemas.workflow_approval import WorkflowApprovalRecord
from app.schemas.workflow_history import WorkflowHistoryAction, WorkflowHistoryEntry


class WorkflowRepository:
    """Thread-safe storage for workflow instances, approvals, and lifecycle transition history."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workflows: Dict[str, WorkflowRecord] = {}
        # Client idempotency key index: idempotency_key -> workflow_id
        self._idempotency_index: Dict[str, str] = {}
        # Logical identity index: (source_type, source_id, definition_id, definition_version, patient_id) -> workflow_id
        self._logical_index: Dict[Tuple[str, str, str, str, Optional[str]], str] = {}
        # History index: workflow_id -> list of WorkflowHistoryEntry
        self._history: Dict[str, List[WorkflowHistoryEntry]] = {}
        # Approval index: workflow_id -> list of WorkflowApprovalRecord
        self._approvals: Dict[str, List[WorkflowApprovalRecord]] = {}
        self._counter: int = 1
        self._history_counter: int = 1
        self._approval_counter: int = 1

    def _generate_workflow_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        wf_id = f"WF-{today_str}-{self._counter:05d}"
        self._counter += 1
        return wf_id

    def _generate_history_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        hist_id = f"HIST-WF-{today_str}-{self._history_counter:05d}"
        self._history_counter += 1
        return hist_id

    def _generate_approval_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        appr_id = f"APPR-WF-{today_str}-{self._approval_counter:05d}"
        self._approval_counter += 1
        return appr_id

    def save(self, workflow: WorkflowRecord) -> WorkflowRecord:
        """Create or update a workflow instance atomically."""
        with self._lock:
            if not workflow.workflow_id:
                workflow = workflow.model_copy(update={"workflow_id": self._generate_workflow_id()})
            workflow = workflow.model_copy(update={"updated_at": datetime.now(timezone.utc)})
            self._workflows[workflow.workflow_id] = workflow

            # Index idempotency key if present
            if workflow.idempotency_key:
                self._idempotency_index[workflow.idempotency_key] = workflow.workflow_id

            # Index logical identity for deduplication
            if workflow.source_event_type and workflow.source_event_id:
                logical_key = (
                    workflow.source_event_type,
                    workflow.source_event_id,
                    workflow.definition_id,
                    workflow.definition_version,
                    workflow.patient_id,
                )
                self._logical_index[logical_key] = workflow.workflow_id

            return workflow

    def get_by_id(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """Fetch a workflow instance by ID."""
        with self._lock:
            return self._workflows.get(workflow_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[WorkflowRecord]:
        """Retrieve workflow by client idempotency key."""
        with self._lock:
            wf_id = self._idempotency_index.get(idempotency_key)
            if wf_id:
                return self._workflows.get(wf_id)
            return None

    def get_by_logical_identity(
        self,
        source_type: str,
        source_id: str,
        definition_id: str,
        definition_version: str,
        patient_id: Optional[str] = None,
    ) -> Optional[WorkflowRecord]:
        """Retrieve existing workflow by domain source identity to prevent duplicate instances."""
        with self._lock:
            logical_key = (source_type, source_id, definition_id, definition_version, patient_id)
            wf_id = self._logical_index.get(logical_key)
            if wf_id:
                return self._workflows.get(wf_id)
            return None

    def add_history(
        self,
        workflow_id: str,
        action: WorkflowHistoryAction,
        to_status: str,
        from_status: Optional[str] = None,
        step_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowHistoryEntry:
        """Record an immutable history audit entry for a workflow transition."""
        with self._lock:
            entry = WorkflowHistoryEntry(
                history_id=self._generate_history_id(),
                workflow_id=workflow_id,
                step_id=step_id,
                action=action,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                metadata=metadata or {},
                created_at=datetime.now(timezone.utc),
            )
            if workflow_id not in self._history:
                self._history[workflow_id] = []
            self._history[workflow_id].append(entry)
            return entry

    def get_history(self, workflow_id: str) -> List[WorkflowHistoryEntry]:
        """Retrieve complete transition history for a workflow."""
        with self._lock:
            return list(self._history.get(workflow_id, []))

    def save_approval(self, approval: WorkflowApprovalRecord) -> WorkflowApprovalRecord:
        """Record a human approval gate decision."""
        with self._lock:
            if not approval.approval_id:
                approval = approval.model_copy(update={"approval_id": self._generate_approval_id()})
            if approval.workflow_id not in self._approvals:
                self._approvals[approval.workflow_id] = []
            self._approvals[approval.workflow_id].append(approval)
            return approval

    def get_approvals(self, workflow_id: str) -> List[WorkflowApprovalRecord]:
        """Retrieve all recorded approvals for a workflow."""
        with self._lock:
            return list(self._approvals.get(workflow_id, []))

    def list_workflows(
        self,
        filters: WorkflowFilter,
        scoped_patient_id: Optional[str] = None,
        scoped_facility_id: Optional[str] = None,
    ) -> Tuple[List[WorkflowRecord], int]:
        """List workflows matching filters with mandatory security scoping."""
        with self._lock:
            results = list(self._workflows.values())

            # Mandatory scoping
            if scoped_patient_id:
                results = [w for w in results if w.patient_id == scoped_patient_id]
            if scoped_facility_id:
                results = [w for w in results if w.facility_id == scoped_facility_id]

            # Filters
            if filters.status:
                results = [w for w in results if w.status == filters.status]
            if filters.category:
                results = [w for w in results if w.category == filters.category]
            if filters.definition_id:
                results = [w for w in results if w.definition_id == filters.definition_id]
            if filters.patient_id:
                results = [w for w in results if w.patient_id == filters.patient_id]
            if filters.facility_id:
                results = [w for w in results if w.facility_id == filters.facility_id]
            if filters.correlation_id:
                results = [w for w in results if w.correlation_id == filters.correlation_id]

            # Sort descending by updated_at
            results.sort(key=lambda w: w.updated_at, reverse=True)

            total = len(results)
            start = (filters.page - 1) * filters.page_size
            end = start + filters.page_size
            return results[start:end], total

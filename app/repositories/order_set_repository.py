"""Order Set and Protocol Template Repository (Phase 39).

Thread-safe in-memory repository for clinical order set templates,
versions, and execution records.

ARCHITECTURAL INVARIANTS:
- Consumes existing domain contracts without creating duplicate database tables.
- Preserves full version provenance and execution history.
- Concurrency safety guaranteed via threading.Lock.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.order_set import (
    OrderSetTemplateRecord,
    OrderSetTemplateVersion,
    TemplateScope,
    TemplateStatus,
    TemplateType,
)
from app.schemas.order_set_execution import (
    OrderSetExecutionRecord,
    OrderSetExecutionStatus,
)


class OrderSetRepository:
    """Thread-safe repository for order set templates, versions, and executions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._templates: Dict[str, OrderSetTemplateRecord] = {}
        self._templates_by_code: Dict[str, str] = {}  # code -> template_id
        self._versions: Dict[str, OrderSetTemplateVersion] = {}  # version_id -> version
        self._executions: Dict[str, OrderSetExecutionRecord] = {}
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> execution_id

    # -----------------------------------------------------------------------
    # Template Operations
    # -----------------------------------------------------------------------

    def save_template(self, template: OrderSetTemplateRecord) -> OrderSetTemplateRecord:
        """Persist or update an order set template."""
        with self._lock:
            self._templates[template.id] = template
            self._templates_by_code[template.code] = template.id
            for version in template.versions:
                self._versions[version.version_id] = version
            return template

    def get_template_by_id(self, template_id: str) -> Optional[OrderSetTemplateRecord]:
        """Retrieve template by ID."""
        with self._lock:
            return self._templates.get(template_id)

    def get_template_by_code(self, code: str) -> Optional[OrderSetTemplateRecord]:
        """Retrieve template by business code."""
        with self._lock:
            template_id = self._templates_by_code.get(code)
            if template_id:
                return self._templates.get(template_id)
            return None

    def list_templates(
        self,
        scope: Optional[TemplateScope] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        template_type: Optional[TemplateType] = None,
        status: Optional[TemplateStatus] = None,
        search_query: Optional[str] = None,
    ) -> List[OrderSetTemplateRecord]:
        """List templates matching filters."""
        with self._lock:
            results = list(self._templates.values())

        filtered: List[OrderSetTemplateRecord] = []
        for t in results:
            if status is not None and t.status != status:
                continue
            if template_type is not None and t.template_type != template_type:
                continue
            if scope is not None and t.scope != scope:
                continue
            if organization_id is not None and t.organization_id is not None and t.organization_id != organization_id:
                continue
            if facility_id is not None and t.facility_id is not None and t.facility_id != facility_id:
                continue
            if search_query:
                q = search_query.lower()
                title_match = q in t.title.lower()
                code_match = q in t.code.lower()
                desc_match = bool(t.description and q in t.description.lower())
                if not (title_match or code_match or desc_match):
                    continue
            filtered.append(t)

        return filtered

    # -----------------------------------------------------------------------
    # Version Operations
    # -----------------------------------------------------------------------

    def get_version_by_id(self, version_id: str) -> Optional[OrderSetTemplateVersion]:
        """Retrieve a specific template version by its ID."""
        with self._lock:
            return self._versions.get(version_id)

    def add_version(
        self,
        template_id: str,
        version: OrderSetTemplateVersion,
    ) -> Optional[OrderSetTemplateRecord]:
        """Add a new version to an existing template."""
        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                return None
            template.versions.append(version)
            template.updated_at = datetime.now(timezone.utc)
            self._versions[version.version_id] = version
            return template

    def update_version(
        self,
        version: OrderSetTemplateVersion,
    ) -> Optional[OrderSetTemplateVersion]:
        """Update an existing version in both index and parent template."""
        with self._lock:
            self._versions[version.version_id] = version
            template = self._templates.get(version.template_id)
            if template:
                for idx, v in enumerate(template.versions):
                    if v.version_id == version.version_id:
                        template.versions[idx] = version
                        template.updated_at = datetime.now(timezone.utc)
                        break
            return version

    # -----------------------------------------------------------------------
    # Execution Operations
    # -----------------------------------------------------------------------

    def save_execution(self, execution: OrderSetExecutionRecord) -> OrderSetExecutionRecord:
        """Persist or update an execution record."""
        with self._lock:
            self._executions[execution.id] = execution
            if execution.idempotency_key:
                self._idempotency_map[execution.idempotency_key] = execution.id
            return execution

    def get_execution_by_id(self, execution_id: str) -> Optional[OrderSetExecutionRecord]:
        """Retrieve execution by ID."""
        with self._lock:
            return self._executions.get(execution_id)

    def get_execution_by_idempotency_key(self, idempotency_key: str) -> Optional[OrderSetExecutionRecord]:
        """Retrieve execution by idempotency key."""
        with self._lock:
            exec_id = self._idempotency_map.get(idempotency_key)
            if exec_id:
                return self._executions.get(exec_id)
            return None

    def list_executions(
        self,
        patient_id: Optional[str] = None,
        template_id: Optional[str] = None,
        status: Optional[OrderSetExecutionStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[OrderSetExecutionRecord]:
        """List execution records matching filters."""
        with self._lock:
            records = list(self._executions.values())

        filtered: List[OrderSetExecutionRecord] = []
        for r in records:
            if patient_id and r.patient_id != patient_id:
                continue
            if template_id and r.template_id != template_id:
                continue
            if status and r.status != status:
                continue
            filtered.append(r)

        # Sort descending by creation date
        filtered.sort(key=lambda x: x.created_at, reverse=True)
        return filtered[offset : offset + limit]

    def count_executions(
        self,
        patient_id: Optional[str] = None,
        template_id: Optional[str] = None,
        status: Optional[OrderSetExecutionStatus] = None,
    ) -> int:
        """Count executions matching filters."""
        with self._lock:
            count = 0
            for r in self._executions.values():
                if patient_id and r.patient_id != patient_id:
                    continue
                if template_id and r.template_id != template_id:
                    continue
                if status and r.status != status:
                    continue
                count += 1
            return count

    def add_execution_history(
        self,
        execution_id: str,
        action: str,
        actor_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an immutable history entry to an execution record."""
        with self._lock:
            record = self._executions.get(execution_id)
            if record:
                entry = {
                    "action": action,
                    "actor_id": actor_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": details or {},
                }
                record.history.append(entry)
                record.updated_at = datetime.now(timezone.utc)

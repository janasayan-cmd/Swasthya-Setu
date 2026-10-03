"""Diagnostic Result Reconciliation Service (Phase 34 & Phase 26).

Identifies data discrepancies, duplicates, unit anomalies, and missing provenance
across laboratory orders and ingested diagnostic results.

CRITICAL CLINICAL SAFETY INVARIANTS:
- DATA QUALITY FINDING != CLINICAL DIAGNOSIS
- RECONCILIATION DISCREPANCY != AUTOMATIC RESULT MERGE
- NEVER AUTOMATICALLY MERGE CONFLICTING CLINICAL RESULTS
- CLINICAL INTEGRITY TAKES PRECEDENCE OVER DATA SILOS
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.repositories.diagnostic_order_repository import DiagnosticOrderRepository
from app.repositories.diagnostic_reconciliation_repository import DiagnosticReconciliationRepository
from app.repositories.diagnostic_result_repository import DiagnosticResultRepository
from app.schemas.audit import AuditEventType, AuditRecord
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_order import DiagnosticOrderFilter, DiagnosticOrderStatus
from app.schemas.diagnostic_reconciliation import (
    DiscrepancySeverity,
    DiscrepancyType,
    ReconciliationFinding,
    ReconciliationStatus,
    ReconciliationSummary,
)
from app.schemas.diagnostic_result import DiagnosticResultFilter
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class DiagnosticReconciliationService:
    """Service auditing diagnostic consistency and data quality integrity."""

    def __init__(
        self,
        order_repository: Optional[DiagnosticOrderRepository] = None,
        result_repository: Optional[DiagnosticResultRepository] = None,
        reconciliation_repository: Optional[DiagnosticReconciliationRepository] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.order_repository = order_repository or DiagnosticOrderRepository()
        self.result_repository = result_repository or DiagnosticResultRepository()
        self.reconciliation_repository = reconciliation_repository or DiagnosticReconciliationRepository()
        self.audit_service = audit_service

    async def reconcile_order(
        self,
        order_id: str,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> ReconciliationSummary:
        """Run deep reconciliation check for a specific diagnostic order."""
        order = self.order_repository.get_by_id(order_id) or self.order_repository.get_by_order_number(order_id)
        if not order:
            finding = ReconciliationFinding(
                finding_id=f"fnd-{uuid.uuid4().hex[:8]}",
                discrepancy_type=DiscrepancyType.ORDER_MISMATCH,
                severity=DiscrepancySeverity.HIGH,
                description=f"Diagnostic order '{order_id}' was not found in system",
                affected_order_id=order_id,
            )
            summary = ReconciliationSummary(
                reconciliation_id=f"rec-{uuid.uuid4().hex[:8]}",
                order_id=order_id,
                status=ReconciliationStatus.DISCREPANCY_DETECTED,
                total_checked=1,
                clean_count=0,
                discrepancy_count=1,
                findings=[finding],
            )
            return self.reconciliation_repository.save(summary)

        # Query all results linked to this order
        res_list = self.result_repository.filter_results(
            DiagnosticResultFilter(order_id=order.order_id, limit=100),
            current_only=False,
        ).items

        findings: List[ReconciliationFinding] = []

        # Check 1: Missing Results for Completed Order
        if order.status == DiagnosticOrderStatus.COMPLETED and not res_list:
            findings.append(
                ReconciliationFinding(
                    finding_id=f"fnd-{uuid.uuid4().hex[:8]}",
                    discrepancy_type=DiscrepancyType.MISSING_RESULT,
                    severity=DiscrepancySeverity.HIGH,
                    description=f"Order '{order.order_number}' marked COMPLETED but no diagnostic results found",
                    affected_order_id=order.order_id,
                    affected_patient_id=order.patient_id,
                )
            )

        # Check 2: Patient Mismatches & Provenance
        seen_analytes: dict[str, list] = {}

        for r in res_list:
            if r.patient_id != order.patient_id:
                findings.append(
                    ReconciliationFinding(
                        finding_id=f"fnd-{uuid.uuid4().hex[:8]}",
                        discrepancy_type=DiscrepancyType.PATIENT_MISMATCH,
                        severity=DiscrepancySeverity.CRITICAL,
                        description=f"Result '{r.result_id}' patient '{r.patient_id}' does not match order patient '{order.patient_id}'",
                        affected_order_id=order.order_id,
                        affected_result_id=r.result_id,
                        affected_patient_id=r.patient_id,
                    )
                )

            if not r.provenance or not r.provenance.get("provider_id"):
                findings.append(
                    ReconciliationFinding(
                        finding_id=f"fnd-{uuid.uuid4().hex[:8]}",
                        discrepancy_type=DiscrepancyType.MISSING_PROVENANCE,
                        severity=DiscrepancySeverity.MEDIUM,
                        description=f"Result '{r.result_id}' lacks authoritative provider provenance",
                        affected_order_id=order.order_id,
                        affected_result_id=r.result_id,
                    )
                )

            # Check analyte units & duplicates among current results
            if r.is_current:
                for item in r.items:
                    if not item.unit and item.numeric_value is not None:
                        findings.append(
                            ReconciliationFinding(
                                finding_id=f"fnd-{uuid.uuid4().hex[:8]}",
                                discrepancy_type=DiscrepancyType.MISSING_UNIT,
                                severity=DiscrepancySeverity.MEDIUM,
                                description=f"Numeric analyte '{item.analyte_name}' in result '{r.result_id}' lacks unit of measure",
                                affected_result_id=r.result_id,
                            )
                        )
                    code_key = item.analyte_code or item.analyte_name
                    if code_key not in seen_analytes:
                        seen_analytes[code_key] = []
                    seen_analytes[code_key].append((r.result_id, item))

        # Check for multiple active current results for same analyte (Conflict detection)
        for code_key, occurrences in seen_analytes.items():
            if len(occurrences) > 1:
                findings.append(
                    ReconciliationFinding(
                        finding_id=f"fnd-{uuid.uuid4().hex[:8]}",
                        discrepancy_type=DiscrepancyType.CONFLICTING_RESULT,
                        severity=DiscrepancySeverity.HIGH,
                        description=f"Multiple current conflicting results detected for analyte '{code_key}'. Manual clinician audit required; results NOT auto-merged.",
                        affected_order_id=order.order_id,
                        details={"analyte": code_key, "count": len(occurrences)},
                    )
                )

        status = ReconciliationStatus.CLEAN if not findings else ReconciliationStatus.DISCREPANCY_DETECTED
        summary = ReconciliationSummary(
            reconciliation_id=f"rec-{uuid.uuid4().hex[:8]}",
            order_id=order.order_id,
            patient_id=order.patient_id,
            status=status,
            total_checked=len(res_list) + 1,
            clean_count=max(0, len(res_list) + 1 - len(findings)),
            discrepancy_count=len(findings),
            findings=findings,
        )

        saved = self.reconciliation_repository.save(summary)

        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_RECONCILIATION_COMPLETED,
                actor=current_user,
                resource_id=saved.reconciliation_id,
                patient_id=order.patient_id,
                outcome="ALLOW",
                discrepancies=len(findings),
            )

        return saved

    async def _audit(
        self,
        event_type: AuditEventType,
        actor: Optional[AuthenticatedUserContext],
        resource_id: str,
        patient_id: Optional[str],
        outcome: str,
        discrepancies: int = 0,
    ) -> None:
        if not self.audit_service:
            return
        actor_id = str(getattr(actor, "id", None) or getattr(actor, "user_id", None) or "system_reconciliation")
        record = AuditRecord(
            event_type=event_type,
            actor_id=actor_id,
            patient_id=patient_id,
            action=event_type.value,
            resource_type="diagnostic_reconciliation",
            resource_id=resource_id,
            outcome=outcome,
            metadata={"discrepancies": discrepancies},
        )
        try:
            await self.audit_service.log_event(record)
        except Exception as e:
            logger.warning("Audit logging failed for reconciliation: %s", e)

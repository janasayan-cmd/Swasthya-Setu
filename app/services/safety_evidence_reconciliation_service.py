"""Phase 62: Safety Evidence Reconciliation Service.

Reconciles disparate authoritative evidence sources (surveillance analytics,
assurance validation, action effectiveness, and incidents).
Preserves contradictions explicitly rather than resolving to favorable outcomes.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.schemas.safety_risk_assessment import (
    ConsolidatedSourceFindingReference,
    EvidenceReconciliationState,
    ReconciledEvidenceItem,
)


class SafetyEvidenceReconciliationService:
    """Evaluates evidence consistency across surveillance, assurance, and effectiveness sources."""

    def reconcile_evidence(
        self,
        findings: List[ConsolidatedSourceFindingReference],
        external_evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[ReconciledEvidenceItem], EvidenceReconciliationState, bool]:
        """Reconcile internal findings and external evidence items, detecting conflicts."""
        evidence_items: List[ReconciledEvidenceItem] = []
        ext_list = external_evidence or []

        has_conflicts = False

        # Transform findings into baseline evidence items
        for f in findings:
            item = ReconciledEvidenceItem(
                source_phase=f.source_phase,
                source_record_id=f.finding_id,
                status="VALIDATED",
                is_conflicted=False,
                reconciliation_state=EvidenceReconciliationState.CONSISTENT,
                description=f"Surveillance finding: {f.title}",
            )
            evidence_items.append(item)

        # Ingest external evidence and detect disagreements
        for ext in ext_list:
            ext_phase = str(ext.get("source_phase", "EXTERNAL"))
            ext_id = str(ext.get("source_record_id", f"ext-{len(evidence_items)}"))
            ext_status = str(ext.get("status", "NORMAL"))
            claims_effective = ext.get("claims_effective", False)

            # Check if external source contradicts internal surveillance failures
            has_failures = any(
                "failure" in f.finding_type.lower() or "degradation" in f.finding_type.lower()
                for f in findings
            )
            is_conflicted = claims_effective and has_failures

            if is_conflicted:
                has_conflicts = True
                rec_state = EvidenceReconciliationState.CONFLICTED
            else:
                rec_state = EvidenceReconciliationState.CONSISTENT

            item = ReconciledEvidenceItem(
                source_phase=ext_phase,
                source_record_id=ext_id,
                status=ext_status,
                is_conflicted=is_conflicted,
                reconciliation_state=rec_state,
                description=str(ext.get("description", "External evidence input")),
            )
            evidence_items.append(item)

        overall_state = (
            EvidenceReconciliationState.CONFLICTED
            if has_conflicts
            else EvidenceReconciliationState.CONSISTENT
        )

        return evidence_items, overall_state, has_conflicts


_evidence_service: Optional[SafetyEvidenceReconciliationService] = None


def get_safety_evidence_reconciliation_service() -> SafetyEvidenceReconciliationService:
    global _evidence_service
    if _evidence_service is None:
        _evidence_service = SafetyEvidenceReconciliationService()
    return _evidence_service

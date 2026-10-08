"""Phase 62: Safety Finding Consolidation Service.

Consolidates related findings from Phase 60, Phase 61, and upstream safety workflows
into unified, traceable risk contexts without hiding or deleting original source findings.
"""

from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_assessment import (
    ConsolidatedRiskContext,
    ConsolidatedSourceFindingReference,
    EvidenceReconciliationState,
    RiskAssessmentScope,
)


class SafetyFindingConsolidationService:
    """Consolidates related analytical findings into unified risk contexts."""

    def consolidate_findings(
        self,
        findings: List[ConsolidatedSourceFindingReference],
        scope: RiskAssessmentScope,
        concern_summary: Optional[str] = None,
    ) -> ConsolidatedRiskContext:
        """Construct a consolidated risk context preserving all source finding relationships."""
        if not findings:
            raise AppException(
                code=ErrorCode.CONSOLIDATION_FAILED,
                message="Cannot consolidate an empty set of eligible safety findings.",
                status_code=400,
            )

        # Build composite summary from finding titles/types
        finding_types = list(set(f.finding_type for f in findings))
        summary = (
            concern_summary
            or f"Consolidated risk context across {len(findings)} findings ({', '.join(finding_types)}) in scope {scope.organization_id}."
        )

        supporting_ids = [f.finding_id for f in findings]

        context = ConsolidatedRiskContext(
            concern_summary=summary,
            affected_scope=scope,
            observation_window_hours=720.0,
            supporting_finding_ids=supporting_ids,
            counter_evidence_ids=[],
            reconciliation_state=EvidenceReconciliationState.CONSISTENT,
            assurance_status="OBSERVED",
            effectiveness_status="UNDER_EVALUATION",
            incident_references=[
                str(f.metadata.get("incident_id"))
                for f in findings
                if f.metadata.get("incident_id")
            ],
            surveillance_status="ACTIVE",
            analytical_note="Consolidated risk context represents systemic evidence and is not a clinical diagnosis or incident investigation.",
        )

        return context


_consolidation_service: Optional[SafetyFindingConsolidationService] = None


def get_safety_finding_consolidation_service() -> SafetyFindingConsolidationService:
    global _consolidation_service
    if _consolidation_service is None:
        _consolidation_service = SafetyFindingConsolidationService()
    return _consolidation_service

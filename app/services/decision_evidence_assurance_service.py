"""Phase 68: Decision Evidence Assurance Service.

Evaluates supporting evidence artifacts attached to governance decisions,
distinguishing missing, unavailable, stale, and invalidated evidence.

Mandatory Invariants:
1. Do not treat unavailable evidence as invalid evidence.
2. Do not treat missing evidence as proof that the original decision was wrong.
3. A decision assurance result does not replace clinical review.
"""

from typing import Any, Dict, List, Tuple

from app.schemas.decision_assurance import (
    EvidenceAssuranceStatus,
    GovernanceDecisionRegisterRecord,
)
from app.schemas.decision_assurance_finding import (
    AssuranceFindingCategory,
    AssuranceFindingRecord,
    FindingSeverity,
)


class DecisionEvidenceAssuranceService:
    """Service evaluating decision-supporting evidence integrity and status."""

    def evaluate_evidence(
        self,
        decision: GovernanceDecisionRegisterRecord,
        assurance_id: str,
    ) -> Tuple[EvidenceAssuranceStatus, Dict[str, Any], List[AssuranceFindingRecord]]:
        """Evaluate evidence completeness, validity, and traceability."""
        findings: List[AssuranceFindingRecord] = []
        status = EvidenceAssuranceStatus.EVIDENCE_VALID

        if not decision.supporting_evidence_refs:
            status = EvidenceAssuranceStatus.EVIDENCE_MISSING
            findings.append(
                AssuranceFindingRecord(
                    decision_id=decision.decision_id,
                    assurance_id=assurance_id,
                    category=AssuranceFindingCategory.EVIDENCE_INCOMPLETE,
                    severity=FindingSeverity.HIGH,
                    title="Missing Supporting Evidence References",
                    description="The decision cites no supporting clinical or governance evidence artifacts.",
                    source_phase=decision.source_phase.value,
                    source_record_id=decision.source_record_id,
                    recommended_action="Attach primary clinical trial or governance evidence references.",
                )
            )
            details = {
                "evidence_status": status.value,
                "evidence_count": 0,
                "evidence_refs": [],
            }
            return status, details, findings

        has_invalidated = False
        has_stale = False
        has_unavailable = False

        for ref in decision.supporting_evidence_refs:
            ref_lower = ref.lower()
            if "invalid" in ref_lower or "withdrawn" in ref_lower:
                has_invalidated = True
                findings.append(
                    AssuranceFindingRecord(
                        decision_id=decision.decision_id,
                        assurance_id=assurance_id,
                        category=AssuranceFindingCategory.EVIDENCE_INVALIDATED,
                        severity=FindingSeverity.CRITICAL,
                        title="Invalidated or Withdrawn Evidence Cited",
                        description=f"Evidence artifact '{ref}' was invalidated or withdrawn post-decision.",
                        source_phase=decision.source_phase.value,
                        source_record_id=decision.source_record_id,
                        evidence_refs=[ref],
                        recommended_action="Trigger source workflow reassessment under current evidence.",
                    )
                )
            elif "stale" in ref_lower or "expired" in ref_lower:
                has_stale = True
                findings.append(
                    AssuranceFindingRecord(
                        decision_id=decision.decision_id,
                        assurance_id=assurance_id,
                        category=AssuranceFindingCategory.EVIDENCE_INCOMPLETE,
                        severity=FindingSeverity.MEDIUM,
                        title="Stale Evidence Reference",
                        description=f"Evidence artifact '{ref}' exceeds policy validity horizon.",
                        source_phase=decision.source_phase.value,
                        source_record_id=decision.source_record_id,
                        evidence_refs=[ref],
                        recommended_action="Update baseline clinical measurements and reverify.",
                    )
                )
            elif "unavail" in ref_lower:
                has_unavailable = True

        if has_invalidated:
            status = EvidenceAssuranceStatus.EVIDENCE_INVALIDATED
        elif has_stale:
            status = EvidenceAssuranceStatus.EVIDENCE_STALE
        elif has_unavailable:
            status = EvidenceAssuranceStatus.EVIDENCE_UNAVAILABLE
        else:
            status = EvidenceAssuranceStatus.EVIDENCE_VALID

        details = {
            "evidence_status": status.value,
            "evidence_count": len(decision.supporting_evidence_refs),
            "evidence_refs": decision.supporting_evidence_refs,
            "has_invalidated": has_invalidated,
            "has_stale": has_stale,
            "has_unavailable": has_unavailable,
        }

        return status, details, findings


# Global singleton
_global_evidence_service = DecisionEvidenceAssuranceService()


def get_decision_evidence_assurance_service() -> DecisionEvidenceAssuranceService:
    """Dependency provider for decision evidence assurance service."""
    return _global_evidence_service

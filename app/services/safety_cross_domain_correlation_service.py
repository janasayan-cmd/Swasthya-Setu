"""Phase 62: Safety Cross-Domain Correlation Service.

Identifies and links findings across distinct operational domains (safety controls,
workflows, versions, rollouts, facilities, assurance, incident references).
Enforces architectural rule: Cross-domain correlation does not establish causation.
"""

from typing import List, Optional

from app.schemas.safety_risk_assessment import (
    ConsolidatedSourceFindingReference,
    CrossDomainCorrelationLink,
    CrossDomainCorrelationOutcome,
    RiskUncertaintyState,
)


class SafetyCrossDomainCorrelationService:
    """Evaluates cross-domain linkages among consolidated findings."""

    def evaluate_correlations(
        self, findings: List[ConsolidatedSourceFindingReference]
    ) -> List[CrossDomainCorrelationLink]:
        """Correlate findings across operational domains."""
        if len(findings) < 2:
            return []

        links: List[CrossDomainCorrelationLink] = []

        for i in range(len(findings)):
            for j in range(i + 1, min(i + 4, len(findings))):
                f_a = findings[i]
                f_b = findings[j]

                # 1. Safety Control Domain Link
                ctrl_a = f_a.metadata.get("safety_control_id") or f_a.provenance.get("safety_control_id")
                ctrl_b = f_b.metadata.get("safety_control_id") or f_b.provenance.get("safety_control_id")
                if ctrl_a and ctrl_b and ctrl_a == ctrl_b:
                    links.append(
                        CrossDomainCorrelationLink(
                            source_domain=f"FINDING({f_a.finding_id})",
                            target_domain=f"FINDING({f_b.finding_id})",
                            dimension="SAFETY_CONTROL",
                            relationship=CrossDomainCorrelationOutcome.STRONGLY_RELATED,
                            confidence=0.9,
                            uncertainty=RiskUncertaintyState.LOW_UNCERTAINTY,
                            evidence_references=[f_a.finding_id, f_b.finding_id],
                            analytical_note="Cross-domain correlation indicates shared architectural context and does not prove causation.",
                        )
                    )

                # 2. Workflow / Release Domain Link
                wf_a = f_a.metadata.get("workflow") or f_a.provenance.get("workflow")
                wf_b = f_b.metadata.get("workflow") or f_b.provenance.get("workflow")
                if wf_a and wf_b and wf_a == wf_b:
                    links.append(
                        CrossDomainCorrelationLink(
                            source_domain=f"FINDING({f_a.finding_id})",
                            target_domain=f"FINDING({f_b.finding_id})",
                            dimension="WORKFLOW",
                            relationship=CrossDomainCorrelationOutcome.POSSIBLY_RELATED,
                            confidence=0.8,
                            uncertainty=RiskUncertaintyState.LOW_UNCERTAINTY,
                            evidence_references=[f_a.finding_id, f_b.finding_id],
                            analytical_note="Cross-domain correlation indicates shared architectural context and does not prove causation.",
                        )
                    )

                # 3. Rollout / Change Domain Link
                roll_a = f_a.metadata.get("rollout_id") or f_a.metadata.get("change_id")
                roll_b = f_b.metadata.get("rollout_id") or f_b.metadata.get("change_id")
                if roll_a and roll_b and roll_a == roll_b:
                    links.append(
                        CrossDomainCorrelationLink(
                            source_domain=f"FINDING({f_a.finding_id})",
                            target_domain=f"FINDING({f_b.finding_id})",
                            dimension="ROLLOUT_GOVERNANCE",
                            relationship=CrossDomainCorrelationOutcome.STRONGLY_RELATED,
                            confidence=0.95,
                            uncertainty=RiskUncertaintyState.LOW_UNCERTAINTY,
                            evidence_references=[f_a.finding_id, f_b.finding_id],
                            analytical_note="Cross-domain correlation indicates shared architectural context and does not prove causation.",
                        )
                    )

        return links


_cross_domain_service: Optional[SafetyCrossDomainCorrelationService] = None


def get_safety_cross_domain_correlation_service() -> SafetyCrossDomainCorrelationService:
    global _cross_domain_service
    if _cross_domain_service is None:
        _cross_domain_service = SafetyCrossDomainCorrelationService()
    return _cross_domain_service

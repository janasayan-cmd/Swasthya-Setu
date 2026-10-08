"""Phase 62: Safety Risk Characterization Service.

Evaluates consolidated risk contexts and assigns governed categorical characterizations.
Enforces non-negotiable architectural invariants:
- System Risk != Patient Harm
- Priority != Clinical Emergency
- No unexplained numeric clinical risk scores
"""

from typing import List, Optional

from app.schemas.safety_risk_assessment import (
    ConsolidatedRiskContext,
    ConsolidatedSourceFindingReference,
    CrossDomainCorrelationLink,
    EvidenceReconciliationState,
    GovernedRiskCharacterization,
    RiskPriority,
)


class SafetyRiskCharacterizationService:
    """Characterizes consolidated risk contexts using approved governance categories."""

    def characterize_risk(
        self,
        context: ConsolidatedRiskContext,
        findings: List[ConsolidatedSourceFindingReference],
        correlations: List[CrossDomainCorrelationLink],
        has_conflicts: bool,
    ) -> GovernedRiskCharacterization:
        """Assign governed operational categories, severity, and governance priority."""
        count = len(findings)

        # 1. Evaluate primary category
        has_control_issues = any(
            "safety_control" in f.finding_type.lower() or "failure" in f.finding_type.lower()
            for f in findings
        )
        if has_control_issues:
            primary_cat = "SAFETY_CONTROL_INTEGRITY"
        elif len(correlations) >= 2:
            primary_cat = "CROSS_DOMAIN_REGRESSION"
        else:
            primary_cat = "SURVEILLANCE_ANOMALY"

        # 2. Persistence & Recurrence
        persistence = "RECURRENT" if count >= 3 else ("EPISODIC" if count >= 2 else "ISOLATED")

        # 3. System Severity (strictly separated from patient harm)
        if any("critical" in f.finding_type.lower() or "severe" in f.finding_type.lower() for f in findings):
            system_sev = "CRITICAL"
        elif count >= 3 or has_control_issues:
            system_sev = "HIGH"
        else:
            system_sev = "MODERATE"

        # 4. Evidence Strength
        if count >= 3 and not has_conflicts:
            ev_strength = "STRONG"
        elif has_conflicts:
            ev_strength = "CONFLICTED"
        else:
            ev_strength = "MODERATE"

        # 5. Routing Priority
        if system_sev == "CRITICAL":
            priority = RiskPriority.CRITICAL_ESCALATION
        elif has_conflicts or (system_sev == "HIGH" and count >= 3):
            priority = RiskPriority.URGENT_GOVERNANCE_REVIEW
        elif system_sev == "HIGH":
            priority = RiskPriority.HIGH_PRIORITY_REVIEW
        elif count >= 2:
            priority = RiskPriority.REVIEW
        else:
            priority = RiskPriority.ROUTINE

        return GovernedRiskCharacterization(
            primary_category=primary_cat,
            persistence=persistence,
            recurrence_count=count,
            system_severity=system_sev,
            evidence_strength=ev_strength,
            exposure="CROSS_DOMAIN" if len(correlations) >= 1 else "LOCALIZED",
            priority=priority,
            notes=f"Characterized across {count} source findings. Priority reflects governance triage, not clinical urgency.",
        )


_characterization_service: Optional[SafetyRiskCharacterizationService] = None


def get_safety_risk_characterization_service() -> SafetyRiskCharacterizationService:
    global _characterization_service
    if _characterization_service is None:
        _characterization_service = SafetyRiskCharacterizationService()
    return _characterization_service

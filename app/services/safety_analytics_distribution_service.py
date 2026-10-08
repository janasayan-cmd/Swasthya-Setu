"""Phase 61: Safety Analytics Distribution Service.

Calculates signal distributions across severity, category, workflow,
and facility dimensions without exposing PHI.
"""

from collections import Counter
from typing import Dict, List, Optional

from app.schemas.safety_analytics import (
    DistributionFinding,
    EligibleSignalReference,
)


class SafetyAnalyticsDistributionService:
    """Computes categorical and severity distributions across surveillance signals."""

    def evaluate_distribution(
        self, signals: List[EligibleSignalReference]
    ) -> List[DistributionFinding]:
        """Compute signal breakdowns across non-PHI dimensions."""
        total = len(signals)
        if total == 0:
            return []

        findings: List[DistributionFinding] = []

        # 1. Severity Distribution
        sev_counts: Dict[str, int] = dict(Counter(s.governed_severity for s in signals))
        sev_pcts = {k: round((v / total) * 100.0, 2) for k, v in sev_counts.items()}
        findings.append(
            DistributionFinding(
                dimension="SEVERITY",
                counts=sev_counts,
                percentages=sev_pcts,
                total_signals=total,
            )
        )

        # 2. Classification / Category Distribution
        cat_counts: Dict[str, int] = dict(Counter(s.classification for s in signals))
        cat_pcts = {k: round((v / total) * 100.0, 2) for k, v in cat_counts.items()}
        findings.append(
            DistributionFinding(
                dimension="CATEGORY",
                counts=cat_counts,
                percentages=cat_pcts,
                total_signals=total,
            )
        )

        # 3. Facility Distribution (if present)
        fac_list = [
            str(s.provenance.get("facility_id") or s.metadata.get("facility_id"))
            for s in signals
            if s.provenance.get("facility_id") or s.metadata.get("facility_id")
        ]
        if fac_list:
            fac_counts: Dict[str, int] = dict(Counter(fac_list))
            fac_pcts = {k: round((v / len(fac_list)) * 100.0, 2) for k, v in fac_counts.items()}
            findings.append(
                DistributionFinding(
                    dimension="FACILITY",
                    counts=fac_counts,
                    percentages=fac_pcts,
                    total_signals=len(fac_list),
                )
            )

        # 4. Workflow Distribution (if present)
        wf_list = [
            str(s.metadata.get("workflow") or s.provenance.get("workflow"))
            for s in signals
            if s.metadata.get("workflow") or s.provenance.get("workflow")
        ]
        if wf_list:
            wf_counts: Dict[str, int] = dict(Counter(wf_list))
            wf_pcts = {k: round((v / len(wf_list)) * 100.0, 2) for k, v in wf_counts.items()}
            findings.append(
                DistributionFinding(
                    dimension="WORKFLOW",
                    counts=wf_counts,
                    percentages=wf_pcts,
                    total_signals=len(wf_list),
                )
            )

        return findings


_distribution_service: Optional[SafetyAnalyticsDistributionService] = None


def get_safety_analytics_distribution_service() -> SafetyAnalyticsDistributionService:
    global _distribution_service
    if _distribution_service is None:
        _distribution_service = SafetyAnalyticsDistributionService()
    return _distribution_service

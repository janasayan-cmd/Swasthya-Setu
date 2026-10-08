"""Phase 61: Safety Analytics Concentration Service.

Detects disproportionate concentration of signals within permitted scopes.
Critical architectural rule: Concentration indicates distribution only and does not establish causality.
"""

from collections import Counter
from typing import List, Optional

from app.schemas.safety_analytics import (
    ConcentrationFinding,
    EligibleSignalReference,
)


class SafetyAnalyticsConcentrationService:
    """Evaluates whether signals are disproportionately concentrated in specific scopes."""

    def evaluate_concentration(
        self, signals: List[EligibleSignalReference]
    ) -> List[ConcentrationFinding]:
        """Detect disproportionate concentration without asserting causality."""
        total = len(signals)
        if total < 2:
            return []

        findings: List[ConcentrationFinding] = []

        # 1. Facility Concentration
        facs = [
            str(s.provenance.get("facility_id") or s.metadata.get("facility_id"))
            for s in signals
            if s.provenance.get("facility_id") or s.metadata.get("facility_id")
        ]
        if facs:
            counts = Counter(facs)
            top_fac, count = counts.most_common(1)[0]
            prop = count / len(facs)
            findings.append(
                ConcentrationFinding(
                    dimension="FACILITY",
                    concentrated_key=top_fac,
                    proportion=round(prop, 4),
                    is_disproportionate=prop >= 0.5 and count >= 3,
                    benchmark_proportion=0.33,
                    analytical_note="Concentration indicates analytical distribution and does not establish facility causality.",
                )
            )

        # 2. Safety Control Concentration
        ctrls = [
            str(s.metadata.get("safety_control_id") or s.provenance.get("safety_control_id"))
            for s in signals
            if s.metadata.get("safety_control_id") or s.provenance.get("safety_control_id")
        ]
        if ctrls:
            counts = Counter(ctrls)
            top_ctrl, count = counts.most_common(1)[0]
            prop = count / len(ctrls)
            findings.append(
                ConcentrationFinding(
                    dimension="SAFETY_CONTROL",
                    concentrated_key=top_ctrl,
                    proportion=round(prop, 4),
                    is_disproportionate=prop >= 0.5 and count >= 3,
                    benchmark_proportion=0.25,
                    analytical_note="Concentration indicates analytical distribution and does not establish safety control causality.",
                )
            )

        # 3. Workflow Concentration
        wfs = [
            str(s.metadata.get("workflow") or s.provenance.get("workflow"))
            for s in signals
            if s.metadata.get("workflow") or s.provenance.get("workflow")
        ]
        if wfs:
            counts = Counter(wfs)
            top_wf, count = counts.most_common(1)[0]
            prop = count / len(wfs)
            findings.append(
                ConcentrationFinding(
                    dimension="WORKFLOW",
                    concentrated_key=top_wf,
                    proportion=round(prop, 4),
                    is_disproportionate=prop >= 0.5 and count >= 3,
                    benchmark_proportion=0.33,
                    analytical_note="Concentration indicates analytical distribution and does not establish workflow causality.",
                )
            )

        return findings


_concentration_service: Optional[SafetyAnalyticsConcentrationService] = None


def get_safety_analytics_concentration_service() -> SafetyAnalyticsConcentrationService:
    global _concentration_service
    if _concentration_service is None:
        _concentration_service = SafetyAnalyticsConcentrationService()
    return _concentration_service

"""Phase 61: Safety Analytics Recurrence Service.

Evaluates repeated occurrences of materially related signals across
safety controls, workflows, categories, facilities, and versions.
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from app.schemas.safety_analytics import (
    AnalyticalUncertaintyState,
    EligibleSignalReference,
    RecurrenceFinding,
    RecurrenceState,
)


class SafetyAnalyticsRecurrenceService:
    """Evaluates longitudinal signal recurrence patterns."""

    def evaluate_recurrence(
        self, signals: List[EligibleSignalReference]
    ) -> List[RecurrenceFinding]:
        """Detect repeated signal occurrences across operational dimensions."""
        if not signals:
            return [
                RecurrenceFinding(
                    dimension="OVERALL",
                    dimension_key="ALL",
                    state=RecurrenceState.INSUFFICIENT_DATA,
                    signal_count=0,
                    signal_ids=[],
                    uncertainty=AnalyticalUncertaintyState.INSUFFICIENT_DATA,
                    notes="No eligible signals provided for recurrence analysis",
                )
            ]

        findings: List[RecurrenceFinding] = []

        # Dimensions to evaluate: classification, safety_control_id, workflow, facility
        groups: Dict[str, Dict[str, List[EligibleSignalReference]]] = {
            "CATEGORY": defaultdict(list),
            "SAFETY_CONTROL": defaultdict(list),
            "WORKFLOW": defaultdict(list),
            "FACILITY": defaultdict(list),
        }

        for sig in signals:
            groups["CATEGORY"][sig.classification].append(sig)

            ctrl = sig.metadata.get("safety_control_id") or sig.provenance.get("safety_control_id")
            if ctrl:
                groups["SAFETY_CONTROL"][str(ctrl)].append(sig)

            wf = sig.metadata.get("workflow") or sig.provenance.get("workflow")
            if wf:
                groups["WORKFLOW"][str(wf)].append(sig)

            fac = sig.provenance.get("facility_id") or sig.metadata.get("facility_id")
            if fac:
                groups["FACILITY"][str(fac)].append(sig)

        for dim, key_dict in groups.items():
            for key, sig_list in key_dict.items():
                count = len(sig_list)
                if count >= 5:
                    state = RecurrenceState.HIGH_RECURRENCE
                elif count >= 3:
                    state = RecurrenceState.RECURRENT
                elif count == 2:
                    state = RecurrenceState.POSSIBLE_RECURRENCE
                else:
                    state = RecurrenceState.NOT_RECURRING

                sorted_sigs = sorted(sig_list, key=lambda s: s.observed_at)
                first_obs = sorted_sigs[0].observed_at if sorted_sigs else None
                last_obs = sorted_sigs[-1].observed_at if sorted_sigs else None

                findings.append(
                    RecurrenceFinding(
                        dimension=dim,
                        dimension_key=f"{dim}:{key}",
                        state=state,
                        signal_count=count,
                        signal_ids=[s.signal_id for s in sorted_sigs],
                        first_observed_at=first_obs,
                        last_observed_at=last_obs,
                        confidence=1.0 if count >= 3 else 0.8,
                        uncertainty=(
                            AnalyticalUncertaintyState.LOW_UNCERTAINTY
                            if count >= 3
                            else AnalyticalUncertaintyState.MODERATE_UNCERTAINTY
                        ),
                        notes=f"Observed {count} occurrences in {dim.lower()} {key}",
                    )
                )

        return findings


_recurrence_service: Optional[SafetyAnalyticsRecurrenceService] = None


def get_safety_analytics_recurrence_service() -> SafetyAnalyticsRecurrenceService:
    global _recurrence_service
    if _recurrence_service is None:
        _recurrence_service = SafetyAnalyticsRecurrenceService()
    return _recurrence_service

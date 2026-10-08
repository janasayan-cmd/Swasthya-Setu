"""Phase 61: Safety Analytics Trend Service.

Detects directional changes and rate shifts across longitudinal surveillance windows.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.schemas.safety_analytics import (
    AnalyticalUncertaintyState,
    EligibleSignalReference,
    ObservationWindow,
    TrendDirection,
    TrendFinding,
)


class SafetyAnalyticsTrendService:
    """Evaluates directional trend changes over surveillance periods."""

    def evaluate_trends(
        self,
        signals: List[EligibleSignalReference],
        window: ObservationWindow,
    ) -> List[TrendFinding]:
        """Compute signal rate trends comparing recent window against baseline."""
        window_hours = window.duration_hours or 720.0

        if not signals:
            return [
                TrendFinding(
                    metric_name="signal_frequency",
                    direction=TrendDirection.INSUFFICIENT_DATA,
                    baseline_value=0.0,
                    observed_value=0.0,
                    percentage_change=0.0,
                    observation_window_hours=window_hours,
                    confidence=0.0,
                    uncertainty=AnalyticalUncertaintyState.INSUFFICIENT_DATA,
                    method="EMPTY_DATASET_EVALUATION",
                    evidence_references=[],
                )
            ]

        # Divide signals by time window midpoint if span > 0, else count half
        sorted_sigs = sorted(signals, key=lambda s: s.observed_at)
        total_count = len(sorted_sigs)

        time_span = (sorted_sigs[-1].observed_at - sorted_sigs[0].observed_at).total_seconds()
        if time_span > 0:
            time_midpoint = sorted_sigs[0].observed_at + (sorted_sigs[-1].observed_at - sorted_sigs[0].observed_at) / 2
            baseline_sigs = [s for s in sorted_sigs if s.observed_at <= time_midpoint]
            observed_sigs = [s for s in sorted_sigs if s.observed_at > time_midpoint]
        else:
            half_point = total_count // 2
            baseline_sigs = sorted_sigs[:half_point]
            observed_sigs = sorted_sigs[half_point:]

        baseline_val = float(len(baseline_sigs))
        observed_val = float(len(observed_sigs))

        # Metric 1: Overall Signal Rate Trend
        if baseline_val == 0.0:
            if observed_val > 0.0:
                direction = TrendDirection.SPIKE
                pct_change = 100.0
            else:
                direction = TrendDirection.STABLE
                pct_change = 0.0
        else:
            pct_change = ((observed_val - baseline_val) / baseline_val) * 100.0
            if pct_change >= 100.0:
                direction = TrendDirection.SPIKE
            elif pct_change > 15.0:
                direction = TrendDirection.INCREASING
            elif pct_change < -15.0:
                direction = TrendDirection.DECREASING
            else:
                direction = TrendDirection.STABLE

        overall_finding = TrendFinding(
            metric_name="overall_signal_rate",
            direction=direction,
            baseline_value=baseline_val,
            observed_value=observed_val,
            percentage_change=round(pct_change, 2),
            observation_window_hours=window_hours,
            confidence=0.9 if total_count >= 6 else 0.7,
            uncertainty=(
                AnalyticalUncertaintyState.LOW_UNCERTAINTY
                if total_count >= 6
                else AnalyticalUncertaintyState.MODERATE_UNCERTAINTY
            ),
            method="HALF_WINDOW_COMPARISON",
            evidence_references=[s.signal_id for s in sorted_sigs],
        )

        # Metric 2: Critical / High Severity Trend
        crit_base = float(sum(1 for s in baseline_sigs if s.governed_severity in ("HIGH", "CRITICAL")))
        crit_obs = float(sum(1 for s in observed_sigs if s.governed_severity in ("HIGH", "CRITICAL")))

        if crit_base == 0.0:
            crit_dir = TrendDirection.SPIKE if crit_obs > 0.0 else TrendDirection.STABLE
            crit_pct = 100.0 if crit_obs > 0.0 else 0.0
        else:
            crit_pct = ((crit_obs - crit_base) / crit_base) * 100.0
            if crit_pct >= 100.0:
                crit_dir = TrendDirection.SPIKE
            elif crit_pct > 15.0:
                crit_dir = TrendDirection.INCREASING
            elif crit_pct < -15.0:
                crit_dir = TrendDirection.DECREASING
            else:
                crit_dir = TrendDirection.STABLE

        crit_finding = TrendFinding(
            metric_name="high_severity_signal_rate",
            direction=crit_dir,
            baseline_value=crit_base,
            observed_value=crit_obs,
            percentage_change=round(crit_pct, 2),
            observation_window_hours=window_hours,
            confidence=0.95 if (crit_base + crit_obs) >= 4 else 0.75,
            uncertainty=(
                AnalyticalUncertaintyState.LOW_UNCERTAINTY
                if (crit_base + crit_obs) >= 4
                else AnalyticalUncertaintyState.MODERATE_UNCERTAINTY
            ),
            method="HIGH_SEVERITY_RATE_COMPARISON",
            evidence_references=[
                s.signal_id for s in sorted_sigs if s.governed_severity in ("HIGH", "CRITICAL")
            ],
        )

        return [overall_finding, crit_finding]


_trend_service: Optional[SafetyAnalyticsTrendService] = None


def get_safety_analytics_trend_service() -> SafetyAnalyticsTrendService:
    global _trend_service
    if _trend_service is None:
        _trend_service = SafetyAnalyticsTrendService()
    return _trend_service

"""Phase 61: Safety Analytics Pattern Service.

Detects multi-signal surveillance patterns across controls, workflows,
facilities, versions, and temporal clusters.
"""

from collections import defaultdict
from typing import List, Optional

from app.schemas.safety_analytics import (
    AnalyticalUncertaintyState,
    EligibleSignalReference,
    ObservationWindow,
    PatternClass,
    PatternLifecycleState,
    SafetyPatternFinding,
)


class SafetyAnalyticsPatternService:
    """Identifies multi-signal clusters and surveillance patterns."""

    def detect_patterns(
        self,
        signals: List[EligibleSignalReference],
        window: ObservationWindow,
    ) -> List[SafetyPatternFinding]:
        """Detect multi-signal patterns from eligible surveillance signals."""
        if not signals:
            return []

        patterns: List[SafetyPatternFinding] = []
        window_hours = window.duration_hours or 720.0

        # 1. Safety Control Cluster / Repeated Failures
        ctrl_map = defaultdict(list)
        for s in signals:
            ctrl = s.metadata.get("safety_control_id") or s.provenance.get("safety_control_id")
            if ctrl:
                ctrl_map[str(ctrl)].append(s)

        for ctrl_id, sig_list in ctrl_map.items():
            if len(sig_list) >= 2:
                has_critical = any(s.governed_severity in ("HIGH", "CRITICAL") for s in sig_list)
                pat_class = (
                    PatternClass.REPEATED_FAILURE
                    if has_critical
                    else PatternClass.SAFETY_CONTROL_CLUSTER
                )
                patterns.append(
                    SafetyPatternFinding(
                        pattern_class=pat_class,
                        lifecycle_state=PatternLifecycleState.DETECTED,
                        source_signal_ids=[s.signal_id for s in sig_list],
                        dimensions=[f"SAFETY_CONTROL:{ctrl_id}"],
                        observation_window_hours=window_hours,
                        confidence=0.9 if len(sig_list) >= 3 else 0.75,
                        uncertainty=(
                            AnalyticalUncertaintyState.LOW_UNCERTAINTY
                            if len(sig_list) >= 3
                            else AnalyticalUncertaintyState.MODERATE_UNCERTAINTY
                        ),
                        requires_human_review=True,
                        evidence_references=[s.signal_id for s in sig_list],
                        notes=f"Cluster of {len(sig_list)} signals observed on safety control {ctrl_id}",
                    )
                )

        # 2. Workflow Cluster
        wf_map = defaultdict(list)
        for s in signals:
            wf = s.metadata.get("workflow") or s.provenance.get("workflow")
            if wf:
                wf_map[str(wf)].append(s)

        for wf_id, sig_list in wf_map.items():
            if len(sig_list) >= 3:
                patterns.append(
                    SafetyPatternFinding(
                        pattern_class=PatternClass.WORKFLOW_CLUSTER,
                        lifecycle_state=PatternLifecycleState.DETECTED,
                        source_signal_ids=[s.signal_id for s in sig_list],
                        dimensions=[f"WORKFLOW:{wf_id}"],
                        observation_window_hours=window_hours,
                        confidence=0.85,
                        uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                        requires_human_review=True,
                        evidence_references=[s.signal_id for s in sig_list],
                        notes=f"Cluster of {len(sig_list)} signals in workflow {wf_id}",
                    )
                )

        # 3. Temporal Cluster (Rapid burst >= 3 signals within short window)
        if len(signals) >= 3:
            sorted_sigs = sorted(signals, key=lambda s: s.observed_at)
            time_delta = (sorted_sigs[-1].observed_at - sorted_sigs[0].observed_at).total_seconds()
            if time_delta < 86400:  # Within 24 hours
                patterns.append(
                    SafetyPatternFinding(
                        pattern_class=PatternClass.TEMPORAL_CLUSTER,
                        lifecycle_state=PatternLifecycleState.DETECTED,
                        source_signal_ids=[s.signal_id for s in sorted_sigs],
                        dimensions=["TIME_BURST_24H"],
                        observation_window_hours=24.0,
                        confidence=0.9,
                        uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                        requires_human_review=True,
                        evidence_references=[s.signal_id for s in sorted_sigs],
                        notes=f"Rapid temporal cluster of {len(sorted_sigs)} signals within 24 hours",
                    )
                )

        # 4. Post-change / Rollout Pattern (signals associated with rollout_id or change_id)
        rollout_sigs = [
            s
            for s in signals
            if s.metadata.get("rollout_id")
            or s.metadata.get("change_id")
            or s.provenance.get("rollout_id")
        ]
        if len(rollout_sigs) >= 2:
            patterns.append(
                SafetyPatternFinding(
                    pattern_class=PatternClass.POST_CHANGE_PATTERN,
                    lifecycle_state=PatternLifecycleState.DETECTED,
                    source_signal_ids=[s.signal_id for s in rollout_sigs],
                    dimensions=["ROLLOUT_SURVEILLANCE"],
                    observation_window_hours=window_hours,
                    confidence=0.85,
                    uncertainty=AnalyticalUncertaintyState.LOW_UNCERTAINTY,
                    requires_human_review=True,
                    evidence_references=[s.signal_id for s in rollout_sigs],
                    notes=f"Post-change cluster of {len(rollout_sigs)} signals linked to active rollout",
                )
            )

        return patterns


_pattern_service: Optional[SafetyAnalyticsPatternService] = None


def get_safety_analytics_pattern_service() -> SafetyAnalyticsPatternService:
    global _pattern_service
    if _pattern_service is None:
        _pattern_service = SafetyAnalyticsPatternService()
    return _pattern_service

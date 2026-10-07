"""Phase 59: Safety Threshold & Pattern Evaluation Service.

Evaluates surveillance signals against governed safety thresholds,
generating reopen triggers and cross-phase escalation records without making causal claims.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from app.schemas.safety_monitoring import (
    MonitoringLifecycleState,
    MonitoringTriggerRecord,
    SafetyMonitoringRecord,
    SurveillanceEvaluationResponse,
    ThresholdEvaluationStatus,
)


class SafetyThresholdService:
    """Evaluates surveillance signals against governed thresholds and triggers."""

    @staticmethod
    def evaluate_surveillance(
        monitoring: SafetyMonitoringRecord,
    ) -> Tuple[SurveillanceEvaluationResponse, List[MonitoringTriggerRecord]]:
        """Evaluate current surveillance health against configured thresholds."""
        now = datetime.now(timezone.utc)
        cfg = monitoring.threshold_config or {}
        max_crit = cfg.get("max_critical_signals", 0)
        max_warn = cfg.get("max_warning_signals", 5)

        crit_count = sum(1 for s in monitoring.signals if s.severity == "CRITICAL")
        warn_count = sum(1 for s in monitoring.signals if s.severity in ("HIGH", "WARNING"))

        # Detailed threshold list evaluation
        threshold_evaluations: List[Dict[str, Any]] = []
        configured_thresholds = monitoring.thresholds or [
            {
                "metric_name": "safety_control_failure_count",
                "threshold_type": "COUNT",
                "warning_threshold": float(max_warn),
                "critical_threshold": float(max_crit or 1.0),
            }
        ]

        any_exceeded = False
        any_reached = False

        for th in configured_thresholds:
            metric = th.get("metric_name", "signals")
            crit_val = float(th.get("critical_threshold", 1.0))
            warn_val = float(th.get("warning_threshold", 5.0))

            if len(monitoring.signals) == 0:
                th_status = ThresholdEvaluationStatus.INSUFFICIENT_DATA
                val = 0.0
            elif "failure" in metric.lower() or "safety_control" in metric.lower():
                val = float(crit_count)
                if val >= crit_val:
                    th_status = ThresholdEvaluationStatus.THRESHOLD_EXCEEDED
                    any_exceeded = True
                elif val >= warn_val:
                    th_status = ThresholdEvaluationStatus.THRESHOLD_REACHED
                    any_reached = True
                else:
                    th_status = ThresholdEvaluationStatus.NOT_TRIGGERED
            elif "error_rate" in metric.lower():
                total = len(monitoring.signals)
                errors = sum(1 for s in monitoring.signals if s.severity in ("HIGH", "CRITICAL"))
                val = (errors / total) if total > 0 else 0.0
                if val >= crit_val:
                    th_status = ThresholdEvaluationStatus.THRESHOLD_EXCEEDED
                    any_exceeded = True
                elif val >= warn_val:
                    th_status = ThresholdEvaluationStatus.THRESHOLD_REACHED
                    any_reached = True
                else:
                    th_status = ThresholdEvaluationStatus.NOT_TRIGGERED
            else:
                val = float(warn_count + crit_count)
                if val >= crit_val:
                    th_status = ThresholdEvaluationStatus.THRESHOLD_EXCEEDED
                    any_exceeded = True
                elif val >= warn_val:
                    th_status = ThresholdEvaluationStatus.THRESHOLD_REACHED
                    any_reached = True
                else:
                    th_status = ThresholdEvaluationStatus.NOT_TRIGGERED

            threshold_evaluations.append(
                {
                    "metric_name": metric,
                    "status": th_status,
                    "current_value": val,
                    "warning_threshold": warn_val,
                    "critical_threshold": crit_val,
                }
            )

        new_triggers: List[MonitoringTriggerRecord] = []

        # 1. Critical Threshold Check -> Triggers Reopen & Escalation
        if any_exceeded or (crit_count > max_crit and len(monitoring.signals) > 0):
            status = ThresholdEvaluationStatus.THRESHOLD_EXCEEDED
            rec_action = "IMMEDIATE_REOPEN_REVIEW_AND_ESCALATION"

            # Create Phase 58 Reopen Trigger
            reopen_trg = MonitoringTriggerRecord(
                trigger_type="REOPEN_TRIGGER",
                target_destination="Phase 58",
                target_phase="PHASE_58",
                lifecycle_state="REOPEN_REQUIRED",
                reason=f"Surveillance detected critical safety signals exceeding threshold ({crit_count} >= {max_crit})",
                signal_references=[s.signal_id for s in monitoring.signals if s.severity == "CRITICAL"],
                triggered_at=now,
                status="DETECTED",
            )
            new_triggers.append(reopen_trg)

            # Create Phase 49 Incident Escalation Trigger
            esc_trg = MonitoringTriggerRecord(
                trigger_type="ESCALATION_TRIGGER",
                target_destination="Phase 49",
                target_phase="PHASE_49",
                lifecycle_state="ESCALATION_REQUIRED",
                reason=f"Critical post-closure safety signal threshold breach: {crit_count} critical events observed",
                signal_references=[s.signal_id for s in monitoring.signals if s.severity == "CRITICAL"],
                triggered_at=now,
                status="DETECTED",
            )
            new_triggers.append(esc_trg)

            monitoring.lifecycle_state = MonitoringLifecycleState.REOPEN_REQUIRED

        # 2. Warning Threshold Check -> Human Review Required
        elif any_reached or warn_count >= max_warn:
            status = ThresholdEvaluationStatus.THRESHOLD_REACHED
            rec_action = "HUMAN_SURVEILLANCE_REVIEW_REQUIRED"
            monitoring.lifecycle_state = MonitoringLifecycleState.REVIEW_REQUIRED

        # 3. Insufficient Data or Nominal
        elif len(monitoring.signals) == 0:
            status = ThresholdEvaluationStatus.NOT_TRIGGERED
            rec_action = "INSUFFICIENT_DATA_AWAITING_OBSERVATION"
        else:
            status = ThresholdEvaluationStatus.NOT_TRIGGERED
            rec_action = "CONTINUE_MONITORING"
            if monitoring.lifecycle_state in {
                MonitoringLifecycleState.REGISTERED,
                MonitoringLifecycleState.PENDING,
            }:
                monitoring.lifecycle_state = MonitoringLifecycleState.OBSERVING

        # Append newly generated triggers
        monitoring.triggers.extend(new_triggers)

        resp = SurveillanceEvaluationResponse(
            monitoring_id=monitoring.monitoring_id,
            lifecycle_state=monitoring.lifecycle_state,
            evaluation_status=status,
            threshold_triggered=status in (ThresholdEvaluationStatus.THRESHOLD_REACHED, ThresholdEvaluationStatus.THRESHOLD_EXCEEDED),
            critical_signals_count=crit_count,
            warning_signals_count=warn_count,
            recommended_action=rec_action,
            threshold_evaluations=threshold_evaluations,
            active_triggers=monitoring.triggers,
        )

        return resp, new_triggers

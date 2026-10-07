"""Phase 52: Safety Assurance Metrics Service.

Thread-safe in-process telemetry for Phase 52 assurance operations.

Tracks:
  - assurance_evaluations_total
  - assurance_evaluations_failed_total
  - assurance_evaluations_degraded_total
  - assurance_evaluations_insufficient_evidence_total
  - assurance_review_pending_total
  - safety_control_bypass_total
  - safety_control_regression_total
  - assurance_job_duration
  - assurance_evidence_collection_duration
  - assurance_provider_failure_total
  - assurance_reassessment_total

Metrics MUST NOT contain unnecessary PHI.
Phase 18 remains authoritative for operational telemetry infrastructure.
Phase 52 exposes these counters for observability probes.
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List


class SafetyAssuranceMetricsService:
    """Thread-safe telemetry instrumentation for Phase 52 assurance operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {
            "assurance_evaluations_total": 0,
            "assurance_evaluations_scheduled_total": 0,
            "assurance_evaluations_completed_total": 0,
            "assurance_evaluations_failed_total": 0,
            "assurance_evaluations_degraded_total": 0,
            "assurance_evaluations_insufficient_evidence_total": 0,
            "assurance_evaluations_cancelled_total": 0,
            "assurance_evaluations_blocked_total": 0,
            "assurance_review_pending_total": 0,
            "assurance_review_completed_total": 0,
            "safety_control_bypass_total": 0,
            "safety_control_regression_total": 0,
            "assurance_provider_failure_total": 0,
            "assurance_reassessment_total": 0,
            "assurance_evidence_insufficient_total": 0,
            "assurance_configuration_drift_total": 0,
            "assurance_version_conflict_total": 0,
            "assurance_idempotency_hit_total": 0,
            "assurance_concurrency_conflict_total": 0,
        }
        self._latencies: Dict[str, List[float]] = {
            "assurance_job_duration_seconds": [],
            "assurance_evidence_collection_duration_seconds": [],
            "assurance_effectiveness_evaluation_duration_seconds": [],
        }

    def increment(self, metric_name: str, count: int = 1) -> None:
        """Increment a counter metric."""
        with self._lock:
            if metric_name in self._counters:
                self._counters[metric_name] += count
            else:
                self._counters[metric_name] = count

    def record_latency(self, metric_name: str, duration_seconds: float) -> None:
        """Record a latency measurement. Bounded to 1000 samples per metric."""
        with self._lock:
            sample_list = self._latencies.setdefault(metric_name, [])
            if len(sample_list) > 1000:
                sample_list.pop(0)
            sample_list.append(duration_seconds)

    def get_summary(self) -> Dict[str, Any]:
        """Return non-PHI telemetry summary for observability probes."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "latency_samples": {k: len(v) for k, v in self._latencies.items()},
                "as_of": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "These are operational assurance metrics only. "
                    "They do not represent clinical safety probability or risk elimination."
                ),
            }

    def reset(self) -> None:
        """Reset metric state for test isolation."""
        with self._lock:
            for k in self._counters:
                self._counters[k] = 0
            for k in self._latencies:
                self._latencies[k].clear()


# Global singleton
safety_assurance_metrics_service = SafetyAssuranceMetricsService()

"""Phase 51: Safety Governance Observability & Telemetry Metrics Service.

Tracks operational safety governance counters, latencies, failure rates,
stale approvals, and rollbacks without logging PHI or clinical narratives.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, Any


class SafetyGovernanceMetricsService:
    """Thread-safe telemetry instrumentation for clinical safety governance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {
            "risk_created_count": 0,
            "risk_assessed_count": 0,
            "risk_accepted_count": 0,
            "risk_closed_count": 0,
            "risk_reopened_count": 0,
            "reassessment_count": 0,
            "expired_acceptance_count": 0,
            "stale_approval_count": 0,
            "change_requested_count": 0,
            "change_approved_count": 0,
            "implementation_failure_count": 0,
            "validation_failure_count": 0,
            "rollback_count": 0,
        }
        self._latencies: Dict[str, list] = {
            "assessment_duration_seconds": [],
            "approval_latency_seconds": [],
            "governance_workflow_duration_seconds": [],
        }

    def increment(self, metric_name: str, count: int = 1) -> None:
        """Increment a bounded telemetry counter."""
        with self._lock:
            if metric_name in self._counters:
                self._counters[metric_name] += count
            else:
                self._counters[metric_name] = count

    def record_latency(self, metric_name: str, duration_seconds: float) -> None:
        """Record bounded latency measurement."""
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
                "recorded_latencies_samples": {k: len(v) for k, v in self._latencies.items()},
            }

    def reset(self) -> None:
        """Reset metric state for test isolation."""
        with self._lock:
            for k in self._counters:
                self._counters[k] = 0
            for k in self._latencies:
                self._latencies[k].clear()


# Global singleton metrics service
safety_governance_metrics_service = SafetyGovernanceMetricsService()

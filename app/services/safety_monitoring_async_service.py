"""Phase 59: Safety Monitoring Asynchronous Job Orchestrator (Phase 22 Integration).

Orchestrates background processing of scheduled surveillance polling,
threshold evaluation, and checkpoint analysis without carrying PHI.
"""

from typing import Any, Dict, Optional

from app.schemas.safety_monitoring import (
    CheckpointCategory,
    EvaluateSurveillanceRequest,
    RunCheckpointRequest,
)
from app.services.safety_monitoring_service import (
    SafetyMonitoringService,
    get_safety_monitoring_service,
)


class SafetyMonitoringAsyncService:
    """Manages asynchronous surveillance task execution."""

    def __init__(self, monitoring_service: Optional[SafetyMonitoringService] = None) -> None:
        self.monitoring_service = monitoring_service or get_safety_monitoring_service()

    async def execute_background_surveillance_evaluation(
        self,
        monitoring_id: str,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        """Execute surveillance threshold evaluation in background worker."""
        req = EvaluateSurveillanceRequest(force_reevaluation=True)
        resp = self.monitoring_service.evaluate(
            monitoring_id=monitoring_id,
            request=req,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {
            "status": "COMPLETED",
            "monitoring_id": monitoring_id,
            "evaluation_status": resp.evaluation_status.value,
            "threshold_triggered": resp.threshold_triggered,
        }

    async def execute_background_checkpoint(
        self,
        monitoring_id: str,
        category: CheckpointCategory,
        observed_state: str,
        actor_id: str,
        actor_role: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute checkpoint evaluation in background worker."""
        req = RunCheckpointRequest(
            category=category,
            observed_state=observed_state,
            notes=notes,
        )
        cp = self.monitoring_service.run_checkpoint(
            monitoring_id=monitoring_id,
            request=req,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {
            "status": "COMPLETED",
            "monitoring_id": monitoring_id,
            "checkpoint_id": cp.checkpoint_id,
            "outcome": cp.outcome.value,
        }

    async def run_scheduled_surveillance_cycle(
        self,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Runs scheduled periodic surveillance cycle across active monitoring contexts."""
        active_list = self.monitoring_service.list_active(organization_id=organization_id)
        processed = 0
        for mon in active_list:
            try:
                # Trigger collection & evaluation
                self.monitoring_service.collect(mon.monitoring_id, actor_id="async-worker", actor_role="SYSTEM")
                processed += 1
            except Exception:
                continue
        return {
            "status": "COMPLETED",
            "organization_id": organization_id,
            "processed_count": processed,
        }


_async_service_instance: Optional[SafetyMonitoringAsyncService] = None


def get_safety_monitoring_async_service() -> SafetyMonitoringAsyncService:
    """Retrieve singleton instance of SafetyMonitoringAsyncService."""
    global _async_service_instance
    if _async_service_instance is None:
        _async_service_instance = SafetyMonitoringAsyncService()
    return _async_service_instance

"""Phase 60: Safety Triage Asynchronous Job Orchestrator (Phase 22 Integration).

Orchestrates background evaluation, reanalysis, and batch triage processing
without carrying unnecessary PHI in worker contexts.
"""

from typing import Any, Dict, Optional

from app.schemas.safety_triage import EvaluateTriageRequest
from app.services.safety_triage_service import (
    SafetyTriageService,
    get_safety_triage_service,
)


class SafetyTriageAsyncService:
    """Manages asynchronous safety triage task execution."""

    def __init__(self, triage_service: Optional[SafetyTriageService] = None) -> None:
        self.triage_service = triage_service or get_safety_triage_service()

    async def execute_background_triage_evaluation(
        self,
        triage_id: str,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        """Execute complete triage evaluation in background worker."""
        req = EvaluateTriageRequest(force_reevaluation=True)
        resp = self.triage_service.evaluate_triage(
            triage_id=triage_id,
            request=req,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {
            "status": "COMPLETED",
            "triage_id": triage_id,
            "lifecycle_state": resp.lifecycle_state.value,
            "governed_severity": resp.governed_severity.value,
            "priority": resp.priority.value,
            "requires_human_review": resp.requires_human_review,
        }

    async def run_scheduled_triage_cycle(
        self,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Runs scheduled periodic triage cycle across unrouted triage contexts."""
        triage_list = self.triage_service.list_triage(organization_id=organization_id)
        processed = 0
        for trg in triage_list:
            try:
                self.triage_service.evaluate_triage(
                    triage_id=trg.triage_id,
                    request=EvaluateTriageRequest(force_reevaluation=True),
                    actor_id="async-worker",
                    actor_role="SYSTEM",
                )
                processed += 1
            except Exception:
                continue
        return {
            "status": "COMPLETED",
            "organization_id": organization_id,
            "processed_count": processed,
        }


_async_service_instance: Optional[SafetyTriageAsyncService] = None


def get_safety_triage_async_service() -> SafetyTriageAsyncService:
    """Retrieve global singleton instance of SafetyTriageAsyncService."""
    global _async_service_instance
    if _async_service_instance is None:
        _async_service_instance = SafetyTriageAsyncService()
    return _async_service_instance

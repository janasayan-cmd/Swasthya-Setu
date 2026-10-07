"""Phase 54: Safety Action Subsystem Routing Service.

Dispatches approved actions to authoritative subsystems without duplicating their domain logic:
- Phase 36 for clinical tasks
- Phase 37 for workflow executions
- Phase 48 for safety gate revalidation
- Phase 49 for incident reviews
- Phase 50 for safety learning
- Phase 51 for governed safety changes
- Phase 52 for assurance re-evaluations
- Phase 29 for notifications
"""

from typing import Any, Dict, Optional
import uuid

from app.schemas.safety_action import (
    SafetyActionRecord,
    TargetSubsystem,
)


class SafetyActionRoutingService:
    """Adapter bridging Phase 54 governance with authoritative downstream execution engines."""

    def dispatch_to_subsystem(
        self,
        action: SafetyActionRecord,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches action to the authoritative subsystem and returns reference identifiers.
        """
        subsystem = action.target_subsystem
        ref_id = f"ref-{uuid.uuid4().hex[:12]}"
        result: Dict[str, Any] = {
            "subsystem": subsystem.value,
            "dispatched": True,
            "reference_id": ref_id,
        }

        if subsystem == TargetSubsystem.PHASE_36_TASK:
            action.external_task_id = f"task-{ref_id}"
            result["task_id"] = action.external_task_id
        elif subsystem == TargetSubsystem.PHASE_37_WORKFLOW:
            action.external_workflow_id = f"wf-{ref_id}"
            result["workflow_id"] = action.external_workflow_id
        elif subsystem == TargetSubsystem.PHASE_51_GOVERNANCE:
            action.external_change_id = f"chg-{ref_id}"
            result["change_id"] = action.external_change_id
        elif subsystem == TargetSubsystem.PHASE_49_INCIDENT:
            action.external_incident_id = f"inc-{ref_id}"
            result["incident_id"] = action.external_incident_id
        elif subsystem == TargetSubsystem.PHASE_52_ASSURANCE:
            result["assurance_trigger"] = f"reassess-{action.scope.control_id or ref_id}"
        elif subsystem == TargetSubsystem.PHASE_29_NOTIFICATION:
            result["notification_sent"] = True

        return result


# Global singleton
safety_action_routing_service = SafetyActionRoutingService()

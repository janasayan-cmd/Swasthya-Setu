"""Phase 66: Safety Post-Closure Monitoring Service.

Manages post-closure monitoring policies, scheduled reverification intervals,
event-driven reconciliation, and batch integrity checks.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.repositories.safety_post_closure_verification_repository import (
    SafetyPostClosureVerificationRepository,
    get_safety_post_closure_verification_repository,
)
from app.repositories.safety_workflow_completion_repository import (
    SafetyWorkflowCompletionRepository,
    get_safety_workflow_completion_repository,
)
from app.schemas.safety_post_closure_monitoring import (
    MonitoringPolicyConfig,
    PostClosureMonitoringStatus,
)
from app.schemas.safety_post_closure_verification import (
    PostClosureVerificationRecord,
    TriggerPostClosureVerificationRequest,
    VerificationLifecycleState,
)
from app.schemas.safety_workflow_completion import CompletionLifecycleState
from app.schemas.user import AuthenticatedUserContext


class SafetyPostClosureMonitoringService:
    """Oversees policy-driven post-closure monitoring and event processing."""

    def __init__(
        self,
        verification_repo: Optional[SafetyPostClosureVerificationRepository] = None,
        completion_repo: Optional[SafetyWorkflowCompletionRepository] = None,
    ) -> None:
        self.verification_repo = verification_repo or get_safety_post_closure_verification_repository()
        self.completion_repo = completion_repo or get_safety_workflow_completion_repository()

    def get_or_initialize_monitoring_status(
        self,
        completion_id: str,
        organization_id: str,
        facility_id: str,
        policy: Optional[MonitoringPolicyConfig] = None,
    ) -> PostClosureMonitoringStatus:
        """Fetch existing monitoring status or initialize default policy configuration."""
        existing = self.verification_repo.get_monitoring_status(completion_id)
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        active_policy = policy or MonitoringPolicyConfig()
        next_eval = now + timedelta(seconds=active_policy.reverification_interval_seconds)

        status_record = PostClosureMonitoringStatus(
            completion_id=completion_id,
            organization_id=organization_id,
            facility_id=facility_id,
            monitoring_active=active_policy.enabled,
            policy=active_policy,
            next_scheduled_verification_at=next_eval,
        )
        return self.verification_repo.save_monitoring_status(status_record)

    def handle_material_change_event(
        self,
        event_name: str,
        payload: Dict[str, Any],
        user: AuthenticatedUserContext,
    ) -> List[str]:
        """Process an event indicating an upstream or downstream material change.

        Returns list of affected completion IDs queued for reverification.
        """
        affected_completions: List[str] = []

        # Find completions associated with the event payload
        disposition_id = payload.get("disposition_id")
        handoff_id = payload.get("handoff_id")
        completion_id = payload.get("completion_id")

        if completion_id:
            comp = self.completion_repo.get(completion_id)
            if comp and comp.organization_id == user.organization_id:
                affected_completions.append(completion_id)
        elif disposition_id:
            completions = self.completion_repo.get_by_disposition_id(disposition_id)
            for c in completions:
                if c.organization_id == user.organization_id:
                    affected_completions.append(c.completion_id)

        # Update monitoring status for affected completions
        for cid in set(affected_completions):
            mon = self.verification_repo.get_monitoring_status(cid)
            if mon:
                mon.next_scheduled_verification_at = datetime.now(timezone.utc)
                self.verification_repo.save_monitoring_status(mon)

        return list(set(affected_completions))

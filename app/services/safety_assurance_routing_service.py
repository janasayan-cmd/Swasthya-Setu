"""Phase 52: Safety Assurance Routing Service.

Determines the correct downstream route for failed, degraded, or
uncertain control assurance outcomes.

Routing table:
  CONTROL FAILURE                  → Phase 51 risk reassessment
  CONTROL FAILURE + SAFETY EVENT   → Phase 49 incident management
  RECURRING CONTROL FAILURE        → Phase 50 safety learning
  REQUIRED SYSTEM CHANGE           → Phase 51 safety change governance
  TASK REQUIRED                    → Phase 36
  WORKFLOW CHANGE REQUIRED         → Phase 37 / Phase 51
  CONFIGURATION CHANGE REQUIRED    → Phase 25 / Phase 51
  SAFETY ENFORCEMENT FAILURE       → Phase 48 / Phase 49 / Phase 51 as appropriate

Phase 52 MUST NOT create duplicate records in downstream systems.
A bypass is a safety signal, NOT automatically an incident.
A failed control is NOT automatically a patient harm event.

Phase 49 remains authoritative for incidents and investigations.
Phase 50 remains authoritative for safety learning.
Phase 51 remains authoritative for risk governance and safety change.
Phase 48 remains authoritative for safety enforcement.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.schemas.safety_assurance import (
    AssuranceEvaluationRecord,
    AssuranceLifecycleState,
    AssuranceRouteTarget,
    BypassRecord,
    ControlEffectivenessState,
    DegradationRecord,
    DegradationState,
    RegressionRecord,
)
from app.repositories.safety_assurance_repository import (
    SafetyAssuranceRepository,
    safety_assurance_repository,
)

logger = logging.getLogger("app.services.safety_assurance_routing_service")


class RoutingDecision:
    """Routing decision for a control assurance outcome."""

    def __init__(
        self,
        target: Optional[AssuranceRouteTarget],
        reason: str,
        requires_action: bool = False,
        duplicate_check_required: bool = True,
    ) -> None:
        self.target = target
        self.reason = reason
        self.requires_action = requires_action
        self.duplicate_check_required = duplicate_check_required
        self.route_reference_id: Optional[str] = None


class SafetyAssuranceRoutingService:
    """Determines downstream routing for assurance outcomes.

    Routes are determined based on assurance state and policy.
    Phase 52 does NOT create duplicate downstream records.
    Phase 49 remains authoritative for incidents.
    """

    def __init__(
        self,
        assurance_repo: Optional[SafetyAssuranceRepository] = None,
    ) -> None:
        self._repo = assurance_repo or safety_assurance_repository

    def determine_evaluation_route(
        self,
        evaluation: AssuranceEvaluationRecord,
        confirmed_safety_event: bool = False,
        recurring_failure: bool = False,
        requires_system_change: bool = False,
        requires_task: bool = False,
        requires_workflow_change: bool = False,
        requires_configuration_change: bool = False,
    ) -> RoutingDecision:
        """Determine the appropriate downstream route for an evaluation outcome.

        Args:
            evaluation: The completed assurance evaluation.
            confirmed_safety_event: Whether a safety event has been confirmed
                (triggers Phase 49 route — never inferred from technical failure alone).
            recurring_failure: Whether this is a recurring control failure
                (triggers Phase 50 safety learning).
            requires_system_change: Whether a safety change is required.
            requires_task: Whether a Phase 36 task should be created.
            requires_workflow_change: Whether workflow changes are needed.
            requires_configuration_change: Whether configuration changes are needed.

        Returns:
            RoutingDecision with target and reason.
        """
        effectiveness = evaluation.effectiveness_state

        # SAFETY EVENT CONFIRMED → Phase 49 (do not auto-confirm from technical failure)
        # "Do not automatically create a clinical incident for every technical control failure."
        if confirmed_safety_event and effectiveness == ControlEffectivenessState.FAILED:
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_49_INCIDENT_MANAGEMENT,
                reason=(
                    "Control failure with confirmed safety event. "
                    "Route to Phase 49 incident management. "
                    "CONTROL FAILURE != PATIENT HARM — confirmation required before routing."
                ),
                requires_action=True,
            )

        # RECURRING FAILURE → Phase 50 safety learning
        if recurring_failure and effectiveness in (
            ControlEffectivenessState.FAILED,
            ControlEffectivenessState.DEGRADED,
        ):
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_50_SAFETY_LEARNING,
                reason=(
                    "Recurring control failure. "
                    "Route to Phase 50 safety learning for pattern analysis."
                ),
                requires_action=True,
            )

        # SYSTEM CHANGE REQUIRED → Phase 51 safety change governance
        if requires_system_change or requires_workflow_change:
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_51_SAFETY_CHANGE,
                reason=(
                    "Safety change required due to control failure or regression. "
                    "Route to Phase 51 safety change governance."
                ),
                requires_action=True,
            )

        # CONFIGURATION CHANGE → Phase 25 / Phase 51
        if requires_configuration_change:
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_25_CONFIGURATION,
                reason=(
                    "Configuration change required. "
                    "Phase 25 remains authoritative for configuration governance."
                ),
                requires_action=True,
            )

        # TASK REQUIRED → Phase 36
        if requires_task:
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_36_TASK,
                reason="Assurance remediation task required. Route to Phase 36 task management.",
                requires_action=True,
            )

        # FAILED → Phase 51 risk reassessment
        if effectiveness == ControlEffectivenessState.FAILED:
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_51_RISK_REASSESSMENT,
                reason=(
                    "Control failed. Risk reassessment required. "
                    "Route to Phase 51. "
                    "CONTROL FAILURE != ROOT CAUSE. "
                    "CONTROL FAILURE != PATIENT HARM."
                ),
                requires_action=True,
            )

        # DEGRADED → Phase 51 risk reassessment
        if effectiveness in (
            ControlEffectivenessState.DEGRADED,
            ControlEffectivenessState.PARTIALLY_EFFECTIVE,
        ):
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_51_RISK_REASSESSMENT,
                reason=(
                    "Control degraded. Risk reassessment may be required. "
                    "CONTROL DEGRADATION != INCIDENT."
                ),
                requires_action=False,
            )

        # DEFAULT: monitor only
        return RoutingDecision(
            target=AssuranceRouteTarget.MONITORING_ONLY,
            reason="Assurance accepted. Continue monitoring.",
            requires_action=False,
        )

    def determine_degradation_route(
        self,
        degradation: DegradationRecord,
    ) -> RoutingDecision:
        """Determine routing for a degradation detection record."""
        if degradation.degradation_state == DegradationState.FAILED:
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_51_RISK_REASSESSMENT,
                reason=(
                    "Control failed. Risk reassessment required. "
                    "CONTROL FAILURE != PATIENT HARM."
                ),
                requires_action=True,
            )
        elif degradation.degradation_state in (
            DegradationState.DEGRADED,
            DegradationState.SIGNIFICANTLY_DEGRADED,
        ):
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_51_RISK_REASSESSMENT,
                reason="Control significantly degraded. Risk reassessment triggered.",
                requires_action=False,
            )
        return RoutingDecision(
            target=AssuranceRouteTarget.MONITORING_ONLY,
            reason="Degradation stable. Continue monitoring.",
            requires_action=False,
        )

    def determine_bypass_route(
        self,
        bypass: BypassRecord,
        policy_requires_incident: bool,
    ) -> RoutingDecision:
        """Determine routing for a bypass detection event.

        A bypass is a safety signal — not automatically an incident.
        Only route to Phase 49 when policy explicitly requires it.
        """
        if policy_requires_incident and bypass.requires_incident_routing:
            return RoutingDecision(
                target=AssuranceRouteTarget.PHASE_49_INCIDENT_MANAGEMENT,
                reason=(
                    "Bypass requires incident routing per policy. "
                    "A bypass is a safety signal — not a confirmed patient harm event."
                ),
                requires_action=True,
            )
        return RoutingDecision(
            target=AssuranceRouteTarget.MONITORING_ONLY,
            reason=(
                "Bypass recorded as safety signal. Policy does not require incident routing. "
                "Continue monitoring."
            ),
            requires_action=False,
        )

    def apply_route_to_evaluation(
        self,
        evaluation: AssuranceEvaluationRecord,
        routing: RoutingDecision,
        route_reference_id: Optional[str] = None,
    ) -> AssuranceEvaluationRecord:
        """Apply a routing decision to the evaluation record."""
        evaluation.routed_to = routing.target
        evaluation.routed_reference_id = route_reference_id
        evaluation.routing_reason = routing.reason
        evaluation.updated_at = datetime.now(timezone.utc)
        return self._repo.save_evaluation(evaluation)


# Global singleton
safety_assurance_routing_service = SafetyAssuranceRoutingService()

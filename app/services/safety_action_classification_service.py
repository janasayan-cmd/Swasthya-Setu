"""Phase 54: Safety Action Classification & Decision Support Service.

Enforces policy-driven finding classification, response selection, and server-side
urgency determination.

Core Invariants:
- FINDING != ACTION
- FINDING != INCIDENT
- FINDING != PATIENT HARM
- AI SUGGESTION != HUMAN DECISION
- Server-side urgency ONLY (clients cannot arbitrarily submit urgent=true)
"""

from typing import Optional, Tuple

from app.schemas.safety_action import (
    ActionPriority,
    ActionType,
    ActionabilityState,
    FindingSourceType,
    SafetyFindingReference,
    TargetSubsystem,
)


class SafetyActionClassificationService:
    """Classifies oversight findings and determines appropriate response routing."""

    def classify_finding(
        self,
        finding: SafetyFindingReference,
        action_type: ActionType,
    ) -> Tuple[ActionabilityState, ActionPriority, bool, TargetSubsystem]:
        """
        Evaluate finding details and determine:
        (actionability, priority, is_urgent, target_subsystem).
        All priority and urgency are derived server-side from policy rules.
        """
        details = finding.finding_details or {}
        
        # Check for urgent escalation triggers (Section 19)
        # - critical safety control failure
        # - confirmed safety incident
        # - repeated critical bypass
        # - active control disablement
        is_critical_control_failure = details.get("control_failed", False) or details.get("degradation_state") == "FAILED"
        is_confirmed_incident = finding.source_type == FindingSourceType.INCIDENT and details.get("incident_severity") in ("CRITICAL", "HIGH")
        has_repeated_bypass = details.get("bypass_count", 0) > 10 or details.get("repeated_bypass", False)
        is_active_disablement = details.get("control_disabled", False)

        is_urgent = bool(
            is_critical_control_failure
            or is_confirmed_incident
            or has_repeated_bypass
            or is_active_disablement
        )

        # 1. Determine Actionability State
        if is_urgent:
            actionability = ActionabilityState.URGENT_ESCALATION_REQUIRED
            priority = ActionPriority.CRITICAL
        elif finding.source_type == FindingSourceType.INCIDENT:
            actionability = ActionabilityState.INCIDENT_REVIEW_REQUIRED
            priority = ActionPriority.HIGH
        elif action_type == ActionType.SAFETY_CHANGE:
            actionability = ActionabilityState.SAFETY_CHANGE_REQUIRED
            priority = ActionPriority.HIGH
        elif action_type in (ActionType.CORRECTIVE_ACTION, ActionType.ROLLBACK_REVIEW):
            actionability = ActionabilityState.CORRECTIVE_ACTION_REQUIRED
            priority = ActionPriority.HIGH
        elif action_type in (ActionType.PREVENTIVE_ACTION, ActionType.DATA_QUALITY_REVIEW):
            actionability = ActionabilityState.PREVENTIVE_ACTION_REQUIRED
            priority = ActionPriority.MEDIUM
        elif action_type in (ActionType.RISK_REASSESSMENT, ActionType.CONTROL_REVALIDATION):
            actionability = ActionabilityState.REASSESSMENT_REQUIRED
            priority = ActionPriority.MEDIUM
        elif action_type == ActionType.MONITOR:
            actionability = ActionabilityState.MONITOR
            priority = ActionPriority.LOW
        elif details.get("insufficient_evidence", False):
            actionability = ActionabilityState.INSUFFICIENT_EVIDENCE
            priority = ActionPriority.MEDIUM
        else:
            actionability = ActionabilityState.REVIEW_REQUIRED
            priority = ActionPriority.MEDIUM

        # Elevate priority if severity tags are present in details
        detail_sev = str(details.get("severity", "")).upper()
        if detail_sev == "CRITICAL":
            priority = ActionPriority.CRITICAL
        elif detail_sev == "HIGH" and priority not in (ActionPriority.CRITICAL,):
            priority = ActionPriority.HIGH

        # 2. Determine Subsystem Routing (Section 14)
        target_subsystem = self.resolve_target_subsystem(action_type, finding.source_type)

        return actionability, priority, is_urgent, target_subsystem

    def resolve_target_subsystem(
        self,
        action_type: ActionType,
        source_type: FindingSourceType,
    ) -> TargetSubsystem:
        """Map action type to authoritative execution subsystem."""
        if action_type in (ActionType.SAFETY_CHANGE, ActionType.ROLLBACK_REVIEW):
            return TargetSubsystem.PHASE_51_GOVERNANCE
        if action_type in (ActionType.CONTROL_REVALIDATION, ActionType.RISK_REASSESSMENT):
            return TargetSubsystem.PHASE_52_ASSURANCE
        if action_type == ActionType.INCIDENT_REVIEW or source_type == FindingSourceType.INCIDENT:
            return TargetSubsystem.PHASE_49_INCIDENT
        if action_type in (ActionType.TASK_CREATION, ActionType.REVIEW, ActionType.PROVIDER_REVIEW):
            return TargetSubsystem.PHASE_36_TASK
        if action_type == ActionType.WORKFLOW_EXECUTION:
            return TargetSubsystem.PHASE_37_WORKFLOW
        if action_type == ActionType.NOTIFICATION:
            return TargetSubsystem.PHASE_29_NOTIFICATION
        if action_type in (ActionType.CORRECTIVE_ACTION, ActionType.PREVENTIVE_ACTION):
            return TargetSubsystem.PHASE_50_LEARNING
        return TargetSubsystem.MANUAL_REVIEW


# Global singleton
safety_action_classification_service = SafetyActionClassificationService()

"""Centralized Alert Policy Evaluation Engine (Phase 35).

CORE SAFETY PRINCIPLES:
- Centralizes alert policy logic; does NOT scatter clinical policies across random endpoints.
- Severity is rule-derived or provider-derived, NEVER invented by AI.
- AI must NOT become the authority for clinical alert generation.
- Historical alert provenance remains tied to the evaluated policy version.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from app.repositories.alert_policy_repository import AlertPolicyRepository
from app.schemas.alert import AlertCategory, AlertSeverity
from app.schemas.alert_policy import AlertPolicy, AlertPolicyEvaluationResult

logger = logging.getLogger(__name__)


class AlertPolicyService:
    """Evaluates domain events against approved versioned alert policies."""

    def __init__(self, policy_repo: AlertPolicyRepository) -> None:
        self.policy_repo = policy_repo

    def evaluate_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        override_severity: Optional[AlertSeverity] = None,
    ) -> AlertPolicyEvaluationResult:
        """Evaluate an authoritative domain event against configured policies.
        
        Returns an explainable AlertPolicyEvaluationResult.
        """
        # Fetch active policies for this event
        active_policies = self.policy_repo.get_active_policies_by_event(event_type)

        if not active_policies:
            logger.info("No active alert policies registered for event type '%s'", event_type)
            return AlertPolicyEvaluationResult(
                requires_alert=False,
                explanation=f"No active alert policy for event type '{event_type}'.",
                suppression_reason="NO_POLICY_MATCHED",
            )

        # Evaluate the highest priority policy matching conditions
        for policy in active_policies:
            matched, reason = self._check_condition(policy, payload)
            if matched:
                final_severity = override_severity or policy.severity
                title = self._generate_title(policy, payload)
                summary = self._generate_summary(policy, payload)

                return AlertPolicyEvaluationResult(
                    requires_alert=True,
                    policy_id=policy.policy_id,
                    policy_version=policy.policy_version,
                    category=policy.category,
                    severity=final_severity,
                    title=title,
                    summary=summary,
                    requires_acknowledgement=policy.requires_acknowledgement,
                    escalation_enabled=policy.escalation_enabled,
                    escalation_timeout_minutes=policy.escalation_timeout_minutes,
                    recipient_class=policy.recipient_class,
                    explanation=f"Matched policy '{policy.policy_id}' v{policy.policy_version} on condition '{policy.condition_expression}'.",
                    evaluation_metadata={
                        "condition": policy.condition_expression,
                        "matched_reason": reason,
                        "policy_name": policy.policy_name,
                    },
                )

        return AlertPolicyEvaluationResult(
            requires_alert=False,
            explanation=f"Event '{event_type}' did not meet activation conditions for any active policy.",
            suppression_reason="CONDITIONS_NOT_MET",
        )

    def _check_condition(self, policy: AlertPolicy, payload: Dict[str, Any]) -> tuple[bool, str]:
        """Check deterministic condition expressions without executing arbitrary code."""
        cond = policy.condition_expression.strip()

        if cond == "is_critical_result == true":
            is_critical = payload.get("is_critical_result") or payload.get("requires_critical_result_handling") or payload.get("critical_flag")
            if bool(is_critical):
                return True, "Diagnostic critical result flag present."
            return False, "Not flagged as critical diagnostic result."

        if cond == "safety_status == 'REVIEW_REQUIRED'":
            status_val = payload.get("safety_status") or payload.get("status")
            if status_val in {"REVIEW_REQUIRED", "CONTRAINDICATED", "HIGH_RISK"}:
                return True, f"Medication safety status is {status_val}."
            return False, f"Medication safety status is {status_val}, not requiring alert."

        if cond == "urgency == 'URGENT'":
            urgency = payload.get("urgency") or payload.get("triage_urgency") or payload.get("triage_category")
            if urgency in {"URGENT", "EMERGENCY", "IMMEDIATE", "CRITICAL"}:
                return True, f"Triage urgency is {urgency}."
            return False, f"Triage urgency '{urgency}' does not trigger alert."

        if cond == "has_data_conflict == true":
            has_conflict = payload.get("has_data_conflict") or payload.get("conflict_detected") or payload.get("review_required")
            if bool(has_conflict):
                return True, "Data discrepancy or conflict detected."
            return False, "No data discrepancy flagged."

        if cond == "status == 'FAILED'":
            st = payload.get("status") or payload.get("import_status")
            if st == "FAILED":
                return True, "Operation or import reported failure."
            return False, f"Status is {st}."

        if cond == "incident_level == 'HIGH'":
            lvl = payload.get("incident_level") or payload.get("security_level") or payload.get("severity")
            if lvl in {"HIGH", "CRITICAL"}:
                return True, f"Security incident level is {lvl}."
            return False, f"Security level is {lvl}."

        if cond == "new_status == 'CANCELLED'":
            nst = payload.get("new_status") or payload.get("appointment_status")
            if nst == "CANCELLED":
                return True, "Appointment was cancelled."
            return False, f"Appointment status is {nst}."

        # Default fallback: if condition expression matches payload key or true
        if cond == "true":
            return True, "Universal trigger condition."

        return False, f"Unrecognized or unmet condition: {cond}"

    def _generate_title(self, policy: AlertPolicy, payload: Dict[str, Any]) -> str:
        """Generate structured title from policy context."""
        if policy.category == AlertCategory.DIAGNOSTIC_RESULT_ALERT:
            res_name = payload.get("test_name") or payload.get("test_code") or "Diagnostic Value"
            return f"Critical Diagnostic Result: {res_name}"

        if policy.category == AlertCategory.MEDICATION_SAFETY_ALERT:
            drug = payload.get("medication_name") or "Prescribed Drug"
            return f"Medication Safety Review: {drug}"

        if policy.category == AlertCategory.TRIAGE_ALERT:
            urg = payload.get("urgency", "Urgent")
            return f"Clinical Triage Alert: {urg}"

        if policy.category == AlertCategory.DATA_QUALITY_ALERT:
            return f"Data Quality Finding: {payload.get('finding_type', 'Record Conflict')}"

        if policy.category == AlertCategory.INTEROPERABILITY_ALERT:
            return f"Interoperability Import Failed: {payload.get('resource_type', 'Records')}"

        if policy.category == AlertCategory.SECURITY_ALERT:
            return f"Security Notice: {payload.get('alert_type', 'Suspicious Activity')}"

        if policy.category == AlertCategory.APPOINTMENT_ALERT:
            return "Appointment Cancellation Notice"

        return f"{policy.policy_name} Alert"

    def _generate_summary(self, policy: AlertPolicy, payload: Dict[str, Any]) -> str:
        """Generate safe, non-diagnostic factual summary."""
        source_id = payload.get("source_id") or payload.get("resource_id") or "N/A"
        return f"Event {policy.event_type} requires authorized clinical/operational attention (Ref: {source_id})."

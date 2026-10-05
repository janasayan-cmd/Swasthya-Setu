"""Approval Policy Service (Phase 40).

Centralized, deterministic, and versioned policy engine for clinical approvals.

CRITICAL INVARIANTS:
- The policy engine is deterministic and configuration-driven.
- LLMs or AI MUST NOT be used to decide if clinical approval is required.
- Safety-sensitive approval policies must fail closed.
- Policies are versioned; historical approvals preserve policy versions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.schemas.approval_policy import ApprovalPolicyRecord, ApprovalPolicyRule


class ApprovalPolicyService:
    """Evaluates approval policies for candidate clinical and operational actions."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._policies: Dict[str, ApprovalPolicyRecord] = {}
        self._init_default_policy()

    def _init_default_policy(self) -> None:
        """Initialize standard baseline policies with versioning."""
        standard_rules = {
            "MEDICATION_ORDER": ApprovalPolicyRule(
                action_type="MEDICATION_ORDER",
                requires_approval=True,
                required_level=1,
                required_roles=["DOCTOR", "ADMIN", "SYSTEM_ADMIN"],
                allow_self_approval=False,  # Strict: cannot self-approve high-impact meds
                multi_approver_count=1,
                expiration_hours=24,
            ),
            "ORDER_SET_APPROVAL": ApprovalPolicyRule(
                action_type="ORDER_SET_APPROVAL",
                requires_approval=True,
                required_level=1,
                required_roles=["DOCTOR", "ADMIN", "SYSTEM_ADMIN"],
                allow_self_approval=False,
                multi_approver_count=1,
                expiration_hours=48,
            ),
            "REFERRAL_ORDER": ApprovalPolicyRule(
                action_type="REFERRAL_ORDER",
                requires_approval=True,
                required_level=1,
                required_roles=["DOCTOR", "ADMIN", "SYSTEM_ADMIN"],
                allow_self_approval=False,
                multi_approver_count=1,
                expiration_hours=72,
            ),
            "DIAGNOSTIC_ORDER": ApprovalPolicyRule(
                action_type="DIAGNOSTIC_ORDER",
                requires_approval=True,
                required_level=1,
                required_roles=["DOCTOR", "ADMIN", "SYSTEM_ADMIN"],
                allow_self_approval=True,  # Clinician ordering routine lab can co-sign/self-authorize
                multi_approver_count=1,
                expiration_hours=48,
            ),
            "TEMPLATE_APPROVAL": ApprovalPolicyRule(
                action_type="TEMPLATE_APPROVAL",
                requires_approval=True,
                required_level=1,
                required_roles=["DOCTOR", "ADMIN", "SYSTEM_ADMIN"],
                allow_self_approval=False,
                multi_approver_count=1,
                expiration_hours=168,  # 7 days
            ),
        }

        default_policy = ApprovalPolicyRecord(
            policy_id="default-clinical-policy",
            policy_name="HealthSetu Standard Clinical Approval Policy",
            policy_version=1,
            rules=standard_rules,
            default_rule=ApprovalPolicyRule(
                action_type="DEFAULT",
                requires_approval=True,
                required_level=1,
                required_roles=["DOCTOR", "ADMIN", "SYSTEM_ADMIN"],
                allow_self_approval=False,
                multi_approver_count=1,
                expiration_hours=48,
            ),
        )

        self._policies[default_policy.policy_id] = default_policy

    def get_policy(self, policy_id: str = "default-clinical-policy") -> ApprovalPolicyRecord:
        """Retrieve policy by ID. Fails closed with default policy if missing."""
        return self._policies.get(policy_id, self._policies["default-clinical-policy"])

    def evaluate_rule(
        self,
        action_type: str,
        policy_id: str = "default-clinical-policy",
    ) -> ApprovalPolicyRule:
        """Evaluate approval rule for an action type.

        SAFETY: Missing or unknown rules fail closed to requiring approval.
        """
        policy = self.get_policy(policy_id)
        rule = policy.rules.get(action_type)
        if not rule:
            # Fallback to default policy rule (fails closed to requiring approval)
            return policy.default_rule
        return rule

    def evaluate_policy(
        self,
        action_type: str,
        policy_id: str = "default-clinical-policy",
        context: Optional[Dict[str, Any]] = None,
    ) -> ApprovalPolicyRule:
        """Evaluate approval rule for an action type with optional clinical context."""
        return self.evaluate_rule(action_type, policy_id)

    def register_rule(
        self,
        rule: ApprovalPolicyRule,
        policy_id: str = "default-clinical-policy",
    ) -> None:
        """Register or override an approval policy rule."""
        policy = self.get_policy(policy_id)
        policy.rules[rule.action_type] = rule

"""Registry and repository of approved declarative Alert Policies (Phase 35).

Centralizes alert policy configuration and versioning.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from app.schemas.alert import AlertCategory, AlertSeverity
from app.schemas.alert_policy import AlertPolicy


class AlertPolicyRepository:
    """Thread-safe registry for alert policies."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._policies: Dict[str, AlertPolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        default_policies = [
            AlertPolicy(
                policy_id="POLICY_CRITICAL_DIAGNOSTIC_RESULT",
                policy_name="Critical Diagnostic Result Escalation Policy",
                policy_version=1,
                event_type="CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE",
                condition_expression="is_critical_result == true",
                category=AlertCategory.DIAGNOSTIC_RESULT_ALERT,
                severity=AlertSeverity.CRITICAL,
                requires_acknowledgement=True,
                escalation_enabled=True,
                escalation_timeout_minutes=15,
                recipient_class="RESPONSIBLE_CLINICIAN",
                description="Authoritative critical diagnostic value flagged by lab provider requires urgent clinician acknowledgement.",
                is_active=True,
            ),
            AlertPolicy(
                policy_id="POLICY_MEDICATION_SAFETY_REVIEW",
                policy_name="Medication Safety Interaction Review Policy",
                policy_version=1,
                event_type="MEDICATION_SAFETY_REVIEW_REQUIRED",
                condition_expression="safety_status == 'REVIEW_REQUIRED'",
                category=AlertCategory.MEDICATION_SAFETY_ALERT,
                severity=AlertSeverity.HIGH,
                requires_acknowledgement=True,
                escalation_enabled=True,
                escalation_timeout_minutes=30,
                recipient_class="RESPONSIBLE_CLINICIAN",
                description="Authoritative medication safety evaluation detected severe interaction or contraindication requiring clinician review.",
                is_active=True,
            ),
            AlertPolicy(
                policy_id="POLICY_URGENT_TRIAGE",
                policy_name="Urgent Clinical Triage Notification Policy",
                policy_version=1,
                event_type="URGENT_TRIAGE_RESULT_AVAILABLE",
                condition_expression="urgency == 'URGENT'",
                category=AlertCategory.TRIAGE_ALERT,
                severity=AlertSeverity.CRITICAL,
                requires_acknowledgement=True,
                escalation_enabled=True,
                escalation_timeout_minutes=15,
                recipient_class="RESPONSIBLE_CLINICIAN",
                description="Authoritative triage evaluation categorized patient as urgent requiring clinician notification.",
                is_active=True,
            ),
            AlertPolicy(
                policy_id="POLICY_DATA_QUALITY_REVIEW",
                policy_name="Data Quality Discrepancy Policy",
                policy_version=1,
                event_type="DATA_QUALITY_REVIEW_REQUIRED",
                condition_expression="has_data_conflict == true",
                category=AlertCategory.DATA_QUALITY_ALERT,
                severity=AlertSeverity.MEDIUM,
                requires_acknowledgement=False,
                escalation_enabled=False,
                escalation_timeout_minutes=60,
                recipient_class="CARE_TEAM",
                description="Data quality conflict or provenance mismatch flagged for review.",
                is_active=True,
            ),
            AlertPolicy(
                policy_id="POLICY_INTEROPERABILITY_FAILED",
                policy_name="Interoperability Integration Failure Policy",
                policy_version=1,
                event_type="INTEROPERABILITY_IMPORT_FAILED",
                condition_expression="status == 'FAILED'",
                category=AlertCategory.INTEROPERABILITY_ALERT,
                severity=AlertSeverity.MEDIUM,
                requires_acknowledgement=False,
                escalation_enabled=False,
                escalation_timeout_minutes=60,
                recipient_class="ADMINISTRATOR",
                description="Interoperability clinical record import failed and requires operational operator review.",
                is_active=True,
            ),
            AlertPolicy(
                policy_id="POLICY_SECURITY_SUSPICIOUS_ACCESS",
                policy_name="Security Alert for Repeated Unauthorized Access",
                policy_version=1,
                event_type="SECURITY_SUSPICIOUS_ACCESS",
                condition_expression="incident_level == 'HIGH'",
                category=AlertCategory.SECURITY_ALERT,
                severity=AlertSeverity.HIGH,
                requires_acknowledgement=True,
                escalation_enabled=False,
                escalation_timeout_minutes=60,
                recipient_class="ADMINISTRATOR",
                description="Security monitoring flagged suspicious access attempt.",
                is_active=True,
            ),
            AlertPolicy(
                policy_id="POLICY_APPOINTMENT_CANCELLATION",
                policy_name="Critical Appointment Cancellation Notice",
                policy_version=1,
                event_type="APPOINTMENT_STATUS_CHANGED",
                condition_expression="new_status == 'CANCELLED'",
                category=AlertCategory.APPOINTMENT_ALERT,
                severity=AlertSeverity.INFO,
                requires_acknowledgement=False,
                escalation_enabled=False,
                escalation_timeout_minutes=60,
                recipient_class="RESPONSIBLE_CLINICIAN",
                description="Appointment cancellation event notification.",
                is_active=True,
            ),
        ]
        for p in default_policies:
            self._policies[p.policy_id] = p

    def get_by_id(self, policy_id: str) -> Optional[AlertPolicy]:
        """Fetch policy by ID."""
        with self._lock:
            return self._policies.get(policy_id)

    def get_active_policies_by_event(self, event_type: str) -> List[AlertPolicy]:
        """Fetch all active policies matching the given domain event type."""
        with self._lock:
            return [
                p for p in self._policies.values()
                if p.event_type == event_type and p.is_active
            ]

    def list_all(self) -> List[AlertPolicy]:
        """Return all registered policies."""
        with self._lock:
            return list(self._policies.values())

    def register_policy(self, policy: AlertPolicy) -> AlertPolicy:
        """Register or update an alert policy."""
        with self._lock:
            self._policies[policy.policy_id] = policy
            return policy

    def reset(self) -> None:
        """Reset to initial default policies."""
        with self._lock:
            self._policies.clear()
            self._load_default_policies()

"""Pydantic schemas for Centralized Alert Policies and Policy Evaluation (Phase 35)."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.alert import AlertCategory, AlertSeverity


class AlertPolicy(BaseModel):
    """Declarative alert policy definition."""

    model_config = ConfigDict(extra="ignore")

    policy_id: str = Field(description="Unique policy identifier (e.g. CRITICAL_DIAGNOSTIC_RESULT_POLICY)")
    policy_name: str = Field(description="Human-readable policy title")
    policy_version: int = Field(default=1, description="Version of the policy rule")
    event_type: str = Field(description="Domain event type triggering this policy")
    condition_expression: str = Field(description="Condition identifier or expression evaluating the event")
    category: AlertCategory = Field(description="Resulting alert category")
    severity: AlertSeverity = Field(description="Resulting alert severity")
    requires_acknowledgement: bool = Field(default=False, description="Whether acknowledgement is required")
    escalation_enabled: bool = Field(default=False, description="Whether automated escalation applies")
    escalation_timeout_minutes: int = Field(default=15, description="Timeout in minutes before escalating")
    recipient_class: str = Field(default="RESPONSIBLE_CLINICIAN", description="Target recipient category")
    description: str = Field(default="", description="Policy description and intent")
    is_active: bool = Field(default=True, description="Whether policy is active")


class AlertPolicyEvaluationResult(BaseModel):
    """Outcome of evaluating domain event against configured policies."""

    model_config = ConfigDict(extra="ignore")

    requires_alert: bool = Field(description="True if an alert must be generated")
    policy_id: Optional[str] = Field(default=None, description="Triggered policy ID")
    policy_version: Optional[int] = Field(default=None, description="Policy version used")
    category: Optional[AlertCategory] = Field(default=None, description="Resolved category")
    severity: Optional[AlertSeverity] = Field(default=None, description="Authoritative resolved severity")
    title: Optional[str] = Field(default=None, description="Generated alert title")
    summary: Optional[str] = Field(default=None, description="Safe summary context")
    requires_acknowledgement: bool = Field(default=False, description="Acknowledgement requirement")
    escalation_enabled: bool = Field(default=False, description="Escalation enablement")
    escalation_timeout_minutes: int = Field(default=15, description="Escalation timeout in minutes")
    recipient_class: Optional[str] = Field(default=None, description="Target recipient class")
    suppression_reason: Optional[str] = Field(default=None, description="Reason if alert was suppressed under policy")
    evaluation_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata explaining policy execution")

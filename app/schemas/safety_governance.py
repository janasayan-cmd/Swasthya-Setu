"""Phase 51: Clinical Safety Governance, Risk Acceptance & Controlled Safety Change Management Schemas.

Defines foundational governance taxonomy, lifecycle states, authority models,
AI traceability metadata, and core event types.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class RiskCategory(str, Enum):
    """Controlled taxonomy of clinical safety risk categories."""

    CLINICAL_SAFETY = "CLINICAL_SAFETY"
    MEDICATION_SAFETY = "MEDICATION_SAFETY"
    TRIAGE_SAFETY = "TRIAGE_SAFETY"
    AI_SAFETY = "AI_SAFETY"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    DATA_RECONCILIATION = "DATA_RECONCILIATION"
    WORKFLOW_SAFETY = "WORKFLOW_SAFETY"
    INTEGRATION_SAFETY = "INTEGRATION_SAFETY"
    PROVIDER_DEPENDENCY = "PROVIDER_DEPENDENCY"
    SECURITY = "SECURITY"
    PRIVACY = "PRIVACY"
    AUTHORIZATION = "AUTHORIZATION"
    CONSENT = "CONSENT"
    INTEROPERABILITY = "INTEROPERABILITY"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    NOTIFICATION = "NOTIFICATION"
    SYSTEM_RELIABILITY = "SYSTEM_RELIABILITY"
    CONFIGURATION = "CONFIGURATION"
    DEPLOYMENT = "DEPLOYMENT"
    OTHER = "OTHER"


class RiskSeverity(str, Enum):
    """Controlled severity levels based on authorized policy and clinical evidence."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskLikelihood(str, Enum):
    """Controlled probability of hazard occurrence."""

    RARE = "RARE"
    UNLIKELY = "UNLIKELY"
    POSSIBLE = "POSSIBLE"
    LIKELY = "LIKELY"
    ALMOST_CERTAIN = "ALMOST_CERTAIN"
    UNKNOWN = "UNKNOWN"


class RiskImpact(str, Enum):
    """Controlled potential or observed impact of hazard."""

    NO_KNOWN_IMPACT = "NO_KNOWN_IMPACT"
    POTENTIAL_IMPACT = "POTENTIAL_IMPACT"
    CONFIRMED_IMPACT = "CONFIRMED_IMPACT"
    UNKNOWN = "UNKNOWN"


class RiskState(str, Enum):
    """Controlled risk lifecycle states."""

    IDENTIFIED = "IDENTIFIED"
    ASSESSMENT_REQUIRED = "ASSESSMENT_REQUIRED"
    ASSESSING = "ASSESSING"
    ASSESSED = "ASSESSED"
    MITIGATION_REQUIRED = "MITIGATION_REQUIRED"
    MITIGATION_PLANNED = "MITIGATION_PLANNED"
    GOVERNANCE_REVIEW = "GOVERNANCE_REVIEW"
    ACCEPTED = "ACCEPTED"
    MITIGATION_IN_PROGRESS = "MITIGATION_IN_PROGRESS"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    MONITORING = "MONITORING"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    CLOSED = "CLOSED"

    # Alternative / Terminal states
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
    ESCALATED = "ESCALATED"
    UNRESOLVED = "UNRESOLVED"
    REOPENED = "REOPENED"


class RiskSourceType(str, Enum):
    """Authoritative sources from which a risk may originate."""

    INCIDENT = "INCIDENT"
    NEAR_MISS = "NEAR_MISS"
    SAFETY_SIGNAL = "SAFETY_SIGNAL"
    UNRESOLVED_INCIDENT = "UNRESOLVED_INCIDENT"
    LEARNING_PATTERN = "LEARNING_PATTERN"
    LEARNING_TREND = "LEARNING_TREND"
    SAFETY_GATE_FAILURE = "SAFETY_GATE_FAILURE"
    WORKFLOW_FAILURE = "WORKFLOW_FAILURE"
    TASK_FAILURE = "TASK_FAILURE"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    INTEROPERABILITY_FAILURE = "INTEROPERABILITY_FAILURE"
    DATA_QUALITY_FINDING = "DATA_QUALITY_FINDING"
    RECONCILIATION_FINDING = "RECONCILIATION_FINDING"
    AI_SAFETY_FINDING = "AI_SAFETY_FINDING"
    CONFIGURATION_FINDING = "CONFIGURATION_FINDING"
    DEPLOYMENT_FINDING = "DEPLOYMENT_FINDING"
    CORRECTIVE_ACTION_FAILURE = "CORRECTIVE_ACTION_FAILURE"
    SECURITY_FINDING = "SECURITY_FINDING"
    PRIVACY_FINDING = "PRIVACY_FINDING"
    HUMAN_REPORT = "HUMAN_REPORT"
    OTHER = "OTHER"


class ChangeRequestState(str, Enum):
    """Controlled safety change request lifecycle states."""

    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    IMPLEMENTATION_READY = "IMPLEMENTATION_READY"
    IMPLEMENTING = "IMPLEMENTING"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    VALIDATED = "VALIDATED"
    ROLLOUT_APPROVED = "ROLLOUT_APPROVED"
    MONITORING = "MONITORING"
    COMPLETED = "COMPLETED"

    # Alternative / Failure states
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"


class SafetyChangeTargetType(str, Enum):
    """Authoritative subsystem targets for governed safety changes."""

    SAFETY_POLICY = "SAFETY_POLICY"
    SAFETY_GATE = "SAFETY_GATE"
    WORKFLOW = "WORKFLOW"
    CONFIGURATION = "CONFIGURATION"
    FEATURE_FLAG = "FEATURE_FLAG"
    PROVIDER_ADAPTER = "PROVIDER_ADAPTER"
    PROVIDER_CONFIGURATION = "PROVIDER_CONFIGURATION"
    VALIDATION_LOGIC = "VALIDATION_LOGIC"
    AI_GUARDRAIL = "AI_GUARDRAIL"
    NOTIFICATION_POLICY = "NOTIFICATION_POLICY"
    INTEROPERABILITY_MAPPING = "INTEROPERABILITY_MAPPING"
    DATA_QUALITY_RULE = "DATA_QUALITY_RULE"
    MONITORING_RULE = "MONITORING_RULE"


class RolloutScopeType(str, Enum):
    """Authorized scope for controlled rollout."""

    INTERNAL = "INTERNAL"
    LIMITED = "LIMITED"
    ORGANIZATION_SCOPED = "ORGANIZATION_SCOPED"
    FACILITY_SCOPED = "FACILITY_SCOPED"
    STAGED = "STAGED"
    PERCENTAGE_BASED = "PERCENTAGE_BASED"
    FULL = "FULL"


class GovernanceEventType(str, Enum):
    """Asynchronous and audit event types for safety governance."""

    RISK_CREATED = "safety_governance.risk_created"
    RISK_ASSESSED = "safety_governance.risk_assessed"
    RISK_ACCEPTED = "safety_governance.risk_accepted"
    RISK_REJECTED = "safety_governance.risk_rejected"
    MITIGATION_CREATED = "safety_governance.mitigation_created"
    CHANGE_REQUESTED = "safety_governance.change_requested"
    CHANGE_APPROVED = "safety_governance.change_approved"
    CHANGE_IMPLEMENTATION_STARTED = "safety_governance.change_implementation_started"
    CHANGE_IMPLEMENTED = "safety_governance.change_implemented"
    CHANGE_VALIDATION_REQUIRED = "safety_governance.change_validation_required"
    CHANGE_VALIDATED = "safety_governance.change_validated"
    CHANGE_FAILED = "safety_governance.change_failed"
    ROLLBACK_STARTED = "safety_governance.rollback_started"
    ROLLBACK_COMPLETED = "safety_governance.rollback_completed"
    MONITORING_STARTED = "safety_governance.monitoring_started"
    REASSESSMENT_REQUIRED = "safety_governance.reassessment_required"
    RISK_CLOSED = "safety_governance.risk_closed"
    RISK_REOPENED = "safety_governance.risk_reopened"


class AIGovernanceStatus(str, Enum):
    """Lifecycle status of AI-assisted governance drafts."""

    HUMAN_AUTHORED = "HUMAN_AUTHORED"
    AI_SUGGESTED = "AI_SUGGESTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    HUMAN_ACCEPTED = "HUMAN_ACCEPTED"
    HUMAN_MODIFIED = "HUMAN_MODIFIED"
    HUMAN_REJECTED = "HUMAN_REJECTED"


class AITraceabilityMetadata(BaseModel):
    """Preserves AI provenance without storing or exposing hidden chain-of-thought."""

    model_config = ConfigDict(extra="ignore")

    model_provider: Optional[str] = None
    model_version: Optional[str] = None
    prompt_template_version: Optional[str] = None
    input_evidence_references: List[str] = Field(default_factory=list)
    output_schema_version: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ai_status: AIGovernanceStatus = Field(default=AIGovernanceStatus.HUMAN_AUTHORED)
    reviewer_status: Optional[str] = None

"""Clinical Decision Schemas & Domain Contracts (Phase 47).

Defines:
- Controlled decision types and lifecycle statuses
- Input reference tracking (avoiding raw PHI duplication)
- Rule-based and AI model execution metadata contracts
- Invariants:
  - DECISION TRACEABILITY != AUDIT LOGGING
  - EXPLANATION != CLINICAL JUSTIFICATION
  - AI OUTPUT != CLINICAL DECISION
  - RECOMMENDATION != ACTION
  - SUGGESTION != APPROVAL
  - APPROVAL != EXECUTION
  - RULE MATCH != DIAGNOSIS
  - NO SYSTEM COMPONENT MAY SILENTLY TURN AN AI OUTPUT OR RULE RESULT INTO AN UNAUTHORIZED CLINICAL ACTION.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DecisionType(str, Enum):
    """Controlled clinical and system decision types."""

    TRIAGE_CLASSIFICATION = "TRIAGE_CLASSIFICATION"
    MEDICATION_SAFETY_RESULT = "MEDICATION_SAFETY_RESULT"
    MEDICATION_SAFETY_WARNING = "MEDICATION_SAFETY_WARNING"
    CLINICAL_ALERT_GENERATION = "CLINICAL_ALERT_GENERATION"
    CARE_PLAN_RECOMMENDATION = "CARE_PLAN_RECOMMENDATION"
    DISCHARGE_INSTRUCTION_PROCESSING = "DISCHARGE_INSTRUCTION_PROCESSING"
    DOCUMENT_CLASSIFICATION = "DOCUMENT_CLASSIFICATION"
    DOCUMENT_EXTRACTION_RESULT = "DOCUMENT_EXTRACTION_RESULT"
    DATA_RECONCILIATION_RECOMMENDATION = "DATA_RECONCILIATION_RECOMMENDATION"
    IDENTITY_MATCH_RECOMMENDATION = "IDENTITY_MATCH_RECOMMENDATION"
    WORKFLOW_ROUTING_RECOMMENDATION = "WORKFLOW_ROUTING_RECOMMENDATION"
    TASK_ROUTING_RECOMMENDATION = "TASK_ROUTING_RECOMMENDATION"
    EXTERNAL_DATA_RECONCILIATION_RESULT = "EXTERNAL_DATA_RECONCILIATION_RESULT"
    AI_SUMMARY = "AI_SUMMARY"
    AI_EXTRACTION = "AI_EXTRACTION"
    AI_CLASSIFICATION = "AI_CLASSIFICATION"
    HUMAN_REVIEW_DECISION = "HUMAN_REVIEW_DECISION"
    SYSTEM_POLICY_DECISION = "SYSTEM_POLICY_DECISION"


class DecisionStatus(str, Enum):
    """Explicit decision lifecycle states."""

    CREATED = "CREATED"
    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    EVALUATING = "EVALUATING"
    GENERATED = "GENERATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    APPLIED = "APPLIED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    CONFLICTED = "CONFLICTED"


class DecisionProvenanceSource(str, Enum):
    """Authoritative source category for decision provenance."""

    PATIENT = "PATIENT"
    CLINICIAN = "CLINICIAN"
    SYSTEM = "SYSTEM"
    RULE_ENGINE = "RULE_ENGINE"
    AI_MODEL = "AI_MODEL"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    IMPORTED_SOURCE = "IMPORTED_SOURCE"
    WORKFLOW = "WORKFLOW"
    ADMINISTRATIVE_PROCESS = "ADMINISTRATIVE_PROCESS"


class DecisionInputReference(BaseModel):
    """Secure traceable pointer to inputs evaluated during decision generation.
    
    CRITICAL PRIVACY RULE (TRD Sec 9):
    Stores secure references, version identifiers, and hashes rather than duplicating
    complete patient PHI records.
    """

    model_config = ConfigDict(extra="ignore")

    resource_type: str = Field(description="Domain resource type e.g. medication, observation, document")
    resource_id: str = Field(description="Unique resource identifier")
    version_number: Optional[int] = Field(default=None, description="Resource version evaluated (Phase 46)")
    field_paths: List[str] = Field(default_factory=list, description="Specific field paths considered")
    snapshot_hash: Optional[str] = Field(default=None, description="SHA-256 integrity hash of input state")
    source: Optional[str] = Field(default=None, description="Origin source system or provider")


class DecisionModelMetadata(BaseModel):
    """Execution metadata for AI-assisted processing."""

    model_config = ConfigDict(extra="ignore")

    provider: Optional[str] = Field(default=None, description="Provider identifier e.g. google, mock")
    model_identifier: Optional[str] = Field(default=None, description="Model family/name e.g. gemini-pro")
    model_version: Optional[str] = Field(default=None, description="Model release version")
    prompt_template_version: Optional[str] = Field(default=None, description="Prompt template version")
    system_instruction_version: Optional[str] = Field(default=None, description="System instructions revision")
    schema_version: Optional[str] = Field(default=None, description="Output validation schema version")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Provider-reported confidence score if available")


class DecisionRuleMetadata(BaseModel):
    """Execution metadata for deterministic rule-based evaluation."""

    model_config = ConfigDict(extra="ignore")

    rule_set_id: Optional[str] = Field(default=None, description="Rule set identifier e.g. TRIAGE_V1")
    rule_set_version: Optional[str] = Field(default=None, description="Rule set version e.g. 1.2.0")
    matched_rule_ids: List[str] = Field(default_factory=list, description="Identifiers of rules satisfied")
    configuration_version: Optional[str] = Field(default=None, description="Configuration revision ID")


class DecisionRecord(BaseModel):
    """Immutable clinical decision record tracking system outputs, rules, and outcomes."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:12]}", description="Unique decision identifier")
    decision_type: DecisionType = Field(description="Controlled decision category")
    patient_id: str = Field(description="Target patient identifier")
    resource_type: Optional[str] = Field(default=None, description="Associated clinical resource type")
    resource_id: Optional[str] = Field(default=None, description="Associated clinical resource ID")
    resource_version: Optional[int] = Field(default=None, description="Version of resource at decision time (Phase 46)")
    status: DecisionStatus = Field(default=DecisionStatus.GENERATED, description="Lifecycle state")
    initiating_actor_id: str = Field(description="User or service initiating evaluation")
    initiating_actor_role: str = Field(description="Role of initiating actor")
    initiating_actor_type: DecisionProvenanceSource = Field(default=DecisionProvenanceSource.SYSTEM)
    source_service: str = Field(description="Subsystem generating decision e.g. triage_service, medication_safety")
    inputs: List[DecisionInputReference] = Field(default_factory=list, description="Traceable input references")
    output_payload: Dict[str, Any] = Field(default_factory=dict, description="Generated recommendation or result")
    rule_metadata: Optional[DecisionRuleMetadata] = None
    model_metadata: Optional[DecisionModelMetadata] = None
    requires_human_oversight: bool = Field(default=False, description="True if clinician oversight is mandatory prior to application")
    is_current: bool = Field(default=True, description="True if active; False if superseded or cancelled")
    superseded_by_id: Optional[str] = Field(default=None, description="ID of replacement decision if superseded")
    supersedes_id: Optional[str] = Field(default=None, description="ID of prior decision replaced by this record")
    downstream_action_type: Optional[str] = Field(default=None, description="Type of clinical action triggered")
    downstream_action_id: Optional[str] = Field(default=None, description="ID of downstream entity (alert, task, workflow)")
    applied_at: Optional[datetime] = Field(default=None, description="Timestamp when decision was applied")
    expires_at: Optional[datetime] = Field(default=None, description="Time-to-live expiration timestamp")
    correlation_id: Optional[str] = Field(default=None, description="Request correlation tracking ID")
    idempotency_key: Optional[str] = Field(default=None, description="Client idempotency key")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionCreateRequest(BaseModel):
    """Contract for initiating or registering a clinical decision."""

    model_config = ConfigDict(extra="forbid")

    decision_type: DecisionType
    patient_id: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_version: Optional[int] = None
    source_service: str
    inputs: List[DecisionInputReference] = Field(default_factory=list)
    output_payload: Dict[str, Any]
    rule_metadata: Optional[DecisionRuleMetadata] = None
    model_metadata: Optional[DecisionModelMetadata] = None
    requires_human_oversight: bool = False
    expires_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None


class DecisionApplyRequest(BaseModel):
    """Request contract for applying an approved decision to clinical workflow."""

    model_config = ConfigDict(extra="forbid")

    expected_resource_version: Optional[int] = Field(default=None, description="Current resource version check (Phase 46)")
    application_reason: str = Field(min_length=3, max_length=500, description="Clinical justification for application")
    downstream_action_type: Optional[str] = Field(default=None, description="Action type to trigger")
    idempotency_key: Optional[str] = None

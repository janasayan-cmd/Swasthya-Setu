"""Feature flags and configuration governance abstractions for HealthSetu (Phase 25).

Defines typed categories, flag states, lifecycle states, context structures,
kill switch constants, and standard flag registries with safe defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagState(str, Enum):
    """Evaluation state of a feature flag."""
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    PERCENTAGE_ROLLOUT = "PERCENTAGE_ROLLOUT"
    ALLOWLIST = "ALLOWLIST"
    ORGANIZATION_ROLLOUT = "ORGANIZATION_ROLLOUT"
    ENVIRONMENT_ONLY = "ENVIRONMENT_ONLY"


class FeatureFlagLifecycle(str, Enum):
    """Lifecycle phase of a feature flag."""
    PROPOSED = "PROPOSED"
    CREATED = "CREATED"
    TESTING = "TESTING"
    STAGING = "STAGING"
    ROLLOUT = "ROLLOUT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    REMOVED = "REMOVED"


class ConfigurationCategory(str, Enum):
    """Centralized configuration categories (TRD Sec 7)."""
    APPLICATION = "APPLICATION"
    SECURITY = "SECURITY"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    CONSENT = "CONSENT"
    DATABASE = "DATABASE"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    MEDICATION = "MEDICATION"
    MEDICATION_SAFETY = "MEDICATION_SAFETY"
    TRIAGE = "TRIAGE"
    CARE_PLAN = "CARE_PLAN"
    CLINICAL_WORKFLOW = "CLINICAL_WORKFLOW"
    FACILITY_DISCOVERY = "FACILITY_DISCOVERY"
    TRANSFER = "TRANSFER"
    INTEROPERABILITY = "INTEROPERABILITY"
    AI = "AI"
    ASYNC_PROCESSING = "ASYNC_PROCESSING"
    PRIVACY = "PRIVACY"
    OBSERVABILITY = "OBSERVABILITY"
    RATE_LIMITING = "RATE_LIMITING"
    STORAGE = "STORAGE"
    EXTERNAL_PROVIDERS = "EXTERNAL_PROVIDERS"


class ValidationLevel(str, Enum):
    """Configuration requirement level (TRD Sec 15)."""
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"
    DEVELOPMENT_ONLY = "DEVELOPMENT_ONLY"
    TEST_ONLY = "TEST_ONLY"
    PRODUCTION_REQUIRED = "PRODUCTION_REQUIRED"


class FeatureFlagName(str, Enum):
    """Canonical feature flag names (TRD Sec 17)."""
    DOCUMENT_PROCESSING_ENABLED = "DOCUMENT_PROCESSING_ENABLED"
    MEDICATION_NORMALIZATION_ENABLED = "MEDICATION_NORMALIZATION_ENABLED"
    MEDICATION_SAFETY_ENABLED = "MEDICATION_SAFETY_ENABLED"
    TRIAGE_ENABLED = "TRIAGE_ENABLED"
    SBAR_ENABLED = "SBAR_ENABLED"
    CARE_PLAN_GENERATION_ENABLED = "CARE_PLAN_GENERATION_ENABLED"
    CLINICAL_WORKSPACE_ENABLED = "CLINICAL_WORKSPACE_ENABLED"
    FACILITY_DISCOVERY_ENABLED = "FACILITY_DISCOVERY_ENABLED"
    TRANSFER_ENABLED = "TRANSFER_ENABLED"
    INTEROPERABILITY_ENABLED = "INTEROPERABILITY_ENABLED"
    FHIR_ENABLED = "FHIR_ENABLED"
    AI_PROCESSING_ENABLED = "AI_PROCESSING_ENABLED"
    CLINICAL_AI_ASSISTANCE_ENABLED = "CLINICAL_AI_ASSISTANCE_ENABLED"
    ASYNC_PROCESSING_ENABLED = "ASYNC_PROCESSING_ENABLED"
    DATA_EXPORT_ENABLED = "DATA_EXPORT_ENABLED"


class KillSwitchName(str, Enum):
    """Canonical operational emergency kill switches (TRD Sec 23)."""
    AI_PROCESSING_KILL_SWITCH = "AI_PROCESSING_KILL_SWITCH"
    MEDICATION_SAFETY_PROVIDER_KILL_SWITCH = "MEDICATION_SAFETY_PROVIDER_KILL_SWITCH"
    DOCUMENT_PROCESSING_KILL_SWITCH = "DOCUMENT_PROCESSING_KILL_SWITCH"
    INTEROPERABILITY_KILL_SWITCH = "INTEROPERABILITY_KILL_SWITCH"


class FeatureFlagContext(BaseModel):
    """Contextual metadata passed for dynamic and deterministic flag evaluation."""
    model_config = ConfigDict(extra="ignore")

    environment: Optional[str] = None
    user_id: Optional[str] = None
    user_role: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    clinician_id: Optional[str] = None
    patient_id: Optional[str] = None
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)


class FeatureFlagDefinition(BaseModel):
    """Typed metadata and evaluation parameters for a feature flag."""
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    category: ConfigurationCategory
    state: FeatureFlagState = FeatureFlagState.ENABLED
    lifecycle: FeatureFlagLifecycle = FeatureFlagLifecycle.ACTIVE
    default_enabled: bool = True
    owner: str = "backend-team"
    dependencies: List[str] = Field(default_factory=list)
    percentage: Optional[int] = Field(default=None, ge=0, le=100)
    allowlist_users: List[str] = Field(default_factory=list)
    allowlist_organizations: List[str] = Field(default_factory=list)
    allowlist_facilities: List[str] = Field(default_factory=list)
    environments: List[str] = Field(default_factory=lambda: ["development", "testing", "staging", "production"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KillSwitchState(BaseModel):
    """Operational status of a system kill switch."""
    model_config = ConfigDict(extra="ignore")

    name: str
    is_active: bool = False
    description: str = ""
    category: ConfigurationCategory = ConfigurationCategory.SECURITY
    activated_by: Optional[str] = None
    activated_at: Optional[datetime] = None
    reason: Optional[str] = None


# Default feature flag registry with explicit dependencies and safe defaults
DEFAULT_FEATURE_FLAGS: Dict[str, FeatureFlagDefinition] = {
    FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value,
        description="Enables document upload, OCR, and medical text extraction",
        category=ConfigurationCategory.DOCUMENT_PROCESSING,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.MEDICATION_NORMALIZATION_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.MEDICATION_NORMALIZATION_ENABLED.value,
        description="Enables drug terminology normalization and RxNorm code mapping",
        category=ConfigurationCategory.MEDICATION,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.MEDICATION_SAFETY_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.MEDICATION_SAFETY_ENABLED.value,
        description="Enables drug-drug interaction and allergy contraindication checks",
        category=ConfigurationCategory.MEDICATION_SAFETY,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[FeatureFlagName.MEDICATION_NORMALIZATION_ENABLED.value],
    ),
    FeatureFlagName.TRIAGE_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.TRIAGE_ENABLED.value,
        description="Enables clinical symptom evaluation and emergency triage acuity categorization",
        category=ConfigurationCategory.TRIAGE,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.SBAR_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.SBAR_ENABLED.value,
        description="Enables clinical SBAR handoff note generation",
        category=ConfigurationCategory.CLINICAL_WORKFLOW,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[FeatureFlagName.TRIAGE_ENABLED.value],
    ),
    FeatureFlagName.CARE_PLAN_GENERATION_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.CARE_PLAN_GENERATION_ENABLED.value,
        description="Enables discharge care plan extraction and structuring",
        category=ConfigurationCategory.CARE_PLAN,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value],
    ),
    FeatureFlagName.CLINICAL_WORKSPACE_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.CLINICAL_WORKSPACE_ENABLED.value,
        description="Enables clinician assessments, notes, and digital signing",
        category=ConfigurationCategory.CLINICAL_WORKFLOW,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.FACILITY_DISCOVERY_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.FACILITY_DISCOVERY_ENABLED.value,
        description="Enables geo-aware healthcare facility and service discovery",
        category=ConfigurationCategory.FACILITY_DISCOVERY,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.TRANSFER_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.TRANSFER_ENABLED.value,
        description="Enables cross-facility patient transfer requests and handoffs",
        category=ConfigurationCategory.TRANSFER,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[FeatureFlagName.FACILITY_DISCOVERY_ENABLED.value],
    ),
    FeatureFlagName.INTEROPERABILITY_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.INTEROPERABILITY_ENABLED.value,
        description="Enables external healthcare data interchange",
        category=ConfigurationCategory.INTEROPERABILITY,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.FHIR_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.FHIR_ENABLED.value,
        description="Enables FHIR R4 resource import/export pipelines",
        category=ConfigurationCategory.INTEROPERABILITY,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[FeatureFlagName.INTEROPERABILITY_ENABLED.value],
    ),
    FeatureFlagName.AI_PROCESSING_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.AI_PROCESSING_ENABLED.value,
        description="Enables generative AI clinical copilot and assistant services",
        category=ConfigurationCategory.AI,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value,
        description="Enables AI clinical reasoning support and automated summarization",
        category=ConfigurationCategory.AI,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[FeatureFlagName.AI_PROCESSING_ENABLED.value],
    ),
    FeatureFlagName.ASYNC_PROCESSING_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.ASYNC_PROCESSING_ENABLED.value,
        description="Enables asynchronous worker task and event handling queues",
        category=ConfigurationCategory.ASYNC_PROCESSING,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
    FeatureFlagName.DATA_EXPORT_ENABLED.value: FeatureFlagDefinition(
        name=FeatureFlagName.DATA_EXPORT_ENABLED.value,
        description="Enables controlled patient data export workflows",
        category=ConfigurationCategory.PRIVACY,
        state=FeatureFlagState.ENABLED,
        lifecycle=FeatureFlagLifecycle.ACTIVE,
        default_enabled=True,
        dependencies=[],
    ),
}

DEFAULT_KILL_SWITCHES: Dict[str, KillSwitchState] = {
    KillSwitchName.AI_PROCESSING_KILL_SWITCH.value: KillSwitchState(
        name=KillSwitchName.AI_PROCESSING_KILL_SWITCH.value,
        description="Immediately halt all generative AI operations across the platform",
        category=ConfigurationCategory.AI,
        is_active=False,
    ),
    KillSwitchName.MEDICATION_SAFETY_PROVIDER_KILL_SWITCH.value: KillSwitchState(
        name=KillSwitchName.MEDICATION_SAFETY_PROVIDER_KILL_SWITCH.value,
        description="Immediately halt medication safety provider integrations to prevent inaccurate evaluations",
        category=ConfigurationCategory.MEDICATION_SAFETY,
        is_active=False,
    ),
    KillSwitchName.DOCUMENT_PROCESSING_KILL_SWITCH.value: KillSwitchState(
        name=KillSwitchName.DOCUMENT_PROCESSING_KILL_SWITCH.value,
        description="Immediately halt optical character recognition and document ingestion",
        category=ConfigurationCategory.DOCUMENT_PROCESSING,
        is_active=False,
    ),
    KillSwitchName.INTEROPERABILITY_KILL_SWITCH.value: KillSwitchState(
        name=KillSwitchName.INTEROPERABILITY_KILL_SWITCH.value,
        description="Immediately halt FHIR/HL7 external interoperability gateways",
        category=ConfigurationCategory.INTEROPERABILITY,
        is_active=False,
    ),
}

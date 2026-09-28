"""Feature flag schemas and request/response models for HealthSetu (Phase 25)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.core.feature_flags import (
    ConfigurationCategory,
    FeatureFlagLifecycle,
    FeatureFlagState,
)


class FeatureFlagResponse(BaseModel):
    """Public representation of a feature flag definition."""
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    category: ConfigurationCategory
    state: FeatureFlagState
    lifecycle: FeatureFlagLifecycle
    default_enabled: bool
    owner: str
    dependencies: List[str]
    percentage: Optional[int] = None
    allowlist_users: List[str] = Field(default_factory=list)
    allowlist_organizations: List[str] = Field(default_factory=list)
    allowlist_facilities: List[str] = Field(default_factory=list)
    environments: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FeatureFlagListResponse(BaseModel):
    """List response for administrative feature flag queries."""
    model_config = ConfigDict(extra="ignore")

    total: int
    items: List[FeatureFlagResponse]


class FeatureFlagUpdateRequest(BaseModel):
    """Administrative request to update flag state or metadata."""
    model_config = ConfigDict(extra="ignore")

    state: Optional[FeatureFlagState] = None
    lifecycle: Optional[FeatureFlagLifecycle] = None
    reason: str = Field(..., min_length=3, description="Justification for modifying flag state")


class FeatureFlagRolloutRequest(BaseModel):
    """Administrative request to configure controlled rollout rules."""
    model_config = ConfigDict(extra="ignore")

    state: FeatureFlagState = Field(
        ...,
        description="Rollout strategy: PERCENTAGE_ROLLOUT, ALLOWLIST, ORGANIZATION_ROLLOUT, or ENABLED",
    )
    percentage: Optional[int] = Field(None, ge=0, le=100)
    allowlist_users: Optional[List[str]] = None
    allowlist_organizations: Optional[List[str]] = None
    allowlist_facilities: Optional[List[str]] = None
    environments: Optional[List[str]] = None
    reason: str = Field(..., min_length=3, description="Audit reason for rollout strategy change")


class KillSwitchResponse(BaseModel):
    """Operational status of a safety kill switch."""
    model_config = ConfigDict(extra="ignore")

    name: str
    is_active: bool
    description: str
    category: ConfigurationCategory
    activated_by: Optional[str] = None
    activated_at: Optional[datetime] = None
    reason: Optional[str] = None


class KillSwitchActionRequest(BaseModel):
    """Request to activate or deactivate an operational kill switch."""
    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=5, description="Mandatory operational justification for kill switch action")


class SystemCapabilitiesResponse(BaseModel):
    """Safe, non-sensitive capability overview for public / authenticated client consumption.
    
    Never exposes internal URLs, secrets, topology, or private flags.
    """
    model_config = ConfigDict(extra="ignore")

    environment: str
    document_processing_available: bool
    medication_normalization_available: bool
    medication_safety_available: bool
    triage_available: bool
    sbar_available: bool
    care_plan_available: bool
    clinical_workspace_available: bool
    facility_discovery_available: bool
    transfer_available: bool
    interoperability_available: bool
    fhir_available: bool
    ai_assistance_available: bool
    async_processing_available: bool
    data_export_available: bool

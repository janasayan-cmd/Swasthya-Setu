"""Configuration governance schemas for HealthSetu (Phase 25)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.core.feature_flags import ConfigurationCategory, ValidationLevel


class ConfigurationItemSummary(BaseModel):
    """Safe, non-secret summary of an application configuration setting."""
    model_config = ConfigDict(extra="ignore")

    key: str
    category: ConfigurationCategory
    level: ValidationLevel
    is_configured: bool
    is_sensitive: bool = False
    description: str = ""


class ConfigurationValidationIssue(BaseModel):
    """Individual configuration validation or dependency failure."""
    model_config = ConfigDict(extra="ignore")

    setting: str
    level: ValidationLevel
    message: str
    category: ConfigurationCategory


class ConfigurationValidationResponse(BaseModel):
    """Results of application startup or on-demand configuration integrity validation."""
    model_config = ConfigDict(extra="ignore")

    status: str  # VALID, DEGRADED, INVALID
    environment: str
    total_checked: int
    passed: bool
    issues: List[ConfigurationValidationIssue] = Field(default_factory=list)
    timestamp: datetime


class ConfigurationDriftItem(BaseModel):
    """Item-level drift between active runtime configuration and baseline environment expectations."""
    model_config = ConfigDict(extra="ignore")

    setting: str
    category: ConfigurationCategory
    expected: str
    actual: str
    severity: str  # INFO, WARNING, CRITICAL


class ConfigurationDriftResponse(BaseModel):
    """Report detailing detected configuration drift."""
    model_config = ConfigDict(extra="ignore")

    environment: str
    has_drift: bool
    drift_count: int
    items: List[ConfigurationDriftItem] = Field(default_factory=list)
    evaluated_at: datetime


class ProviderStatusResponse(BaseModel):
    """Metadata describing configured domain providers without exposing API credentials."""
    model_config = ConfigDict(extra="ignore")

    category: ConfigurationCategory
    provider_name: str
    is_mock: bool
    is_operational: bool
    supported_versions: List[str] = Field(default_factory=list)

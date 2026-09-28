"""Central configuration governance, validation, and drift analysis service (Phase 25)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.exceptions import ConfigurationInvalidException
from app.core.feature_flags import (
    ConfigurationCategory,
    FeatureFlagContext,
    FeatureFlagName,
    ValidationLevel,
)
from app.core.metrics import (
    CONFIGURATION_DRIFT_COUNTER,
    CONFIGURATION_VALIDATION_FAILURES_COUNTER,
)
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.configuration import (
    ConfigurationDriftItem,
    ConfigurationDriftResponse,
    ConfigurationValidationIssue,
    ConfigurationValidationResponse,
    ProviderStatusResponse,
)
from app.schemas.feature_flag import SystemCapabilitiesResponse
from app.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger("app.configuration_service")


class ConfigurationService:
    """Service governing typed settings integrity, dependency validation, and drift analysis."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        feature_flag_service: Optional[FeatureFlagService] = None,
        audit_repo: Optional[AuditRepository] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.flags = feature_flag_service or FeatureFlagService(settings=self.settings)
        self.audit_repo = audit_repo or AuditRepository()

    # -----------------------------------------------------------------------
    # Configuration Validation & Dependency Checks (TRD Sec 14, 15, 16)
    # -----------------------------------------------------------------------

    def validate_configuration(
        self, fail_fast: bool = False
    ) -> ConfigurationValidationResponse:
        """Validate application configuration against requirements, dependencies, and environment rules."""
        issues: List[ConfigurationValidationIssue] = []
        is_prod = self.settings.is_production
        env = self.settings.APP_ENV

        # 1. Production Requirements
        if is_prod:
            if not self.settings.DATABASE_URL:
                issues.append(
                    ConfigurationValidationIssue(
                        setting="DATABASE_URL",
                        level=ValidationLevel.PRODUCTION_REQUIRED,
                        message="DATABASE_URL must be configured in production environments.",
                        category=ConfigurationCategory.DATABASE,
                    )
                )

            if self.settings.DEBUG:
                issues.append(
                    ConfigurationValidationIssue(
                        setting="DEBUG",
                        level=ValidationLevel.PRODUCTION_REQUIRED,
                        message="DEBUG mode must be set to False in production.",
                        category=ConfigurationCategory.APPLICATION,
                    )
                )

            if getattr(self.settings, "SECRET_KEY", None) in (
                "insecure-default-change-me",
                "secret",
                "change-me",
                "",
                None,
            ):
                issues.append(
                    ConfigurationValidationIssue(
                        setting="SECRET_KEY",
                        level=ValidationLevel.PRODUCTION_REQUIRED,
                        message="SECRET_KEY must be set to a secure, non-default cryptographic key.",
                        category=ConfigurationCategory.SECURITY,
                    )
                )

        # 2. Conditional Dependencies (TRD Sec 16)
        # AI Provider credentials
        if self.settings.AI_PROVIDER.lower() in ("openai", "gemini", "anthropic"):
            if not self.settings.AI_API_KEY:
                issues.append(
                    ConfigurationValidationIssue(
                        setting="AI_API_KEY",
                        level=ValidationLevel.CONDITIONAL,
                        message=f"AI_API_KEY is required when AI_PROVIDER is set to '{self.settings.AI_PROVIDER}'.",
                        category=ConfigurationCategory.AI,
                    )
                )

        # Medication Safety Provider credentials
        if self.settings.MEDICATION_SAFETY_PROVIDER.lower() in ("licensed_provider", "external"):
            if not self.settings.MEDICATION_SAFETY_API_KEY:
                issues.append(
                    ConfigurationValidationIssue(
                        setting="MEDICATION_SAFETY_API_KEY",
                        level=ValidationLevel.CONDITIONAL,
                        message="MEDICATION_SAFETY_API_KEY is required for external medication safety provider.",
                        category=ConfigurationCategory.MEDICATION_SAFETY,
                    )
                )

        # Interoperability dependencies
        if self.settings.FHIR_ENABLED and not self.settings.INTEROPERABILITY_ENABLED:
            issues.append(
                ConfigurationValidationIssue(
                    setting="FHIR_ENABLED",
                    level=ValidationLevel.CONDITIONAL,
                    message="FHIR_ENABLED requires INTEROPERABILITY_ENABLED to be True.",
                    category=ConfigurationCategory.INTEROPERABILITY,
                )
            )

        if self.settings.CARE_PLAN_GENERATION_ENABLED and not self.settings.DOCUMENT_PROCESSING_ENABLED:
            issues.append(
                ConfigurationValidationIssue(
                    setting="CARE_PLAN_GENERATION_ENABLED",
                    level=ValidationLevel.CONDITIONAL,
                    message="CARE_PLAN_GENERATION_ENABLED requires DOCUMENT_PROCESSING_ENABLED to be True.",
                    category=ConfigurationCategory.CARE_PLAN,
                )
            )

        if self.settings.CLINICAL_AI_ASSISTANCE_ENABLED and not self.settings.AI_PROCESSING_ENABLED:
            issues.append(
                ConfigurationValidationIssue(
                    setting="CLINICAL_AI_ASSISTANCE_ENABLED",
                    level=ValidationLevel.CONDITIONAL,
                    message="CLINICAL_AI_ASSISTANCE_ENABLED requires AI_PROCESSING_ENABLED to be True.",
                    category=ConfigurationCategory.AI,
                )
            )

        if self.settings.TRANSFER_ENABLED and not self.settings.FACILITY_DISCOVERY_ENABLED:
            issues.append(
                ConfigurationValidationIssue(
                    setting="TRANSFER_ENABLED",
                    level=ValidationLevel.CONDITIONAL,
                    message="TRANSFER_ENABLED requires FACILITY_DISCOVERY_ENABLED to be True.",
                    category=ConfigurationCategory.TRANSFER,
                )
            )

        total_checked = 20
        passed = len(issues) == 0
        status = "VALID" if passed else ("INVALID" if is_prod else "DEGRADED")

        if not passed:
            try:
                CONFIGURATION_VALIDATION_FAILURES_COUNTER.labels(
                    environment=env, severity=status
                ).inc()
            except Exception:
                pass

        if not passed and (fail_fast or (is_prod and self.settings.CONFIG_GOVERNANCE_STRICT_MODE)):
            error_details = [{"setting": i.setting, "message": i.message} for i in issues]
            raise ConfigurationInvalidException(
                message="Application configuration validation failed with critical errors.",
                details=error_details,
            )

        return ConfigurationValidationResponse(
            status=status,
            environment=env,
            total_checked=total_checked,
            passed=passed,
            issues=issues,
            timestamp=datetime.now(timezone.utc),
        )

    # -----------------------------------------------------------------------
    # Configuration Drift Detection (TRD Sec 31)
    # -----------------------------------------------------------------------

    def detect_drift(self, environment: Optional[str] = None) -> ConfigurationDriftResponse:
        """Detect configuration divergence between active settings and expected environment baseline."""
        target_env = environment or self.settings.APP_ENV
        items: List[ConfigurationDriftItem] = []

        # Compare against baseline expectations
        if target_env == "production":
            if self.settings.DEBUG:
                items.append(
                    ConfigurationDriftItem(
                        setting="DEBUG",
                        category=ConfigurationCategory.APPLICATION,
                        expected="False",
                        actual=str(self.settings.DEBUG),
                        severity="CRITICAL",
                    )
                )
            if self.settings.MEDICATION_SAFETY_PROVIDER == "mock":
                items.append(
                    ConfigurationDriftItem(
                        setting="MEDICATION_SAFETY_PROVIDER",
                        category=ConfigurationCategory.MEDICATION_SAFETY,
                        expected="licensed_provider",
                        actual="mock",
                        severity="WARNING",
                    )
                )
            if self.settings.AI_PROVIDER == "mock":
                items.append(
                    ConfigurationDriftItem(
                        setting="AI_PROVIDER",
                        category=ConfigurationCategory.AI,
                        expected="approved_cloud_ai",
                        actual="mock",
                        severity="INFO",
                    )
                )

        has_drift = len(items) > 0
        if has_drift:
            try:
                CONFIGURATION_DRIFT_COUNTER.labels(environment=target_env).inc()
            except Exception:
                pass

        return ConfigurationDriftResponse(
            environment=target_env,
            has_drift=has_drift,
            drift_count=len(items),
            items=items,
            evaluated_at=datetime.now(timezone.utc),
        )

    # -----------------------------------------------------------------------
    # Safe Capabilities Discovery (TRD Sec 28)
    # -----------------------------------------------------------------------

    def get_system_capabilities(
        self, context: Optional[FeatureFlagContext] = None
    ) -> SystemCapabilitiesResponse:
        """Expose safe, non-sensitive capability booleans without leaking credentials or topology."""
        ctx = context or FeatureFlagContext(environment=self.settings.APP_ENV)

        return SystemCapabilitiesResponse(
            environment=self.settings.APP_ENV,
            document_processing_available=self.flags.is_enabled(
                FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value, ctx
            ),
            medication_normalization_available=self.flags.is_enabled(
                FeatureFlagName.MEDICATION_NORMALIZATION_ENABLED.value, ctx
            ),
            medication_safety_available=self.flags.is_enabled(
                FeatureFlagName.MEDICATION_SAFETY_ENABLED.value, ctx
            ),
            triage_available=self.flags.is_enabled(
                FeatureFlagName.TRIAGE_ENABLED.value, ctx
            ),
            sbar_available=self.flags.is_enabled(
                FeatureFlagName.SBAR_ENABLED.value, ctx
            ),
            care_plan_available=self.flags.is_enabled(
                FeatureFlagName.CARE_PLAN_GENERATION_ENABLED.value, ctx
            ),
            clinical_workspace_available=self.flags.is_enabled(
                FeatureFlagName.CLINICAL_WORKSPACE_ENABLED.value, ctx
            ),
            facility_discovery_available=self.flags.is_enabled(
                FeatureFlagName.FACILITY_DISCOVERY_ENABLED.value, ctx
            ),
            transfer_available=self.flags.is_enabled(
                FeatureFlagName.TRANSFER_ENABLED.value, ctx
            ),
            interoperability_available=self.flags.is_enabled(
                FeatureFlagName.INTEROPERABILITY_ENABLED.value, ctx
            ),
            fhir_available=self.flags.is_enabled(
                FeatureFlagName.FHIR_ENABLED.value, ctx
            ),
            ai_assistance_available=self.flags.is_enabled(
                FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value, ctx
            ),
            async_processing_available=self.flags.is_enabled(
                FeatureFlagName.ASYNC_PROCESSING_ENABLED.value, ctx
            ),
            data_export_available=self.flags.is_enabled(
                FeatureFlagName.DATA_EXPORT_ENABLED.value, ctx
            ),
        )

    def list_providers(self) -> List[ProviderStatusResponse]:
        """Summarize configured domain providers safely."""
        return [
            ProviderStatusResponse(
                category=ConfigurationCategory.MEDICATION_SAFETY,
                provider_name=self.settings.MEDICATION_SAFETY_PROVIDER,
                is_mock=self.settings.MEDICATION_SAFETY_PROVIDER == "mock",
                is_operational=not self.flags.is_kill_switch_active("MEDICATION_SAFETY_PROVIDER_KILL_SWITCH"),
                supported_versions=["v1.0"],
            ),
            ProviderStatusResponse(
                category=ConfigurationCategory.AI,
                provider_name=self.settings.AI_PROVIDER,
                is_mock=self.settings.AI_PROVIDER == "mock",
                is_operational=not self.flags.is_kill_switch_active("AI_PROCESSING_KILL_SWITCH"),
                supported_versions=["v1.0"],
            ),
            ProviderStatusResponse(
                category=ConfigurationCategory.DOCUMENT_PROCESSING,
                provider_name=self.settings.OCR_PROVIDER,
                is_mock=self.settings.OCR_PROVIDER == "mock",
                is_operational=not self.flags.is_kill_switch_active("DOCUMENT_PROCESSING_KILL_SWITCH"),
                supported_versions=["v1.0"],
            ),
            ProviderStatusResponse(
                category=ConfigurationCategory.INTEROPERABILITY,
                provider_name=self.settings.INTEROPERABILITY_PROVIDER,
                is_mock=self.settings.INTEROPERABILITY_PROVIDER == "internal",
                is_operational=not self.flags.is_kill_switch_active("INTEROPERABILITY_KILL_SWITCH"),
                supported_versions=[self.settings.FHIR_VERSION, self.settings.HL7_VERSION],
            ),
        ]

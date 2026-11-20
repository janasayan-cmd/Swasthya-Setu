"""Phase 71: Analytics Configuration & Versioning Service.

Coordinates:
- Creation of versioned analytical configurations
- Governance approval of configuration versions
- Retrieval of active configuration for reproducible scoring and matching
- Safe deprecation of superseded configurations
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_intelligence_repository import (
    GovernanceAuditIntelligenceRepository,
    get_governance_audit_intelligence_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_analytics_config import (
    AnalyticsConfigRecord,
    ApproveAnalyticsConfigRequest,
    CreateAnalyticsConfigRequest,
    DeprecateAnalyticsConfigRequest,
)
from app.schemas.user import AuthenticatedUserContext


class AuditAnalyticsConfigService:
    """Service governing analytical configuration lifecycle and version tracking."""

    def __init__(
        self, repository: Optional[GovernanceAuditIntelligenceRepository] = None
    ) -> None:
        self.repository = repository or get_governance_audit_intelligence_repository()

    def get_or_create_default_config(self, organization_id: str) -> AnalyticsConfigRecord:
        """Retrieve active configuration or bootstrap standard approved v1.0.0 configuration."""
        active = self.repository.get_active_config(organization_id)
        if active:
            return active

        default_cfg = AnalyticsConfigRecord(
            version="v1.0.0",
            name="Standard Clinical Safety Audit Intelligence Configuration",
            description="Default deterministic rules for repeat matching, pattern detection, and systemic scoring.",
            repeat_matching_rules={
                "match_category": True,
                "match_control": True,
                "match_process": True,
                "min_similarity_score": 0.65,
            },
            severity_weights={
                "CRITICAL": 10.0,
                "URGENT": 7.0,
                "HIGH": 5.0,
                "ELEVATED": 3.0,
                "ROUTINE": 1.0,
            },
            pattern_detection_thresholds={
                "min_findings_per_pattern": 2,
                "min_facilities_for_cross_unit": 2,
            },
            priority_scoring_factors={
                "severity_weight": 0.35,
                "recurrence_weight": 0.25,
                "facility_spread_weight": 0.20,
                "unresolved_duration_weight": 0.20,
            },
            is_active=True,
            is_deprecated=False,
            approved_by="SYSTEM_BOOTSTRAP",
            approved_at=datetime.now(timezone.utc),
            created_by="SYSTEM_BOOTSTRAP",
            organization_id=organization_id,
        )
        return self.repository.save_config(default_cfg)

    def create_config(
        self, user: AuthenticatedUserContext, payload: CreateAnalyticsConfigRequest
    ) -> AnalyticsConfigRecord:
        """Establish a new draft analytical configuration version."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can create analytics configurations.",
                status_code=403,
            )

        # Increment semantic version based on existing configs
        existing = self.repository.list_configs(user.organization_id)
        next_ver = f"v1.{len(existing)}.0"

        now = datetime.now(timezone.utc)
        record = AnalyticsConfigRecord(
            version=next_ver,
            name=payload.name,
            description=payload.description,
            repeat_matching_rules=payload.repeat_matching_rules
            or {
                "match_category": True,
                "match_control": True,
                "match_process": True,
                "min_similarity_score": 0.65,
            },
            severity_weights=payload.severity_weights
            or {
                "CRITICAL": 10.0,
                "URGENT": 7.0,
                "HIGH": 5.0,
                "ELEVATED": 3.0,
                "ROUTINE": 1.0,
            },
            pattern_detection_thresholds=payload.pattern_detection_thresholds
            or {
                "min_findings_per_pattern": 2,
                "min_facilities_for_cross_unit": 2,
            },
            priority_scoring_factors=payload.priority_scoring_factors
            or {
                "severity_weight": 0.35,
                "recurrence_weight": 0.25,
                "facility_spread_weight": 0.20,
                "unresolved_duration_weight": 0.20,
            },
            is_active=False,  # Requires formal approval before activation
            is_deprecated=False,
            created_by=user.user_id,
            created_at=now,
            organization_id=user.organization_id,
            metadata=payload.metadata or {},
        )
        return self.repository.save_config(record)

    def approve_config(
        self,
        user: AuthenticatedUserContext,
        configuration_id: str,
        payload: ApproveAnalyticsConfigRequest,
    ) -> AnalyticsConfigRecord:
        """Formally approve and activate an analytics configuration."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can approve analytics configurations.",
                status_code=403,
            )

        cfg = self.repository.get_config(configuration_id)
        if not cfg:
            raise AppException(
                code=ErrorCode.ANALYTICS_CONFIGURATION_NOT_FOUND,
                message=f"Configuration {configuration_id} not found.",
                status_code=404,
            )
        if cfg.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot approve configuration across tenant boundaries.",
                status_code=403,
            )

        # Deactivate previous active configurations
        for c in self.repository.list_configs(user.organization_id):
            if c.is_active and c.configuration_id != configuration_id:
                c.is_active = False
                self.repository.save_config(c)

        now = datetime.now(timezone.utc)
        cfg.is_active = True
        cfg.approved_by = user.user_id
        cfg.approved_at = now
        cfg.metadata["approval_notes"] = payload.approval_notes
        return self.repository.save_config(cfg)

    def deprecate_config(
        self,
        user: AuthenticatedUserContext,
        configuration_id: str,
        payload: DeprecateAnalyticsConfigRequest,
    ) -> AnalyticsConfigRecord:
        """Deprecate an existing configuration."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can deprecate analytics configurations.",
                status_code=403,
            )

        cfg = self.repository.get_config(configuration_id)
        if not cfg:
            raise AppException(
                code=ErrorCode.ANALYTICS_CONFIGURATION_NOT_FOUND,
                message=f"Configuration {configuration_id} not found.",
                status_code=404,
            )
        if cfg.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot deprecate configuration across tenant boundaries.",
                status_code=403,
            )

        cfg.is_active = False
        cfg.is_deprecated = True
        cfg.metadata["deprecation_reason"] = payload.deprecation_reason
        return self.repository.save_config(cfg)

    def list_configs(self, user: AuthenticatedUserContext) -> List[AnalyticsConfigRecord]:
        """List versioned configurations within tenant scope."""
        configs = self.repository.list_configs(user.organization_id)
        if not configs:
            # Seed default if empty
            default_cfg = self.get_or_create_default_config(user.organization_id)
            return [default_cfg]
        return configs

    def get_config(
        self, user: AuthenticatedUserContext, configuration_id: str
    ) -> AnalyticsConfigRecord:
        """Retrieve a specific configuration ensuring tenant boundary enforcement."""
        cfg = self.repository.get_config(configuration_id)
        if not cfg:
            raise AppException(
                code=ErrorCode.ANALYTICS_CONFIGURATION_NOT_FOUND,
                message=f"Configuration {configuration_id} not found.",
                status_code=404,
            )
        if cfg.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access configuration across tenant boundaries.",
                status_code=403,
            )
        return cfg


# Global singleton
_global_config_service = AuditAnalyticsConfigService()


def get_audit_analytics_config_service() -> AuditAnalyticsConfigService:
    """Dependency provider for analytics configuration service."""
    return _global_config_service

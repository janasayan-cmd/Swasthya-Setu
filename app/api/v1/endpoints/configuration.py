"""Configuration governance, feature flags, controlled rollout, and kill switch API (Phase 25).

Implements:
- Administrative feature flag inspection, enabling, disabling, and gradual rollout
- Operational safety kill switches for emergency component halting
- Startup and on-demand configuration integrity validation
- Environment configuration drift analysis
- Safe public capability overview
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_configuration_service,
    get_current_user,
    get_feature_flag_service,
)
from app.core.exceptions import ForbiddenException
from app.core.policies import Permission, ROLE_PERMISSIONS
from app.schemas.auth import UserRole
from app.schemas.configuration import (
    ConfigurationDriftResponse,
    ConfigurationValidationResponse,
    ProviderStatusResponse,
)
from app.schemas.feature_flag import (
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagRolloutRequest,
    FeatureFlagUpdateRequest,
    KillSwitchActionRequest,
    KillSwitchResponse,
    SystemCapabilitiesResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.configuration_service import ConfigurationService
from app.services.feature_flag_service import FeatureFlagService

router = APIRouter(tags=["Configuration Governance & Feature Flags"])


def _require_permission(actor: AuthenticatedUserContext, permission: Permission) -> None:
    """Validate that authenticated actor holds the specified permission."""
    role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
    allowed = ROLE_PERMISSIONS.get(role_str, frozenset())
    if permission not in allowed:
        raise ForbiddenException(
            message=f"Actor lacks required administrative permission: '{permission.value}'."
        )


# ---------------------------------------------------------------------------
# Public / Authenticated Safe Capabilities API (TRD Sec 28)
# ---------------------------------------------------------------------------

@router.get(
    "/configuration/capabilities",
    response_model=SystemCapabilitiesResponse,
    summary="Get safe system capabilities overview",
    description="Returns high-level booleans indicating operational features without exposing credentials or internal topology.",
)
async def get_capabilities(
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)],
) -> SystemCapabilitiesResponse:
    return config_service.get_system_capabilities()


# ---------------------------------------------------------------------------
# Administrative Feature Flag Management (TRD Sec 27)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/configuration/features",
    response_model=FeatureFlagListResponse,
    summary="List all registered feature flags",
)
async def list_features(
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> FeatureFlagListResponse:
    _require_permission(actor, Permission.FEATURE_FLAG_READ)
    flags = flag_service.list_flags()
    return FeatureFlagListResponse(
        total=len(flags),
        items=[FeatureFlagResponse.model_validate(f.model_dump()) for f in flags],
    )


@router.get(
    "/admin/configuration/features/{flag_name}",
    response_model=FeatureFlagResponse,
    summary="Get feature flag details",
)
async def get_feature(
    flag_name: str,
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> FeatureFlagResponse:
    _require_permission(actor, Permission.FEATURE_FLAG_READ)
    flag = flag_service.get_flag(flag_name)
    return FeatureFlagResponse.model_validate(flag.model_dump())


@router.post(
    "/admin/configuration/features/{flag_name}/enable",
    response_model=FeatureFlagResponse,
    summary="Enable a feature flag",
)
async def enable_feature(
    flag_name: str,
    request: FeatureFlagUpdateRequest,
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> FeatureFlagResponse:
    _require_permission(actor, Permission.FEATURE_FLAG_MANAGE)
    flag = await flag_service.enable_flag(
        flag_name=flag_name,
        actor_id=actor.id,
        reason=request.reason,
    )
    return FeatureFlagResponse.model_validate(flag.model_dump())


@router.post(
    "/admin/configuration/features/{flag_name}/disable",
    response_model=FeatureFlagResponse,
    summary="Disable a feature flag",
)
async def disable_feature(
    flag_name: str,
    request: FeatureFlagUpdateRequest,
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> FeatureFlagResponse:
    _require_permission(actor, Permission.FEATURE_FLAG_MANAGE)
    flag = await flag_service.disable_flag(
        flag_name=flag_name,
        actor_id=actor.id,
        reason=request.reason,
    )
    return FeatureFlagResponse.model_validate(flag.model_dump())


@router.post(
    "/admin/configuration/features/{flag_name}/rollout",
    response_model=FeatureFlagResponse,
    summary="Configure controlled rollout strategy for a feature flag",
)
async def update_feature_rollout(
    flag_name: str,
    request: FeatureFlagRolloutRequest,
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> FeatureFlagResponse:
    _require_permission(actor, Permission.FEATURE_FLAG_MANAGE)
    flag = await flag_service.update_rollout(
        flag_name=flag_name,
        request=request,
        actor_id=actor.id,
    )
    return FeatureFlagResponse.model_validate(flag.model_dump())


# ---------------------------------------------------------------------------
# Operational Emergency Kill Switches (TRD Sec 23 & 24)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/configuration/kill-switches",
    response_model=List[KillSwitchResponse],
    summary="List operational safety kill switches",
)
async def list_kill_switches(
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> List[KillSwitchResponse]:
    _require_permission(actor, Permission.CONFIGURATION_READ)
    switches = flag_service.list_kill_switches()
    return [KillSwitchResponse.model_validate(s.model_dump()) for s in switches]


@router.post(
    "/admin/configuration/kill-switches/{switch_name}/activate",
    response_model=KillSwitchResponse,
    summary="Activate an operational safety kill switch (Emergency Halt)",
)
async def activate_kill_switch(
    switch_name: str,
    request: KillSwitchActionRequest,
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> KillSwitchResponse:
    _require_permission(actor, Permission.KILL_SWITCH_MANAGE)
    switch = await flag_service.activate_kill_switch(
        switch_name=switch_name,
        actor_id=actor.id,
        reason=request.reason,
    )
    return KillSwitchResponse.model_validate(switch.model_dump())


@router.post(
    "/admin/configuration/kill-switches/{switch_name}/deactivate",
    response_model=KillSwitchResponse,
    summary="Deactivate an operational kill switch",
)
async def deactivate_kill_switch(
    switch_name: str,
    request: KillSwitchActionRequest,
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    flag_service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> KillSwitchResponse:
    _require_permission(actor, Permission.KILL_SWITCH_MANAGE)
    switch = await flag_service.deactivate_kill_switch(
        switch_name=switch_name,
        actor_id=actor.id,
        reason=request.reason,
    )
    return KillSwitchResponse.model_validate(switch.model_dump())


# ---------------------------------------------------------------------------
# Configuration Validation & Drift (TRD Sec 14, 31)
# ---------------------------------------------------------------------------

@router.post(
    "/admin/configuration/validate",
    response_model=ConfigurationValidationResponse,
    summary="Run configuration integrity and dependency validation",
)
async def run_configuration_validation(
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)],
    fail_fast: bool = Query(False, description="Raise immediately on critical configuration errors"),
) -> ConfigurationValidationResponse:
    _require_permission(actor, Permission.CONFIGURATION_MANAGE)
    return config_service.validate_configuration(fail_fast=fail_fast)


@router.get(
    "/admin/configuration/drift",
    response_model=ConfigurationDriftResponse,
    summary="Analyze configuration drift across environments",
)
async def check_configuration_drift(
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)],
    target_environment: Optional[str] = Query(None, description="Target environment to compare against"),
) -> ConfigurationDriftResponse:
    _require_permission(actor, Permission.CONFIGURATION_READ)
    return config_service.detect_drift(environment=target_environment)


@router.get(
    "/admin/configuration/providers",
    response_model=List[ProviderStatusResponse],
    summary="List active domain providers safely",
)
async def list_configured_providers(
    actor: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)],
) -> List[ProviderStatusResponse]:
    _require_permission(actor, Permission.CONFIGURATION_READ)
    return config_service.list_providers()

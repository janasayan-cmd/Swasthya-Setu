"""Feature flag evaluation, rollout control, caching, and kill switch service (Phase 25)."""

from __future__ import annotations

import copy
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ConfigurationNotFoundException,
    FeatureDisabledException,
    KillSwitchActiveException,
)
from app.core.feature_flags import (
    DEFAULT_FEATURE_FLAGS,
    DEFAULT_KILL_SWITCHES,
    FeatureFlagContext,
    FeatureFlagDefinition,
    FeatureFlagLifecycle,
    FeatureFlagName,
    FeatureFlagState,
    KillSwitchName,
    KillSwitchState,
)
from app.core.metrics import (
    FEATURE_FLAG_DISABLED_COUNTER,
    FEATURE_FLAG_ENABLED_COUNTER,
    FEATURE_FLAG_EVALUATION_ERRORS_COUNTER,
    FEATURE_FLAG_EVALUATIONS_COUNTER,
    KILL_SWITCH_ACTIVATIONS_COUNTER,
)
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.feature_flag import FeatureFlagRolloutRequest

logger = logging.getLogger("app.feature_flag_service")


class FeatureFlagService:
    """Central evaluator for runtime feature flags, controlled rollouts, and kill switches."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        audit_repo: Optional[AuditRepository] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.audit_repo = audit_repo or AuditRepository()
        self._flags: Dict[str, FeatureFlagDefinition] = copy.deepcopy(DEFAULT_FEATURE_FLAGS)
        self._kill_switches: Dict[str, KillSwitchState] = copy.deepcopy(DEFAULT_KILL_SWITCHES)
        
        # In-memory evaluation cache with bounded TTL
        self._cache: Dict[str, tuple[bool, float]] = {}
        self._cache_ttl: float = float(self.settings.CONFIG_CACHE_TTL_SECONDS)

        # Synchronize flags with Settings environment overrides
        self._sync_from_settings()

    def _sync_from_settings(self) -> None:
        """Hydrate feature flag and kill switch defaults from Settings environment."""
        # Feature flag settings sync
        attr_map = {
            FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value: self.settings.DOCUMENT_PROCESSING_ENABLED,
            FeatureFlagName.MEDICATION_NORMALIZATION_ENABLED.value: self.settings.MEDICATION_NORMALIZATION_ENABLED,
            FeatureFlagName.MEDICATION_SAFETY_ENABLED.value: self.settings.MEDICATION_SAFETY_ENABLED,
            FeatureFlagName.TRIAGE_ENABLED.value: self.settings.TRIAGE_ENABLED,
            FeatureFlagName.SBAR_ENABLED.value: self.settings.SBAR_ENABLED,
            FeatureFlagName.CARE_PLAN_GENERATION_ENABLED.value: self.settings.CARE_PLAN_GENERATION_ENABLED,
            FeatureFlagName.CLINICAL_WORKSPACE_ENABLED.value: self.settings.CLINICAL_WORKSPACE_ENABLED,
            FeatureFlagName.FACILITY_DISCOVERY_ENABLED.value: self.settings.FACILITY_DISCOVERY_ENABLED,
            FeatureFlagName.TRANSFER_ENABLED.value: self.settings.TRANSFER_ENABLED,
            FeatureFlagName.INTEROPERABILITY_ENABLED.value: self.settings.INTEROPERABILITY_ENABLED,
            FeatureFlagName.FHIR_ENABLED.value: self.settings.FHIR_ENABLED,
            FeatureFlagName.AI_PROCESSING_ENABLED.value: self.settings.AI_PROCESSING_ENABLED,
            FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value: self.settings.CLINICAL_AI_ASSISTANCE_ENABLED,
            FeatureFlagName.ASYNC_PROCESSING_ENABLED.value: self.settings.ASYNC_PROCESSING_ENABLED,
            FeatureFlagName.DATA_EXPORT_ENABLED.value: self.settings.DATA_EXPORT_ENABLED,
        }
        for flag_name, is_enabled in attr_map.items():
            if flag_name in self._flags:
                self._flags[flag_name].state = (
                    FeatureFlagState.ENABLED if is_enabled else FeatureFlagState.DISABLED
                )

        # Kill switch settings sync
        switch_map = {
            KillSwitchName.AI_PROCESSING_KILL_SWITCH.value: self.settings.AI_PROCESSING_KILL_SWITCH,
            KillSwitchName.MEDICATION_SAFETY_PROVIDER_KILL_SWITCH.value: self.settings.MEDICATION_SAFETY_PROVIDER_KILL_SWITCH,
            KillSwitchName.DOCUMENT_PROCESSING_KILL_SWITCH.value: self.settings.DOCUMENT_PROCESSING_KILL_SWITCH,
            KillSwitchName.INTEROPERABILITY_KILL_SWITCH.value: self.settings.INTEROPERABILITY_KILL_SWITCH,
        }
        for switch_name, is_active in switch_map.items():
            if switch_name in self._kill_switches:
                self._kill_switches[switch_name].is_active = is_active
                if is_active:
                    self._kill_switches[switch_name].reason = "Activated by startup configuration"
                    self._kill_switches[switch_name].activated_at = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Kill Switch Management (TRD Sec 23 & 24)
    # -----------------------------------------------------------------------

    def is_kill_switch_active(self, switch_name: str) -> bool:
        """Check if an operational emergency kill switch is currently engaged."""
        switch = self._kill_switches.get(switch_name)
        if not switch:
            return False
        return switch.is_active

    async def activate_kill_switch(
        self, switch_name: str, actor_id: str, reason: str
    ) -> KillSwitchState:
        """Activate an operational emergency kill switch halting operations."""
        switch = self._kill_switches.get(switch_name)
        if not switch:
            raise ConfigurationNotFoundException(switch_name)

        previous_state = switch.is_active
        now = datetime.now(timezone.utc)
        switch.is_active = True
        switch.activated_by = actor_id
        switch.activated_at = now
        switch.reason = reason

        self.invalidate_cache()
        logger.warning(
            f"KILL SWITCH ACTIVATED: {switch_name} by actor {actor_id}. Reason: {reason}"
        )

        try:
            KILL_SWITCH_ACTIVATIONS_COUNTER.labels(switch_name=switch_name).inc()
        except Exception:
            pass

        await self._audit(
            event_type=AuditEventType.KILL_SWITCH_ENABLED,
            actor_id=actor_id,
            action="ACTIVATE_KILL_SWITCH",
            outcome="SUCCESS",
            metadata={
                "switch_name": switch_name,
                "previous_state": previous_state,
                "new_state": True,
                "reason": reason,
            },
        )
        return switch

    async def deactivate_kill_switch(
        self, switch_name: str, actor_id: str, reason: str
    ) -> KillSwitchState:
        """Deactivate an operational kill switch restoring standard evaluation."""
        switch = self._kill_switches.get(switch_name)
        if not switch:
            raise ConfigurationNotFoundException(switch_name)

        previous_state = switch.is_active
        switch.is_active = False
        switch.reason = f"Deactivated: {reason}"

        self.invalidate_cache()
        logger.info(
            f"KILL SWITCH DEACTIVATED: {switch_name} by actor {actor_id}. Reason: {reason}"
        )

        try:
            KILL_SWITCH_ACTIVATIONS_COUNTER.labels(switch_name=switch_name).inc()
        except Exception:
            pass

        await self._audit(
            event_type=AuditEventType.KILL_SWITCH_DISABLED,
            actor_id=actor_id,
            action="DEACTIVATE_KILL_SWITCH",
            outcome="SUCCESS",
            metadata={
                "switch_name": switch_name,
                "previous_state": previous_state,
                "new_state": False,
                "reason": reason,
            },
        )
        return switch

    def get_kill_switch(self, switch_name: str) -> KillSwitchState:
        """Fetch kill switch status."""
        switch = self._kill_switches.get(switch_name)
        if not switch:
            raise ConfigurationNotFoundException(switch_name)
        return switch

    def list_kill_switches(self) -> List[KillSwitchState]:
        """List all registered operational kill switches."""
        return list(self._kill_switches.values())

    # -----------------------------------------------------------------------
    # Feature Flag Evaluation (TRD Sec 8, 9, 10, 20, 21)
    # -----------------------------------------------------------------------

    def is_enabled(
        self,
        flag_name: str,
        context: Optional[FeatureFlagContext] = None,
        use_cache: bool = True,
    ) -> bool:
        """Evaluate whether a feature flag is enabled for the given context.
        
        Safe default: if flag not found or uncertainty exists -> returns False.
        """
        ctx = context or FeatureFlagContext(environment=self.settings.APP_ENV)
        env = ctx.environment or self.settings.APP_ENV

        # 1. Component Kill Switch Check (Overrides feature state)
        if self._is_blocked_by_kill_switch(flag_name):
            self._record_metric(flag_name, False)
            return False

        # 2. Global feature flags master switch
        if not self.settings.FEATURE_FLAGS_ENABLED:
            defn = self._flags.get(flag_name)
            res = defn.default_enabled if defn else False
            self._record_metric(flag_name, res)
            return res

        # 3. Check Cache
        cache_key = self._build_cache_key(flag_name, ctx)
        now = time.time()
        if use_cache and cache_key in self._cache:
            val, exp = self._cache[cache_key]
            if now < exp:
                return val

        # 4. Lookup Definition
        defn = self._flags.get(flag_name)
        if not defn:
            # Safe default: unknown flag is DISABLED
            self._record_metric(flag_name, False)
            return False

        # 5. Dependency Evaluation (fail closed if dependency disabled)
        for dep in defn.dependencies:
            if not self.is_enabled(dep, context=ctx, use_cache=use_cache):
                logger.debug(f"Flag '{flag_name}' disabled because dependency '{dep}' is disabled.")
                self._record_metric(flag_name, False)
                return False

        # 6. Evaluate State
        result = self._evaluate_state(defn, ctx, env)

        # 7. Store in Cache
        if use_cache:
            self._cache[cache_key] = (result, now + self._cache_ttl)

        self._record_metric(flag_name, result)
        return result

    def require_feature(
        self,
        flag_name: str,
        context: Optional[FeatureFlagContext] = None,
    ) -> None:
        """Assert that a feature is enabled; raises FeatureDisabledException if not."""
        if self._is_blocked_by_kill_switch(flag_name):
            switch_name = self._get_associated_kill_switch(flag_name) or "SYSTEM_KILL_SWITCH"
            raise KillSwitchActiveException(
                kill_switch=switch_name,
                reason="Component operation halted by active operational safety kill switch.",
            )

        if not self.is_enabled(flag_name, context=context):
            raise FeatureDisabledException(
                feature_name=flag_name,
                message=f"Clinical capability or feature '{flag_name}' is currently disabled.",
            )

    def _is_blocked_by_kill_switch(self, flag_name: str) -> bool:
        """Check if feature flag belongs to a component with an active kill switch."""
        assoc_switch = self._get_associated_kill_switch(flag_name)
        if assoc_switch and self.is_kill_switch_active(assoc_switch):
            return True
        return False

    def _get_associated_kill_switch(self, flag_name: str) -> Optional[str]:
        """Map feature flag to its governing kill switch."""
        if flag_name in (
            FeatureFlagName.AI_PROCESSING_ENABLED.value,
            FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value,
        ):
            return KillSwitchName.AI_PROCESSING_KILL_SWITCH.value
        elif flag_name in (
            FeatureFlagName.MEDICATION_SAFETY_ENABLED.value,
        ):
            return KillSwitchName.MEDICATION_SAFETY_PROVIDER_KILL_SWITCH.value
        elif flag_name in (
            FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value,
            FeatureFlagName.CARE_PLAN_GENERATION_ENABLED.value,
        ):
            return KillSwitchName.DOCUMENT_PROCESSING_KILL_SWITCH.value
        elif flag_name in (
            FeatureFlagName.INTEROPERABILITY_ENABLED.value,
            FeatureFlagName.FHIR_ENABLED.value,
        ):
            return KillSwitchName.INTEROPERABILITY_KILL_SWITCH.value
        return None

    def _evaluate_state(
        self, defn: FeatureFlagDefinition, ctx: FeatureFlagContext, env: str
    ) -> bool:
        """Internal strategy evaluation based on flag state."""
        if defn.state == FeatureFlagState.DISABLED:
            return False

        # Environment restriction check
        if defn.environments and env not in defn.environments:
            return False

        if defn.state == FeatureFlagState.ENABLED:
            return True

        if defn.state == FeatureFlagState.ENVIRONMENT_ONLY:
            return env in defn.environments

        if defn.state == FeatureFlagState.ALLOWLIST:
            # Matches any configured allowlist dimension
            if ctx.user_id and ctx.user_id in defn.allowlist_users:
                return True
            if ctx.organization_id and ctx.organization_id in defn.allowlist_organizations:
                return True
            if ctx.facility_id and ctx.facility_id in defn.allowlist_facilities:
                return True
            return False

        if defn.state == FeatureFlagState.ORGANIZATION_ROLLOUT:
            return bool(ctx.organization_id and ctx.organization_id in defn.allowlist_organizations)

        if defn.state == FeatureFlagState.PERCENTAGE_ROLLOUT:
            # Deterministic hashing (TRD Sec 20, 21)
            target_id = (
                ctx.organization_id
                or ctx.facility_id
                or ctx.clinician_id
                or ctx.user_id
                or ctx.patient_id
            )
            if not target_id:
                # No stable entity context provided -> fail closed
                return False
            
            percentage = defn.percentage or 0
            hash_input = f"{defn.name}:{target_id}".encode("utf-8")
            bucket = int(hashlib.sha256(hash_input).hexdigest(), 16) % 100
            return bucket < percentage

        return False

    def _build_cache_key(self, flag_name: str, ctx: FeatureFlagContext) -> str:
        """Construct deterministic cache key for feature evaluation."""
        return (
            f"{flag_name}:{ctx.environment}:{ctx.user_id}:{ctx.organization_id}:"
            f"{ctx.facility_id}:{ctx.patient_id}"
        )

    def _record_metric(self, flag_name: str, is_enabled: bool) -> None:
        """Record Prometheus telemetry without PHI."""
        try:
            FEATURE_FLAG_EVALUATIONS_COUNTER.labels(flag_name=flag_name).inc()
            if is_enabled:
                FEATURE_FLAG_ENABLED_COUNTER.labels(flag_name=flag_name).inc()
            else:
                FEATURE_FLAG_DISABLED_COUNTER.labels(flag_name=flag_name).inc()
        except Exception:
            pass

    def invalidate_cache(self) -> None:
        """Flush in-memory evaluation cache."""
        self._cache.clear()

    # -----------------------------------------------------------------------
    # Flag Administration & Rollout API (TRD Sec 27)
    # -----------------------------------------------------------------------

    def get_flag(self, flag_name: str) -> FeatureFlagDefinition:
        """Retrieve flag definition."""
        defn = self._flags.get(flag_name)
        if not defn:
            raise ConfigurationNotFoundException(flag_name)
        return defn

    def list_flags(self) -> List[FeatureFlagDefinition]:
        """List all registered feature flags."""
        return list(self._flags.values())

    async def enable_flag(
        self, flag_name: str, actor_id: str, reason: str
    ) -> FeatureFlagDefinition:
        """Fully enable a feature flag across all environments."""
        defn = self.get_flag(flag_name)
        previous_state = defn.state
        defn.state = FeatureFlagState.ENABLED
        defn.updated_at = datetime.now(timezone.utc)
        self.invalidate_cache()

        await self._audit(
            event_type=AuditEventType.FEATURE_FLAG_ENABLED,
            actor_id=actor_id,
            action="ENABLE_FEATURE_FLAG",
            outcome="SUCCESS",
            metadata={
                "flag_name": flag_name,
                "previous_state": previous_state.value,
                "new_state": FeatureFlagState.ENABLED.value,
                "reason": reason,
            },
        )
        return defn

    async def disable_flag(
        self, flag_name: str, actor_id: str, reason: str
    ) -> FeatureFlagDefinition:
        """Disable a feature flag."""
        defn = self.get_flag(flag_name)
        previous_state = defn.state
        defn.state = FeatureFlagState.DISABLED
        defn.updated_at = datetime.now(timezone.utc)
        self.invalidate_cache()

        await self._audit(
            event_type=AuditEventType.FEATURE_FLAG_DISABLED,
            actor_id=actor_id,
            action="DISABLE_FEATURE_FLAG",
            outcome="SUCCESS",
            metadata={
                "flag_name": flag_name,
                "previous_state": previous_state.value,
                "new_state": FeatureFlagState.DISABLED.value,
                "reason": reason,
            },
        )
        return defn

    async def update_rollout(
        self,
        flag_name: str,
        request: FeatureFlagRolloutRequest,
        actor_id: str,
    ) -> FeatureFlagDefinition:
        """Configure advanced rollout rules (percentage, allowlists, environments)."""
        defn = self.get_flag(flag_name)
        previous_state = defn.state
        
        defn.state = request.state
        if request.percentage is not None:
            defn.percentage = request.percentage
        if request.allowlist_users is not None:
            defn.allowlist_users = request.allowlist_users
        if request.allowlist_organizations is not None:
            defn.allowlist_organizations = request.allowlist_organizations
        if request.allowlist_facilities is not None:
            defn.allowlist_facilities = request.allowlist_facilities
        if request.environments is not None:
            defn.environments = request.environments
        defn.updated_at = datetime.now(timezone.utc)
        self.invalidate_cache()

        await self._audit(
            event_type=AuditEventType.FEATURE_FLAG_ROLLOUT_CHANGED,
            actor_id=actor_id,
            action="UPDATE_FEATURE_ROLLOUT",
            outcome="SUCCESS",
            metadata={
                "flag_name": flag_name,
                "previous_state": previous_state.value,
                "new_state": request.state.value,
                "percentage": defn.percentage,
                "reason": request.reason,
            },
        )
        return defn

    async def _audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        action: str,
        outcome: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Audit configuration governance events."""
        try:
            record = AuditEventRecord(
                event_type=event_type,
                user_id=actor_id,
                action=action,
                outcome=outcome,
                details=metadata,
                timestamp=datetime.now(timezone.utc),
            )
            await self.audit_repo.append(record)
        except Exception as e:
            logger.warning(f"Failed to record feature flag audit event: {e}")

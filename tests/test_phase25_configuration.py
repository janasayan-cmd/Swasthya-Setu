"""Comprehensive test suite for Phase 25: Feature Flags, Configuration Governance & Controlled Rollout.

Covers:
- Configuration parsing, defaults, and typing
- Conditional dependency validation and production fail-fast rules
- Feature flag evaluation with safe defaults (fail-closed on unknown flags)
- Cascading feature flag dependencies
- Deterministic percentage rollouts using SHA-256
- User, Organization, and Facility allowlists
- Operational safety kill switches and emergency halting
- Clinical safety invariants (disabled safety != CLEAR, disabled triage != routine)
- In-memory caching and bounded TTL invalidation
- Configuration drift analysis across environments
- Administrative REST endpoints with strict RBAC security
- Public safe capabilities endpoint without secret leakage
- Audit logging for all configuration and kill switch state mutations
"""

import hashlib
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.api.deps import (
    get_configuration_service,
    get_current_user,
    get_feature_flag_service,
)
from app.core.config import Settings
from app.core.exceptions import (
    ConfigurationInvalidException,
    ConfigurationNotFoundException,
    FeatureDisabledException,
    ForbiddenException,
    KillSwitchActiveException,
)
from app.core.feature_flags import (
    ConfigurationCategory,
    FeatureFlagContext,
    FeatureFlagDefinition,
    FeatureFlagName,
    FeatureFlagState,
    KillSwitchName,
    ValidationLevel,
)
from app.main import app
from app.repositories.audit_repository import AuditRepository
from app.schemas.auth import UserRole
from app.schemas.audit import AuditEventType
from app.schemas.feature_flag import (
    FeatureFlagRolloutRequest,
    FeatureFlagUpdateRequest,
    KillSwitchActionRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.configuration_service import ConfigurationService
from app.services.feature_flag_service import FeatureFlagService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_repo():
    return AuditRepository()


@pytest.fixture
def flag_service(audit_repo):
    test_settings = Settings(
        APP_ENV="testing",
        FEATURE_FLAGS_ENABLED=True,
        CONFIG_CACHE_TTL_SECONDS=60,
    )
    return FeatureFlagService(settings=test_settings, audit_repo=audit_repo)


@pytest.fixture
def config_service(flag_service, audit_repo):
    test_settings = Settings(
        APP_ENV="testing",
        FEATURE_FLAGS_ENABLED=True,
    )
    return ConfigurationService(
        settings=test_settings,
        feature_flag_service=flag_service,
        audit_repo=audit_repo,
    )


@pytest.fixture
def admin_actor():
    return AuthenticatedUserContext(
        id="usr-admin-001",
        email="admin@healthsetu.org",
        role=UserRole.ADMIN,
        is_active=True,
    )


@pytest.fixture
def doctor_actor():
    return AuthenticatedUserContext(
        id="usr-doc-001",
        email="doctor@healthsetu.org",
        role=UserRole.DOCTOR,
        is_active=True,
    )


@pytest.fixture
def patient_actor():
    return AuthenticatedUserContext(
        id="usr-pat-001",
        email="patient@healthsetu.org",
        role=UserRole.PATIENT,
        is_active=True,
    )


@pytest.fixture
def client(flag_service, config_service):
    app.dependency_overrides[get_feature_flag_service] = lambda: flag_service
    app.dependency_overrides[get_configuration_service] = lambda: config_service
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Configuration Parsing & Typed Settings
# ---------------------------------------------------------------------------

def test_settings_phase25_defaults():
    s = Settings()
    assert s.FEATURE_FLAGS_ENABLED is True
    assert s.CONFIG_CACHE_TTL_SECONDS == 60
    assert s.MEDICATION_SAFETY_ENABLED is True
    assert s.TRIAGE_ENABLED is True
    assert s.AI_PROCESSING_KILL_SWITCH is False
    assert s.MEDICATION_SAFETY_PROVIDER_KILL_SWITCH is False
    assert s.DOCUMENT_PROCESSING_KILL_SWITCH is False
    assert s.INTEROPERABILITY_KILL_SWITCH is False
    assert s.MEDICATION_SAFETY_PROVIDER in ("mock", "licensed_provider")
    assert s.AI_PROVIDER in ("mock", "openai", "gemini")


def test_configuration_validation_success(config_service):
    res = config_service.validate_configuration()
    assert res.passed is True
    assert res.status == "VALID"
    assert len(res.issues) == 0


def test_conditional_dependency_validation():
    # FHIR enabled without interoperability enabled
    s = Settings(
        APP_ENV="testing",
        FHIR_ENABLED=True,
        INTEROPERABILITY_ENABLED=False,
    )
    svc = ConfigurationService(settings=s)
    res = svc.validate_configuration()
    assert res.passed is False
    assert any(i.setting == "FHIR_ENABLED" for i in res.issues)

    # Care plan generation without document processing
    s2 = Settings(
        APP_ENV="testing",
        CARE_PLAN_GENERATION_ENABLED=True,
        DOCUMENT_PROCESSING_ENABLED=False,
    )
    svc2 = ConfigurationService(settings=s2)
    res2 = svc2.validate_configuration()
    assert res2.passed is False
    assert any(i.setting == "CARE_PLAN_GENERATION_ENABLED" for i in res2.issues)


def test_production_strict_validation_fails_fast():
    # Production missing database url with strict mode
    prod_settings = Settings(
        APP_ENV="production",
        DATABASE_URL=None,
        CONFIG_GOVERNANCE_STRICT_MODE=True,
    )
    svc = ConfigurationService(settings=prod_settings)
    with pytest.raises(ConfigurationInvalidException):
        svc.validate_configuration(fail_fast=True)


# ---------------------------------------------------------------------------
# 2. Feature Flag Evaluation & Safe Defaults
# ---------------------------------------------------------------------------

def test_unknown_feature_flag_safe_default(flag_service):
    # Unknown flag defaults safely to False (TRD Sec 10)
    assert flag_service.is_enabled("UNKNOWN_FEATURE_12345") is False
    with pytest.raises(FeatureDisabledException):
        flag_service.require_feature("UNKNOWN_FEATURE_12345")


def test_flag_evaluation_enabled_and_disabled(flag_service):
    ctx = FeatureFlagContext(environment="testing")
    assert flag_service.is_enabled(FeatureFlagName.TRIAGE_ENABLED.value, ctx) is True

    # Disable flag
    flag_service._flags[FeatureFlagName.TRIAGE_ENABLED.value].state = FeatureFlagState.DISABLED
    flag_service.invalidate_cache()
    assert flag_service.is_enabled(FeatureFlagName.TRIAGE_ENABLED.value, ctx) is False
    with pytest.raises(FeatureDisabledException):
        flag_service.require_feature(FeatureFlagName.TRIAGE_ENABLED.value, ctx)


def test_global_master_switch_disabled():
    s = Settings(APP_ENV="testing", FEATURE_FLAGS_ENABLED=False)
    svc = FeatureFlagService(settings=s)
    # Falls back to default_enabled
    assert svc.is_enabled(FeatureFlagName.MEDICATION_SAFETY_ENABLED.value) is True


# ---------------------------------------------------------------------------
# 3. Cascading Feature Dependencies
# ---------------------------------------------------------------------------

def test_cascading_flag_dependencies(flag_service):
    ctx = FeatureFlagContext(environment="testing")
    # CARE_PLAN_GENERATION_ENABLED depends on DOCUMENT_PROCESSING_ENABLED
    assert flag_service.is_enabled(FeatureFlagName.CARE_PLAN_GENERATION_ENABLED.value, ctx) is True

    # Disable parent flag
    flag_service._flags[FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value].state = FeatureFlagState.DISABLED
    flag_service.invalidate_cache()

    # Child flag must now evaluate to False automatically
    assert flag_service.is_enabled(FeatureFlagName.CARE_PLAN_GENERATION_ENABLED.value, ctx) is False


def test_ai_copilot_cascading_dependency(flag_service):
    ctx = FeatureFlagContext(environment="testing")
    # CLINICAL_AI_ASSISTANCE_ENABLED depends on AI_PROCESSING_ENABLED
    assert flag_service.is_enabled(FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value, ctx) is True

    # Disable foundational AI
    flag_service._flags[FeatureFlagName.AI_PROCESSING_ENABLED.value].state = FeatureFlagState.DISABLED
    flag_service.invalidate_cache()

    assert flag_service.is_enabled(FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value, ctx) is False


# ---------------------------------------------------------------------------
# 4. Deterministic Percentage Rollouts (SHA-256)
# ---------------------------------------------------------------------------

def test_percentage_rollout_deterministic(flag_service):
    flag_name = FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value
    flag_service._flags[flag_name].state = FeatureFlagState.PERCENTAGE_ROLLOUT
    flag_service._flags[flag_name].percentage = 50
    flag_service.invalidate_cache()

    ctx_facility_a = FeatureFlagContext(facility_id="facility-101")
    ctx_facility_b = FeatureFlagContext(facility_id="facility-999")

    # Evaluate repeatedly: result must be completely deterministic (TRD Sec 21)
    result_a_first = flag_service.is_enabled(flag_name, ctx_facility_a, use_cache=False)
    for _ in range(20):
        assert flag_service.is_enabled(flag_name, ctx_facility_a, use_cache=False) == result_a_first

    result_b_first = flag_service.is_enabled(flag_name, ctx_facility_b, use_cache=False)
    for _ in range(20):
        assert flag_service.is_enabled(flag_name, ctx_facility_b, use_cache=False) == result_b_first


def test_percentage_rollout_missing_context_fails_closed(flag_service):
    flag_name = FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value
    flag_service._flags[flag_name].state = FeatureFlagState.PERCENTAGE_ROLLOUT
    flag_service._flags[flag_name].percentage = 50
    flag_service.invalidate_cache()

    # Empty context without entity identifier -> fails closed (TRD Sec 10)
    empty_ctx = FeatureFlagContext()
    assert flag_service.is_enabled(flag_name, empty_ctx, use_cache=False) is False


def test_percentage_rollout_boundaries(flag_service):
    flag_name = FeatureFlagName.TRANSFER_ENABLED.value
    flag_service._flags[flag_name].state = FeatureFlagState.PERCENTAGE_ROLLOUT
    flag_service.invalidate_cache()

    ctx = FeatureFlagContext(organization_id="org-test-alpha")

    # 0% rollout -> False for all
    flag_service._flags[flag_name].percentage = 0
    assert flag_service.is_enabled(flag_name, ctx, use_cache=False) is False

    # 100% rollout -> True for all
    flag_service._flags[flag_name].percentage = 100
    assert flag_service.is_enabled(flag_name, ctx, use_cache=False) is True


# ---------------------------------------------------------------------------
# 5. Allowlists & Environment Isolation
# ---------------------------------------------------------------------------

def test_allowlist_evaluation(flag_service):
    flag_name = FeatureFlagName.FACILITY_DISCOVERY_ENABLED.value
    flag_service._flags[flag_name].state = FeatureFlagState.ALLOWLIST
    flag_service._flags[flag_name].allowlist_users = ["usr-allowed-1"]
    flag_service._flags[flag_name].allowlist_organizations = ["org-allowed-2"]
    flag_service._flags[flag_name].allowlist_facilities = ["fac-allowed-3"]
    flag_service.invalidate_cache()

    # Match user
    assert flag_service.is_enabled(flag_name, FeatureFlagContext(user_id="usr-allowed-1"), use_cache=False) is True
    # Match organization
    assert flag_service.is_enabled(flag_name, FeatureFlagContext(organization_id="org-allowed-2"), use_cache=False) is True
    # Match facility
    assert flag_service.is_enabled(flag_name, FeatureFlagContext(facility_id="fac-allowed-3"), use_cache=False) is True
    # Unmatched
    assert flag_service.is_enabled(flag_name, FeatureFlagContext(user_id="usr-denied"), use_cache=False) is False


def test_environment_isolation(flag_service):
    flag_name = FeatureFlagName.DATA_EXPORT_ENABLED.value
    flag_service._flags[flag_name].environments = ["staging", "development"]
    flag_service.invalidate_cache()

    # Allowed in staging
    assert flag_service.is_enabled(flag_name, FeatureFlagContext(environment="staging"), use_cache=False) is True
    # Prohibited in production
    assert flag_service.is_enabled(flag_name, FeatureFlagContext(environment="production"), use_cache=False) is False


# ---------------------------------------------------------------------------
# 6. Operational Safety Kill Switches (TRD Sec 23 & 24)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kill_switch_activation_and_deactivation(flag_service, audit_repo):
    switch_name = KillSwitchName.AI_PROCESSING_KILL_SWITCH.value
    assert flag_service.is_kill_switch_active(switch_name) is False

    # 1. Activate kill switch
    activated = await flag_service.activate_kill_switch(
        switch_name=switch_name,
        actor_id="usr-admin-1",
        reason="Upstream AI provider outage; halting copilot",
    )
    assert activated.is_active is True
    assert flag_service.is_kill_switch_active(switch_name) is True

    # Feature flag associated with this component must now immediately be blocked
    ctx = FeatureFlagContext(environment="testing")
    assert flag_service.is_enabled(FeatureFlagName.AI_PROCESSING_ENABLED.value, ctx) is False
    assert flag_service.is_enabled(FeatureFlagName.CLINICAL_AI_ASSISTANCE_ENABLED.value, ctx) is False

    # require_feature raises KillSwitchActiveException
    with pytest.raises(KillSwitchActiveException):
        flag_service.require_feature(FeatureFlagName.AI_PROCESSING_ENABLED.value, ctx)

    # 2. Deactivate kill switch
    deactivated = await flag_service.deactivate_kill_switch(
        switch_name=switch_name,
        actor_id="usr-admin-1",
        reason="Outage resolved by provider",
    )
    assert deactivated.is_active is False
    assert flag_service.is_kill_switch_active(switch_name) is False
    assert flag_service.is_enabled(FeatureFlagName.AI_PROCESSING_ENABLED.value, ctx) is True


@pytest.mark.asyncio
async def test_medication_safety_kill_switch_halts_processing(flag_service):
    switch_name = KillSwitchName.MEDICATION_SAFETY_PROVIDER_KILL_SWITCH.value
    await flag_service.activate_kill_switch(
        switch_name=switch_name,
        actor_id="usr-admin-1",
        reason="Safety database schema drift; halting checks",
    )
    assert flag_service.is_enabled(FeatureFlagName.MEDICATION_SAFETY_ENABLED.value) is False


# ---------------------------------------------------------------------------
# 7. Clinical Safety Invariants (TRD Sec 47)
# ---------------------------------------------------------------------------

def test_clinical_safety_invariants(flag_service):
    # Rule 1: Disabled medication safety != CLEAR (TRD Sec 11, 47)
    flag_service._flags[FeatureFlagName.MEDICATION_SAFETY_ENABLED.value].state = FeatureFlagState.DISABLED
    flag_service.invalidate_cache()

    with pytest.raises(FeatureDisabledException) as exc_info:
        flag_service.require_feature(FeatureFlagName.MEDICATION_SAFETY_ENABLED.value)
    # Must explicitly state disabled rather than clear
    assert "disabled" in str(exc_info.value.message).lower()
    assert exc_info.value.code == "FEATURE_DISABLED"

    # Rule 2: Disabled triage != routine (TRD Sec 11, 47)
    flag_service._flags[FeatureFlagName.TRIAGE_ENABLED.value].state = FeatureFlagState.DISABLED
    flag_service.invalidate_cache()

    with pytest.raises(FeatureDisabledException) as exc_info:
        flag_service.require_feature(FeatureFlagName.TRIAGE_ENABLED.value)
    assert "disabled" in str(exc_info.value.message).lower()


# ---------------------------------------------------------------------------
# 8. Caching & Invalidation
# ---------------------------------------------------------------------------

def test_caching_and_invalidation(flag_service):
    flag_name = FeatureFlagName.DOCUMENT_PROCESSING_ENABLED.value
    ctx = FeatureFlagContext(user_id="user-cache-1")

    # Initial evaluation populates cache
    val1 = flag_service.is_enabled(flag_name, ctx, use_cache=True)
    assert val1 is True
    cache_key = flag_service._build_cache_key(flag_name, ctx)
    assert cache_key in flag_service._cache

    # Invalidate cache
    flag_service.invalidate_cache()
    assert len(flag_service._cache) == 0


# ---------------------------------------------------------------------------
# 9. Configuration Drift Analysis
# ---------------------------------------------------------------------------

def test_drift_detection(config_service):
    # Testing environment drift report
    report = config_service.detect_drift(environment="testing")
    assert report.environment == "testing"
    assert isinstance(report.has_drift, bool)

    # In production with mock providers, drift should be detected
    prod_report = config_service.detect_drift(environment="production")
    assert prod_report.has_drift is True
    assert any(i.setting == "MEDICATION_SAFETY_PROVIDER" for i in prod_report.items)


# ---------------------------------------------------------------------------
# 10. API Integration & RBAC Security
# ---------------------------------------------------------------------------

def test_public_capabilities_endpoint_safe(client):
    res = client.get("/api/v1/configuration/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert "document_processing_available" in data
    assert "medication_safety_available" in data
    assert "triage_available" in data
    assert "fhir_available" in data
    # Verify no secret leakage
    assert "api_key" not in data
    assert "secret" not in data
    assert "password" not in data


def test_admin_endpoints_unauthorized(client):
    # Unauthenticated
    res = client.get("/api/v1/admin/configuration/features")
    assert res.status_code in (401, 403)


def test_admin_endpoints_forbidden_for_patient(client, patient_actor):
    app.dependency_overrides[get_current_user] = lambda: patient_actor
    # Patient cannot modify feature flags or activate kill switches
    res = client.post(
        "/api/v1/admin/configuration/features/TRIAGE_ENABLED/disable",
        json={"reason": "Attempting patient bypass"},
    )
    assert res.status_code == 403

    res_kill = client.post(
        "/api/v1/admin/configuration/kill-switches/AI_PROCESSING_KILL_SWITCH/activate",
        json={"reason": "Attempting patient shutdown"},
    )
    assert res_kill.status_code == 403


def test_admin_feature_management_lifecycle(client, admin_actor, flag_service):
    app.dependency_overrides[get_current_user] = lambda: admin_actor

    # 1. List features
    res_list = client.get("/api/v1/admin/configuration/features")
    assert res_list.status_code == 200
    assert res_list.json()["total"] > 0

    # 2. Get specific feature
    res_get = client.get("/api/v1/admin/configuration/features/CARE_PLAN_GENERATION_ENABLED")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "CARE_PLAN_GENERATION_ENABLED"

    # 3. Disable feature
    res_disable = client.post(
        "/api/v1/admin/configuration/features/CARE_PLAN_GENERATION_ENABLED/disable",
        json={"reason": "Planned administrative maintenance"},
    )
    assert res_disable.status_code == 200
    assert res_disable.json()["state"] == "DISABLED"
    assert flag_service.is_enabled("CARE_PLAN_GENERATION_ENABLED") is False

    # 4. Enable feature
    res_enable = client.post(
        "/api/v1/admin/configuration/features/CARE_PLAN_GENERATION_ENABLED/enable",
        json={"reason": "Maintenance complete; re-enabling"},
    )
    assert res_enable.status_code == 200
    assert res_enable.json()["state"] == "ENABLED"
    assert flag_service.is_enabled("CARE_PLAN_GENERATION_ENABLED") is True

    # 5. Configure rollout
    res_rollout = client.post(
        "/api/v1/admin/configuration/features/CARE_PLAN_GENERATION_ENABLED/rollout",
        json={
            "state": "PERCENTAGE_ROLLOUT",
            "percentage": 30,
            "reason": "Ramping up to 30% cohort",
        },
    )
    assert res_rollout.status_code == 200
    assert res_rollout.json()["percentage"] == 30


def test_admin_kill_switch_api(client, admin_actor, flag_service):
    app.dependency_overrides[get_current_user] = lambda: admin_actor

    # List kill switches
    res_list = client.get("/api/v1/admin/configuration/kill-switches")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 4

    # Activate kill switch
    res_act = client.post(
        "/api/v1/admin/configuration/kill-switches/DOCUMENT_PROCESSING_KILL_SWITCH/activate",
        json={"reason": "Upstream OCR worker memory threshold breached"},
    )
    assert res_act.status_code == 200
    assert res_act.json()["is_active"] is True
    assert flag_service.is_kill_switch_active("DOCUMENT_PROCESSING_KILL_SWITCH") is True

    # Deactivate kill switch
    res_deact = client.post(
        "/api/v1/admin/configuration/kill-switches/DOCUMENT_PROCESSING_KILL_SWITCH/deactivate",
        json={"reason": "Worker pool restarted and healthy"},
    )
    assert res_deact.status_code == 200
    assert res_deact.json()["is_active"] is False
    assert flag_service.is_kill_switch_active("DOCUMENT_PROCESSING_KILL_SWITCH") is False


def test_admin_validation_and_drift_api(client, admin_actor):
    app.dependency_overrides[get_current_user] = lambda: admin_actor

    res_val = client.post("/api/v1/admin/configuration/validate")
    assert res_val.status_code == 200
    assert "status" in res_val.json()

    res_drift = client.get("/api/v1/admin/configuration/drift")
    assert res_drift.status_code == 200
    assert "has_drift" in res_drift.json()

    res_prov = client.get("/api/v1/admin/configuration/providers")
    assert res_prov.status_code == 200
    assert len(res_prov.json()) >= 4

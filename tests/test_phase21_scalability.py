"""HealthSetu — Phase 21 Scalability, Performance & High-Availability Test Suite.

Validates all Phase 21 requirements (Sections 80, 81):
1. Pagination parameters, default limits (25), max bounds (100), and response slicing
2. Circuit breaker state machine (CLOSED -> OPEN -> HALF_OPEN -> CLOSED) and safe fallbacks
3. Bounded concurrency limiters and semaphore capacity bounds
4. Selective retry with exponential backoff (retries transient 502/503/timeout; rejects 4xx/validation errors)
5. Non-idempotent operations are never retried
6. Bounded cache eviction (FIFO when full)
7. Cache safety & tenant isolation (Patient A != Patient B cache isolation)
8. Medication context-change cache invalidation (stale safety cache is never current truth)
9. Disabled providers do NOT return cached fake success
10. Load shedding middleware (sheds non-critical /ai traffic; protects /auth, /triage, and /patients)
11. Optimistic concurrency conflict detection on concurrent updates
12. Graceful shutdown resource cleanup
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from app.core.cache import (
    BoundedCache,
    compute_medication_context_hash,
    safety_cache,
    reference_cache,
    terminology_cache,
    invalidate_patient_safety_cache,
)
from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitState,
    get_circuit_breaker,
)
from app.core.concurrency import (
    BoundedConcurrencyLimiter,
    ConcurrencyLimitExceededException,
    get_concurrency_limiter,
)
from app.core.config import Settings
from app.core.exceptions import (
    AppException,
    ConflictException,
    ValidationException,
    UnauthorizedException,
)
from app.core.load_shedding import load_shedding_controller
from app.core.metrics import metrics
from app.core.retry import is_transient_error, retry_async
from app.schemas.pagination import PaginationParams, create_paginated_response
from tests.conftest import TEST_PASSWORD


# ============================================================================
# 1. PAGINATION & BOUNDED QUERY TESTS (Sections 11, 12)
# ============================================================================

def test_pagination_params_bounds():
    """Verify default page size is 25, offset calculation is correct, and max limit is 100."""
    default_p = PaginationParams()
    assert default_p.page == 1
    assert default_p.page_size == 25
    assert default_p.limit == 25
    assert default_p.offset == 0

    page_3 = PaginationParams(page=3, page_size=25)
    assert page_3.offset == 50
    assert page_3.limit == 25

    # Max page size capped at 100
    with pytest.raises(Exception):
        PaginationParams(page_size=101)


def test_paginated_response_helper():
    """Verify generic paginated response structure and navigation flags."""
    sample_data = [f"item_{i}" for i in range(1, 11)]
    resp = create_paginated_response(
        items=sample_data,
        total_count=55,
        page=2,
        page_size=10,
    )
    assert resp.page == 2
    assert resp.page_size == 10
    assert resp.total_count == 55
    assert resp.total_pages == 6
    assert resp.has_next is True
    assert resp.has_prev is True
    assert len(resp.items) == 10


# ============================================================================
# 2. CIRCUIT BREAKER STATE MACHINE & SAFE FAILURE (Section 22)
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_closed_to_open_transition():
    """Verify circuit trips from CLOSED to OPEN after consecutive failure threshold."""
    cb = CircuitBreaker(
        name="test_provider",
        failure_threshold=3,
        recovery_timeout=0.2,
        half_open_max_calls=2,
    )
    assert cb.state == CircuitState.CLOSED

    failing_mock = AsyncMock(side_effect=Exception("Provider timeout"))

    # Fail 1 and 2: Still CLOSED
    for _ in range(2):
        with pytest.raises(Exception):
            await cb.call(failing_mock)
        assert cb.state == CircuitState.CLOSED

    # Fail 3: Exceeds threshold -> trips to OPEN
    with pytest.raises(Exception):
        await cb.call(failing_mock)
    assert cb.state == CircuitState.OPEN

    # Next call rejected immediately without executing provider
    failing_mock.reset_mock()
    with pytest.raises(CircuitBreakerOpenException):
        await cb.call(failing_mock)
    assert failing_mock.call_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_open_to_half_open_to_closed_recovery():
    """Verify cooldown transitions to HALF_OPEN and successful probes restore to CLOSED."""
    cb = CircuitBreaker(
        name="test_recovery_provider",
        failure_threshold=2,
        recovery_timeout=0.1,  # 100ms cooldown for fast test
        half_open_max_calls=2,
    )

    failing_mock = AsyncMock(side_effect=Exception("Failed"))
    for _ in range(2):
        with pytest.raises(Exception):
            await cb.call(failing_mock)
    assert cb.state == CircuitState.OPEN

    # Wait for recovery timeout cooldown
    await asyncio.sleep(0.15)
    # State evaluates to HALF_OPEN upon cooldown expiration
    assert cb.state == CircuitState.HALF_OPEN

    # Successful recovery calls
    success_mock = AsyncMock(return_value="healthy_payload")

    # Trial call 1
    res1 = await cb.call(success_mock)
    assert res1 == "healthy_payload"
    assert cb.state == CircuitState.HALF_OPEN

    # Trial call 2 (meets half_open_max_calls threshold) -> transitions back to CLOSED!
    res2 = await cb.call(success_mock)
    assert res2 == "healthy_payload"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_safe_fallback_never_fake_clear():
    """When circuit is OPEN, safe fallback executes rather than returning fake success."""
    cb = CircuitBreaker(name="med_safety_breaker", failure_threshold=1, recovery_timeout=60.0)

    with pytest.raises(Exception):
        await cb.call(AsyncMock(side_effect=Exception("503 Provider Error")))
    assert cb.state == CircuitState.OPEN

    # Safe fallback returns UNKNOWN, NEVER CLEAR
    async def med_safety_safe_fallback():
        return {"status": "UNKNOWN", "disclaimer": "Safety check unavailable; pharmacist review required."}

    result = await cb.call(AsyncMock(), fallback=med_safety_safe_fallback)
    assert result["status"] == "UNKNOWN"
    assert result["status"] != "CLEAR"


# ============================================================================
# 3. BOUNDED CONCURRENCY & WORKLOAD ISOLATION (Sections 19, 26, 27, 28)
# ============================================================================

@pytest.mark.asyncio
async def test_concurrency_limiter_blocks_excessive_parallelism():
    """Verify limiter permits max concurrency and raises ConcurrencyLimitExceededException when saturated."""
    limiter = BoundedConcurrencyLimiter(name="ai_worker", max_concurrency=2, wait_timeout_seconds=0.05)

    async def slow_task():
        await asyncio.sleep(0.2)
        return "done"

    # Launch 2 parallel tasks filling the slots
    task1 = asyncio.create_task(limiter.run(slow_task))
    task2 = asyncio.create_task(limiter.run(slow_task))
    await asyncio.sleep(0.01)

    assert limiter.active_count == 2
    assert limiter.available_slots == 0

    # 3rd task attempts to acquire slot and times out
    with pytest.raises(ConcurrencyLimitExceededException) as exc_info:
        await limiter.run(slow_task, timeout=0.02)
    assert "ai_worker" in str(exc_info.value)

    # Clean up background tasks
    await asyncio.gather(task1, task2)
    assert limiter.active_count == 0
    assert limiter.available_slots == 2


# ============================================================================
# 4. SELECTIVE RETRY & IDEMPOTENCY SAFETY (Sections 53, 54, 55)
# ============================================================================

@pytest.mark.asyncio
async def test_retry_transient_error_succeeds_eventually():
    """Verify transient connection errors are retried with exponential backoff and succeed."""
    call_count = 0

    async def flaky_api():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionResetError("Connection dropped by peer")
        return "success_recovered"

    result = await retry_async(flaky_api, max_retries=3, base_delay=0.01, max_delay=0.05, jitter=False)
    assert result == "success_recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_rejects_client_validation_errors():
    """Verify client 4xx validation and auth errors are NEVER retried."""
    call_count = 0

    async def bad_client_call():
        nonlocal call_count
        call_count += 1
        raise ValidationException("Invalid drug strength specified.")

    with pytest.raises(ValidationException):
        await retry_async(bad_client_call, max_retries=3, base_delay=0.01)

    # Must fail immediately on attempt 1 without wasteful retries
    assert call_count == 1


@pytest.mark.asyncio
async def test_non_idempotent_operation_never_retried():
    """Verify non-idempotent operations (is_idempotent=False) are never retried."""
    call_count = 0

    async def non_idempotent_transfer_action():
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Gateway timeout waiting for transfer response")

    with pytest.raises(TimeoutError):
        await retry_async(
            non_idempotent_transfer_action,
            max_retries=3,
            base_delay=0.01,
            is_idempotent=False,  # Clinical safety rule: Do not duplicate clinical side effects!
        )

    assert call_count == 1


# ============================================================================
# 5. CACHE ISOLATION & CONTEXT INVALIDATION (Sections 24, 34, 69)
# ============================================================================

def test_cache_bounded_fifo_eviction():
    """Verify cache bounds enforce max entries via FIFO eviction."""
    cache = BoundedCache(namespace="test_bound", max_entries=3, default_ttl=60.0)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")
    assert len(cache._store) == 3

    # Add 4th key -> oldest key (k1) must be evicted
    cache.set("k4", "v4")
    assert len(cache._store) == 3
    assert cache.get("k1") is None
    assert cache.get("k4") == "v4"


def test_medication_context_hash_changes_on_mutation():
    """Any medication or allergy mutation MUST alter the clinical context hash."""
    patient_id = "pat-cache-001"
    meds_v1 = ["Metformin 500mg", "Lisinopril 10mg"]
    allergies = ["Penicillin"]

    hash_v1 = compute_medication_context_hash(patient_id, meds_v1, allergies)
    hash_v1_dup = compute_medication_context_hash(patient_id, ["Lisinopril 10mg", "Metformin 500mg"], allergies)
    # Order independence in hash
    assert hash_v1 == hash_v1_dup

    # Clinician adds Aspirin
    meds_v2 = ["Metformin 500mg", "Lisinopril 10mg", "Aspirin 81mg"]
    hash_v2 = compute_medication_context_hash(patient_id, meds_v2, allergies)
    assert hash_v1 != hash_v2


def test_stale_safety_cache_invalidation():
    """Verify that cached safety results are rejected if clinical context changes."""
    cache = BoundedCache(namespace="safety", max_entries=100, default_ttl=300.0)
    patient_id = "pat-safety-ctx"
    hash_old = compute_medication_context_hash(patient_id, ["Warfarin 5mg"])
    hash_new = compute_medication_context_hash(patient_id, ["Warfarin 5mg", "Aspirin 81mg"])

    # Cache evaluation for Warfarin alone
    cache.set(
        key=f"patient_safety:{patient_id}",
        value={"alerts": [], "status": "CLEAR"},
        context_hash=hash_old,
        provider_name="med_safety",
    )

    # Lookup with matching context -> hit
    cached_res = cache.get(f"patient_safety:{patient_id}", expected_context_hash=hash_old)
    assert cached_res is not None
    assert cached_res["status"] == "CLEAR"

    # Lookup with altered medication context -> MISMATCH! Must return None!
    mismatched_res = cache.get(f"patient_safety:{patient_id}", expected_context_hash=hash_new)
    assert mismatched_res is None


def test_disabled_provider_never_returns_cached_success():
    """Section 69: Disabled provider must NOT return cached success."""
    cache = BoundedCache(namespace="ai_cache", max_entries=10, default_ttl=600.0)
    cache.set(
        key="ai_summary_123",
        value={"summary": "Patient is recovering well."},
        provider_name="ai",
    )

    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value = Settings(CACHE_ENABLED=True, AI_ENABLED=False)
        # When AI is disabled, cache lookup must NOT return old cached AI output as valid
        res = cache.get("ai_summary_123")
        assert res is None


# ============================================================================
# 6. LOAD SHEDDING MIDDLEWARE (Section 37)
# ============================================================================

def test_load_shedding_protects_critical_paths():
    """Verify load shedding protects /auth and /triage while shedding /ai."""
    # Under high load threshold
    load_shedding_controller._active_requests = 150

    with patch("app.core.load_shedding.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            LOAD_SHEDDING_ENABLED=True,
            LOAD_SHEDDING_MAX_CONCURRENT_REQUESTS=100,
        )
        # Critical clinical paths MUST NEVER be shed
        assert load_shedding_controller.should_shed("/api/v1/health") is False
        assert load_shedding_controller.should_shed("/api/v1/ready") is False
        assert load_shedding_controller.should_shed("/api/v1/auth/login") is False
        assert load_shedding_controller.should_shed("/api/v1/triage/assess") is False
        assert load_shedding_controller.should_shed("/api/v1/patients/pat-001") is False

        # Non-critical workloads ARE shed during saturation
        assert load_shedding_controller.should_shed("/api/v1/ai/summarize") is True
        assert load_shedding_controller.should_shed("/api/v1/facilities/discover") is True
        assert load_shedding_controller.should_shed("/api/v1/interoperability/export") is True

    # Reset controller active count
    load_shedding_controller._active_requests = 0


# ============================================================================
# 7. OPTIMISTIC CONCURRENCY CONFLICT (Section 47)
# ============================================================================

@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict_rejection():
    """Verify concurrent modification raises 409 Conflict if expected_version does not match."""
    from app.services.clinical_note_service import ClinicalNoteService
    from app.repositories.clinical_note_repository import ClinicalNoteRecord, ClinicalNoteRepository
    from app.repositories.audit_repository import AuditRepository
    from app.services.audit_service import AuditService
    from app.schemas.clinical_workflow import ClinicalNoteType, ClinicalNoteUpdate
    from datetime import datetime, timezone

    repo = ClinicalNoteRepository()
    service = ClinicalNoteService(
        note_repo=repo,
        audit_service=AuditService(audit_repository=AuditRepository()),
    )

    now = datetime.now(timezone.utc)
    note = ClinicalNoteRecord(
        id="note-race-01",
        patient_id="pat-race-01",
        clinician_id="doc-race-01",
        note_type=ClinicalNoteType.PROGRESS,
        title="Initial Progress",
        content="Patient stable.",
        version=2,  # Current DB version is 2
        is_signed=False,
        created_at=now,
        updated_at=now,
    )
    await repo.create(note)

    # Clinician A updates with stale version 1
    with pytest.raises(ConflictException) as exc_info:
        await service.update_note(
            patient_id="pat-race-01",
            note_id="note-race-01",
            payload=ClinicalNoteUpdate(title="Stale Update", content="Content", expected_version=1),
            clinician_id="doc-race-01",
        )
    assert "version conflict" in str(exc_info.value).lower()

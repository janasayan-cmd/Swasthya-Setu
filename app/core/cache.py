"""Bounded caching architecture with strict clinical safety and tenant isolation (Phase 21).

Enforces Sections 23, 24, 25, 32, 33, 34, 69:
- Thread-safe, bounded-cardinality in-memory cache
- TTL expiration with explicit context-hash validation
- Authorize-BEFORE-Lookup pattern: patient cache keys are isolated and checked after auth
- Context-change invalidation: Any change to medications/allergies invalidates safety cache
- Provider disablement safety: If a provider is disabled, cached output is NEVER returned as fake success
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Sequence

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.core.cache")


class CacheEntry:
    """Wrapper around a cached payload with TTL and context validation."""

    def __init__(
        self,
        value: Any,
        ttl_seconds: float,
        context_hash: str | None = None,
        provider_name: str | None = None,
        provider_version: str | None = None,
    ) -> None:
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl_seconds
        self.context_hash = context_hash
        self.provider_name = provider_name
        self.provider_version = provider_version

    @property
    def is_expired(self) -> bool:
        """Check if time-to-live has elapsed."""
        return (time.time() - self.created_at) > self.ttl

    def matches_context(self, context_hash: str | None) -> bool:
        """Verify that current clinical context matches the cached context."""
        if self.context_hash is None and context_hash is None:
            return True
        return self.context_hash == context_hash


class BoundedCache:
    """Thread-safe bounded in-memory cache with eviction and TTL support."""

    def __init__(self, namespace: str, max_entries: int = 1000, default_ttl: float = 3600.0) -> None:
        self.namespace = namespace
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str, expected_context_hash: str | None = None) -> Any | None:
        """Retrieve cached value if present, not expired, and context matches."""
        settings = get_settings()
        if not settings.CACHE_ENABLED:
            return None

        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None

            # Check expiration
            if entry.is_expired:
                del self._store[key]
                self.misses += 1
                return None

            # Check clinical context matching
            if expected_context_hash is not None and not entry.matches_context(expected_context_hash):
                logger.debug(f"Cache miss [{self.namespace}:{key}]: clinical context hash mismatch.")
                self.misses += 1
                return None

            # Section 69: Disabled providers must NOT return cached success
            if entry.provider_name == "ai" and not settings.AI_ENABLED:
                return None
            if entry.provider_name == "med_safety" and not settings.MEDICATION_SAFETY_ENABLED:
                return None

            self.hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        context_hash: str | None = None,
        provider_name: str | None = None,
        provider_version: str | None = None,
    ) -> None:
        """Store value with bounds enforcement."""
        settings = get_settings()
        if not settings.CACHE_ENABLED:
            return

        effective_ttl = ttl if ttl is not None else self.default_ttl

        with self._lock:
            # Enforce max entries bound via FIFO eviction of oldest items
            if len(self._store) >= self.max_entries and key not in self._store:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]

            self._store[key] = CacheEntry(
                value=value,
                ttl_seconds=effective_ttl,
                context_hash=context_hash,
                provider_name=provider_name,
                provider_version=provider_version,
            )

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries in namespace."""
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0


# ---------------------------------------------------------------------------
# Clinical Context Hash Generator for Medication Safety
# ---------------------------------------------------------------------------

def compute_medication_context_hash(
    patient_id: str,
    medications: Sequence[str],
    allergies: Sequence[str] | None = None,
) -> str:
    """Compute a deterministic hash of patient medication and allergy context.

    If ANY medication is added, changed, or removed, the context hash changes,
    preventing stale safety results from ever returning as current clinical truth.
    """
    normalized_meds = sorted(m.strip().lower() for m in medications if m and m.strip())
    normalized_allergies = sorted(a.strip().lower() for a in (allergies or []) if a and a.strip())

    payload = {
        "patient_id": patient_id,
        "medications": normalized_meds,
        "allergies": normalized_allergies,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Global Domain Cache Singletons
# ---------------------------------------------------------------------------

reference_cache = BoundedCache(namespace="reference", max_entries=500, default_ttl=3600.0)
terminology_cache = BoundedCache(namespace="terminology", max_entries=2000, default_ttl=86400.0)
safety_cache = BoundedCache(namespace="safety", max_entries=1000, default_ttl=300.0)


def invalidate_patient_safety_cache(patient_id: str) -> None:
    """Invalidate all cached safety evaluations for a patient upon clinical mutation."""
    safety_cache.invalidate(f"patient_safety:{patient_id}")
    logger.info(f"Invalidated safety cache for patient [{patient_id}].")

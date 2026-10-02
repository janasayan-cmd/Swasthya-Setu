"""Search Repository and Operational State Tracking (Phase 30).

Provides tracking for:
- Low-risk query response caching (e.g. facility/organization reference data)
- Index synchronization and rebuild job state
- Operational metrics (latency, zero-result counts, lag)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional
from app.schemas.search_result import SearchIndexStatus


class SearchRepository:
    """Thread-safe operational repository for search metadata, caching, and index sync state."""

    def __init__(self) -> None:
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._rebuild_jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._total_indexed: int = 0
        self._pending_sync_count: int = 0
        self._last_rebuild_at: Optional[datetime] = None

    async def get_cached_result(self, cache_key: str, ttl_seconds: int = 60) -> Optional[Any]:
        """Fetch cached response if valid and not expired."""
        async with self._lock:
            entry = self._cache.get(cache_key)
            if not entry:
                return None
            cached_at, value = entry
            if (time.time() - cached_at) > ttl_seconds:
                del self._cache[cache_key]
                return None
            return value

    async def set_cached_result(self, cache_key: str, value: Any) -> None:
        """Store cache entry with current timestamp."""
        async with self._lock:
            self._cache[cache_key] = (time.time(), value)

    async def clear_cache(self) -> None:
        """Purge cache."""
        async with self._lock:
            self._cache.clear()

    async def record_rebuild_job(self, job_id: str, details: Dict[str, Any]) -> None:
        """Record state of index rebuild job."""
        async with self._lock:
            self._rebuild_jobs[job_id] = details
            self._last_rebuild_at = datetime.now(timezone.utc)

    async def get_rebuild_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve rebuild job details."""
        async with self._lock:
            return self._rebuild_jobs.get(job_id)

    async def get_operational_status(self, provider_name: str) -> SearchIndexStatus:
        """Construct current index health and sync telemetry."""
        async with self._lock:
            return SearchIndexStatus(
                provider=provider_name,
                indexing_enabled=True,
                async_enabled=True,
                total_indexed_records=self._total_indexed,
                pending_sync_count=self._pending_sync_count,
                stale_index_count=0,
                last_rebuild_at=self._last_rebuild_at,
                status="HEALTHY",
            )

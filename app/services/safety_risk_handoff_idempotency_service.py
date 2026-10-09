"""Phase 64: Clinical Safety Risk Handoff Idempotency Service.

Protects against duplicate execution of handoff operations.
"""

from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Any, Dict, Optional, Tuple
from fastapi import status

from app.core.exceptions import AppException, ErrorCode


class SafetyRiskHandoffIdempotencyService:
    """In-memory idempotency cache for Phase 64 handoff operations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: Dict[str, Tuple[str, Any, datetime]] = {}

    def _hash_payload(self, payload: Any) -> str:
        try:
            serialized = json.dumps(payload, sort_keys=True, default=str)
        except Exception:
            serialized = str(payload)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def check_or_record(
        self,
        idempotency_key: Optional[str],
        operation: str,
        payload: Any,
    ) -> Optional[Any]:
        """Check for duplicate execution or record key."""
        if not idempotency_key:
            return None

        combined_key = f"{operation}:{idempotency_key}"
        curr_hash = self._hash_payload(payload)

        with self._lock:
            if combined_key in self._cache:
                cached_hash, result, _ = self._cache[combined_key]
                if cached_hash != curr_hash:
                    raise AppException(
                        code=ErrorCode.IDEMPOTENCY_CONFLICT,
                        message=f"Idempotency key '{idempotency_key}' reused with conflicting payload.",
                        status_code=status.HTTP_409_CONFLICT,
                    )
                return result

            self._cache[combined_key] = (curr_hash, None, datetime.now(timezone.utc))
            return None

    def store_result(
        self,
        idempotency_key: Optional[str],
        operation: str,
        payload: Any,
        result: Any,
    ) -> None:
        """Store the completed operation result for cached replay."""
        if not idempotency_key:
            return
        combined_key = f"{operation}:{idempotency_key}"
        curr_hash = self._hash_payload(payload)
        with self._lock:
            self._cache[combined_key] = (curr_hash, result, datetime.now(timezone.utc))

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_idempotency_svc_instance: Optional[SafetyRiskHandoffIdempotencyService] = None


def get_safety_risk_handoff_idempotency_service() -> SafetyRiskHandoffIdempotencyService:
    global _idempotency_svc_instance
    if _idempotency_svc_instance is None:
        _idempotency_svc_instance = SafetyRiskHandoffIdempotencyService()
    return _idempotency_svc_instance

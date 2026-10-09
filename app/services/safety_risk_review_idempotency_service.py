"""Phase 63: Clinical Safety Review Idempotency Service.

Guarantees exactly-once semantics for safety risk reviews, evidence updates,
review actions, dispositions, routings, and reassessments.
"""

from datetime import datetime, timezone
import hashlib
import json
import threading
from typing import Any, Dict, Optional, Tuple
from fastapi import status

from app.core.exceptions import AppException, ErrorCode


class SafetyRiskReviewIdempotencyService:
    """Thread-safe idempotency tracking service for Phase 63 operations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # key -> (fingerprint, result_payload, created_at)
        self._store: Dict[str, Tuple[str, Any, datetime]] = {}

    def _compute_fingerprint(self, payload: Any) -> str:
        """Generate deterministic SHA256 digest of request payload."""
        try:
            serialized = json.dumps(payload, sort_keys=True, default=str)
        except Exception:
            serialized = str(payload)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def check_or_record(
        self,
        idempotency_key: Optional[str],
        operation_name: str,
        payload: Any,
    ) -> Optional[Any]:
        """Check for existing idempotency record.

        Returns:
            Existing cached result if same payload was previously processed.
        Raises:
            AppException(IDEMPOTENCY_CONFLICT) if key is reused with different payload.
        """
        if not idempotency_key:
            return None

        composite_key = f"{operation_name}:{idempotency_key}"
        fingerprint = self._compute_fingerprint(payload)

        with self._lock:
            existing = self._store.get(composite_key)
            if existing:
                prev_fingerprint, prev_result, _ = existing
                if prev_fingerprint != fingerprint:
                    raise AppException(
                        code=ErrorCode.IDEMPOTENCY_CONFLICT,
                        message=f"Idempotency conflict: key '{idempotency_key}' previously used with differing parameters for '{operation_name}'.",
                        status_code=status.HTTP_409_CONFLICT,
                    )
                return prev_result
            return None

    def store_result(
        self,
        idempotency_key: Optional[str],
        operation_name: str,
        payload: Any,
        result: Any,
    ) -> None:
        """Store the successful operation result against the idempotency key."""
        if not idempotency_key:
            return

        composite_key = f"{operation_name}:{idempotency_key}"
        fingerprint = self._compute_fingerprint(payload)

        with self._lock:
            self._store[composite_key] = (fingerprint, result, datetime.now(timezone.utc))

    def clear(self) -> None:
        """Clear the idempotency store (for testing)."""
        with self._lock:
            self._store.clear()


_idempotency_service_instance: Optional[SafetyRiskReviewIdempotencyService] = None


def get_safety_risk_review_idempotency_service() -> SafetyRiskReviewIdempotencyService:
    global _idempotency_service_instance
    if _idempotency_service_instance is None:
        _idempotency_service_instance = SafetyRiskReviewIdempotencyService()
    return _idempotency_service_instance

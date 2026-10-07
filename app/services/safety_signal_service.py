"""Phase 59: Safety Signal Ingestion, Normalization & Deduplication Service.

Coordinates post-closure surveillance signal intake across Phases 18, 35, 48, 49, 52, 55, 56,
preserving provenance without making unsupported causal assertions.
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Optional, Tuple

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_monitoring_repository import (
    SafetyMonitoringRepository,
    get_safety_monitoring_repository,
)
from app.schemas.safety_monitoring import (
    IngestSignalRequest,
    SafetyMonitoringRecord,
    SurveillanceSignalRecord,
)


class SafetySignalService:
    """Manages surveillance signal ingestion, normalization, and deduplication."""

    def __init__(self, repository: Optional[SafetyMonitoringRepository] = None) -> None:
        self.repository = repository or get_safety_monitoring_repository()

    @staticmethod
    def generate_dedup_key(source_phase: str, source_record_id: str, version: str) -> str:
        """Create deterministic deduplication key."""
        raw = f"{source_phase}:{source_record_id}:{version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def ingest_signal(
        self, monitoring: SafetyMonitoringRecord, request: IngestSignalRequest
    ) -> Tuple[bool, SurveillanceSignalRecord]:
        """Normalize, deduplicate, and record incoming surveillance signal."""
        # 1. Scope validation (TRD Section 10)
        req_scope = request.scope or {}
        req_org = req_scope.get("organization_id")
        monitoring_org = getattr(monitoring.scope, "organization_id", None) or monitoring.organization_id
        if req_org and req_org != monitoring_org:
            raise AppException(
                code=ErrorCode.MONITORING_SCOPE_MISMATCH,
                message=f"Signal organization '{req_org}' does not match monitoring scope '{monitoring_org}'",
                status_code=400,
            )

        # 2. Version validation (TRD Section 32)
        sig_ver = request.version or request.application_version or "v1.0.0"
        mon_ver = monitoring.monitored_version or monitoring.application_version
        if sig_ver and mon_ver and sig_ver != mon_ver:
            raise AppException(
                code=ErrorCode.MONITORING_CONTEXT_STALE,
                message=(
                    f"Signal version '{sig_ver}' does not match monitored context '{mon_ver}'. "
                    "Surveillance context is stale."
                ),
                status_code=409,
            )

        src = request.source or request.source_phase or "Phase 18"
        dedup_key = self.generate_dedup_key(src, request.source_record_id, sig_ver)

        # 3. Deduplication check (TRD Section 14)
        if self.repository.is_signal_duplicate(monitoring.monitoring_id, dedup_key):
            for s in monitoring.signals:
                if s.deduplication_key == dedup_key:
                    s.is_duplicate = True
                    return False, s
            dup_sig = SurveillanceSignalRecord(
                source=src,
                source_phase=src,
                source_record_id=request.source_record_id,
                signal_type=request.signal_type,
                severity=(request.severity or "MEDIUM").upper(),
                version=sig_ver,
                provenance={"source": src, "source_record_id": request.source_record_id},
                deduplication_key=dedup_key,
                is_duplicate=True,
                status="DUPLICATE",
            )
            return False, dup_sig

        now = datetime.now(timezone.utc)
        provenance = {
            "source": src,
            "source_record_id": request.source_record_id,
            "version": sig_ver,
            "ingested_at": now.isoformat(),
        }
        signal = SurveillanceSignalRecord(
            source=src,
            source_phase=src,
            source_record_id=request.source_record_id,
            signal_type=request.signal_type,
            severity=(request.severity or "MEDIUM").upper(),
            timestamp=now,
            scope=request.scope or (monitoring.scope.model_dump() if hasattr(monitoring.scope, "model_dump") else {}),
            version=sig_ver,
            provenance=provenance,
            deduplication_key=dedup_key,
            status="VALIDATED",
            is_duplicate=False,
            metadata=request.metadata or request.payload or {},
        )

        monitoring.signals.append(signal)
        self.repository.record_signal_dedup(monitoring.monitoring_id, dedup_key)
        return True, signal

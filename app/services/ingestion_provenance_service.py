"""Ingestion Provenance Service (Phase 45).

Maintains immutable provenance tracing for external data imports:
- Origin source organization, facility, and external identifier
- Transformation and mapping version
- Technical validation and domain reconciliation results
- Verification and trust state transitions
- SHA-256 payload integrity fingerprints
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, Optional
import uuid

from app.schemas.ingestion import (
    DataTrustStatus,
    IngestionProvenanceRecord,
)


class IngestionProvenanceService:
    """Coordinates immutable provenance record generation and verification for external imports."""

    def __init__(self) -> None:
        self._provenance_store: Dict[str, IngestionProvenanceRecord] = {}

    def compute_payload_hash(self, payload: Dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash digest of inbound payload."""
        try:
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        except Exception:
            serialized = str(payload)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def record_provenance(
        self,
        ingestion_id: str,
        source_system: str,
        source_resource_id: str,
        source_organization: Optional[str] = None,
        source_facility: Optional[str] = None,
        source_version: Optional[str] = None,
        source_timestamp: Optional[datetime] = None,
        transformation_version: str = "1.0",
        mapper_version: str = "FHIR_R4_V1",
        validation_result: str = "VALID",
        reconciliation_result: Optional[str] = None,
        verification_state: DataTrustStatus = DataTrustStatus.UNVERIFIED,
    ) -> IngestionProvenanceRecord:
        """Construct and persist an immutable provenance record."""
        prov_id = f"prov-{uuid.uuid4().hex[:12]}"
        record = IngestionProvenanceRecord(
            provenance_id=prov_id,
            ingestion_id=ingestion_id,
            source_organization=source_organization,
            source_facility=source_facility,
            source_system=source_system,
            source_resource_id=source_resource_id,
            source_version=source_version,
            source_timestamp=source_timestamp,
            received_timestamp=datetime.now(timezone.utc),
            transformation_version=transformation_version,
            mapper_version=mapper_version,
            validation_result=validation_result,
            reconciliation_result=reconciliation_result,
            verification_state=verification_state,
        )
        self._provenance_store[prov_id] = record
        return record

    async def get_provenance(self, provenance_id: str) -> Optional[IngestionProvenanceRecord]:
        """Fetch provenance record by ID."""
        return self._provenance_store.get(provenance_id)

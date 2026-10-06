"""Data Provenance Service for Clinical Data Sharing (Phase 44).

Tracks data lineage and origin metadata for all shared and exported records:
- Source system: HealthSetu
- Source resource IDs
- Transformation pipeline & format
- Intended destination & recipient
- Execution timestamp
- Non-authoritative external provenance for inbound records
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRecord(BaseModel):
    """Immutable provenance record documenting origin and transformation."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    provenance_id: str = Field(default_factory=lambda: f"prov-{uuid.uuid4().hex[:12]}")
    share_or_export_id: str
    source_system: str = "HealthSetu"
    patient_id: str
    requester_id: str
    recipient_id: str
    destination: Optional[str] = None
    resource_scopes: List[str]
    action: str
    format: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload_hash: Optional[str] = None
    is_external_inbound: bool = False
    is_verified_clinical_truth: bool = False  # IMPORTED != VERIFIED


class SharingProvenanceService:
    """Service responsible for minting and querying provenance records."""

    def __init__(self) -> None:
        self._provenance_store: Dict[str, ProvenanceRecord] = {}

    def record_outbound_provenance(
        self,
        share_or_export_id: str,
        patient_id: str,
        requester_id: str,
        recipient_id: str,
        resource_scopes: List[str],
        action: str,
        format_type: str,
        destination: Optional[str] = None,
        payload_data: Optional[Dict[str, Any]] = None,
    ) -> ProvenanceRecord:
        """Create and store outbound provenance snapshot metadata."""
        payload_hash = None
        if payload_data:
            try:
                dumped = json.dumps(payload_data, sort_keys=True, default=str)
                payload_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()
            except Exception:
                pass

        record = ProvenanceRecord(
            share_or_export_id=share_or_export_id,
            source_system="HealthSetu",
            patient_id=patient_id,
            requester_id=requester_id,
            recipient_id=recipient_id,
            destination=destination,
            resource_scopes=resource_scopes,
            action=action,
            format=format_type,
            payload_hash=payload_hash,
            is_external_inbound=False,
            is_verified_clinical_truth=False,
        )
        self._provenance_store[record.provenance_id] = record
        return record

    def get_provenance(self, provenance_id: str) -> Optional[ProvenanceRecord]:
        """Fetch a provenance record by ID."""
        return self._provenance_store.get(provenance_id)

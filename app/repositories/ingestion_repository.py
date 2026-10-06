"""Ingestion Data Repository (Phase 45).

Consumes existing database contracts; operates on thread-safe in-memory
storage for development and testing prior to database team schema deployment.

DATABASE TEAM DEPENDENCIES:
- `ingestion_sources` table
- `clinical_ingestions` table
- `ingestion_provenance` table
- `webhook_delivery_logs` table
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.base import BaseRepository
from app.schemas.ingestion import (
    ExternalSourceContext,
    IngestionRecord,
    IngestionStatus,
    SourceTrustState,
    SourceType,
)


class IngestionRepository(BaseRepository[Any]):
    """Thread-safe repository managing inbound clinical data ingestion records and sources."""

    def __init__(self, session: Any = None) -> None:
        super().__init__(session=session)
        self._ingestions: Dict[str, IngestionRecord] = {}
        self._sources: Dict[str, ExternalSourceContext] = {}
        # (source_system, external_resource_id) -> ingestion_id
        self._external_resource_index: Dict[Tuple[str, str], str] = {}
        # idempotency_key -> ingestion_id
        self._idempotency_index: Dict[str, str] = {}
        # (provider, event_id, nonce) -> timestamp
        self._webhook_replay_cache: Dict[Tuple[str, str, str], float] = {}
        self._lock = asyncio.Lock()

        # Seed initial trusted test sources
        self._seed_default_sources()

    def _seed_default_sources(self) -> None:
        """Seed known external sources for tests and default mock runtime."""
        sources = [
            ExternalSourceContext(
                source_id="lab-apollo",
                source_type=SourceType.LABORATORY,
                source_name="Apollo Diagnostics Reference Lab",
                trust_state=SourceTrustState.ACTIVE,
                allowed_resource_types=["Observation", "DiagnosticReport"],
                api_key_hash=hashlib.sha256(b"secret-apollo-key").hexdigest(),
                shared_secret="secret-apollo-hmac",
            ),
            ExternalSourceContext(
                source_id="hospital-max",
                source_type=SourceType.HOSPITAL,
                source_name="Max Super Speciality Hospital",
                trust_state=SourceTrustState.ACTIVE,
                allowed_resource_types=[
                    "Patient", "Observation", "Condition", "AllergyIntolerance",
                    "MedicationRequest", "Medication", "DocumentReference", "CarePlan"
                ],
                api_key_hash=hashlib.sha256(b"secret-max-key").hexdigest(),
                shared_secret="secret-max-hmac",
            ),
            ExternalSourceContext(
                source_id="mock-interop",
                source_type=SourceType.INTEROPERABILITY_PROVIDER,
                source_name="Standard Mock FHIR Gateway",
                trust_state=SourceTrustState.ACTIVE,
                allowed_resource_types=[
                    "Patient", "Observation", "Condition", "AllergyIntolerance",
                    "MedicationRequest", "Medication", "DiagnosticReport",
                    "DocumentReference", "CarePlan"
                ],
                api_key_hash=hashlib.sha256(b"secret-mock-key").hexdigest(),
                shared_secret="secret-mock-hmac",
            ),
            ExternalSourceContext(
                source_id="suspended-lab",
                source_type=SourceType.LABORATORY,
                source_name="Suspended External Lab",
                trust_state=SourceTrustState.SUSPENDED,
                allowed_resource_types=["Observation"],
                api_key_hash=hashlib.sha256(b"suspended-key").hexdigest(),
            ),
        ]
        for src in sources:
            self._sources[src.source_id.lower().strip()] = src

    def register_source(self, source: ExternalSourceContext) -> None:
        """Register or update an external source configuration."""
        self._sources[source.source_id.lower().strip()] = source

    async def get_source(self, source_id: str) -> Optional[ExternalSourceContext]:
        """Fetch external source context by ID."""
        async with self._lock:
            return self._sources.get(source_id.lower().strip())

    async def list_sources(self) -> List[ExternalSourceContext]:
        """List all registered external sources."""
        async with self._lock:
            return list(self._sources.values())

    async def create_ingestion(self, record: IngestionRecord) -> IngestionRecord:
        """Atomically persist a new ingestion record and index lookup keys."""
        async with self._lock:
            self._ingestions[record.id] = record
            idx_key = (record.source_system.lower().strip(), record.external_resource_id.strip())
            self._external_resource_index[idx_key] = record.id
            if record.idempotency_key:
                self._idempotency_index[record.idempotency_key] = record.id
            return record

    async def get_ingestion(self, ingestion_id: str) -> Optional[IngestionRecord]:
        """Fetch an ingestion record by unique ID."""
        async with self._lock:
            return self._ingestions.get(ingestion_id)

    async def update_ingestion(self, record: IngestionRecord) -> IngestionRecord:
        """Update existing ingestion record."""
        async with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._ingestions[record.id] = record
            return record

    async def find_by_source_resource(
        self, source_system: str, external_resource_id: str
    ) -> Optional[IngestionRecord]:
        """Lookup by source system and external resource ID for idempotency."""
        async with self._lock:
            key = (source_system.lower().strip(), external_resource_id.strip())
            ing_id = self._external_resource_index.get(key)
            if ing_id:
                return self._ingestions.get(ing_id)
            return None

    async def find_by_idempotency_key(self, idempotency_key: str) -> Optional[IngestionRecord]:
        """Lookup by client idempotency key."""
        async with self._lock:
            ing_id = self._idempotency_index.get(idempotency_key)
            if ing_id:
                return self._ingestions.get(ing_id)
            return None

    async def list_ingestions(
        self,
        source_system: Optional[str] = None,
        patient_id: Optional[str] = None,
        status: Optional[IngestionStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[IngestionRecord], int]:
        """List paginated ingestion records with optional filtering."""
        async with self._lock:
            records = list(self._ingestions.values())
            if source_system:
                records = [r for r in records if r.source_system.lower() == source_system.lower()]
            if patient_id:
                records = [r for r in records if r.healthsetu_patient_id == patient_id]
            if status:
                records = [r for r in records if r.status == status]

            records.sort(key=lambda r: r.created_at, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total

    async def list_by_patient(
        self, patient_id: str, limit: int = 20, offset: int = 0
    ) -> Tuple[List[IngestionRecord], int]:
        """List paginated ingestion records for a specific patient."""
        return await self.list_ingestions(patient_id=patient_id, limit=limit, offset=offset)

    async def check_and_record_webhook(
        self, provider: str, event_id: str, nonce: str, max_age_seconds: int = 300
    ) -> bool:
        """Check for replay and register webhook nonce. Returns False if replayed."""
        async with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            key = (provider.lower().strip(), event_id.strip(), nonce.strip())

            # Cleanup expired nonces
            expired = [k for k, ts in self._webhook_replay_cache.items() if now - ts > max_age_seconds]
            for exp in expired:
                del self._webhook_replay_cache[exp]

            if key in self._webhook_replay_cache:
                return False  # Replay detected!

            self._webhook_replay_cache[key] = now
            return True

    def clear(self) -> None:
        """Reset in-memory storage (for test isolation)."""
        self._ingestions.clear()
        self._external_resource_index.clear()
        self._idempotency_index.clear()
        self._webhook_replay_cache.clear()
        self._sources.clear()
        self._seed_default_sources()

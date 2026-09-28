"""Document metadata, processing job, and extraction repository.

DATABASE TEAM DEPENDENCY — PHASE 5
====================================
Entities required:
1. `documents` table:
   - id: UUID PK
   - patient_id: UUID FK -> patients.id
   - uploader_id: UUID FK -> users.id
   - document_type: VARCHAR / ENUM
   - source: VARCHAR / ENUM
   - filename: VARCHAR
   - mime_type: VARCHAR
   - size_bytes: BIGINT
   - checksum_sha256: VARCHAR(64)
   - storage_key: VARCHAR
   - lifecycle_state: VARCHAR / ENUM
   - processing_status: VARCHAR / ENUM
   - is_archived: BOOLEAN DEFAULT FALSE
   - created_at: TIMESTAMPTZ
   - updated_at: TIMESTAMPTZ

2. `document_processing_jobs` table:
   - id: UUID PK
   - document_id: UUID FK -> documents.id
   - status: VARCHAR / ENUM
   - attempts: INTEGER DEFAULT 0
   - processor: VARCHAR
   - processor_version: VARCHAR
   - started_at: TIMESTAMPTZ
   - completed_at: TIMESTAMPTZ NULL
   - error_message: TEXT NULL
   - created_at: TIMESTAMPTZ

3. `document_extractions` table:
   - id: UUID PK
   - document_id: UUID FK -> documents.id
   - processor: VARCHAR
   - processor_version: VARCHAR
   - extracted_text: TEXT
   - language: VARCHAR(10)
   - page_count: INTEGER
   - structured_fields: JSONB DEFAULT '[]'
   - created_at: TIMESTAMPTZ
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.schemas.document import (
    DocumentLifecycleState,
    DocumentSource,
    DocumentType,
    ProcessingStatus,
)


@dataclass
class DocumentRecord:
    """Internal entity representing document metadata."""
    id: str
    patient_id: str
    uploader_id: str
    document_type: DocumentType
    source: DocumentSource
    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    storage_key: str
    lifecycle_state: DocumentLifecycleState
    processing_status: ProcessingStatus
    created_at: datetime
    updated_at: datetime
    is_archived: bool = False


@dataclass
class DocumentProcessingRecord:
    """Internal entity tracking background processing attempts."""
    id: str
    document_id: str
    status: ProcessingStatus
    attempts: int
    processor: str
    processor_version: str
    started_at: datetime
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


@dataclass
class ExtractionRecord:
    """Internal entity representing an extraction artifact."""
    id: str
    document_id: str
    processor: str
    processor_version: str
    extracted_text: str
    language: str
    page_count: int
    structured_fields: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentRepository(BaseRepository[Any]):
    """Repository managing medical documents, processing jobs, and extractions."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session=session)  # type: ignore[arg-type]
        self._documents: dict[str, DocumentRecord] = {}
        self._jobs: dict[str, DocumentProcessingRecord] = {}
        self._extractions: dict[str, list[ExtractionRecord]] = {}  # doc_id -> list of extractions

    async def create_document(self, record: DocumentRecord) -> DocumentRecord:
        """Persist document metadata."""
        self._documents[record.id] = record
        return record

    create = create_document

    async def get_document_by_id(self, document_id: str) -> DocumentRecord | None:
        """Fetch document metadata by ID."""
        return self._documents.get(document_id)

    get_by_id = get_document_by_id

    async def get_extractions(self, document_id: str) -> list[ExtractionRecord]:
        """Fetch all extractions for document."""
        return self._extractions.get(document_id, [])

    async def get_latest_extraction(self, document_id: str) -> ExtractionRecord | None:
        """Fetch the most recent extraction record for a document."""
        extractions = self._extractions.get(document_id, [])
        if not extractions:
            return None
        return extractions[-1]

    async def list_documents_by_patient(
        self, patient_id: str, include_archived: bool = False
    ) -> list[DocumentRecord]:
        """List documents for patient."""
        results = [
            doc for doc in self._documents.values()
            if doc.patient_id == patient_id and (include_archived or not doc.is_archived)
        ]
        return sorted(results, key=lambda d: d.created_at, reverse=True)

    async def update_document_status(
        self,
        document_id: str,
        lifecycle_state: DocumentLifecycleState,
        processing_status: ProcessingStatus,
    ) -> DocumentRecord | None:
        """Update lifecycle and processing states."""
        doc = self._documents.get(document_id)
        if not doc:
            return None
        updated = replace(
            doc,
            lifecycle_state=lifecycle_state,
            processing_status=processing_status,
            updated_at=datetime.now(timezone.utc),
        )
        self._documents[document_id] = updated
        return updated

    async def archive_document(self, document_id: str) -> DocumentRecord | None:
        """Soft-delete / archive a document."""
        doc = self._documents.get(document_id)
        if not doc:
            return None
        updated = replace(
            doc,
            is_archived=True,
            lifecycle_state=DocumentLifecycleState.ARCHIVED,
            updated_at=datetime.now(timezone.utc),
        )
        self._documents[document_id] = updated
        return updated

    async def create_or_update_job(
        self, record: DocumentProcessingRecord
    ) -> DocumentProcessingRecord:
        """Persist or update processing job state."""
        self._jobs[record.document_id] = record
        return record

    async def get_job_by_document_id(
        self, document_id: str
    ) -> DocumentProcessingRecord | None:
        """Retrieve latest processing job for document."""
        return self._jobs.get(document_id)

    async def save_extraction(self, record: ExtractionRecord) -> ExtractionRecord:
        """Append an extraction version (never overwriting historical versions)."""
        if record.document_id not in self._extractions:
            self._extractions[record.document_id] = []
        self._extractions[record.document_id].append(record)
        return record

    list_by_patient_id = list_documents_by_patient

    async def set_archived(self, document_id: str, is_archived: bool = True) -> DocumentRecord | None:
        """Set archival status of document."""
        if is_archived:
            return await self.archive_document(document_id)
        doc = self._documents.get(document_id)
        if not doc:
            return None
        updated = replace(
            doc,
            is_archived=False,
            lifecycle_state=DocumentLifecycleState.UPLOADED,
            updated_at=datetime.now(timezone.utc),
        )
        self._documents[document_id] = updated
        return updated

    async def delete(self, document_id: str) -> bool:
        """Delete document record."""
        return bool(self._documents.pop(document_id, None))

    def clear(self) -> None:
        """Clear all in-memory records (used in tests)."""
        self._documents.clear()
        self._jobs.clear()
        self._extractions.clear()

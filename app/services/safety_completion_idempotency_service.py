"""Phase 65: Safety Completion Idempotency & Concurrency Services.

Guarantees idempotent request processing and race-condition prevention.
"""

from typing import Any, Dict, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_workflow_completion_repository import (
    SafetyWorkflowCompletionRepository,
    get_safety_workflow_completion_repository,
)
from app.schemas.safety_workflow_completion import SafetyWorkflowCompletionRecord


class SafetyCompletionIdempotencyService:
    """Enforces deduplication and idempotency key safety."""

    def __init__(
        self,
        repo: Optional[SafetyWorkflowCompletionRepository] = None,
    ) -> None:
        self.repo = repo or get_safety_workflow_completion_repository()

    def check_or_store(
        self,
        idempotency_key: str,
        organization_id: str,
        incoming_disposition_id: str,
    ) -> Optional[SafetyWorkflowCompletionRecord]:
        """Check for existing idempotency key.

        Returns existing record if payload matches; raises IDEMPOTENCY_CONFLICT if payload differs.
        """
        existing = self.repo.get_by_idempotency_key(idempotency_key, organization_id=organization_id)
        if not existing:
            return None

        # Conflict check: did caller reuse key with different disposition?
        if existing.source_disposition_id != incoming_disposition_id:
            raise AppException(
                code=ErrorCode.IDEMPOTENCY_CONFLICT,
                message=f"Idempotency key '{idempotency_key}' already used with a different disposition ID.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return existing


class SafetyCompletionConcurrencyService:
    """Guarantees optimistic concurrency and state version integrity."""

    @staticmethod
    def validate_version(
        current_record: SafetyWorkflowCompletionRecord,
        expected_version: Optional[int] = None,
        source_disposition_revision: Optional[str] = None,
    ) -> None:
        """Validate that current record matches expected revision and version."""
        if expected_version is not None and current_record.version != expected_version:
            raise AppException(
                code=ErrorCode.CONCURRENCY_CONFLICT,
                message=(
                    f"Concurrency conflict: completion record version {current_record.version} "
                    f"does not match expected version {expected_version}."
                ),
                status_code=status.HTTP_409_CONFLICT,
            )

        if (
            source_disposition_revision is not None
            and current_record.source_revision != source_disposition_revision
        ):
            raise AppException(
                code=ErrorCode.VERSION_CONFLICT,
                message=(
                    f"Version conflict: source disposition revision has changed from "
                    f"'{current_record.source_revision}' to '{source_disposition_revision}'. Reassessment required."
                ),
                status_code=status.HTTP_409_CONFLICT,
            )

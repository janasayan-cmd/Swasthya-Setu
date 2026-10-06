"""Clinical Record History Service (Phase 46).

Manages:
- Authorized history querying with pagination
- Historical version retrieval with explicit non-current indicators
- Consent & authorization validation for historical access
- Differential comparison (diff) between versions
- Strict audit integration
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import (
    HistoryAccessDeniedException,
    ResourceVersionNotFoundException,
)
from app.repositories.versioning_repository import (
    VersioningRepository,
    versioning_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.history import (
    FieldDiff,
    HistoryQueryResponse,
    VersionDiffResponse,
    VersionSummaryItem,
)
from app.schemas.versioning import ClinicalVersionRecord
from app.services.audit_service import AuditService
from app.services.consent_service import ConsentService

logger = logging.getLogger(__name__)


class HistoryService:
    """Service providing authorized clinical history queries and temporal state traversal."""

    def __init__(
        self,
        repository: Optional[VersioningRepository] = None,
        consent_service: Optional[ConsentService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or versioning_repository
        self.consent_service = consent_service
        self.audit_service = audit_service

    async def _record_audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        outcome: str = "ALLOW",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Safely record audit event without PHI."""
        if not self.audit_service:
            return
        try:
            await self.audit_service.record(
                event_type=event_type,
                outcome=outcome,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata,
            )
        except Exception as ex:
            logger.warning("Failed to record audit event %s: %s", event_type, ex)

    def validate_history_access_authorization(
        self,
        actor_id: str,
        actor_role: str,
        resource_type: str,
        patient_id: str,
        history_scope_granted: bool = True,
    ) -> None:
        """Enforce that actor has explicit authority to view historical versions.
        
        INVARIANT:
        Reading current state does NOT automatically grant historical record access.
        Actors flagged with CURRENT_ONLY scope or lacking clinical relation are denied.
        """
        normalized_role = (actor_role or "").upper()
        if not history_scope_granted or normalized_role == "CURRENT_ONLY":
            raise HistoryAccessDeniedException(
                f"Actor {actor_id} is not authorized to access historical revisions of {resource_type} for patient {patient_id}."
            )

    async def get_history(
        self,
        resource_type: str,
        resource_id: str,
        actor_id: str,
        actor_role: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        reverse: bool = True,
        history_scope_granted: bool = True,
    ) -> HistoryQueryResponse:
        """Query chronological version history for a clinical entity."""
        current = self.repository.get_current_version(resource_type, resource_id)
        if not current:
            raise ResourceVersionNotFoundException(f"Resource {resource_type}:{resource_id} not found.")

        # Validate authorization
        self.validate_history_access_authorization(
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type=resource_type,
            patient_id=current.patient_id,
            history_scope_granted=history_scope_granted,
        )

        max_limit = getattr(settings, "VERSIONING_MAX_HISTORY_LIMIT", 100)
        clamped_limit = min(max(1, limit), max_limit)

        records, next_cursor, has_more, total_count = self.repository.list_history(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=clamped_limit,
            cursor=cursor,
            reverse=reverse,
        )

        summary_items: List[VersionSummaryItem] = [
            VersionSummaryItem(
                version_id=r.id,
                version_number=r.version_number,
                version_type=r.version_type,
                is_current=r.is_current,
                actor_id=r.actor_id,
                actor_role=r.actor_role,
                change_reason=r.change_reason,
                verification_state=r.verification_state,
                provenance_id=r.provenance_id,
                source_system=r.source_system,
                is_deleted=r.is_deleted,
                effective_time=r.temporal.effective_time,
                recorded_time=r.temporal.recorded_time,
                created_at=r.created_at,
            )
            for r in records
        ]

        await self._record_audit(
            event_type=AuditEventType.RECORD_HISTORY_ACCESSED,
            actor_id=actor_id,
            action="READ_HISTORY",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"count_returned": len(summary_items), "total_versions": total_count},
        )

        return HistoryQueryResponse(
            resource_id=resource_id,
            resource_type=resource_type,
            patient_id=current.patient_id,
            current_version_number=current.version_number,
            total_versions=total_count,
            versions=summary_items,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def get_version_detail(
        self,
        resource_type: str,
        resource_id: str,
        version_number: int,
        actor_id: str,
        actor_role: str,
        history_scope_granted: bool = True,
    ) -> ClinicalVersionRecord:
        """Retrieve a specific historical version of a resource.
        
        INVARIANT:
        If version is not current, response explicitly contains `is_current=False`
        and consumer cannot mistake it for current active state.
        """
        record = self.repository.get_version(resource_type, resource_id, version_number)
        if not record:
            raise ResourceVersionNotFoundException(
                f"Version {version_number} of {resource_type}:{resource_id} not found."
            )

        # Non-current version reads require history authorization
        if not record.is_current:
            self.validate_history_access_authorization(
                actor_id=actor_id,
                actor_role=actor_role,
                resource_type=resource_type,
                patient_id=record.patient_id,
                history_scope_granted=history_scope_granted,
            )

        await self._record_audit(
            event_type=AuditEventType.RECORD_HISTORY_ACCESSED,
            actor_id=actor_id,
            action="READ_VERSION",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"version_number": version_number, "is_current": record.is_current},
        )
        return record

    def diff_versions(
        self,
        resource_type: str,
        resource_id: str,
        base_version_number: int,
        compared_version_number: int,
    ) -> VersionDiffResponse:
        """Generate field-level diff between two versions of a clinical resource."""
        base_record = self.repository.get_version(resource_type, resource_id, base_version_number)
        if not base_record:
            raise ResourceVersionNotFoundException(
                f"Base version {base_version_number} of {resource_type}:{resource_id} not found."
            )

        compared_record = self.repository.get_version(resource_type, resource_id, compared_version_number)
        if not compared_record:
            raise ResourceVersionNotFoundException(
                f"Compared version {compared_version_number} of {resource_type}:{resource_id} not found."
            )

        base_state = base_record.state_data or {}
        comp_state = compared_record.state_data or {}

        all_keys = set(base_state.keys()) | set(comp_state.keys())
        diffs: List[FieldDiff] = []

        for k in sorted(all_keys):
            old_val = base_state.get(k)
            new_val = comp_state.get(k)
            if old_val != new_val:
                diffs.append(FieldDiff(field_name=k, old_value=old_val, new_value=new_val))

        return VersionDiffResponse(
            resource_id=resource_id,
            resource_type=resource_type,
            base_version_number=base_version_number,
            compared_version_number=compared_version_number,
            diff_count=len(diffs),
            field_diffs=diffs,
            generated_at=datetime.now(timezone.utc),
        )


history_service = HistoryService()

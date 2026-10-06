"""Clinical Record Versioning Service (Phase 46).

Orchestrates version mutations, optimistic concurrency enforcement,
preservation of clinical provenance, change justification validation,
and temporal integrity.

CRITICAL INVARIANTS:
- CURRENT STATE != COMPLETE HISTORY
- UPDATE != OVERWRITE HISTORY
- CORRECTION != DELETION
- SUPERSESSION != DELETION
- RESTORE != HISTORY DELETION (Restore appends a new version from target history)
- AI CANNOT AUTONOMOUSLY AUTHOR OR APPROVE CLINICAL RECORD VERSIONS
- VERSIONING CANNOT AUTONOMOUSLY DIAGNOSE, PRESCRIBE, OR TRIAGE
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from app.core.exceptions import (
    ResourceVersionNotFoundException,
    StaleResourceException,
    VersionConflictException,
)
from app.repositories.versioning_repository import (
    VersioningRepository,
    versioning_repository,
)
from app.schemas.audit import AuditEventType
from app.schemas.versioning import (
    ClinicalVersionRecord,
    RecordTemporalMetadata,
    VersionCorrectionRequest,
    VersionRestoreRequest,
    VersionSupersedeRequest,
    VersionType,
    VersionUpdateRequest,
)
from app.services.audit_service import AuditService
from app.services.change_validation_service import (
    ChangeValidationService,
    change_validation_service,
)
from app.services.concurrency_service import (
    ConcurrencyService,
    concurrency_service,
)

logger = logging.getLogger(__name__)


class VersioningService:
    """Master domain service managing temporal clinical records and version transitions."""

    def __init__(
        self,
        repository: Optional[VersioningRepository] = None,
        concurrency_svc: Optional[ConcurrencyService] = None,
        change_validator: Optional[ChangeValidationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.repository = repository or versioning_repository
        self.concurrency_service = concurrency_svc or concurrency_service
        self.change_validation_service = change_validator or change_validation_service
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
        """Safely record non-PHI audit event if audit service is available."""
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

    async def create_initial_version(
        self,
        resource_type: str,
        resource_id: str,
        patient_id: str,
        state_data: Dict[str, Any],
        actor_id: str,
        actor_role: str,
        actor_type: str = "CLINICIAN",
        change_reason: str = "Initial clinical record creation",
        temporal: Optional[RecordTemporalMetadata] = None,
        provenance_id: Optional[str] = None,
        source_system: Optional[str] = None,
        source_version: Optional[str] = None,
        verification_state: str = "UNVERIFIED",
        idempotency_key: Optional[str] = None,
    ) -> ClinicalVersionRecord:
        """Create version 1 of a clinical entity."""
        # 1. Enforce AI safety boundary
        self.change_validation_service.validate_actor_ai_boundary(actor_role, actor_type, "CREATE")

        # 2. Enforce change justification
        self.change_validation_service.validate_change_reason(change_reason)

        now = datetime.now(timezone.utc)
        meta_temporal = temporal or RecordTemporalMetadata(
            recorded_time=now,
            effective_time=now,
            updated_time=now,
        )

        record = ClinicalVersionRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            patient_id=patient_id,
            version_number=1,
            previous_version_number=None,
            version_type=VersionType.CREATED,
            is_current=True,
            temporal=meta_temporal,
            state_data=copy.deepcopy(state_data),
            actor_id=actor_id,
            actor_role=actor_role,
            actor_type=actor_type,
            change_reason=change_reason,
            provenance_id=provenance_id,
            source_system=source_system,
            source_version=source_version,
            verification_state=verification_state,
            created_at=now,
        )

        created = self.repository.create_initial_version(record, idempotency_key=idempotency_key)

        await self._record_audit(
            event_type=AuditEventType.RECORD_VERSION_CREATED,
            actor_id=actor_id,
            action="CREATE",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={
                "version_number": 1,
                "version_type": VersionType.CREATED.value,
                "change_reason": change_reason,
            },
        )
        return created

    async def update_version(
        self,
        resource_type: str,
        resource_id: str,
        request: VersionUpdateRequest,
        actor_id: str,
        actor_role: str,
        actor_type: str = "CLINICIAN",
        provenance_id: Optional[str] = None,
        source_system: Optional[str] = None,
    ) -> ClinicalVersionRecord:
        """Apply an incremental update with optimistic concurrency control."""
        if request.idempotency_key:
            cached = self.repository.get_by_idempotency_key(request.idempotency_key)
            if cached:
                return cached

        # 1. AI Safety & Clinical Safety validation
        self.change_validation_service.validate_actor_ai_boundary(actor_role, actor_type, "UPDATE")
        self.change_validation_service.validate_change_reason(request.change_reason)
        self.change_validation_service.validate_clinical_safety_actions(
            resource_type=resource_type,
            changes=request.changes,
            actor_role=actor_role,
        )

        # 2. Current version inspection
        current = self.repository.get_current_version(resource_type, resource_id)
        if not current:
            raise ResourceVersionNotFoundException(
                f"Resource {resource_type}:{resource_id} not found."
            )

        # 3. State transition check
        self.change_validation_service.validate_state_transition(current, VersionType.UPDATED)

        # 4. Concurrency check
        try:
            self.concurrency_service.validate_expected_version(
                current_version=current.version_number,
                expected_version=request.expected_version,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        except (VersionConflictException, StaleResourceException) as exc:
            await self._record_audit(
                event_type=AuditEventType.RECORD_VERSION_CONFLICT_DETECTED,
                actor_id=actor_id,
                action="UPDATE",
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="DENY",
                metadata={
                    "expected_version": request.expected_version,
                    "current_version": current.version_number,
                },
            )
            raise exc

        # 5. Build merged state
        merged_state = copy.deepcopy(current.state_data)
        merged_state.update(request.changes)

        now = datetime.now(timezone.utc)
        temporal = copy.deepcopy(current.temporal)
        temporal.updated_time = now
        if request.event_time:
            temporal.event_time = request.event_time
        if request.effective_time:
            temporal.effective_time = request.effective_time

        new_record = ClinicalVersionRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            patient_id=current.patient_id,
            version_number=current.version_number + 1,
            previous_version_number=current.version_number,
            version_type=VersionType.UPDATED,
            is_current=True,
            temporal=temporal,
            state_data=merged_state,
            actor_id=actor_id,
            actor_role=actor_role,
            actor_type=actor_type,
            change_reason=request.change_reason,
            provenance_id=provenance_id or current.provenance_id,
            source_system=source_system or current.source_system,
            source_version=current.source_version,
            verification_state=current.verification_state,
            created_at=now,
        )

        committed = self.repository.append_version(
            new_record=new_record,
            expected_version=request.expected_version,
            idempotency_key=request.idempotency_key,
        )

        await self._record_audit(
            event_type=AuditEventType.RECORD_VERSION_UPDATED,
            actor_id=actor_id,
            action="UPDATE",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={
                "previous_version": current.version_number,
                "new_version": committed.version_number,
                "change_reason": request.change_reason,
            },
        )
        return committed

    async def correct_version(
        self,
        resource_type: str,
        resource_id: str,
        request: VersionCorrectionRequest,
        actor_id: str,
        actor_role: str,
        actor_type: str = "CLINICIAN",
        provenance_id: Optional[str] = None,
    ) -> ClinicalVersionRecord:
        """Apply a data correction without overwriting history."""
        if request.idempotency_key:
            cached = self.repository.get_by_idempotency_key(request.idempotency_key)
            if cached:
                return cached

        # 1. AI Safety & Reason validation
        self.change_validation_service.validate_actor_ai_boundary(actor_role, actor_type, "CORRECT")
        self.change_validation_service.validate_change_reason(request.correction_reason)

        current = self.repository.get_current_version(resource_type, resource_id)
        if not current:
            raise ResourceVersionNotFoundException(f"Resource {resource_type}:{resource_id} not found.")

        self.change_validation_service.validate_state_transition(current, VersionType.CORRECTED)

        try:
            self.concurrency_service.validate_expected_version(
                current_version=current.version_number,
                expected_version=request.expected_version,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        except (VersionConflictException, StaleResourceException) as exc:
            await self._record_audit(
                event_type=AuditEventType.RECORD_VERSION_CONFLICT_DETECTED,
                actor_id=actor_id,
                action="CORRECT",
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="DENY",
                metadata={"expected_version": request.expected_version, "current_version": current.version_number},
            )
            raise exc

        corrected_state = copy.deepcopy(current.state_data)
        corrected_state.update(request.corrected_data)

        now = datetime.now(timezone.utc)
        temporal = copy.deepcopy(current.temporal)
        temporal.updated_time = now
        if request.event_time:
            temporal.event_time = request.event_time

        new_record = ClinicalVersionRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            patient_id=current.patient_id,
            version_number=current.version_number + 1,
            previous_version_number=current.version_number,
            version_type=VersionType.CORRECTED,
            is_current=True,
            temporal=temporal,
            state_data=corrected_state,
            actor_id=actor_id,
            actor_role=actor_role,
            actor_type=actor_type,
            change_reason=request.correction_reason,
            provenance_id=provenance_id or current.provenance_id,
            source_system=current.source_system,
            source_version=current.source_version,
            verification_state=current.verification_state,
            created_at=now,
        )

        committed = self.repository.append_version(
            new_record=new_record,
            expected_version=request.expected_version,
            idempotency_key=request.idempotency_key,
        )

        await self._record_audit(
            event_type=AuditEventType.RECORD_VERSION_CORRECTED,
            actor_id=actor_id,
            action="CORRECT",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={
                "previous_version": current.version_number,
                "new_version": committed.version_number,
                "correction_reason": request.correction_reason,
            },
        )
        return committed

    async def supersede_version(
        self,
        resource_type: str,
        resource_id: str,
        request: VersionSupersedeRequest,
        actor_id: str,
        actor_role: str,
        actor_type: str = "CLINICIAN",
        provenance_id: Optional[str] = None,
    ) -> ClinicalVersionRecord:
        """Supersede the current record with a new clinical state."""
        if request.idempotency_key:
            cached = self.repository.get_by_idempotency_key(request.idempotency_key)
            if cached:
                return cached

        self.change_validation_service.validate_actor_ai_boundary(actor_role, actor_type, "SUPERSEDE")
        self.change_validation_service.validate_change_reason(request.supersede_reason)

        current = self.repository.get_current_version(resource_type, resource_id)
        if not current:
            raise ResourceVersionNotFoundException(f"Resource {resource_type}:{resource_id} not found.")

        self.change_validation_service.validate_state_transition(current, VersionType.SUPERSEDED)

        try:
            self.concurrency_service.validate_expected_version(
                current_version=current.version_number,
                expected_version=request.expected_version,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        except (VersionConflictException, StaleResourceException) as exc:
            await self._record_audit(
                event_type=AuditEventType.RECORD_VERSION_CONFLICT_DETECTED,
                actor_id=actor_id,
                action="SUPERSEDE",
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="DENY",
                metadata={"expected_version": request.expected_version, "current_version": current.version_number},
            )
            raise exc

        now = datetime.now(timezone.utc)
        temporal = copy.deepcopy(current.temporal)
        temporal.updated_time = now
        temporal.effective_time = now
        if request.event_time:
            temporal.event_time = request.event_time

        new_record = ClinicalVersionRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            patient_id=current.patient_id,
            version_number=current.version_number + 1,
            previous_version_number=current.version_number,
            version_type=VersionType.SUPERSEDED,
            is_current=True,
            temporal=temporal,
            state_data=copy.deepcopy(request.new_state_data),
            actor_id=actor_id,
            actor_role=actor_role,
            actor_type=actor_type,
            change_reason=request.supersede_reason,
            provenance_id=provenance_id or current.provenance_id,
            source_system=current.source_system,
            source_version=current.source_version,
            verification_state=current.verification_state,
            created_at=now,
        )

        committed = self.repository.append_version(
            new_record=new_record,
            expected_version=request.expected_version,
            idempotency_key=request.idempotency_key,
        )

        await self._record_audit(
            event_type=AuditEventType.RECORD_VERSION_SUPERSEDED,
            actor_id=actor_id,
            action="SUPERSEDE",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={
                "previous_version": current.version_number,
                "new_version": committed.version_number,
                "supersede_reason": request.supersede_reason,
            },
        )
        return committed

    async def restore_version(
        self,
        resource_type: str,
        resource_id: str,
        request: VersionRestoreRequest,
        actor_id: str,
        actor_role: str,
        actor_type: str = "CLINICIAN",
    ) -> ClinicalVersionRecord:
        """Restore a historical version by appending a new version that adopts target state.
        
        CRITICAL ARCHITECTURAL INVARIANT:
        RESTORE != HISTORY DELETION.
        Intervening versions (e.g. v5, v6) remain intact in history.
        A new version (e.g. v7) is appended reflecting the restored state of v4.
        """
        if request.idempotency_key:
            cached = self.repository.get_by_idempotency_key(request.idempotency_key)
            if cached:
                return cached

        self.change_validation_service.validate_actor_ai_boundary(actor_role, actor_type, "RESTORE")
        self.change_validation_service.validate_change_reason(request.restore_reason)

        target_historical = self.repository.get_version(
            resource_type=resource_type,
            resource_id=resource_id,
            version_number=request.target_version_number,
        )
        if not target_historical:
            raise ResourceVersionNotFoundException(
                f"Historical version {request.target_version_number} of {resource_type}:{resource_id} not found."
            )

        current = self.repository.get_current_version(resource_type, resource_id)
        if not current:
            raise ResourceVersionNotFoundException(f"Resource {resource_type}:{resource_id} not found.")

        try:
            self.concurrency_service.validate_expected_version(
                current_version=current.version_number,
                expected_version=request.expected_current_version,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        except (VersionConflictException, StaleResourceException) as exc:
            await self._record_audit(
                event_type=AuditEventType.RECORD_VERSION_CONFLICT_DETECTED,
                actor_id=actor_id,
                action="RESTORE",
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="DENY",
                metadata={"expected_version": request.expected_current_version, "current_version": current.version_number},
            )
            raise exc

        now = datetime.now(timezone.utc)
        restored_temporal = RecordTemporalMetadata(
            event_time=target_historical.temporal.event_time,
            recorded_time=now,
            effective_time=now,
            updated_time=now,
        )

        new_record = ClinicalVersionRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            patient_id=current.patient_id,
            version_number=current.version_number + 1,
            previous_version_number=current.version_number,
            version_type=VersionType.RESTORED,
            is_current=True,
            temporal=restored_temporal,
            state_data=copy.deepcopy(target_historical.state_data),
            actor_id=actor_id,
            actor_role=actor_role,
            actor_type=actor_type,
            change_reason=f"Restored from version {target_historical.version_number}: {request.restore_reason}",
            provenance_id=target_historical.provenance_id,
            source_system=target_historical.source_system,
            source_version=target_historical.source_version,
            verification_state=target_historical.verification_state,
            created_at=now,
        )

        committed = self.repository.append_version(
            new_record=new_record,
            expected_version=request.expected_current_version,
            idempotency_key=request.idempotency_key,
        )

        await self._record_audit(
            event_type=AuditEventType.RECORD_VERSION_RESTORED,
            actor_id=actor_id,
            action="RESTORE",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={
                "restored_from_version": target_historical.version_number,
                "new_version": committed.version_number,
                "restore_reason": request.restore_reason,
            },
        )
        return committed

    def get_current_version(self, resource_type: str, resource_id: str) -> Optional[ClinicalVersionRecord]:
        """Fetch current version record."""
        return self.repository.get_current_version(resource_type, resource_id)

    def get_version(
        self, resource_type: str, resource_id: str, version_number: int
    ) -> Optional[ClinicalVersionRecord]:
        """Fetch specific historical version."""
        return self.repository.get_version(resource_type, resource_id, version_number)


versioning_service = VersioningService()

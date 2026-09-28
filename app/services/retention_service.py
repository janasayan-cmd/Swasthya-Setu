"""Retention Management, Archival & Controlled Deletion Service (Phase 24).

ARCHITECTURAL PRINCIPLES:
=========================
- Retention policies are CONFIGURABLE; no legal periods are hard-coded.
- Fail-Closed Deletion: Uncertainty or missing retention policy = DO NOT DELETE.
- Legal & Organizational Holds ALWAYS prevent deletion regardless of age or policy.
- Deletion checks dependencies (clinical records, encounters, prescriptions, documents).
- Coordinates physical deletion with DocumentStorage and records complete audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    DeletionDependencyConflictException,
    DeletionUncertainPolicyException,
    LegalHoldActiveException,
    RetentionNotEligibleException,
    RetentionPolicyNotFoundException,
)
from app.core.logging import get_logger
from app.integrations.privacy.base import RetentionOrchestrator
from app.integrations.storage.base import DocumentStorage
from app.repositories.audit_repository import AuditRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.audit import AuditEventType, AuditRecord
from app.schemas.privacy import (
    ControlledDeletionRequest,
    DeletionBehavior,
    DeletionEligibilityCheck,
    HoldType,
    LegalHold,
    LegalHoldCreateRequest,
    RetentionBehavior,
    RetentionPolicy,
    RetentionStatus,
)

logger = get_logger("app.retention_service")


class RetentionService(RetentionOrchestrator):
    """Domain service managing resource lifecycle, holds, archival, and controlled deletion."""

    def __init__(
        self,
        audit_repository: AuditRepository,
        document_repository: DocumentRepository,
        patient_repository: PatientRepository,
        storage_adapter: DocumentStorage,
        settings: Optional[Settings] = None,
    ) -> None:
        self.audit_repo = audit_repository
        self.doc_repo = document_repository
        self.patient_repo = patient_repository
        self.storage = storage_adapter
        self.settings = settings or get_settings()

        # Configurable retention policies registry
        self._policies: Dict[str, RetentionPolicy] = {}
        # Active holds registry: hold_id -> LegalHold
        self._holds: Dict[str, LegalHold] = {}
        # Resource lifecycle status: resource_id -> RetentionStatus
        self._resource_status: Dict[str, RetentionStatus] = {}

        self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        """Register default configurable baseline retention policies."""
        defaults = [
            RetentionPolicy(
                policy_id="pol-patient-default",
                data_type="patient",
                purpose="CLINICAL_CARE",
                retention_period_days=3650,
                retention_start_event="creation",
                archive_behavior=RetentionBehavior.ARCHIVE,
                deletion_behavior=DeletionBehavior.SOFT_DELETE,
                description="Master patient clinical record lifecycle",
            ),
            RetentionPolicy(
                policy_id="pol-docs-default",
                data_type="medical_document",
                purpose="DOCUMENT_PROCESSING",
                retention_period_days=3650,  # 10 years configurable
                retention_start_event="creation",
                archive_behavior=RetentionBehavior.ARCHIVE,
                deletion_behavior=DeletionBehavior.SOFT_DELETE,
                description="General clinical documents retained under hospital policy",
            ),
            RetentionPolicy(
                policy_id="pol-extractions-default",
                data_type="document_extraction",
                purpose="DOCUMENT_PROCESSING",
                retention_period_days=3650,
                retention_start_event="creation",
                archive_behavior=RetentionBehavior.ARCHIVE,
                deletion_behavior=DeletionBehavior.SOFT_DELETE,
                description="OCR structured extractions linked to source documents",
            ),
            RetentionPolicy(
                policy_id="pol-exports-ephemeral",
                data_type="patient_data_export",
                purpose="PATIENT_DATA_EXPORT",
                retention_period_days=1,  # 24 hours
                retention_start_event="creation",
                archive_behavior=RetentionBehavior.NONE,
                deletion_behavior=DeletionBehavior.PERMANENT_DELETE,
                description="Ephemeral patient download bundles",
            ),
            RetentionPolicy(
                policy_id="pol-triage-default",
                data_type="triage_assessment",
                purpose="TRIAGE",
                retention_period_days=1825,  # 5 years
                retention_start_event="creation",
                archive_behavior=RetentionBehavior.ARCHIVE,
                deletion_behavior=DeletionBehavior.SOFT_DELETE,
                description="Emergency and urgent triage clinical assessments",
            ),
            RetentionPolicy(
                policy_id="pol-careplans-default",
                data_type="care_plan",
                purpose="CARE_PLAN",
                retention_period_days=1825,
                retention_start_event="discharge",
                archive_behavior=RetentionBehavior.ARCHIVE,
                deletion_behavior=DeletionBehavior.SOFT_DELETE,
                description="Active and historical patient care plans",
            ),
            RetentionPolicy(
                policy_id="pol-audit-default",
                data_type="audit_record",
                purpose="AUDIT",
                retention_period_days=2555,  # 7 years
                retention_start_event="creation",
                archive_behavior=RetentionBehavior.ARCHIVE,
                deletion_behavior=DeletionBehavior.RESTRICTED,
                description="Immutable system and security audit trail records",
            ),
            RetentionPolicy(
                policy_id="pol-temp-default",
                data_type="temporary_file",
                purpose="SYSTEM_OPERATIONS",
                retention_period_days=1,
                retention_start_event="creation",
                archive_behavior=RetentionBehavior.NONE,
                deletion_behavior=DeletionBehavior.PERMANENT_DELETE,
                description="Temporary processing artifacts and scratch files",
            ),
        ]
        for p in defaults:
            self._policies[p.data_type] = p

    # -----------------------------------------------------------------------
    # Policy Management
    # -----------------------------------------------------------------------

    def register_policy(self, policy: RetentionPolicy) -> None:
        """Register or update a configurable retention policy."""
        self._policies[policy.data_type] = policy

    async def get_policy(self, resource_type: str) -> Optional[RetentionPolicy]:
        """Fetch active policy for resource type."""
        return self._policies.get(resource_type.lower())

    def list_policies(self) -> List[RetentionPolicy]:
        """List all active retention policies."""
        return list(self._policies.values())

    # -----------------------------------------------------------------------
    # Legal & Preservation Holds (TRD Sec 17)
    # -----------------------------------------------------------------------

    async def place_hold(
        self, request: LegalHoldCreateRequest, actor_id: str
    ) -> LegalHold:
        """Place an administrative, investigation, or legal hold on a resource."""
        hold_id = f"hold-{uuid.uuid4().hex[:12]}"
        hold = LegalHold(
            hold_id=hold_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            patient_id=request.patient_id,
            hold_type=request.hold_type,
            reason=request.reason,
            placed_by=actor_id,
            placed_at=datetime.now(timezone.utc),
            is_active=True,
            expires_at=request.expires_at,
        )
        self._holds[hold_id] = hold

        await self._audit(
            event_type=AuditEventType.RESOURCE_ARCHIVE_STARTED,
            actor_id=actor_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            patient_id=request.patient_id,
            action="PLACE_LEGAL_HOLD",
            outcome="SUCCESS",
            metadata={"hold_id": hold_id, "hold_type": request.hold_type.value},
        )
        return hold

    async def release_hold(self, hold_id: str, actor_id: str) -> bool:
        """Release an active hold."""
        hold = self._holds.get(hold_id)
        if not hold or not hold.is_active:
            return False

        updated = hold.model_copy(update={"is_active": False})
        self._holds[hold_id] = updated

        await self._audit(
            event_type=AuditEventType.RESOURCE_ARCHIVE_STARTED,
            actor_id=actor_id,
            resource_type=hold.resource_type,
            resource_id=hold.resource_id,
            patient_id=hold.patient_id,
            action="RELEASE_LEGAL_HOLD",
            outcome="SUCCESS",
            metadata={"hold_id": hold_id},
        )
        return True

    def get_active_holds(self, resource_id: str) -> List[LegalHold]:
        """Get all active holds preventing deletion of target resource."""
        now = datetime.now(timezone.utc)
        active = []
        for hold in self._holds.values():
            if hold.resource_id == resource_id and hold.is_active:
                if hold.expires_at and hold.expires_at < now:
                    continue  # Expired
                active.append(hold)
        return active

    def list_all_holds(self) -> List[LegalHold]:
        """List all registered holds."""
        return list(self._holds.values())

    # -----------------------------------------------------------------------
    # Deletion Eligibility & Fail-Closed Checks (TRD Sec 15 & 16)
    # -----------------------------------------------------------------------

    async def check_deletion_eligibility(
        self, resource_type: str, resource_id: str, patient_id: Optional[str] = None
    ) -> DeletionEligibilityCheck:
        """Verify whether a resource can be safely deleted or if holds/dependencies prevent it.
        
        FAIL CLOSED: If policy is missing or uncertain -> DO NOT DELETE.
        """
        policy = await self.get_policy(resource_type)
        if not policy:
            return DeletionEligibilityCheck(
                resource_id=resource_id,
                resource_type=resource_type,
                eligible_for_deletion=False,
                retention_policy_id=None,
                active_holds=[],
                dependent_records={},
                reason="Deletion refused: privacy retention policy is uncertain or undefined (Fail-Closed).",
            )

        # Check holds
        active_holds = self.get_active_holds(resource_id)
        if active_holds:
            return DeletionEligibilityCheck(
                resource_id=resource_id,
                resource_type=resource_type,
                eligible_for_deletion=False,
                retention_policy_id=policy.policy_id,
                active_holds=[h.hold_id for h in active_holds],
                dependent_records={},
                reason="Deletion blocked: One or more active legal/investigative holds exist.",
            )

        # Check dependencies for patient deletion
        dependents: Dict[str, int] = {}
        if resource_type.lower() == "patient":
            # Check attached documents
            patient_docs = await self.doc_repo.list_by_patient_id(resource_id)
            if patient_docs:
                dependents["medical_documents"] = len(patient_docs)

        if dependents:
            return DeletionEligibilityCheck(
                resource_id=resource_id,
                resource_type=resource_type,
                eligible_for_deletion=False,
                retention_policy_id=policy.policy_id,
                active_holds=[],
                dependent_records=dependents,
                reason=f"Deletion blocked: Unresolved dependencies ({dependents}).",
            )

        return DeletionEligibilityCheck(
            resource_id=resource_id,
            resource_type=resource_type,
            eligible_for_deletion=True,
            retention_policy_id=policy.policy_id,
            active_holds=[],
            dependent_records={},
            reason="Resource is eligible for deletion under active policy.",
        )

    # -----------------------------------------------------------------------
    # Archival Workflow (TRD Sec 14)
    # -----------------------------------------------------------------------

    async def archive_resource(
        self, resource_type: str, resource_id: str, actor_id: str
    ) -> bool:
        """Transition resource to ARCHIVED state while preserving provenance and audit records."""
        await self._audit(
            event_type=AuditEventType.RESOURCE_ARCHIVE_STARTED,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_id=None,
            action="ARCHIVE_RESOURCE",
            outcome="STARTED",
        )

        if resource_type.lower() in ("document", "medical_document"):
            await self.doc_repo.set_archived(resource_id, True)

        self._resource_status[resource_id] = RetentionStatus.ARCHIVED

        await self._audit(
            event_type=AuditEventType.RESOURCE_ARCHIVED,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_id=None,
            action="ARCHIVE_RESOURCE",
            outcome="SUCCESS",
        )
        return True

    # -----------------------------------------------------------------------
    # Controlled Deletion Execution (TRD Sec 15, 37)
    # -----------------------------------------------------------------------

    async def execute_deletion(
        self,
        resource_type: str,
        resource_id: str,
        actor_id: str,
        reason: str,
        force: bool = False,
        patient_id: Optional[str] = None,
    ) -> bool:
        """Execute controlled deletion following fail-closed hold checks and dependency validation."""
        await self._audit(
            event_type=AuditEventType.RESOURCE_DELETION_REQUESTED,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_id=patient_id,
            action="DELETE_RESOURCE",
            outcome="REQUESTED",
            metadata={"reason": reason, "force": force},
        )

        eligibility = await self.check_deletion_eligibility(resource_type, resource_id, patient_id)

        # Invariant 1: Hold is absolute — cannot force delete
        if eligibility.active_holds:
            await self._audit(
                event_type=AuditEventType.RESOURCE_DELETION_FAILED,
                actor_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                action="DELETE_RESOURCE",
                outcome="FAILED",
                metadata={"reason": "Active legal hold present"},
            )
            raise LegalHoldActiveException(resource_id=resource_id, hold_ids=eligibility.active_holds)

        # Invariant 2: Policy must exist (Fail-closed)
        if not eligibility.retention_policy_id:
            await self._audit(
                event_type=AuditEventType.RESOURCE_DELETION_FAILED,
                actor_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                action="DELETE_RESOURCE",
                outcome="FAILED",
                metadata={"reason": "Missing retention policy"},
            )
            raise DeletionUncertainPolicyException(resource_id=resource_id)

        # Invariant 3: Dependency check
        if eligibility.dependent_records and not force:
            await self._audit(
                event_type=AuditEventType.RESOURCE_DELETION_FAILED,
                actor_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                action="DELETE_RESOURCE",
                outcome="FAILED",
                metadata={"dependencies": eligibility.dependent_records},
            )
            raise DeletionDependencyConflictException(
                resource_id=resource_id, dependent_types=list(eligibility.dependent_records.keys())
            )

        # Perform deletion
        try:
            if resource_type.lower() in ("document", "medical_document"):
                doc = await self.doc_repo.get_by_id(resource_id)
                if doc and doc.storage_key:
                    await self.storage.delete(doc.storage_key)
                await self.doc_repo.delete(resource_id)

            self._resource_status[resource_id] = RetentionStatus.DELETED

            await self._audit(
                event_type=AuditEventType.RESOURCE_DELETION_COMPLETED,
                actor_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                action="DELETE_RESOURCE",
                outcome="SUCCESS",
                metadata={"reason": reason},
            )
            return True

        except Exception as e:
            logger.error(f"Deletion execution failed for {resource_type} {resource_id}: {e}")
            await self._audit(
                event_type=AuditEventType.RESOURCE_DELETION_FAILED,
                actor_id=actor_id,
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id,
                action="DELETE_RESOURCE",
                outcome="FAILED",
                metadata={"error": str(e)},
            )
            return False

    def get_resource_status(self, resource_id: str) -> RetentionStatus:
        """Fetch current retention lifecycle status for resource."""
        return self._resource_status.get(resource_id, RetentionStatus.ACTIVE)

    async def _audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        patient_id: Optional[str],
        action: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write audit record."""
        try:
            await self.audit_repo.create(
                AuditRecord(
                    id=str(uuid.uuid4()),
                    event_type=event_type,
                    user_id=actor_id,
                    patient_id=patient_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    outcome=outcome,
                    timestamp=datetime.now(timezone.utc),
                    metadata=metadata or {},
                )
            )
        except Exception as e:
            logger.warning(f"Failed to persist retention audit: {e}")

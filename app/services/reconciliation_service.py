import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from app.core.config import settings
from app.core.exceptions import (
    ReconciliationNotFoundException,
    ResourceVersionConflictException,
    InvalidResolutionException,
)
from app.schemas.reconciliation import (
    ReconciliationRecord,
    ReconciliationScope,
    ReconciliationStatus,
    ReconciliationSourceItem,
    ReconciliationConflictItem,
    ReconciliationRequest,
    ReconciliationResponse,
    ReconciliationResolveRequest,
    ReconciliationResolutionAction,
)
from app.schemas.provenance import ProvenanceCategory, ProvenanceVerificationState
from app.repositories.reconciliation_repository import ReconciliationRepository
from app.repositories.allergy_repository import AllergyRepository
from app.repositories.patient_medication_repository import PatientMedicationRepository
from app.repositories.patient_repository import PatientRepository
from app.services.provenance_service import ProvenanceService
from app.services.audit_service import AuditService
from app.schemas.audit import AuditEventType, AuditSeverity, AuditActor

logger = logging.getLogger(__name__)

class ReconciliationService:
    """
    Coordinates multi-source clinical reconciliation (Medications, Allergies, Vitals, Interoperability Imports).
    Crucial Safety Invariants:
      - Comparing records never overwrites verified data silently.
      - Discrepant records produce explicit conflicts and route for human review.
      - Never marks unverified external or extracted records as verified clinical truth autonomously.
      - Preserves full provenance and historical records upon resolution.
    """

    def __init__(
        self,
        reconciliation_repo: ReconciliationRepository,
        allergy_repo: AllergyRepository,
        medication_repo: PatientMedicationRepository,
        patient_repo: PatientRepository,
        provenance_service: ProvenanceService,
        audit_service: AuditService,
    ):
        self.reconciliation_repo = reconciliation_repo
        self.allergy_repo = allergy_repo
        self.medication_repo = medication_repo
        self.patient_repo = patient_repo
        self.provenance_service = provenance_service
        self.audit_service = audit_service

    async def reconcile_patient(
        self,
        patient_id: str,
        request: ReconciliationRequest,
        actor: Optional[AuditActor] = None,
    ) -> ReconciliationResponse:
        """
        Executes cross-source clinical reconciliation for a patient across specified scopes
        (Medications, Allergies, Conditions, Demographics, etc.).
        """
        is_enabled = getattr(settings, "RECONCILIATION_ENABLED", True)
        if not is_enabled:
            # Safety invariant: Never treat disabled reconciliation as CLEAR / SAFE
            now = datetime.now(timezone.utc)
            rec = ReconciliationRecord(
                id=f"rec_{uuid.uuid4().hex[:12]}",
                patient_id=patient_id,
                scope=request.scope,
                status=ReconciliationStatus.UNRESOLVED,
                sources=[],
                conflicts=[],
                created_at=now,
                summary="Reconciliation is disabled in configuration. Clinical data was NOT reconciled.",
            )
            return ReconciliationResponse(**rec.model_dump())

        if actor:
            await self.audit_service.log_event(
                event_type=AuditEventType.RECONCILIATION_STARTED,
                actor=actor,
                patient_id=patient_id,
                resource_type="clinical_reconciliation",
                resource_id=patient_id,
                severity=AuditSeverity.INFO,
                description=f"Reconciliation initiated for patient {patient_id} on scope {request.scope.value}",
                payload={"scope": request.scope.value}
            )

        sources: List[ReconciliationSourceItem] = []
        conflicts: List[ReconciliationConflictItem] = []

        now = datetime.now(timezone.utc)

        # 1. Scope: ALLERGIES
        if request.scope in (ReconciliationScope.ALLERGIES, ReconciliationScope.ALL):
            allergy_sources, allergy_conflicts = await self._reconcile_allergies(patient_id, request.external_records)
            sources.extend(allergy_sources)
            conflicts.extend(allergy_conflicts)

        # 2. Scope: MEDICATIONS
        if request.scope in (ReconciliationScope.MEDICATIONS, ReconciliationScope.ALL):
            if getattr(settings, "MEDICATION_RECONCILIATION_ENABLED", True):
                med_sources, med_conflicts = await self._reconcile_medications(patient_id, request.external_records)
                sources.extend(med_sources)
                conflicts.extend(med_conflicts)

        # 3. Scope: EXTERNAL / INTEROPERABILITY
        if request.scope in (ReconciliationScope.EXTERNAL_DATA, ReconciliationScope.ALL):
            if getattr(settings, "EXTERNAL_DATA_RECONCILIATION_ENABLED", True):
                ext_sources, ext_conflicts = await self._reconcile_external_data(patient_id, request.external_records)
                sources.extend(ext_sources)
                conflicts.extend(ext_conflicts)

        # Determine aggregate status
        if conflicts:
            rec_status = ReconciliationStatus.PENDING
            summary = f"Detected {len(conflicts)} clinical conflict(s) requiring clinician review."
        else:
            rec_status = ReconciliationStatus.RESOLVED if sources else ReconciliationStatus.PENDING
            summary = "No conflicting clinical values detected across evaluated sources."

        rec_record = ReconciliationRecord(
            id=f"rec_{uuid.uuid4().hex[:12]}",
            patient_id=patient_id,
            scope=request.scope,
            status=rec_status,
            sources=sources,
            conflicts=conflicts,
            created_at=now,
            summary=summary,
            version=1,
        )

        saved = self.reconciliation_repo.create(rec_record)

        if actor:
            await self.audit_service.log_event(
                event_type=AuditEventType.RECONCILIATION_COMPLETED,
                actor=actor,
                patient_id=patient_id,
                resource_type="clinical_reconciliation",
                resource_id=saved.id,
                severity=AuditSeverity.WARNING if conflicts else AuditSeverity.INFO,
                description=f"Reconciliation completed for patient {patient_id}. Status: {rec_status.value}",
                payload={"conflicts_count": len(conflicts), "sources_count": len(sources)}
            )

        return ReconciliationResponse(**saved.model_dump())

    async def _reconcile_allergies(
        self,
        patient_id: str,
        external_records: List[Dict[str, Any]],
    ) -> tuple[List[ReconciliationSourceItem], List[ReconciliationConflictItem]]:
        sources: List[ReconciliationSourceItem] = []
        conflicts: List[ReconciliationConflictItem] = []

        existing_allergies = await self.allergy_repo.list_by_patient(patient_id) if hasattr(self.allergy_repo, "list_by_patient") else []

        for alg in existing_allergies:
            alg_id = getattr(alg, "id", "")
            allergen = getattr(alg, "allergen", "")
            status = getattr(alg, "status", None)
            status_val = status.value if hasattr(status, "value") else str(status)
            source_cat = ProvenanceCategory.CLINICIAN_ENTERED
            sources.append(ReconciliationSourceItem(
                source_id=f"allergy:{alg_id}",
                source_category=source_cat,
                concept_name=allergen,
                value={"status": status_val, "severity": getattr(alg, "severity", "")},
                is_verified=True,
            ))

        # Check external records
        for ext in external_records:
            if ext.get("resource_type") == "allergy":
                ext_allergen = (ext.get("allergen") or "").strip().lower()
                ext_status = ext.get("status")
                sources.append(ReconciliationSourceItem(
                    source_id=str(ext.get("id", "ext_alg")),
                    source_category=ProvenanceCategory.IMPORTED,
                    source_system=ext.get("source_system", "external"),
                    concept_name=ext.get("allergen", ""),
                    value={"status": ext_status},
                    is_verified=False,
                ))

                # Check conflict with existing
                for alg in existing_allergies:
                    existing_name = (getattr(alg, "allergen", "") or "").strip().lower()
                    if existing_name == ext_allergen:
                        internal_status = getattr(alg, "status", None)
                        internal_val = internal_status.value if hasattr(internal_status, "value") else str(internal_status)
                        if str(ext_status).lower() != internal_val.lower():
                            conflicts.append(ReconciliationConflictItem(
                                conflict_id=f"cnf_{uuid.uuid4().hex[:8]}",
                                concept_name=existing_name,
                                field_name="status",
                                internal_source_id=f"allergy:{getattr(alg, 'id', '')}",
                                internal_value=internal_val,
                                external_source_id=str(ext.get("id", "ext_alg")),
                                external_value=ext_status,
                                description=f"Allergy '{existing_name}' has status '{internal_val}' internally but '{ext_status}' externally."
                            ))

        return sources, conflicts

    async def _reconcile_medications(
        self,
        patient_id: str,
        external_records: List[Dict[str, Any]],
    ) -> tuple[List[ReconciliationSourceItem], List[ReconciliationConflictItem]]:
        sources: List[ReconciliationSourceItem] = []
        conflicts: List[ReconciliationConflictItem] = []

        existing_meds = await self.medication_repo.list_by_patient(patient_id, limit=200) if hasattr(self.medication_repo, "list_by_patient") else []

        for med in existing_meds:
            med_id = getattr(med, "id", "")
            drug_name = getattr(med, "drug_name_raw", "")
            strength = getattr(med, "strength_raw", "")
            status = getattr(med, "status", None)
            sources.append(ReconciliationSourceItem(
                source_id=f"medication:{med_id}",
                source_category=ProvenanceCategory.CLINICIAN_ENTERED,
                concept_name=drug_name,
                value={"strength": strength, "status": str(status)},
                is_verified=getattr(med, "verification_status", None) == "VERIFIED",
            ))

        # Check external medication items
        for ext in external_records:
            if ext.get("resource_type") == "medication":
                ext_name = (ext.get("drug_name") or ext.get("canonical_name") or "").strip().lower()
                ext_strength = (ext.get("strength") or "").strip().lower()
                sources.append(ReconciliationSourceItem(
                    source_id=str(ext.get("id", "ext_med")),
                    source_category=ProvenanceCategory.IMPORTED,
                    source_system=ext.get("source_system", "external"),
                    concept_name=ext_name,
                    value={"strength": ext_strength, "status": ext.get("status")},
                    is_verified=False,
                ))

                for med in existing_meds:
                    existing_name = (getattr(med, "drug_name_raw", "") or "").strip().lower()
                    if existing_name == ext_name:
                        existing_str = (getattr(med, "strength_raw", "") or "").strip().lower()
                        if existing_str and ext_strength and existing_str != ext_strength:
                            conflicts.append(ReconciliationConflictItem(
                                conflict_id=f"cnf_{uuid.uuid4().hex[:8]}",
                                concept_name=existing_name,
                                field_name="strength",
                                internal_source_id=f"medication:{getattr(med, 'id', '')}",
                                internal_value=getattr(med, "strength_raw", ""),
                                external_source_id=str(ext.get("id", "ext_med")),
                                external_value=ext.get("strength"),
                                description=f"Medication '{existing_name}' has conflicting strength: '{getattr(med, 'strength_raw', '')}' internal vs '{ext.get('strength')}' external."
                            ))

        return sources, conflicts

    async def _reconcile_external_data(
        self,
        patient_id: str,
        external_records: List[Dict[str, Any]],
    ) -> tuple[List[ReconciliationSourceItem], List[ReconciliationConflictItem]]:
        sources: List[ReconciliationSourceItem] = []
        conflicts: List[ReconciliationConflictItem] = []

        patient = await self.patient_repo.get_by_id(patient_id)
        if patient:
            sources.append(ReconciliationSourceItem(
                source_id=f"patient:{patient.id}",
                source_category=ProvenanceCategory.CLINICIAN_ENTERED,
                concept_name="Demographics",
                value={"name": f"{patient.first_name} {patient.last_name}", "phone": patient.phone},
                is_verified=True,
            ))

        for ext in external_records:
            if ext.get("resource_type") == "patient_demographics":
                sources.append(ReconciliationSourceItem(
                    source_id=str(ext.get("id", "ext_demo")),
                    source_category=ProvenanceCategory.IMPORTED,
                    source_system=ext.get("source_system", "external"),
                    concept_name="Demographics",
                    value=ext.get("data", {}),
                    is_verified=False,
                ))
                if patient and ext.get("data", {}).get("phone") and patient.phone:
                    if ext.get("data", {}).get("phone") != patient.phone:
                        conflicts.append(ReconciliationConflictItem(
                            conflict_id=f"cnf_{uuid.uuid4().hex[:8]}",
                            concept_name="Demographics",
                            field_name="phone",
                            internal_source_id=f"patient:{patient.id}",
                            internal_value=patient.phone,
                            external_source_id=str(ext.get("id", "ext_demo")),
                            external_value=ext.get("data", {}).get("phone"),
                            description="Patient phone number differs between verified record and imported external record."
                        ))

        return sources, conflicts

    async def get_reconciliation(self, reconciliation_id: str) -> ReconciliationResponse:
        record = self.reconciliation_repo.get_by_id(reconciliation_id)
        if not record:
            raise ReconciliationNotFoundException(reconciliation_id)
        return ReconciliationResponse(**record.model_dump())

    async def list_by_patient(
        self,
        patient_id: str,
        status: Optional[ReconciliationStatus] = None,
        scope: Optional[ReconciliationScope] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ReconciliationResponse]:
        records = self.reconciliation_repo.list_by_patient(
            patient_id=patient_id,
            status=status,
            scope=scope,
            skip=skip,
            limit=limit,
        )
        return [ReconciliationResponse(**r.model_dump()) for r in records]

    async def resolve_reconciliation(
        self,
        reconciliation_id: str,
        request: ReconciliationResolveRequest,
        resolver_id: str,
        actor: AuditActor,
    ) -> ReconciliationResponse:
        """
        Applies clinician resolution decision to reconciliation record.
        Respects optimistic concurrency version checks.
        Preserves original records and never performs silent automated clinical overrides.
        """
        record = self.reconciliation_repo.get_by_id(reconciliation_id)
        if not record:
            raise ReconciliationNotFoundException(reconciliation_id)

        # Optimistic concurrency version check
        if request.expected_version is not None and record.version != request.expected_version:
            raise ResourceVersionConflictException(
                f"Reconciliation {reconciliation_id} version mismatch: expected {request.expected_version}, found {record.version}"
            )

        now = datetime.now(timezone.utc)
        record.resolved_at = now
        record.resolved_by = resolver_id
        record.resolution_action = request.action
        record.resolution_notes = request.notes

        if request.action == ReconciliationResolutionAction.REJECT_EXTERNAL:
            record.status = ReconciliationStatus.REJECTED
        elif request.action == ReconciliationResolutionAction.LEAVE_UNRESOLVED:
            record.status = ReconciliationStatus.UNRESOLVED
        else:
            record.status = ReconciliationStatus.RESOLVED

        action_str = request.action.value if hasattr(request.action, "value") else str(request.action)

        # Audit resolution
        await self.audit_service.log_event(
            event_type=AuditEventType.RECONCILIATION_RESOLVED,
            actor=actor,
            patient_id=record.patient_id,
            resource_type="clinical_reconciliation",
            resource_id=record.id,
            severity=AuditSeverity.INFO,
            description=f"Reconciliation {reconciliation_id} resolved with action {action_str} by {resolver_id}",
            payload={"action": action_str, "reason": request.reason}
        )

        return ReconciliationResponse(**record.model_dump())


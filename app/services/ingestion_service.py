"""Master Clinical Data Ingestion & Reconciliation Service (Phase 45).

Orchestrates:
1. Source authentication, registration & trust verification
2. Safety invariants enforcement (IMPORT != VERIFICATION; INGESTION != DIAGNOSIS)
3. Interoperability & structural payload validation (FHIR R4 / HL7)
4. Deterministic patient identity resolution & AI match boundary
5. Phase 43 consent & access policy evaluation
6. Immutable origin and transformation provenance tracking
7. Phase 13 interoperability data mapping
8. Phase 26 domain reconciliation invocation
9. Review gating (creating review tasks when conflicts exist)
10. Idempotent deduplication and bounded retry classification
11. Structured audit event generation
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AIIngestionAuthorityProhibitedException,
    IngestionAutonomousClinicalProhibitedException,
    IngestionCancelledException,
    IngestionConsentRequiredException,
    IngestionConsentRevokedException,
    IngestionDisabledException,
    IngestionDuplicateDetectedException,
    IngestionIdempotencyConflictException,
    IngestionNotFoundException,
    IngestionPayloadInvalidException,
    IngestionProviderTimeoutException,
    IngestionProviderUnavailableException,
    IngestionQuarantinedException,
    IngestionReconciliationFailedException,
    IngestionResourceUnsupportedException,
    IngestionSourceAuthenticationFailedException,
    IngestionSourceNotFoundException,
    IngestionSourceSuspendedException,
    IngestionSourceUnauthorizedException,
)
from app.integrations.interoperability.fhir.mapper import FHIRMapper
from app.repositories.ingestion_repository import IngestionRepository
from app.schemas.access_decision import AccessEvaluationRequest, AccessEvaluationResponse
from app.schemas.audit import AuditEventType
from app.schemas.ingestion import (
    DataTrustStatus,
    ExternalRecordsListResponse,
    ExternalSourceContext,
    IdentityMatchOutcome,
    IngestionCreateRequest,
    IngestionHistoryResponse,
    IngestionListResponse,
    IngestionRecord,
    IngestionResponse,
    IngestionStatus,
    IngestionStatusResponse,
    ReconciliationResolveAction,
    SourceTrustState,
    WebhookIngestionPayload,
)
from app.schemas.reconciliation import (
    ReconciliationConflictItem,
    ReconciliationRecord,
    ReconciliationRequest,
    ReconciliationResolutionAction,
    ReconciliationScope,
    ReconciliationSourceItem,
    ReconciliationStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.consent_access_service import ConsentAccessService
from app.services.identity_resolution_service import IdentityResolutionService
from app.services.ingestion_provenance_service import IngestionProvenanceService
from app.services.ingestion_validation_service import IngestionValidationService
from app.services.interoperability_service import InteroperabilityService
from app.services.reconciliation_service import ReconciliationService

logger = logging.getLogger("app.services.ingestion")


class IngestionService:
    """Master domain service coordinating external data ingestion, reconciliation, and integration."""

    def __init__(
        self,
        ingestion_repo: IngestionRepository,
        validation_service: IngestionValidationService,
        identity_service: IdentityResolutionService,
        provenance_service: IngestionProvenanceService,
        consent_access_service: Optional[ConsentAccessService] = None,
        reconciliation_service: Optional[ReconciliationService] = None,
        interop_service: Optional[InteroperabilityService] = None,
        audit_service: Optional[AuditService] = None,
        fhir_mapper: Optional[FHIRMapper] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.ingestion_repo = ingestion_repo
        self.validation_service = validation_service
        self.identity_service = identity_service
        self.provenance_service = provenance_service
        self.consent_access_service = consent_access_service
        self.reconciliation_service = reconciliation_service
        self.interop_service = interop_service
        self.audit_service = audit_service
        self.fhir_mapper = fhir_mapper or FHIRMapper()
        self.settings = settings or get_settings()

    async def ingest_clinical_data(
        self,
        request: IngestionCreateRequest,
        requester_id: str = "system",
        requester_role: str = "SYSTEM",
        is_ai_agent: bool = False,
    ) -> IngestionRecord:
        """Receive, validate, resolve, reconcile, and safely stage external clinical data."""
        # 1. AI Safety Enforcement: AI cannot authorize or initiate clinical ingestion
        if is_ai_agent or (requester_role or "").upper() in ("AI", "BOT", "SYSTEM_INFERRED"):
            raise AIIngestionAuthorityProhibitedException(
                "AI is not an authorizing authority and cannot initiate or authorize external clinical data ingestion."
            )

        if not getattr(self.settings, "DATA_INGESTION_ENABLED", True):
            raise IngestionDisabledException("External clinical data ingestion subsystem is disabled.")

        # 2. Idempotency Check
        if request.idempotency_key:
            existing_by_key = await self.ingestion_repo.find_by_idempotency_key(request.idempotency_key)
            if existing_by_key:
                # Verify payload match
                current_hash = self.provenance_service.compute_payload_hash(request.payload)
                if existing_by_key.raw_payload_hash != current_hash:
                    raise IngestionIdempotencyConflictException(
                        f"Idempotency key '{request.idempotency_key}' was previously used with a different payload."
                    )
                return existing_by_key

        # Check duplicate resource from same source system
        existing_duplicate = await self.ingestion_repo.find_by_source_resource(
            source_system=request.source_system,
            external_resource_id=request.external_resource_id,
        )
        if existing_duplicate:
            logger.info(
                f"Idempotent hit: Resource '{request.external_resource_id}' from '{request.source_system}' already exists as '{existing_duplicate.id}'."
            )
            return existing_duplicate

        # 3. Source & Safety Invariant Validation
        is_webhook = bool(requester_role == "EXTERNAL_PROVIDER" or (requester_id and requester_id.startswith("webhook:")))
        source_context = await self.validation_service.validate_source_and_authorization(
            request, is_webhook_authenticated=is_webhook
        )
        self.validation_service.validate_safety_invariants(request)

        # 4. Payload & Interoperability Validation (FHIR R4 / HL7)
        self.validation_service.validate_payload_and_interoperability(request)

        # 5. Compute Payload Hash & Initial Ingestion Record
        ingestion_id = f"ing-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        payload_hash = self.provenance_service.compute_payload_hash(request.payload)

        record = IngestionRecord(
            id=ingestion_id,
            source_system=request.source_system,
            source_type=request.source_type,
            source_organization_id=request.source_organization_id or source_context.organization_id,
            source_facility_id=request.source_facility_id or source_context.facility_id,
            resource_type=request.resource_type,
            format=request.format,
            format_version=request.format_version or "R4",
            external_resource_id=request.external_resource_id,
            external_patient_id=request.external_patient_id,
            healthsetu_patient_id=request.healthsetu_patient_id,
            status=IngestionStatus.RECEIVED,
            verification_status=DataTrustStatus.UNVERIFIED,
            raw_payload_hash=payload_hash,
            raw_payload_preview={k: str(v)[:100] for k, v in list(request.payload.items())[:5]},
            idempotency_key=request.idempotency_key,
            history=[{
                "status": IngestionStatus.RECEIVED.value,
                "timestamp": now.isoformat(),
                "actor": requester_id,
                "note": "Payload received and validated for interoperability.",
            }],
            created_at=now,
            updated_at=now,
        )
        await self.ingestion_repo.create_ingestion(record)

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.INGESTION_RECEIVED,
                outcome="ALLOW",
                actor_id=requester_id,
                action=AuditEventType.INGESTION_RECEIVED.value,
                resource_type=request.resource_type,
                resource_id=ingestion_id,
                metadata={
                    "source_system": request.source_system,
                    "external_resource_id": request.external_resource_id,
                },
            )

        # 6. Patient Identity Resolution
        demographics = None
        if request.resource_type.lower() == "patient":
            demographics = {
                "name": f"{request.payload.get('name', [{}])[0].get('given', [''])[0]} {request.payload.get('name', [{}])[0].get('family', '')}".strip() if isinstance(request.payload.get("name"), list) else None,
                "phone": request.payload.get("telecom", [{}])[0].get("value") if isinstance(request.payload.get("telecom"), list) else None,
            }

        outcome, resolved_patient_id, match_note = await self.identity_service.resolve_patient_identity(
            source_system=request.source_system,
            external_patient_id=request.external_patient_id,
            healthsetu_patient_id=request.healthsetu_patient_id,
            demographics=demographics,
            is_ai_agent=False,
        )

        record.identity_outcome = outcome
        if resolved_patient_id:
            record.healthsetu_patient_id = resolved_patient_id

        # Record Identity Transition
        self._record_transition(
            record,
            new_status=IngestionStatus.PROCESSING,
            note=f"Identity resolution outcome: {outcome.value}. {match_note or ''}",
        )

        # Stop automated integration if identity is conflicted, multiple, or unresolvable
        if outcome in (IdentityMatchOutcome.CONFLICT, IdentityMatchOutcome.MULTIPLE_MATCHES):
            self._record_transition(
                record,
                new_status=IngestionStatus.REVIEW_REQUIRED,
                verification_status=DataTrustStatus.CONFLICTED,
                note=f"Identity ambiguity or conflict: {match_note}. Human review required.",
            )
            await self.ingestion_repo.update_ingestion(record)
            if self.audit_service:
                await self.audit_service.record(
                    event_type=AuditEventType.INGESTION_IDENTITY_REVIEW_REQUIRED,
                    outcome="ALLOW",
                    actor_id=requester_id,
                    action=AuditEventType.INGESTION_IDENTITY_REVIEW_REQUIRED.value,
                    resource_type=request.resource_type,
                    resource_id=ingestion_id,
                    metadata={"identity_outcome": outcome.value},
                )
            return record

        if outcome in (IdentityMatchOutcome.NO_MATCH, IdentityMatchOutcome.INSUFFICIENT_INFORMATION):
            self._record_transition(
                record,
                new_status=IngestionStatus.REVIEW_REQUIRED,
                verification_status=DataTrustStatus.UNVERIFIED,
                note=f"Patient identity could not be matched: {match_note}.",
            )
            await self.ingestion_repo.update_ingestion(record)
            return record

        # 7. Phase 43 Consent & Access Control Check
        if resolved_patient_id and self.consent_access_service:
            consent_eval_req = AccessEvaluationRequest(
                actor_id=request.source_system,
                patient_id=resolved_patient_id,
                resource_type=request.resource_type.upper(),
                action="IMPORT",
                purpose=request.purpose or "CARE_DELIVERY",
                actor_role="EXTERNAL_SYSTEM",
                organization_id=record.source_organization_id,
                facility_id=record.source_facility_id,
            )
            eval_res = await self.consent_access_service.evaluate_access(consent_eval_req)
            if not eval_res.allowed:
                reason = eval_res.reason_code or "Consent evaluation denied access."
                self._record_transition(
                    record,
                    new_status=IngestionStatus.REJECTED,
                    verification_status=DataTrustStatus.REJECTED,
                    note=f"Phase 43 Consent Denied: {reason}",
                )
                record.error_code = "CONSENT_DENIED"
                record.error_message = reason
                await self.ingestion_repo.update_ingestion(record)
                if "REVOKED" in reason or "WITHDRAWN" in reason:
                    raise IngestionConsentRevokedException(f"Patient consent has been withdrawn ({reason}).")
                raise IngestionConsentRequiredException(f"Patient consent denied for external ingestion: {reason}")

        # 8. Record Provenance
        prov_record = await self.provenance_service.record_provenance(
            ingestion_id=ingestion_id,
            source_system=request.source_system,
            source_resource_id=request.external_resource_id,
            source_organization=record.source_organization_id,
            source_facility=record.source_facility_id,
            validation_result="VALID",
            verification_state=DataTrustStatus.UNVERIFIED,
        )
        record.provenance_id = prov_record.provenance_id

        # 9. Map Resource via Phase 13 FHIRMapper
        try:
            mapped_data = self.fhir_mapper.map_inbound_resource(
                resource_type=request.resource_type,
                payload=request.payload,
                source_system=request.source_system,
                healthsetu_patient_id=resolved_patient_id,
            )
            record.mapped_data = mapped_data
            self._record_transition(record, IngestionStatus.MAPPED, note="Interoperability mapping complete.")
        except Exception as exc:
            logger.error(f"Mapping error on ingestion {ingestion_id}: {exc}")
            record.mapped_data = {"raw": request.payload}

        # 10. Domain Reconciliation Integration (Phase 26)
        if resolved_patient_id and self.reconciliation_service:
            scope_map = {
                "medicationrequest": ReconciliationScope.MEDICATIONS,
                "medication": ReconciliationScope.MEDICATIONS,
                "allergyintolerance": ReconciliationScope.ALLERGIES,
                "observation": ReconciliationScope.EXTERNAL_DATA,
                "diagnosticreport": ReconciliationScope.EXTERNAL_DATA,
                "condition": ReconciliationScope.CONDITIONS,
                "documentreference": ReconciliationScope.DOCUMENTS,
            }
            target_scope = scope_map.get(request.resource_type.lower(), ReconciliationScope.EXTERNAL_DATA)

            try:
                rec_res = await self.reconciliation_service.reconcile_patient(
                    patient_id=resolved_patient_id,
                    request=ReconciliationRequest(scope=target_scope),
                )
                record.reconciliation_id = getattr(rec_res, "id", None) or getattr(rec_res, "reconciliation_id", None)
                record.reconciliation_status = rec_res.status.value

                if rec_res.status == ReconciliationStatus.UNRESOLVED or (getattr(rec_res, "conflicts", None) and len(rec_res.conflicts) > 0):
                    # Clinical Conflict Detected -> Route to Human Review!
                    self._record_transition(
                        record,
                        new_status=IngestionStatus.REVIEW_REQUIRED,
                        verification_status=DataTrustStatus.PENDING_REVIEW,
                        note=f"Reconciliation detected {len(getattr(rec_res, 'conflicts', []))} conflicts. Clinical review required.",
                    )
                    await self.ingestion_repo.update_ingestion(record)
                    return record
            except Exception as exc:
                logger.warning(f"Reconciliation execution non-fatal error: {exc}")

        # 11. Staged Integration (Marked UNVERIFIED / PENDING_REVIEW - IMPORT != CLINICAL TRUTH)
        # Even when technically integrated into repository/store, it is tagged UNVERIFIED!
        self._record_transition(
            record,
            new_status=IngestionStatus.INTEGRATED,
            verification_status=DataTrustStatus.UNVERIFIED,
            note="Resource successfully ingested and staged. Tagged UNVERIFIED pending clinician verification.",
        )
        record.processed_at = datetime.now(timezone.utc)
        await self.ingestion_repo.update_ingestion(record)

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.INGESTION_INTEGRATED,
                outcome="ALLOW",
                actor_id=requester_id,
                action=AuditEventType.INGESTION_INTEGRATED.value,
                resource_type=request.resource_type,
                resource_id=ingestion_id,
                metadata={
                    "patient_id": resolved_patient_id,
                    "verification_status": DataTrustStatus.UNVERIFIED.value,
                },
            )

        return record

    async def get_ingestion(self, ingestion_id: str) -> IngestionRecord:
        """Retrieve an ingestion transaction by ID."""
        record = await self.ingestion_repo.get_ingestion(ingestion_id)
        if not record:
            raise IngestionNotFoundException(f"Ingestion record '{ingestion_id}' not found.")
        return record

    async def list_ingestions(
        self,
        source_system: Optional[str] = None,
        patient_id: Optional[str] = None,
        status: Optional[IngestionStatus] = None,
        page: int = 1,
        size: int = 20,
    ) -> IngestionListResponse:
        """List ingestion transactions paginated."""
        offset = (page - 1) * size
        items, total = await self.ingestion_repo.list_ingestions(
            source_system=source_system,
            patient_id=patient_id,
            status=status,
            limit=size,
            offset=offset,
        )
        return IngestionListResponse(
            items=[self._to_response(i) for i in items],
            total=total,
            page=page,
            size=size,
        )

    async def list_patient_external_records(
        self, patient_id: str, page: int = 1, size: int = 20
    ) -> ExternalRecordsListResponse:
        """List all external clinical data staged for a specific patient."""
        offset = (page - 1) * size
        items, total = await self.ingestion_repo.list_by_patient(patient_id=patient_id, limit=size, offset=offset)
        return ExternalRecordsListResponse(
            patient_id=patient_id,
            records=[self._to_response(i) for i in items],
            total=total,
        )

    async def cancel_ingestion(
        self, ingestion_id: str, actor_id: str, actor_role: str
    ) -> IngestionRecord:
        """Cancel a pending ingestion transaction."""
        record = await self.get_ingestion(ingestion_id)
        if record.status in (IngestionStatus.INTEGRATED, IngestionStatus.REJECTED, IngestionStatus.CANCELLED):
            raise IngestionCancelledException(f"Ingestion {ingestion_id} is in terminal state '{record.status.value}'.")

        self._record_transition(
            record,
            new_status=IngestionStatus.CANCELLED,
            note=f"Ingestion cancelled by actor {actor_id} ({actor_role}).",
        )
        await self.ingestion_repo.update_ingestion(record)

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.INGESTION_CANCELLED,
                outcome="ALLOW",
                actor_id=actor_id,
                action=AuditEventType.INGESTION_CANCELLED.value,
                resource_type=record.resource_type,
                resource_id=ingestion_id,
            )
        return record

    async def resolve_reconciliation(
        self,
        reconciliation_id: str,
        action: ReconciliationResolveAction,
        current_user: AuthenticatedUserContext,
    ) -> Dict[str, Any]:
        """Clinician manually resolves a clinical reconciliation case."""
        if current_user.is_ai:
            raise AIIngestionAuthorityProhibitedException("AI cannot resolve clinical reconciliation cases.")

        resolution_map = {
            "ACCEPT_EXTERNAL": ReconciliationResolutionAction.ACCEPT_EXTERNAL,
            "KEEP_INTERNAL": ReconciliationResolutionAction.ACCEPT_CLINICIAN,
            "SUPERSEDE": ReconciliationResolutionAction.MARK_SUPERSEDED,
            "DISCARD": ReconciliationResolutionAction.REJECT_EXTERNAL,
        }
        domain_action = resolution_map.get(action.resolution.upper(), ReconciliationResolutionAction.ACCEPT_EXTERNAL)

        # Update reconciliation status if service available
        if self.reconciliation_service and hasattr(self.reconciliation_service, "resolve_reconciliation"):
            try:
                await self.reconciliation_service.resolve_reconciliation(
                    reconciliation_id=reconciliation_id,
                    action=domain_action,
                    actor_id=current_user.user_id,
                    notes=action.notes,
                )
            except Exception as exc:
                logger.warning(f"Reconciliation resolution dispatch error: {exc}")

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.INGESTION_RECONCILIATION_RESOLVED,
                outcome="ALLOW",
                actor_id=current_user.user_id,
                action=AuditEventType.INGESTION_RECONCILIATION_RESOLVED.value,
                resource_type="reconciliation",
                resource_id=reconciliation_id,
                metadata={"resolution": action.resolution, "notes": action.notes},
            )

        return {
            "reconciliation_id": reconciliation_id,
            "status": "RESOLVED",
            "resolution": action.resolution,
            "resolved_by": current_user.user_id,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def process_webhook(self, webhook_payload: WebhookIngestionPayload) -> IngestionRecord:
        """Handle inbound webhook callback from an external healthcare provider."""
        # 1. Validate signature & replay window
        source_context = await self.validation_service.validate_webhook(webhook_payload)

        # 2. Extract clinical data and construct IngestionCreateRequest
        resource_data = webhook_payload.data
        resource_type = resource_data.get("resourceType", "Observation")
        ext_res_id = str(resource_data.get("id") or webhook_payload.event_id)
        ext_pat_id = None
        hs_pat_id = None
        if "subject" in resource_data and isinstance(resource_data["subject"], dict):
            ref = str(resource_data["subject"].get("reference", ""))
            if "Patient/" in ref:
                candidate = ref.split("Patient/")[1]
                if candidate.startswith("patient-"):
                    hs_pat_id = candidate
                else:
                    ext_pat_id = candidate
            elif "identifier" in resource_data["subject"] and isinstance(resource_data["subject"]["identifier"], dict):
                ext_pat_id = resource_data["subject"]["identifier"].get("value")

        ingest_req = IngestionCreateRequest(
            source_system=source_context.source_id,
            source_type=source_context.source_type,
            source_organization_id=source_context.organization_id,
            source_facility_id=source_context.facility_id,
            resource_type=resource_type,
            format="FHIR",
            external_resource_id=ext_res_id,
            external_patient_id=ext_pat_id,
            healthsetu_patient_id=hs_pat_id,
            payload=resource_data,
            idempotency_key=f"wh-{webhook_payload.provider}-{webhook_payload.event_id}",
        )

        if self.audit_service:
            await self.audit_service.record(
                event_type=AuditEventType.INGESTION_WEBHOOK_RECEIVED,
                outcome="ALLOW",
                actor_id=webhook_payload.provider,
                action=AuditEventType.INGESTION_WEBHOOK_RECEIVED.value,
                resource_type=resource_type,
                resource_id=webhook_payload.event_id,
            )

        return await self.ingest_clinical_data(
            request=ingest_req,
            requester_id=f"webhook:{webhook_payload.provider}",
            requester_role="EXTERNAL_PROVIDER",
        )

    def _record_transition(
        self,
        record: IngestionRecord,
        new_status: IngestionStatus,
        verification_status: Optional[DataTrustStatus] = None,
        note: Optional[str] = None,
    ) -> None:
        """Atomically transition state and record historical entry."""
        now = datetime.now(timezone.utc)
        record.status = new_status
        if verification_status:
            record.verification_status = verification_status
        record.history.append({
            "status": new_status.value,
            "verification_status": record.verification_status.value,
            "timestamp": now.isoformat(),
            "note": note or "",
        })
        record.updated_at = now

    def _to_response(self, record: IngestionRecord) -> IngestionResponse:
        return IngestionResponse(
            id=record.id,
            source_system=record.source_system,
            source_type=record.source_type,
            resource_type=record.resource_type,
            external_resource_id=record.external_resource_id,
            healthsetu_patient_id=record.healthsetu_patient_id,
            status=record.status,
            verification_status=record.verification_status,
            identity_outcome=record.identity_outcome,
            reconciliation_id=record.reconciliation_id,
            reconciliation_status=record.reconciliation_status,
            raw_payload_hash=record.raw_payload_hash,
            provenance_id=record.provenance_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            error_code=record.error_code,
            error_message=record.error_message,
        )

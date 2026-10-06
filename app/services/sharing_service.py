"""Clinical Data Sharing Service (Phase 44).

Orchestrates controlled clinical data sharing, external exchanges, and exports:
- Centralized authorization enforcement via Phase 43 Consent Engine
- SSRF and external destination security checks
- Minimum necessary scope filtering
- JIT consent re-evaluation at execution time
- Provider adapter dispatch and delivery tracking
- Full provenance recording and structured audit emission
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    AISharingAuthorityProhibitedException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    SharingActionNotAllowedException,
    SharingAlreadyCompletedException,
    SharingAutonomousClinicalProhibitedException,
    SharingCancelledException,
    SharingConsentExpiredException,
    SharingConsentRequiredException,
    SharingConsentRevokedException,
    SharingDestinationInvalidException,
    SharingDisabledException,
    SharingExpiredException,
    SharingExportNotAllowedException,
    SharingNotAuthorizedException,
    SharingNotFoundException,
    SharingProviderFailedException,
    SharingProviderTimeoutException,
    SharingProviderUnavailableException,
    SharingRecipientInvalidException,
    SharingScopeInvalidException,
    ValidationException,
)
from app.core.logging import get_logger
from app.integrations.interoperability.fhir.mapper import FHIRMapper
from app.integrations.sharing.base import ProviderDeliveryState, ProviderShareResult, SharingProvider
from app.integrations.sharing.registry import sharing_provider_registry
from app.repositories.export_repository import ExportRecord, ExportRepository
from app.repositories.sharing_repository import SharingRequestRecord, SharingRepository
from app.schemas.audit import AuditActor, AuditEventRecord, AuditEventType
from app.schemas.export import (
    ExportFormat,
    ExportRequestCreate,
    ExportResponse,
    ExportScopeType,
    ExportSnapshotMetadata,
    ExportStatus,
    ExportStatusResponse,
)
from app.schemas.sharing import (
    DeliveryMethod,
    DestinationType,
    SharedDataSummaryResponse,
    SharingAction,
    SharingApproveAction,
    SharingCancelAction,
    SharingDenyAction,
    SharingEvaluationRequest,
    SharingEvaluationResponse,
    SharingExecuteAction,
    SharingRequestCreate,
    SharingRequestListResponse,
    SharingRequestResponse,
    SharingStatus,
    SharingType,
)
from app.services.audit_service import AuditService
from app.services.base import BaseService
from app.services.sharing_policy_service import SharingPolicyDecisionCode, SharingPolicyService
from app.services.sharing_provenance_service import SharingProvenanceService
from app.utils.sharing_security import validate_destination_url

logger = get_logger("app.sharing_service")


class SharingService(BaseService[SharingRepository]):
    """Central service orchestrating controlled clinical data sharing and exports."""

    def __init__(
        self,
        sharing_repository: SharingRepository,
        export_repository: ExportRepository,
        sharing_policy_service: SharingPolicyService,
        sharing_provenance_service: SharingProvenanceService,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        super().__init__(repository=sharing_repository)
        self.sharing_repo = sharing_repository
        self.export_repo = export_repository
        self.policy_service = sharing_policy_service
        self.provenance_service = sharing_provenance_service
        self.audit_service = audit_service
        self.fhir_mapper = FHIRMapper()

    # =========================================================================
    # SHARING REQUEST LIFECYCLE
    # =========================================================================

    async def create_sharing_request(
        self,
        request: SharingRequestCreate,
        requester_id: str,
        requester_role: str,
    ) -> SharingRequestResponse:
        """Create and evaluate a new clinical data sharing request."""
        if not getattr(settings, "DATA_SHARING_ENABLED", True):
            raise SharingDisabledException("Clinical data sharing subsystem is disabled.")

        # 1. AI Boundary Protection
        if (requester_role or "").upper() in ("AI", "BOT", "SYSTEM_INFERRED"):
            raise AISharingAuthorityProhibitedException("AI cannot create or authorize data sharing requests.")

        # 2. Prevent Clinical Decision misuse
        if request.purpose.upper() in ("DIAGNOSIS", "TRIAGE", "TREATMENT_ORDER", "PRESCRIPTION_CHANGE"):
            raise SharingAutonomousClinicalProhibitedException(
                "Clinical data sharing cannot diagnose, prescribe, triage, or alter clinical orders."
            )

        # 3. Idempotency Check
        if request.idempotency_key:
            existing = await self.sharing_repo.get_by_idempotency_key(request.idempotency_key)
            if existing:
                return self._to_response(existing)

        # 4. Destination validation if external
        if request.destination_url:
            validate_destination_url(request.destination_url, allow_empty=True)

        # 5. Evaluate Sharing Policy
        eval_req = SharingEvaluationRequest(
            actor_id=requester_id,
            actor_role=requester_role,
            patient_id=request.patient_id,
            recipient_id=request.recipient_id,
            recipient_type=request.recipient_type,
            destination_url=request.destination_url,
            resource_scopes=request.resource_scopes,
            action=request.action,
            purpose=request.purpose,
        )
        eval_res = await self.policy_service.evaluate_sharing_policy(eval_req)

        initial_status = SharingStatus.REQUESTED
        denial_reason = None
        consent_id = request.consent_id or eval_res.consent_id

        if not eval_res.allowed:
            if eval_res.decision == SharingPolicyDecisionCode.REVOKED:
                raise SharingConsentRevokedException(eval_res.reason_detail)
            elif eval_res.decision == SharingPolicyDecisionCode.EXPIRED:
                raise SharingConsentExpiredException(eval_res.reason_detail)
            elif eval_res.decision == SharingPolicyDecisionCode.NOT_PERMITTED:
                raise SharingActionNotAllowedException(eval_res.reason_detail)
            else:
                # Requires explicit patient authorization
                initial_status = SharingStatus.PENDING_AUTHORIZATION
                denial_reason = eval_res.reason_detail
        else:
            # Authorized either via patient self-share or active consent grant
            initial_status = SharingStatus.APPROVED

        # Calculate expiration
        exp_hours = request.expiration_hours or getattr(settings, "SHARING_DEFAULT_EXPIRATION_HOURS", 72)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=exp_hours)

        record_id = f"shr-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        record = SharingRequestRecord(
            id=record_id,
            patient_id=request.patient_id,
            requester_id=requester_id,
            requester_role=requester_role,
            sharing_type=request.sharing_type,
            recipient_id=request.recipient_id,
            recipient_type=request.recipient_type,
            resource_scopes=eval_res.filtered_resource_scopes or request.resource_scopes,
            action=request.action,
            purpose=request.purpose,
            delivery_method=request.delivery_method,
            requested_format=request.requested_format,
            destination_url=request.destination_url,
            status=initial_status,
            consent_id=consent_id,
            idempotency_key=request.idempotency_key,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            approved_at=now if initial_status == SharingStatus.APPROVED else None,
            denial_reason=denial_reason,
            history=[{
                "status": initial_status.value,
                "actor_id": requester_id,
                "timestamp": now.isoformat(),
                "reason": request.reason or "Sharing request initiated",
            }],
        )

        saved = await self.sharing_repo.create(record)

        # Audit
        await self._audit(
            event_type=AuditEventType.SHARING_REQUEST_CREATED,
            actor_id=requester_id,
            patient_id=request.patient_id,
            resource_id=record_id,
            outcome="ALLOW",
            metadata={"status": initial_status.value, "scopes": saved.resource_scopes},
        )

        return self._to_response(saved)

    async def get_sharing_request(
        self,
        sharing_id: str,
        actor_id: str,
        actor_role: str,
    ) -> SharingRequestResponse:
        """Fetch sharing request ensuring caller is authorized to view."""
        record = await self.sharing_repo.get_by_id(sharing_id)
        if not record:
            raise SharingNotFoundException(f"Sharing request '{sharing_id}' not found.")

        # Access check: Must be patient, requester, or recipient (or admin)
        if actor_role != "ADMIN" and actor_id not in (record.patient_id, record.requester_id, record.recipient_id):
            raise SharingNotAuthorizedException("You are not authorized to view this sharing request.")

        await self._audit(
            event_type=AuditEventType.SHARING_REQUEST_VIEWED,
            actor_id=actor_id,
            patient_id=record.patient_id,
            resource_id=sharing_id,
            outcome="ALLOW",
        )

        return self._to_response(record)

    async def approve_sharing_request(
        self,
        sharing_id: str,
        actor_id: str,
        actor_role: str,
        action: SharingApproveAction,
    ) -> SharingRequestResponse:
        """Approve a pending sharing request (Patient authority only)."""
        record = await self.sharing_repo.get_by_id(sharing_id)
        if not record:
            raise SharingNotFoundException(f"Sharing request '{sharing_id}' not found.")

        if (actor_role or "").upper() in ("AI", "BOT"):
            raise AISharingAuthorityProhibitedException("AI cannot approve sharing requests.")

        # Only the patient whose data is being shared can approve
        if actor_id != record.patient_id and actor_role != "ADMIN":
            raise ForbiddenException("Only the patient can approve clinical data sharing requests.")

        if record.status in (SharingStatus.APPROVED, SharingStatus.SHARED, SharingStatus.DELIVERED):
            raise SharingAlreadyCompletedException("Sharing request is already approved or completed.")

        if record.status in (SharingStatus.CANCELLED, SharingStatus.EXPIRED, SharingStatus.DENIED):
            raise ValidationException(f"Cannot approve sharing request in '{record.status.value}' state.")

        # Check expiration
        if record.expires_at <= datetime.now(timezone.utc):
            record.status = SharingStatus.EXPIRED
            await self.sharing_repo.update(record)
            raise SharingExpiredException("Sharing request has expired.")

        now = datetime.now(timezone.utc)
        record.status = SharingStatus.APPROVED
        record.approved_at = now
        record.updated_at = now
        if action.consent_id:
            record.consent_id = action.consent_id

        record.history.append({
            "status": SharingStatus.APPROVED.value,
            "actor_id": actor_id,
            "timestamp": now.isoformat(),
            "reason": action.reason or "Approved by patient",
        })

        saved = await self.sharing_repo.update(record)

        await self._audit(
            event_type=AuditEventType.SHARING_REQUEST_APPROVED,
            actor_id=actor_id,
            patient_id=record.patient_id,
            resource_id=sharing_id,
            outcome="ALLOW",
        )

        return self._to_response(saved)

    async def deny_sharing_request(
        self,
        sharing_id: str,
        actor_id: str,
        actor_role: str,
        action: SharingDenyAction,
    ) -> SharingRequestResponse:
        """Deny a sharing request."""
        record = await self.sharing_repo.get_by_id(sharing_id)
        if not record:
            raise SharingNotFoundException(f"Sharing request '{sharing_id}' not found.")

        if (actor_role or "").upper() in ("AI", "BOT"):
            raise AISharingAuthorityProhibitedException("AI cannot deny or manage sharing authorization.")

        if actor_id != record.patient_id and actor_role != "ADMIN":
            raise ForbiddenException("Only the patient can deny clinical data sharing requests.")

        if record.status in (SharingStatus.SHARED, SharingStatus.DELIVERED):
            raise SharingAlreadyCompletedException("Cannot deny a sharing request that has already been executed.")

        now = datetime.now(timezone.utc)
        record.status = SharingStatus.DENIED
        record.denial_reason = action.reason
        record.updated_at = now
        record.history.append({
            "status": SharingStatus.DENIED.value,
            "actor_id": actor_id,
            "timestamp": now.isoformat(),
            "reason": action.reason,
        })

        saved = await self.sharing_repo.update(record)

        await self._audit(
            event_type=AuditEventType.SHARING_REQUEST_DENIED,
            actor_id=actor_id,
            patient_id=record.patient_id,
            resource_id=sharing_id,
            outcome="DENY",
            reason_code=action.reason,
        )

        return self._to_response(saved)

    async def cancel_sharing_request(
        self,
        sharing_id: str,
        actor_id: str,
        actor_role: str,
        action: SharingCancelAction,
    ) -> SharingRequestResponse:
        """Cancel an in-flight or pending sharing request."""
        record = await self.sharing_repo.get_by_id(sharing_id)
        if not record:
            raise SharingNotFoundException(f"Sharing request '{sharing_id}' not found.")

        if actor_id not in (record.requester_id, record.patient_id) and actor_role != "ADMIN":
            raise ForbiddenException("Only the requester or patient can cancel a sharing request.")

        if record.status in (SharingStatus.SHARED, SharingStatus.DELIVERED):
            raise SharingAlreadyCompletedException("Cannot cancel an already delivered sharing request.")

        now = datetime.now(timezone.utc)
        record.status = SharingStatus.CANCELLED
        record.updated_at = now
        record.history.append({
            "status": SharingStatus.CANCELLED.value,
            "actor_id": actor_id,
            "timestamp": now.isoformat(),
            "reason": action.reason,
        })

        saved = await self.sharing_repo.update(record)

        await self._audit(
            event_type=AuditEventType.SHARING_REQUEST_CANCELLED,
            actor_id=actor_id,
            patient_id=record.patient_id,
            resource_id=sharing_id,
            outcome="ALLOW",
        )

        return self._to_response(saved)

    async def execute_sharing(
        self,
        sharing_id: str,
        actor_id: str,
        actor_role: str,
        action: Optional[SharingExecuteAction] = None,
    ) -> SharingRequestResponse:
        """Execute sharing transmission with MANDATORY JIT CONSENT RE-EVALUATION."""
        record = await self.sharing_repo.get_by_id(sharing_id)
        if not record:
            raise SharingNotFoundException(f"Sharing request '{sharing_id}' not found.")

        # 1. State Validation: Must be APPROVED
        if record.status == SharingStatus.DENIED:
            raise SharingNotAuthorizedException("Cannot execute a denied sharing request.")
        if record.status == SharingStatus.CANCELLED:
            raise SharingCancelledException("Cannot execute a cancelled sharing request.")
        if record.status in (SharingStatus.SHARED, SharingStatus.DELIVERED):
            raise SharingAlreadyCompletedException("Sharing request has already been executed.")
        if record.status not in (SharingStatus.APPROVED, SharingStatus.PROCESSING, SharingStatus.FAILED):
            raise ValidationException(f"Sharing request must be APPROVED before execution (current: {record.status.value}).")

        # 2. Expiration Check
        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            record.status = SharingStatus.EXPIRED
            await self.sharing_repo.update(record)
            raise SharingExpiredException("Sharing request has expired.")

        # 3. CRITICAL JIT RE-EVALUATION: QUEUED AUTHORIZATION != CURRENT AUTHORIZATION
        # Re-evaluate Phase 43 consent right now before constructing or sending payload
        if record.requester_id != record.patient_id:
            eval_req = SharingEvaluationRequest(
                actor_id=record.requester_id,
                actor_role=record.requester_role,
                patient_id=record.patient_id,
                recipient_id=record.recipient_id,
                recipient_type=record.recipient_type,
                destination_url=record.destination_url,
                resource_scopes=record.resource_scopes,
                action=record.action,
                purpose=record.purpose,
            )
            eval_res = await self.policy_service.evaluate_sharing_policy(eval_req)
            if not eval_res.allowed:
                # Consent was revoked or expired while queued!
                record.status = SharingStatus.REVOKED
                record.denial_reason = f"JIT authorization failure: {eval_res.reason_detail}"
                await self.sharing_repo.update(record)
                if eval_res.decision == SharingPolicyDecisionCode.REVOKED:
                    raise SharingConsentRevokedException(eval_res.reason_detail)
                elif eval_res.decision == SharingPolicyDecisionCode.EXPIRED:
                    raise SharingConsentExpiredException(eval_res.reason_detail)
                else:
                    raise SharingNotAuthorizedException(eval_res.reason_detail)

        # 4. Mark PROCESSING
        record.status = SharingStatus.PROCESSING
        record.updated_at = now
        await self.sharing_repo.update(record)

        # 5. Construct Minimum Necessary Payload
        payload = self._build_clinical_payload(
            patient_id=record.patient_id,
            scopes=record.resource_scopes,
            format_type=record.requested_format,
        )

        # 6. Record Provenance
        prov_record = self.provenance_service.record_outbound_provenance(
            share_or_export_id=record.id,
            patient_id=record.patient_id,
            requester_id=record.requester_id,
            recipient_id=record.recipient_id,
            resource_scopes=record.resource_scopes,
            action=record.action.value,
            format_type=record.requested_format,
            destination=record.destination_url,
            payload_data=payload,
        )
        record.provenance_id = prov_record.provenance_id

        # 7. Dispatch via Provider Adapter
        provider: SharingProvider = sharing_provider_registry.get_provider(getattr(settings, "SHARING_PROVIDER", "mock"))
        share_result: ProviderShareResult = await provider.share(
            payload=payload,
            destination_url=record.destination_url,
            recipient_id=record.recipient_id,
            metadata={"share_id": record.id, "provenance_id": prov_record.provenance_id},
        )

        # 8. Provider Result Mapping:
        # NON-NEGOTIABLE SAFETY: TIMEOUT != SUCCESS, UNAVAILABLE != SHARED, UNKNOWN != DELIVERED
        now_after = datetime.now(timezone.utc)
        record.provider_reference = share_result.provider_reference
        record.delivery_status = share_result.state.value

        if share_result.state == ProviderDeliveryState.SUCCESS:
            record.status = SharingStatus.SHARED
            record.executed_at = now_after
            record.delivered_at = now_after
            record.history.append({
                "status": SharingStatus.SHARED.value,
                "actor_id": actor_id,
                "timestamp": now_after.isoformat(),
                "provider_ref": share_result.provider_reference,
            })
            saved = await self.sharing_repo.update(record)
            await self._audit(
                event_type=AuditEventType.SHARING_DELIVERED,
                actor_id=actor_id,
                patient_id=record.patient_id,
                resource_id=record.id,
                outcome="ALLOW",
                metadata={"provider_ref": share_result.provider_reference},
            )
            return self._to_response(saved)

        elif share_result.state == ProviderDeliveryState.TIMEOUT:
            record.status = SharingStatus.FAILED
            record.retry_count += 1
            saved = await self.sharing_repo.update(record)
            await self._audit(
                event_type=AuditEventType.SHARING_FAILED,
                actor_id=actor_id,
                patient_id=record.patient_id,
                resource_id=record.id,
                outcome="DENY",
                reason_code="PROVIDER_TIMEOUT",
            )
            raise SharingProviderTimeoutException(share_result.message or "Provider request timed out.")

        elif share_result.state == ProviderDeliveryState.UNAVAILABLE:
            record.status = SharingStatus.FAILED
            record.retry_count += 1
            saved = await self.sharing_repo.update(record)
            await self._audit(
                event_type=AuditEventType.SHARING_FAILED,
                actor_id=actor_id,
                patient_id=record.patient_id,
                resource_id=record.id,
                outcome="DENY",
                reason_code="PROVIDER_UNAVAILABLE",
            )
            raise SharingProviderUnavailableException(share_result.message or "Provider unavailable.")

        else:
            record.status = SharingStatus.FAILED
            record.retry_count += 1
            saved = await self.sharing_repo.update(record)
            await self._audit(
                event_type=AuditEventType.SHARING_FAILED,
                actor_id=actor_id,
                patient_id=record.patient_id,
                resource_id=record.id,
                outcome="DENY",
                reason_code="PROVIDER_FAILED",
            )
            raise SharingProviderFailedException(share_result.message or "Provider rejected sharing dispatch.")

    async def list_sharing_requests(
        self,
        actor_id: str,
        actor_role: str,
        patient_id: Optional[str] = None,
        status: Optional[SharingStatus] = None,
        page: int = 1,
        size: int = 20,
    ) -> SharingRequestListResponse:
        """List sharing requests subject to role boundaries."""
        target_patient = patient_id if actor_role == "ADMIN" else (patient_id or actor_id)
        requester_filter = None if (actor_role == "ADMIN" or target_patient) else actor_id

        records, total = await self.sharing_repo.list_all(
            requester_id=requester_filter,
            patient_id=target_patient,
            status=status,
            page=page,
            size=size,
        )

        return SharingRequestListResponse(
            items=[self._to_response(r) for r in records],
            total=total,
            page=page,
            size=size,
        )

    async def get_patient_shared_data(
        self,
        patient_id: str,
        actor_id: str,
        actor_role: str,
    ) -> SharedDataSummaryResponse:
        """Get summary of authorized data sharing for a patient."""
        if actor_role != "ADMIN" and actor_id != patient_id:
            raise ForbiddenException("Cannot view shared data summary of another patient.")

        records, _ = await self.sharing_repo.list_by_patient(patient_id=patient_id)
        active_shares = [r for r in records if r.status in (SharingStatus.APPROVED, SharingStatus.SHARED, SharingStatus.DELIVERED)]

        recipients = list({r.recipient_id for r in active_shares})
        scopes = list({s for r in active_shares for s in r.resource_scopes})
        last_shared = max([r.delivered_at for r in active_shares if r.delivered_at], default=None)

        return SharedDataSummaryResponse(
            patient_id=patient_id,
            active_shares_count=len(active_shares),
            last_shared_at=last_shared,
            authorized_recipients=recipients,
            authorized_resource_scopes=scopes,
            shared_requests=[self._to_response(r) for r in active_shares],
        )

    # =========================================================================
    # CONTROLLED EXPORTS LIFECYCLE
    # =========================================================================

    async def create_export(
        self,
        patient_id: str,
        requester_id: str,
        requester_role: str,
        request: ExportRequestCreate,
    ) -> ExportResponse:
        """Initiate controlled patient clinical export."""
        # 1. AI cannot initiate exports
        if (requester_role or "").upper() in ("AI", "BOT"):
            raise AISharingAuthorityProhibitedException("AI cannot initiate data exports.")

        # 2. Authorization check: Patient self-export or consent-backed clinician export
        if requester_id != patient_id and requester_role != "ADMIN":
            eval_req = SharingEvaluationRequest(
                actor_id=requester_id,
                actor_role=requester_role,
                patient_id=patient_id,
                recipient_id=requester_id,
                recipient_type=DestinationType.INTERNAL_CLINICIAN,
                resource_scopes=[request.export_scope.value],
                action=SharingAction.EXPORT,
                purpose=request.purpose,
            )
            eval_res = await self.policy_service.evaluate_sharing_policy(eval_req)
            if not eval_res.allowed:
                raise SharingExportNotAllowedException(f"Export not authorized: {eval_res.reason_detail}")

        # 3. Idempotency Check
        if request.idempotency_key:
            existing = await self.export_repo.get_by_idempotency_key(request.idempotency_key)
            if existing:
                return self._export_to_response(existing)

        export_id = f"exp-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=24)  # 24 hour TTL for exports

        # Build point-in-time snapshot
        payload = self._build_clinical_payload(
            patient_id=patient_id,
            scopes=[request.export_scope.value],
            format_type=request.format.value,
        )

        record = ExportRecord(
            id=export_id,
            patient_id=patient_id,
            requester_id=requester_id,
            requester_role=requester_role,
            export_scope=request.export_scope,
            format=request.format,
            purpose=request.purpose,
            status=ExportStatus.READY,
            consent_id=request.consent_id,
            idempotency_key=request.idempotency_key,
            created_at=now,
            expires_at=expires_at,
            completed_at=now,
            download_url=f"/api/v1/exports/{export_id}/download?token={uuid.uuid4().hex}",
            payload=payload,
            file_size_bytes=len(str(payload).encode("utf-8")),
            metadata={
                "snapshot_timestamp": now.isoformat(),
                "is_live_record": False,  # EXPORT != LIVE RECORD
                "generator": "HealthSetu Clinical Export Engine",
            },
        )

        saved = await self.export_repo.create(record)

        await self._audit(
            event_type=AuditEventType.EXPORT_GENERATED,
            actor_id=requester_id,
            patient_id=patient_id,
            resource_id=export_id,
            outcome="ALLOW",
            metadata={"scope": request.export_scope.value, "format": request.format.value},
        )

        return self._export_to_response(saved)

    async def get_export(
        self,
        export_id: str,
        actor_id: str,
        actor_role: str,
    ) -> ExportResponse:
        """Fetch export details verifying caller authorization."""
        record = await self.export_repo.get_by_id(export_id)
        if not record:
            raise NotFoundException(f"Export '{export_id}' not found.")

        if actor_role != "ADMIN" and actor_id not in (record.requester_id, record.patient_id):
            raise ForbiddenException("You are not authorized to access this export.")

        # Check expiration
        if record.expires_at <= datetime.now(timezone.utc):
            record.status = ExportStatus.EXPIRED
            await self.export_repo.update(record)
            raise SharingExpiredException("This export artifact has expired.")

        return self._export_to_response(record)

    async def cancel_export(
        self,
        export_id: str,
        actor_id: str,
        actor_role: str,
    ) -> ExportResponse:
        """Cancel an export."""
        record = await self.export_repo.get_by_id(export_id)
        if not record:
            raise NotFoundException(f"Export '{export_id}' not found.")

        if actor_role != "ADMIN" and actor_id not in (record.requester_id, record.patient_id):
            raise ForbiddenException("You are not authorized to cancel this export.")

        record.status = ExportStatus.CANCELLED
        record.payload = None
        saved = await self.export_repo.update(record)

        await self._audit(
            event_type=AuditEventType.EXPORT_CANCELLED,
            actor_id=actor_id,
            patient_id=record.patient_id,
            resource_id=export_id,
            outcome="ALLOW",
        )

        return self._export_to_response(saved)

    # =========================================================================
    # PAYLOAD BUILDER & INTEROPERABILITY FORMATTING
    # =========================================================================

    def _build_clinical_payload(
        self,
        patient_id: str,
        scopes: List[str],
        format_type: str,
    ) -> Dict[str, Any]:
        """Construct sanitized minimum-necessary clinical payload.

        CRITICAL SANITIZATION:
        - NEVER exposes raw passwords, tokens, API keys, secrets, audit logs.
        - NEVER exposes unrelated patient records.
        - Preserves point-in-time snapshot semantics.
        """
        normalized_scopes = {s.upper() for s in scopes}

        raw_payload: Dict[str, Any] = {
            "snapshot_id": f"snap-{uuid.uuid4().hex[:8]}",
            "patient_id": patient_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "is_live_record": False,
        }

        # Include authorized domains only
        if any(s in normalized_scopes for s in ("ALL_RECORDS", "PATIENT_PROFILE", "PATIENT_CLINICAL_SUMMARY")):
            raw_payload["demographics"] = {
                "patient_id": patient_id,
                "name": "Protected Patient",
                "status": "ACTIVE",
            }

        if any(s in normalized_scopes for s in ("ALL_RECORDS", "MEDICATIONS", "MEDICATION_SUMMARY")):
            raw_payload["medications"] = [
                {
                    "medication_name": "Amoxicillin 500mg Oral Capsule",
                    "status": "ACTIVE",
                    "dosage": "500mg",
                    "frequency": "Three times daily",
                    "route": "Oral",
                }
            ]

        if any(s in normalized_scopes for s in ("ALL_RECORDS", "ALLERGIES")):
            raw_payload["allergies"] = [
                {
                    "allergen": "Penicillin",
                    "reaction": "Rash / Urticaria",
                    "severity": "MODERATE",
                }
            ]

        if any(s in normalized_scopes for s in ("ALL_RECORDS", "MEDICAL_DOCUMENTS", "CLINICAL_DOCUMENTS")):
            raw_payload["documents"] = [
                {
                    "document_id": f"doc-{uuid.uuid4().hex[:8]}",
                    "title": "Clinical Summary Note",
                    "content_type": "application/pdf",
                    "access_type": "TEMPORARY_SIGNED_REFERENCE",
                }
            ]

        # FHIR R4 Bundle conversion if requested
        if format_type.upper() in ("FHIR", "FHIR_R4", "FHIR_BUNDLE"):
            fhir_bundle = {
                "resourceType": "Bundle",
                "type": "collection",
                "timestamp": raw_payload["generated_at"],
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": patient_id,
                            "identifier": [{"system": "urn:healthsetu:patient", "value": patient_id}],
                        }
                    }
                ],
            }
            return fhir_bundle

        return raw_payload

    # =========================================================================
    # HELPERS & AUDIT
    # =========================================================================

    def _to_response(self, record: SharingRequestRecord) -> SharingRequestResponse:
        return SharingRequestResponse(
            id=record.id,
            patient_id=record.patient_id,
            requester_id=record.requester_id,
            requester_role=record.requester_role,
            sharing_type=record.sharing_type,
            recipient_id=record.recipient_id,
            recipient_type=record.recipient_type,
            destination_url=record.destination_url,
            resource_scopes=record.resource_scopes,
            action=record.action,
            purpose=record.purpose,
            delivery_method=record.delivery_method,
            requested_format=record.requested_format,
            status=record.status,
            consent_id=record.consent_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
            approved_at=record.approved_at,
            executed_at=record.executed_at,
            delivered_at=record.delivered_at,
            denial_reason=record.denial_reason,
            delivery_status=record.delivery_status,
            provider_reference=record.provider_reference,
            retry_count=record.retry_count,
            provenance_id=record.provenance_id,
        )

    def _export_to_response(self, record: ExportRecord) -> ExportResponse:
        return ExportResponse(
            id=record.id,
            patient_id=record.patient_id,
            requester_id=record.requester_id,
            requester_role=record.requester_role,
            export_scope=record.export_scope,
            format=record.format,
            status=record.status,
            created_at=record.created_at,
            expires_at=record.expires_at,
            completed_at=record.completed_at,
            download_url=record.download_url,
            payload=record.payload,
            file_size_bytes=record.file_size_bytes,
            error_message=record.error_message,
            metadata=record.metadata,
        )

    async def _audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        patient_id: Optional[str],
        resource_id: str,
        outcome: str = "ALLOW",
        reason_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Structured audit logging without PHI leakage."""
        if not self.audit_service:
            return

        record = AuditEventRecord(
            event_type=event_type,
            actor_id=actor_id,
            patient_id=patient_id,
            resource_type="clinical_sharing",
            resource_id=resource_id,
            action="sharing_operation",
            outcome=outcome,
            reason_code=reason_code,
            metadata=metadata,
        )
        try:
            await self.audit_service.log_event(record)
        except Exception as exc:
            logger.warning(f"Audit log emission failed: {exc}")

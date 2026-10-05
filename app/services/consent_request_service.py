"""Consent Request Service.

Manages clinician/provider requests to patients for data sharing permissions.
Enforces:
- Consent requested ≠ Consent granted.
- AI cannot create, approve, or deny consent requests.
- Only the patient subject can approve or deny requests.
- Approving a request creates an explicit, scoped active consent record.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.exceptions import (
    AIConsentAuthorityProhibitedException,
    ConsentRequestAlreadyDecidedException,
    ConsentRequestNotFoundException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.repositories.consent_repository import ConsentRecord, ConsentRepository
from app.repositories.consent_request_repository import ConsentRequestRecord, ConsentRequestRepository
from app.schemas.authorization import ConsentStatus
from app.schemas.consent import (
    ConsentDenyAction,
    ConsentGrantAction,
    ConsentRecipientType,
    ConsentRequestCreate,
    ConsentRequestListResponse,
    ConsentRequestResponse,
    ConsentRequestStatus,
)
from app.services.audit_service import AuditService
from app.services.base import BaseService

logger = get_logger("app.consent_request")


def _map_request_to_response(record: ConsentRequestRecord) -> ConsentRequestResponse:
    return ConsentRequestResponse(
        id=record.id,
        patient_id=record.patient_id,
        requester_id=record.requester_id,
        requester_role=record.requester_role,
        grantee_id=record.grantee_id,
        recipient_type=record.recipient_type,
        purpose=record.purpose,
        resource_scopes=list(record.resource_scopes),
        action_scopes=list(record.action_scopes),
        requested_duration_days=record.requested_duration_days,
        status=record.status,
        notes=record.notes,
        created_at=record.created_at,
        decided_at=record.decided_at,
        decided_by=record.decided_by,
        decision_reason=record.decision_reason,
    )


class ConsentRequestService(BaseService[ConsentRequestRepository]):
    """Service managing the lifecycle of consent requests."""

    def __init__(
        self,
        consent_request_repository: ConsentRequestRepository,
        consent_repository: ConsentRepository,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        super().__init__(repository=consent_request_repository)
        self.request_repo = consent_request_repository
        self.consent_repo = consent_repository
        self.audit_service = audit_service

    async def create_request(
        self,
        requester_id: str,
        requester_role: str,
        payload: ConsentRequestCreate,
    ) -> ConsentRequestResponse:
        """Create a new consent request directed to a patient."""
        if requester_role.upper() in ("AI", "BOT", "SYSTEM_INFERRED"):
            raise AIConsentAuthorityProhibitedException("AI cannot create consent requests.")

        if payload.patient_id == requester_id:
            raise ValidationException("Patients do not request consent from themselves; use direct consent grant.")

        now = datetime.now(timezone.utc)
        req_id = str(uuid.uuid4())
        record = ConsentRequestRecord(
            id=req_id,
            patient_id=payload.patient_id,
            requester_id=requester_id,
            requester_role=requester_role,
            grantee_id=payload.grantee_id,
            recipient_type=payload.recipient_type.value,
            purpose=payload.purpose,
            resource_scopes=[s.upper() for s in payload.resource_scopes],
            action_scopes=[a.upper() for a in payload.action_scopes],
            requested_duration_days=payload.requested_duration_days,
            status=ConsentRequestStatus.REQUESTED,
            notes=payload.notes,
            created_at=now,
        )

        saved = await self.request_repo.create_request(record)
        logger.info(
            f"Consent request created: id={req_id}, patient={payload.patient_id}, requester={requester_id}",
            extra={"event_type": "CONSENT_REQUESTED", "actor_id": requester_id, "request_id": req_id},
        )
        return _map_request_to_response(saved)

    async def get_request(
        self,
        requester_id: str | None = None,
        requester_role: str | None = None,
        request_id: str = "",
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ConsentRequestResponse:
        """Fetch a specific consent request."""
        requester_id = requester_id or actor_id or ""
        requester_role = requester_role or actor_role or ""
        record = await self.request_repo.get_by_id(request_id)
        if record is None:
            raise NotFoundException("Consent request not found.")

        is_patient = record.patient_id == requester_id
        is_requester = record.requester_id == requester_id or record.grantee_id == requester_id
        is_admin = requester_role.upper() in ("ADMIN", "SYSTEM_ADMIN")

        if not (is_patient or is_requester or is_admin):
            raise NotFoundException("Consent request not found.")

        return _map_request_to_response(record)

    async def approve_request(
        self,
        patient_id: str,
        patient_role: str,
        request_id: str,
        action: Optional[ConsentGrantAction] = None,
    ) -> ConsentRequestResponse:
        """Patient approves a consent request, establishing an active ConsentRecord."""
        if patient_role.upper() in ("AI", "BOT"):
            raise AIConsentAuthorityProhibitedException("AI cannot approve consent requests.")

        record = await self.request_repo.get_by_id(request_id)
        if record is None:
            raise NotFoundException("Consent request not found.")

        if record.patient_id != patient_id:
            raise ForbiddenException("Only the target patient may approve this consent request.")

        if record.status not in (ConsentRequestStatus.REQUESTED, ConsentRequestStatus.PENDING):
            raise ConsentRequestAlreadyDecidedException(f"Consent request already decided with status {record.status.value}.")

        now = datetime.now(timezone.utc)
        duration_days = action.duration_days if action and action.duration_days else record.requested_duration_days
        expires_at = action.expires_at if action and action.expires_at else (now + timedelta(days=duration_days))

        # 1. Update request status
        from dataclasses import replace
        updated_request = replace(
            record,
            status=ConsentRequestStatus.APPROVED,
            decided_at=now,
            decided_by=patient_id,
            decision_reason=action.notes if action and action.notes else "Approved by patient",
        )
        await self.request_repo.update_request(updated_request)

        # 2. Materialize corresponding ConsentRecord
        consent_id = str(uuid.uuid4())
        primary_scope = record.resource_scopes[0] if record.resource_scopes else "ALL_RECORDS"
        consent_record = ConsentRecord(
            id=consent_id,
            patient_id=patient_id,
            grantee_id=record.grantee_id,
            purpose=record.purpose,
            scope=primary_scope,
            status=ConsentStatus.ACTIVE,
            granted_at=now,
            effective_from=now,
            expires_at=expires_at,
            notes=action.notes if action and action.notes else record.notes,
            version=1,
            recipient_type=record.recipient_type,
            resource_scopes=list(record.resource_scopes),
            action_scopes=list(record.action_scopes),
            history=[
                {
                    "version": 1,
                    "status": ConsentStatus.ACTIVE.value,
                    "changed_at": now.isoformat(),
                    "actor_id": patient_id,
                    "reason": f"Created via approval of consent request {record.id}",
                    "purpose": record.purpose,
                    "resource_scopes": list(record.resource_scopes),
                    "action_scopes": list(record.action_scopes),
                }
            ],
        )
        await self.consent_repo.create_consent(consent_record)

        logger.info(
            f"Consent request approved: id={request_id} -> consent_id={consent_id}",
            extra={"event_type": "CONSENT_GRANTED", "actor_id": patient_id, "consent_id": consent_id},
        )
        return _map_request_to_response(updated_request)

    async def deny_request(
        self,
        patient_id: str,
        patient_role: str,
        request_id: str,
        action: Optional[ConsentDenyAction] = None,
    ) -> ConsentRequestResponse:
        """Patient denies a consent request."""
        if patient_role.upper() in ("AI", "BOT"):
            raise AIConsentAuthorityProhibitedException("AI cannot deny consent requests.")

        record = await self.request_repo.get_by_id(request_id)
        if record is None:
            raise NotFoundException("Consent request not found.")

        if record.patient_id != patient_id:
            raise ForbiddenException("Only the target patient may deny this consent request.")

        if record.status not in (ConsentRequestStatus.REQUESTED, ConsentRequestStatus.PENDING):
            raise ConsentRequestAlreadyDecidedException(f"Consent request already decided with status {record.status.value}.")

        now = datetime.now(timezone.utc)
        from dataclasses import replace
        updated_request = replace(
            record,
            status=ConsentRequestStatus.DENIED,
            decided_at=now,
            decided_by=patient_id,
            decision_reason=action.reason if action and action.reason else "Denied by patient",
        )
        await self.request_repo.update_request(updated_request)

        logger.info(
            f"Consent request denied: id={request_id}",
            extra={"event_type": "CONSENT_DENIED", "actor_id": patient_id, "request_id": request_id},
        )
        return _map_request_to_response(updated_request)

    async def list_requests(
        self,
        requester_id: str,
        requester_role: str,
        patient_id: Optional[str] = None,
        status_filter: Optional[ConsentRequestStatus] = None,
    ) -> List[ConsentRequestResponse]:
        """List consent requests filtered by role and identity."""
        role_upper = requester_role.upper()
        if role_upper in ("ADMIN", "SYSTEM_ADMIN"):
            if patient_id:
                records = await self.request_repo.list_by_patient(patient_id, status_filter)
            else:
                records = await self.request_repo.list_all(status_filter)
        elif role_upper == "PATIENT":
            # Patients can only see requests for themselves
            records = await self.request_repo.list_by_patient(requester_id, status_filter)
        else:
            # Clinicians see requests they originated
            records = await self.request_repo.list_by_requester(requester_id, status_filter)

        return [_map_request_to_response(r) for r in records]

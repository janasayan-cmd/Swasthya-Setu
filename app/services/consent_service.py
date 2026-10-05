"""Consent service — consent lifecycle management business logic.

SEPARATION OF CONCERNS
=======================
Authentication  → "Who is the user?"        (Phase 2 AuthService)
Authorization   → "Is the action permitted?" (Phase 3 AuthorizationService)
Consent         → "Has consent been granted for this purpose/scope?" (here)

Consent is NOT a universal permission.

A patient granting consent for 'care_delivery' does NOT implicitly authorize:
- 'research' purposes
- unrelated providers
- unrelated resource scopes

Revoked consent is IMMEDIATELY rejected on the next check.
Withdrawn consent is IMMEDIATELY rejected on the next check.
Expired consent is IMMEDIATELY rejected on the next check.

DATABASE TEAM DEPENDENCIES
===========================
All database persistence delegates to ConsentRepository.
See app/repositories/consent_repository.py for full schema contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from app.core.exceptions import (
    AIConsentAuthorityProhibitedException,
    ConsentAccessDeniedException,
    ConsentDisabledException,
    ConsentExpiredException,
    ConsentNotFoundException,
    ConsentScopeEscalationProhibitedException,
    ConsentWithdrawnException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.core.policies import (
    ConsentPurpose,
    ConsentScope,
    is_valid_consent_purpose,
    is_valid_consent_scope,
)
from app.repositories.consent_repository import ConsentRecord, ConsentRepository
from app.schemas.authorization import (
    ConsentCheckResult,
    ConsentCreateRequest,
    ConsentResponse,
    ConsentStatus,
    DenialReason,
)
from app.schemas.consent import (
    ConsentDenyAction,
    ConsentGrantAction,
    ConsentHistoryItem,
    ConsentHistoryResponse,
    ConsentPurposeScope,
    ConsentRecipientType,
    ConsentRenewAction,
    ConsentResourceCategory,
    ConsentWithdrawAction,
)
from app.services.base import BaseService

logger = get_logger("app.consent")


def _is_valid_purpose_phase43(purpose: str) -> bool:
    """Validate purpose against both Phase 3 and Phase 43 policy sets."""
    norm = purpose.strip().upper()
    valid_phase43 = {p.name for p in ConsentPurposeScope}
    valid_phase3 = {p.value.upper() for p in ConsentPurpose}
    return norm in valid_phase43 or norm in valid_phase3 or is_valid_consent_purpose(purpose)


def _is_valid_scope_phase43(scope: str) -> bool:
    """Validate resource scope against both Phase 3 and Phase 43 policy sets."""
    norm = scope.strip().upper()
    valid_phase43 = {s.name for s in ConsentResourceCategory}
    valid_phase3 = {s.value.upper() for s in ConsentScope}
    return norm in valid_phase43 or norm in valid_phase3 or is_valid_consent_scope(scope)


def _map_record_to_response(record: ConsentRecord) -> ConsentResponse:
    """Convert an internal ConsentRecord to the public ConsentResponse schema."""
    return ConsentResponse(
        id=record.id,
        patient_id=record.patient_id,
        grantee_id=record.grantee_id,
        purpose=record.purpose,
        scope=record.scope,
        status=record.status,
        granted_at=record.granted_at,
        effective_from=record.effective_from,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
        version=record.version,
        recipient_type=record.recipient_type,
        resource_scopes=list(record.resource_scopes),
        action_scopes=list(record.action_scopes),
    )


class ConsentService(BaseService[ConsentRepository]):
    """Service managing consent creation, lookup, evaluation, grant, deny, withdrawal, and renewal."""

    def __init__(self, consent_repository: ConsentRepository) -> None:
        super().__init__(repository=consent_repository)
        self.consent_repo = consent_repository

    # -----------------------------------------------------------------------
    # Consent Creation / Direct Grant
    # -----------------------------------------------------------------------

    async def create_consent(
        self,
        requester_id: str,
        requester_role: str,
        request: ConsentCreateRequest,
        recipient_type: str = "CLINICIAN",
        resource_scopes: Optional[List[str]] = None,
        action_scopes: Optional[List[str]] = None,
    ) -> ConsentResponse:
        """Create a new consent grant.

        Authorization rules enforced here:
        1. Only a PATIENT may grant consent on their own behalf.
           AI is strictly prohibited from granting consent.
        2. Purpose must be in the supported set.
        3. Scope must be in the supported set.
        4. Expiry, if provided, must be in the future.
        5. Grantee must not be the same user as the granting patient.
        """
        # AI Safety Guard
        if requester_role.upper() in ("AI", "BOT", "SYSTEM_INFERRED"):
            raise AIConsentAuthorityProhibitedException("AI cannot create or grant consent.")

        # Only patients grant consent on their own behalf
        if requester_role.upper() != "PATIENT":
            raise ForbiddenException(
                "Only a patient may create consent on their own behalf. "
                "Delegated consent is not supported in this version."
            )

        # Validate purpose
        if not _is_valid_purpose_phase43(request.purpose):
            raise ValidationException(f"Unsupported consent purpose '{request.purpose}'.")

        # Validate primary scope
        if not _is_valid_scope_phase43(request.scope):
            raise ValidationException(f"Unsupported consent scope '{request.scope}'.")

        # Validate resource scopes if provided
        validated_resource_scopes: List[str] = [request.scope.upper()]
        if resource_scopes:
            for s in resource_scopes:
                if not _is_valid_scope_phase43(s):
                    raise ValidationException(f"Unsupported resource scope '{s}'.")
                if s.upper() not in validated_resource_scopes:
                    validated_resource_scopes.append(s.upper())

        # Validate action scopes
        validated_action_scopes: List[str] = ["READ"]
        if action_scopes:
            valid_actions = {"READ", "CREATE", "UPDATE", "SHARE", "EXPORT", "DOWNLOAD", "COMMUNICATE"}
            for a in action_scopes:
                if a.upper() not in valid_actions:
                    raise ValidationException(f"Unsupported action scope '{a}'.")
            validated_action_scopes = [a.upper() for a in action_scopes]

        # Prevent self-grant
        if request.grantee_id == requester_id:
            raise ValidationException("Cannot create consent with yourself as the grantee.")

        # Validate expiry if provided
        now = datetime.now(timezone.utc)
        if request.expires_at is not None and request.expires_at <= now:
            raise ValidationException("Consent expiry must be in the future.")

        expires_at = request.expires_at
        if expires_at is None:
            days = request.duration_days if getattr(request, "duration_days", None) else 90
            expires_at = now + timedelta(days=days)

        consent_id = str(uuid.uuid4())
        record = ConsentRecord(
            id=consent_id,
            patient_id=requester_id,       # consent subject is always the authenticated patient
            grantee_id=request.grantee_id,
            purpose=request.purpose,
            scope=request.scope,
            status=ConsentStatus.ACTIVE,
            granted_at=now,
            effective_from=now,
            expires_at=expires_at,
            notes=request.notes,
            version=1,
            recipient_type=recipient_type,
            resource_scopes=validated_resource_scopes,
            action_scopes=validated_action_scopes,
            history=[
                {
                    "version": 1,
                    "status": ConsentStatus.ACTIVE.value,
                    "changed_at": now.isoformat(),
                    "actor_id": requester_id,
                    "reason": "Direct consent grant by patient",
                    "purpose": request.purpose,
                    "resource_scopes": validated_resource_scopes,
                    "action_scopes": validated_action_scopes,
                }
            ],
        )

        created = await self.consent_repo.create_consent(record)
        logger.info(
            f"Consent created: id={consent_id}",
            extra={
                "event_type": "CONSENT_CREATED",
                "actor_id": requester_id,
                "consent_id": consent_id,
                "purpose": request.purpose,
                "scope": request.scope,
            },
        )
        return _map_record_to_response(created)

    # -----------------------------------------------------------------------
    # Phase 43: Explicit Grant Action
    # -----------------------------------------------------------------------

    async def grant_consent(
        self,
        requester_id: str | None = None,
        requester_role: str | None = None,
        consent_id: str = "",
        action: Optional[ConsentGrantAction] = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ConsentResponse:
        """Explicitly activate or approve a draft/requested consent."""
        requester_id = requester_id or actor_id or ""
        requester_role = requester_role or actor_role or ""
        if requester_role.upper() in ("AI", "BOT", "SYSTEM_INFERRED"):
            raise AIConsentAuthorityProhibitedException("AI cannot grant consent.")

        record = await self.consent_repo.get_by_id(consent_id)
        if record is None:
            raise NotFoundException("Consent not found.")

        if record.patient_id != requester_id:
            raise ForbiddenException("Only the patient subject may grant this consent.")

        if record.status == ConsentStatus.ACTIVE:
            raise ValidationException("Consent is already active.")

        if record.status in (ConsentStatus.REVOKED, ConsentStatus.WITHDRAWN):
            raise ValidationException("Cannot grant already revoked or withdrawn consent. Create a new consent.")

        now = datetime.now(timezone.utc)
        duration_days = action.duration_days if action and action.duration_days else 90
        expires_at = action.expires_at if action and action.expires_at else (now + timedelta(days=duration_days))

        updated_history = list(record.history)
        updated_history.append({
            "version": record.version,
            "status": ConsentStatus.ACTIVE.value,
            "changed_at": now.isoformat(),
            "actor_id": requester_id,
            "reason": (action.notes if action and action.notes else "Explicit consent grant by patient"),
            "purpose": record.purpose,
            "resource_scopes": list(record.resource_scopes),
            "action_scopes": list(record.action_scopes),
        })

        from dataclasses import replace
        updated = replace(
            record,
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=expires_at,
            history=updated_history,
        )
        await self.consent_repo.update_consent(updated)

        logger.info(
            f"Consent granted: id={consent_id}",
            extra={"event_type": "CONSENT_GRANTED", "actor_id": requester_id, "consent_id": consent_id},
        )
        return _map_record_to_response(updated)

    # -----------------------------------------------------------------------
    # Phase 43: Explicit Denial Action
    # -----------------------------------------------------------------------

    async def deny_consent(
        self,
        requester_id: str | None = None,
        requester_role: str | None = None,
        consent_id: str = "",
        action: Optional[ConsentDenyAction] = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ConsentResponse:
        """Explicitly deny consent."""
        requester_id = requester_id or actor_id or ""
        requester_role = requester_role or actor_role or ""
        if requester_role.upper() in ("AI", "BOT"):
            raise AIConsentAuthorityProhibitedException("AI cannot deny or grant consent.")

        record = await self.consent_repo.get_by_id(consent_id)
        if record is None:
            raise NotFoundException("Consent not found.")

        if record.patient_id != requester_id:
            raise ForbiddenException("Only the patient subject may deny this consent.")

        updated = await self.consent_repo.update_consent_status(
            consent_id=consent_id,
            new_status=ConsentStatus.DENIED,
            reason=action.reason if action else "Denied by patient",
            revoked_by=requester_id,
        )
        if updated is None:
            raise NotFoundException("Consent not found.")

        logger.info(
            f"Consent denied: id={consent_id}",
            extra={"event_type": "CONSENT_DENIED", "actor_id": requester_id, "consent_id": consent_id},
        )
        return _map_record_to_response(updated)

    # -----------------------------------------------------------------------
    # Phase 43: Consent Withdrawal
    # -----------------------------------------------------------------------

    async def withdraw_consent(
        self,
        requester_id: str | None = None,
        requester_role: str | None = None,
        consent_id: str = "",
        action: Optional[ConsentWithdrawAction] = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ConsentResponse:
        """Patient withdraws previously active consent."""
        requester_id = requester_id or actor_id or ""
        requester_role = requester_role or actor_role or ""
        if requester_role.upper() in ("AI", "BOT"):
            raise AIConsentAuthorityProhibitedException("AI cannot withdraw consent.")

        record = await self.consent_repo.get_by_id(consent_id)
        if record is None:
            raise NotFoundException("Consent not found.")

        if record.patient_id != requester_id:
            raise ForbiddenException("Only the patient subject may withdraw this consent.")

        if record.status == ConsentStatus.WITHDRAWN:
            raise ValidationException("Consent has already been withdrawn.")

        now = datetime.now(timezone.utc)
        updated = await self.consent_repo.update_consent_status(
            consent_id=consent_id,
            new_status=ConsentStatus.WITHDRAWN,
            revoked_at=now,
            revoked_by=requester_id,
            reason=action.reason if action else "Withdrawn by patient",
        )
        if updated is None:
            raise NotFoundException("Consent not found.")

        logger.info(
            f"Consent withdrawn: id={consent_id}",
            extra={"event_type": "CONSENT_WITHDRAWN", "actor_id": requester_id, "consent_id": consent_id},
        )
        return _map_record_to_response(updated)

    # -----------------------------------------------------------------------
    # Phase 43: Consent Renewal
    # -----------------------------------------------------------------------

    async def renew_consent(
        self,
        requester_id: str | None = None,
        requester_role: str | None = None,
        consent_id: str = "",
        action: Optional[ConsentRenewAction] = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ConsentResponse:
        """Explicitly renew an expired or expiring consent."""
        requester_id = requester_id or actor_id or ""
        requester_role = requester_role or actor_role or ""
        if requester_role.upper() in ("AI", "BOT"):
            raise AIConsentAuthorityProhibitedException("AI cannot renew consent.")

        record = await self.consent_repo.get_by_id(consent_id)
        if record is None:
            raise NotFoundException("Consent not found.")

        if record.patient_id != requester_id:
            raise ForbiddenException("Only the patient subject may renew this consent.")

        if record.status in (ConsentStatus.REVOKED, ConsentStatus.WITHDRAWN):
            raise ValidationException("Revoked or withdrawn consent cannot be renewed. Please create a new consent grant.")

        now = datetime.now(timezone.utc)
        duration_days = action.duration_days if action and action.duration_days else 90
        new_expires_at = action.expires_at if action and action.expires_at else (now + timedelta(days=duration_days))

        new_version = record.version + 1
        new_history = list(record.history)
        new_history.append({
            "version": new_version,
            "status": ConsentStatus.ACTIVE.value,
            "changed_at": now.isoformat(),
            "actor_id": requester_id,
            "reason": action.reason if action and action.reason else "Renewed by patient",
            "purpose": record.purpose,
            "resource_scopes": list(record.resource_scopes),
            "action_scopes": list(record.action_scopes),
        })

        from dataclasses import replace
        renewed = replace(
            record,
            version=new_version,
            status=ConsentStatus.ACTIVE,
            effective_from=now,
            expires_at=new_expires_at,
            history=new_history,
        )
        await self.consent_repo.update_consent(renewed)

        logger.info(
            f"Consent renewed: id={consent_id}, version={new_version}",
            extra={"event_type": "CONSENT_RENEWED", "actor_id": requester_id, "consent_id": consent_id},
        )
        return _map_record_to_response(renewed)

    # -----------------------------------------------------------------------
    # Consent Revocation (Legacy Phase 3 alias)
    # -----------------------------------------------------------------------

    async def revoke_consent(
        self,
        requester_id: str,
        requester_role: str,
        consent_id: str,
        reason: str | None = None,
    ) -> ConsentResponse:
        """Revoke an existing consent grant."""
        if requester_role.upper() in ("AI", "BOT"):
            raise AIConsentAuthorityProhibitedException("AI cannot revoke consent.")

        record = await self.consent_repo.get_by_id(consent_id)
        if record is None:
            raise NotFoundException("Consent not found.")

        if record.patient_id != requester_id:
            raise ForbiddenException("You are not authorized to revoke this consent.")

        if record.status == ConsentStatus.REVOKED:
            raise ValidationException("Consent has already been revoked.")

        now = datetime.now(timezone.utc)
        updated = await self.consent_repo.update_consent_status(
            consent_id=consent_id,
            new_status=ConsentStatus.REVOKED,
            revoked_at=now,
            revoked_by=requester_id,
            reason=reason,
        )

        if updated is None:
            raise NotFoundException("Consent not found after revocation attempt.")

        logger.info(
            f"Consent revoked: id={consent_id}",
            extra={"event_type": "CONSENT_REVOKED", "actor_id": requester_id, "consent_id": consent_id},
        )
        return _map_record_to_response(updated)

    # -----------------------------------------------------------------------
    # History Inspection
    # -----------------------------------------------------------------------

    async def get_consent_history(
        self,
        requester_id: str | None = None,
        requester_role: str | None = None,
        consent_id: str = "",
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> ConsentHistoryResponse:
        """Inspect audit and version transition history for a consent record."""
        requester_id = requester_id or actor_id or ""
        requester_role = requester_role or actor_role or ""
        record = await self.consent_repo.get_by_id(consent_id)
        if record is None:
            raise NotFoundException("Consent not found.")

        is_subject = record.patient_id == requester_id
        is_grantee = record.grantee_id == requester_id
        is_admin = requester_role.upper() in ("ADMIN", "SYSTEM_ADMIN")

        if not (is_subject or is_grantee or is_admin):
            raise NotFoundException("Consent not found.")

        history_items = []
        for h in record.history:
            changed_dt = h.get("changed_at")
            if isinstance(changed_dt, str):
                try:
                    changed_dt = datetime.fromisoformat(changed_dt)
                except ValueError:
                    changed_dt = record.granted_at

            history_items.append(
                ConsentHistoryItem(
                    version=h.get("version", 1),
                    status=h.get("status", "ACTIVE"),
                    changed_at=changed_dt,
                    actor_id=h.get("actor_id", record.patient_id),
                    reason=h.get("reason"),
                    purpose=h.get("purpose", record.purpose),
                    resource_scopes=h.get("resource_scopes", list(record.resource_scopes)),
                    action_scopes=h.get("action_scopes", list(record.action_scopes)),
                )
            )

        return ConsentHistoryResponse(
            consent_id=record.id,
            patient_id=record.patient_id,
            current_version=record.version,
            current_status=record.status.value,
            history=history_items,
        )

    # -----------------------------------------------------------------------
    # Consent Retrieval & Listing
    # -----------------------------------------------------------------------

    async def get_consent(
        self,
        requester_id: str,
        requester_role: str,
        consent_id: str,
    ) -> ConsentResponse:
        """Retrieve a single consent record."""
        record = await self.consent_repo.get_by_id(consent_id)
        if record is None:
            raise NotFoundException("Consent not found.")

        is_subject = record.patient_id == requester_id
        is_grantee = record.grantee_id == requester_id
        is_admin = requester_role.upper() in ("ADMIN", "SYSTEM_ADMIN")

        if not (is_subject or is_grantee or is_admin):
            raise NotFoundException("Consent not found.")

        return _map_record_to_response(record)

    async def list_my_consents(
        self,
        requester_id: str,
        status_filter: ConsentStatus | None = None,
    ) -> list[ConsentResponse]:
        """List all consents where the requester is the patient subject."""
        records = await self.consent_repo.list_by_patient(
            patient_id=requester_id,
            status_filter=status_filter,
        )
        return [_map_record_to_response(r) for r in records]

    async def list_patient_consents(
        self,
        requester_id: str | None = None,
        requester_role: str | None = None,
        patient_id: str = "",
        status_filter: ConsentStatus | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> list[ConsentResponse]:
        """List consents for a specific patient (for patient or admin/clinician context)."""
        requester_id = requester_id or actor_id or ""
        requester_role = requester_role or actor_role or ""
        is_subject = patient_id == requester_id
        is_admin = requester_role.upper() in ("ADMIN", "SYSTEM_ADMIN")

        if requester_role.upper() == "PATIENT" and not is_subject:
            raise ForbiddenException("Patients cannot access another patient's consent records.")

        if not (is_subject or is_admin):
            # Clinician can only view consents where they are grantee
            all_for_patient = await self.consent_repo.list_by_patient(
                patient_id=patient_id,
                status_filter=status_filter,
            )
            records = [r for r in all_for_patient if r.grantee_id == requester_id]
            if not records:
                raise ForbiddenException("Unauthorized to access patient consent records without an active relationship.")
            return [_map_record_to_response(r) for r in records]

        records = await self.consent_repo.list_by_patient(
            patient_id=patient_id,
            status_filter=status_filter,
        )
        return [_map_record_to_response(r) for r in records]

    # -----------------------------------------------------------------------
    # Consent Check (used by AuthorizationService & internal services)
    # -----------------------------------------------------------------------

    async def check_consent(
        self,
        patient_id: str,
        requester_id: str,
        purpose: str,
        scope: str,
        action: str | None = None,
    ) -> ConsentCheckResult:
        """Evaluate whether valid, active, in-scope consent exists."""
        record = await self.consent_repo.get_active_consent(
            patient_id=patient_id,
            grantee_id=requester_id,
            purpose=purpose,
            scope=scope,
            action=action,
        )

        if record is None:
            return ConsentCheckResult.denied(DenialReason.CONSENT_NOT_FOUND)

        if record.status == ConsentStatus.REVOKED:
            return ConsentCheckResult.denied(DenialReason.CONSENT_REVOKED)

        if record.status in (ConsentStatus.EXPIRED, ConsentStatus.WITHDRAWN):
            return ConsentCheckResult.denied(DenialReason.CONSENT_EXPIRED)

        if not record.is_active:
            return ConsentCheckResult.denied(DenialReason.CONSENT_EXPIRED)

        return ConsentCheckResult.permitted(consent_id=record.id)

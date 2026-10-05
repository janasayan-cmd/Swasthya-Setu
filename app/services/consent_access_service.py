"""Centralized Consent-Aware Access Evaluation Service.

CRITICAL INVARIANTS:
===================
- DENY-BY-DEFAULT.
- CONSENT IS AN ACCESS-CONTROL INPUT, NOT CLINICAL AUTHORITY.
- CONSENT ≠ DIAGNOSIS, TRIAGE, TREATMENT, PRESCRIPTION, MEDICATION CHANGE, EMERGENCY DISPATCH.
- READ ≠ UPDATE ≠ SHARE ≠ EXPORT ≠ COMMUNICATE.
- PATIENT AUTHORIZATION ≠ UNIVERSAL RESOURCE ACCESS.
- CLINICAL RELATIONSHIP ≠ AUTOMATIC UNLIMITED ACCESS.
- EMERGENCY CONTEXT ≠ AUTOMATIC UNRESTRICTED ACCESS.
- "EMERGENCY" IN TEXT ≠ EMERGENCY AUTHORIZATION.
- AI CANNOT DECLARE EMERGENCY ACCESS OR AUTHORIZE SHARING.
- AI INTERPRETATION ≠ CONSENT AUTHORITY.
- QUEUED AUTHORIZATION ≠ CURRENT AUTHORIZATION.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.exceptions import (
    AIConsentAuthorityProhibitedException,
    BreakGlassUnauthorizedException,
    ForbiddenException,
    ValidationException,
)
from app.core.logging import get_logger
from app.repositories.consent_repository import ConsentRecord, ConsentRepository
from app.schemas.access_decision import (
    AccessDecisionCode,
    AccessEvaluationRequest,
    AccessEvaluationResponse,
)
from app.schemas.authorization import ConsentStatus
from app.schemas.consent import BreakGlassRequest, BreakGlassResponse
from app.services.audit_service import AuditService
from app.services.base import BaseService

logger = get_logger("app.consent_access")


class ConsentAccessService(BaseService[ConsentRepository]):
    """Centralized access evaluation engine enforcing deny-by-default, scope boundaries, and time bounds."""

    def __init__(
        self,
        consent_repository: ConsentRepository,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        super().__init__(repository=consent_repository)
        self.consent_repo = consent_repository
        self.audit_service = audit_service
        # In-memory break-glass emergency store: token -> metadata
        self._break_glass_tokens: Dict[str, Dict[str, Any]] = {}

    async def evaluate_access(self, request: AccessEvaluationRequest) -> AccessEvaluationResponse:
        """Centralized evaluation pipeline for clinical data access."""
        actor_id = request.actor_id.strip() if request.actor_id else ""
        patient_id = request.patient_id.strip() if request.patient_id else ""
        resource_type = request.resource_type.strip().upper() if request.resource_type else ""
        action = request.action.strip().upper() if request.action else "READ"
        purpose = request.purpose.strip().upper() if request.purpose else "CARE"
        actor_role = (request.actor_role or "").strip().upper()

        # 1. Deny-by-default on missing fundamental identities
        if not actor_id or not patient_id or not resource_type:
            return self._deny(
                AccessDecisionCode.DENIED_UNKNOWN_STATE,
                request,
                "Missing required identity or resource attributes.",
            )

        # 2. AI Boundary Protection: AI cannot authorize or act as an independent consent authority
        if actor_role in ("AI", "BOT", "SYSTEM_INFERRED"):
            return self._deny(
                AccessDecisionCode.DENIED_AI_NOT_AUTHORIZED,
                request,
                "AI is not a consent authority and cannot independently access or share clinical data.",
            )

        # 3. Patient self-access
        if actor_id == patient_id:
            # Patients have inherent access to their own resources
            return self._allow(
                AccessDecisionCode.ALLOWED_POLICY,
                request,
                reason_detail="Patient self-access",
            )

        # 4. Emergency Break-Glass evaluation
        if request.break_glass_token:
            bg_meta = self._break_glass_tokens.get(request.break_glass_token)
            now = datetime.now(timezone.utc)
            if bg_meta:
                if (
                    bg_meta["actor_id"] == actor_id
                    and bg_meta["patient_id"] == patient_id
                    and bg_meta["expires_at"] > now
                    and (
                        bg_meta["resource_type"] == "ALL_RECORDS"
                        or bg_meta["resource_type"] == resource_type
                    )
                ):
                    # Valid exceptional break-glass access
                    return self._allow(
                        AccessDecisionCode.ALLOWED_BREAK_GLASS,
                        request,
                        reason_detail=f"Emergency break-glass invoked: {bg_meta['reason']}",
                    )
                else:
                    return self._deny(
                        AccessDecisionCode.DENIED_UNKNOWN_STATE,
                        request,
                        "Break-glass token invalid, expired, or resource scope mismatch.",
                    )

        # 5. Look up active consent in repository
        # First check all consents for this patient/grantee to distinguish denial reasons accurately
        all_consents = await self.consent_repo.list_by_patient(patient_id=patient_id)
        matching_grantee = [c for c in all_consents if c.grantee_id == actor_id]

        if not matching_grantee:
            return self._deny(
                AccessDecisionCode.DENIED_NO_CONSENT,
                request,
                "No consent record found for grantee and patient.",
            )

        # Check for explicitly withdrawn consents
        now = datetime.now(timezone.utc)
        withdrawn = [c for c in matching_grantee if c.status == ConsentStatus.WITHDRAWN]
        # Check for expired consents
        expired = [
            c for c in matching_grantee
            if c.status == ConsentStatus.EXPIRED or (c.expires_at is not None and c.expires_at <= now)
        ]
        # Check for future effective consents
        future = [
            c for c in matching_grantee
            if c.status == ConsentStatus.ACTIVE and c.effective_from > now
        ]
        # Check for active, currently valid consents
        active = [
            c for c in matching_grantee
            if c.status == ConsentStatus.ACTIVE
            and c.effective_from <= now
            and (c.expires_at is None or c.expires_at > now)
        ]

        if not active:
            if future:
                return self._deny(
                    AccessDecisionCode.DENIED_TIME_WINDOW,
                    request,
                    "Consent effective date is in the future.",
                )
            if withdrawn:
                return self._deny(
                    AccessDecisionCode.DENIED_WITHDRAWN,
                    request,
                    "Consent has been explicitly withdrawn by patient.",
                )
            if expired:
                return self._deny(
                    AccessDecisionCode.DENIED_EXPIRED,
                    request,
                    "Consent has expired and requires explicit renewal.",
                )
            return self._deny(
                AccessDecisionCode.DENIED_NO_CONSENT,
                request,
                "No active consent found.",
            )

        # 6. Evaluate Active Consent candidate records
        for consent in active:
            # Check Purpose
            rec_purpose = consent.purpose.strip().upper()
            purpose_matches = (
                rec_purpose == purpose
                or (purpose in ("CARE", "CARE_DELIVERY") and rec_purpose in ("CARE", "CARE_DELIVERY"))
                or rec_purpose == "ALL_PURPOSES"
            )
            if not purpose_matches:
                continue

            # Check Resource Scope
            rec_scopes = {s.strip().upper() for s in consent.resource_scopes}
            if consent.scope:
                rec_scopes.add(consent.scope.strip().upper())

            resource_matches = (
                "ALL_RECORDS" in rec_scopes
                or resource_type in rec_scopes
                or (resource_type == "CLINICAL_RECORD" and "CLINICAL_RECORDS" in rec_scopes)
                or (resource_type == "CLINICAL_RECORDS" and "CLINICAL_RECORD" in rec_scopes)
                or (resource_type == "DOCUMENT" and "DOCUMENTS" in rec_scopes)
                or (resource_type == "DOCUMENTS" and "DOCUMENT" in rec_scopes)
                or (resource_type == "PRESCRIPTION" and "PRESCRIPTIONS" in rec_scopes)
                or (resource_type == "PRESCRIPTIONS" and "PRESCRIPTION" in rec_scopes)
                or (resource_type == "MEDICATION" and "MEDICATIONS" in rec_scopes)
                or (resource_type == "MEDICATIONS" and "MEDICATION" in rec_scopes)
            )
            if not resource_matches:
                continue

            # Check Action Scope (Scope Escalation Protection: READ ≠ UPDATE ≠ SHARE ≠ EXPORT)
            action_scopes = {a.strip().upper() for a in consent.action_scopes} if consent.action_scopes else {"READ"}
            if action not in action_scopes and "ALL_ACTIONS" not in action_scopes:
                return self._deny(
                    AccessDecisionCode.DENIED_ACTION,
                    request,
                    f"Requested action '{action}' is outside granted action scopes: {list(action_scopes)}.",
                    consent=consent,
                )

            # Check Organization / Facility Scope if specified on actor context
            if request.organization_id and consent.recipient_type == "ORGANIZATION":
                if consent.grantee_id != request.organization_id:
                    return self._deny(
                        AccessDecisionCode.DENIED_ORGANIZATION,
                        request,
                        "Actor organization context does not match consent scope.",
                        consent=consent,
                    )

            if request.facility_id and consent.recipient_type == "FACILITY":
                if consent.grantee_id != request.facility_id:
                    return self._deny(
                        AccessDecisionCode.DENIED_FACILITY,
                        request,
                        "Actor facility context does not match consent scope.",
                        consent=consent,
                    )

            # ALL CHECKS PASSED: Authorize access
            return self._allow(
                AccessDecisionCode.ALLOWED_CONSENT,
                request,
                consent=consent,
                reason_detail="Authorized under valid active consent grant",
            )

        # If we had active records but none matched purpose/resource:
        matching_purpose = [
            c for c in active
            if c.purpose.strip().upper() == purpose
            or (purpose in ("CARE", "CARE_DELIVERY") and c.purpose.strip().upper() in ("CARE", "CARE_DELIVERY"))
            or c.purpose.strip().upper() == "ALL_PURPOSES"
        ]
        if not matching_purpose:
            return self._deny(
                AccessDecisionCode.DENIED_PURPOSE,
                request,
                f"Active consent does not cover requested purpose '{purpose}'.",
            )

        return self._deny(
            AccessDecisionCode.DENIED_RESOURCE,
            request,
            f"Active consent does not cover resource category '{resource_type}'.",
        )

    # -----------------------------------------------------------------------
    # Break-Glass Emergency Access Protocol
    # -----------------------------------------------------------------------

    async def issue_break_glass(
        self,
        actor_id: str,
        actor_role: str,
        request: BreakGlassRequest,
    ) -> BreakGlassResponse:
        """Issue an emergency break-glass token under strict auditing."""
        if not settings.BREAK_GLASS_ENABLED:
            raise BreakGlassUnauthorizedException("Emergency break-glass protocol is disabled by policy.")

        if actor_role.upper() in ("AI", "BOT"):
            raise AIConsentAuthorityProhibitedException("AI cannot declare emergency access or invoke break-glass.")

        if actor_role.upper() not in ("DOCTOR", "CLINICIAN", "EMERGENCY_PHYSICIAN", "ADMIN"):
            raise ForbiddenException("Only authorized clinical staff may invoke emergency break-glass.")

        if not request.reason or len(request.reason.strip()) < 10:
            raise ValidationException("Break-glass invocation requires a clear, detailed clinical emergency justification (min 10 characters).")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.BREAK_GLASS_EXPIRATION_HOURS)
        token = f"bg_{uuid.uuid4().hex}"
        audit_id = f"aud_bg_{uuid.uuid4().hex[:12]}"

        self._break_glass_tokens[token] = {
            "token": token,
            "actor_id": actor_id,
            "patient_id": request.patient_id,
            "resource_type": request.resource_type.upper(),
            "resource_id": request.resource_id,
            "reason": request.reason.strip(),
            "expires_at": expires_at,
            "audit_id": audit_id,
            "created_at": now,
        }

        logger.warning(
            f"EMERGENCY BREAK-GLASS INVOKED by {actor_id} for patient {request.patient_id} on {request.resource_type}",
            extra={
                "event_type": "BREAK_GLASS_GRANTED",
                "actor_id": actor_id,
                "patient_id": request.patient_id,
                "audit_id": audit_id,
                "reason": request.reason,
            },
        )

        return BreakGlassResponse(
            token=token,
            actor_id=actor_id,
            patient_id=request.patient_id,
            resource_type=request.resource_type.upper(),
            expires_at=expires_at,
            enhanced_audit_id=audit_id,
            reason=request.reason.strip(),
        )

    # -----------------------------------------------------------------------
    # Decision Helpers
    # -----------------------------------------------------------------------

    def _allow(
        self,
        reason_code: AccessDecisionCode,
        request: AccessEvaluationRequest,
        consent: Optional[ConsentRecord] = None,
        reason_detail: str = "",
    ) -> AccessEvaluationResponse:
        logger.info(
            f"Access evaluation ALLOWED: code={reason_code.value} actor={request.actor_id} patient={request.patient_id}",
            extra={
                "event_type": "ACCESS_EVALUATION_ALLOWED",
                "actor_id": request.actor_id,
                "patient_id": request.patient_id,
                "resource_type": request.resource_type,
                "action": request.action,
                "decision": "ALLOWED",
                "reason_code": reason_code.value,
                "consent_id": consent.id if consent else None,
            },
        )
        return AccessEvaluationResponse(
            allowed=True,
            decision="ALLOWED",
            reason_code=reason_code.value,
            consent_id=consent.id if consent else None,
            consent_version=consent.version if consent else None,
        )

    def _deny(
        self,
        reason_code: AccessDecisionCode,
        request: AccessEvaluationRequest,
        reason_detail: str,
        consent: Optional[ConsentRecord] = None,
    ) -> AccessEvaluationResponse:
        logger.warning(
            f"Access evaluation DENIED: code={reason_code.value} actor={request.actor_id} patient={request.patient_id} detail={reason_detail}",
            extra={
                "event_type": "ACCESS_EVALUATION_DENIED",
                "actor_id": request.actor_id,
                "patient_id": request.patient_id,
                "resource_type": request.resource_type,
                "action": request.action,
                "decision": "DENIED",
                "reason_code": reason_code.value,
                "consent_id": consent.id if consent else None,
            },
        )
        return AccessEvaluationResponse(
            allowed=False,
            decision="DENIED",
            reason_code=reason_code.value,
            consent_id=consent.id if consent else None,
            consent_version=consent.version if consent else None,
        )

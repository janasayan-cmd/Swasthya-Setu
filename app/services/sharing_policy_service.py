"""Sharing Policy Engine (Phase 44).

Evaluates sharing and export eligibility across actor identity, patient ownership,
Phase 43 consent status, action scope, destination safety, and minimum necessary bounds.

CRITICAL INVARIANTS:
- AI != SHARING AUTHORITY
- READ ACCESS != EXPORT ACCESS != SHARE ACCESS
- QUEUED AUTHORIZATION != CURRENT AUTHORIZATION
- DENY-BY-DEFAULT
"""

from __future__ import annotations

from typing import List, Optional

from app.core.exceptions import (
    AISharingAuthorityProhibitedException,
    SharingAutonomousClinicalProhibitedException,
    SharingDestinationInvalidException,
)
from app.core.logging import get_logger
from app.schemas.access_decision import (
    AccessDecisionCode,
    AccessEvaluationRequest,
    AccessEvaluationResponse,
)
from app.schemas.sharing import (
    DestinationType,
    SharingAction,
    SharingEvaluationRequest,
    SharingEvaluationResponse,
    SharingType,
)
from app.services.consent_access_service import ConsentAccessService
from app.utils.sharing_security import validate_destination_url

logger = get_logger("app.sharing_policy")


class SharingPolicyDecisionCode:
    ALLOW = "ALLOW"
    DENY = "DENY"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    REQUIRES_AUTHORIZATION = "REQUIRES_AUTHORIZATION"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    NOT_PERMITTED = "NOT_PERMITTED"


class SharingPolicyService:
    """Centralized policy engine controlling clinical data sharing and export permissions."""

    def __init__(self, consent_access_service: ConsentAccessService) -> None:
        self.consent_access_service = consent_access_service

    async def evaluate_sharing_policy(
        self, request: SharingEvaluationRequest
    ) -> SharingEvaluationResponse:
        """Comprehensive evaluation of a data sharing request."""
        actor_id = request.actor_id.strip() if request.actor_id else ""
        actor_role = (request.actor_role or "").strip().upper()
        patient_id = request.patient_id.strip() if request.patient_id else ""
        recipient_id = request.recipient_id.strip() if request.recipient_id else ""
        action = request.action.value if hasattr(request.action, "value") else str(request.action).upper()
        purpose = (request.purpose or "CARE_DELIVERY").strip().upper()
        resource_scopes = request.resource_scopes or []

        # 1. Reject missing fundamental context
        if not actor_id or not patient_id or not recipient_id or not resource_scopes:
            return SharingEvaluationResponse(
                allowed=False,
                decision=SharingPolicyDecisionCode.INSUFFICIENT_CONTEXT,
                reason_code="MISSING_CONTEXT",
                reason_detail="Actor, patient, recipient, and resource scopes are all mandatory.",
            )

        # 2. AI Boundary Protection: AI cannot authorize or grant sharing
        if actor_role in ("AI", "BOT", "SYSTEM_INFERRED", "LLM"):
            return SharingEvaluationResponse(
                allowed=False,
                decision=SharingPolicyDecisionCode.NOT_PERMITTED,
                reason_code="AI_SHARING_AUTHORITY_PROHIBITED",
                reason_detail="AI is not an authorizing authority and cannot grant or approve data sharing.",
            )

        # 3. Clinical Safety Gate: Sharing cannot diagnose, prescribe, triage, or alter clinical orders
        prohibited_clinical_purposes = {"DIAGNOSIS", "TRIAGE", "TREATMENT_ORDER", "PRESCRIPTION_CHANGE"}
        if purpose in prohibited_clinical_purposes:
            return SharingEvaluationResponse(
                allowed=False,
                decision=SharingPolicyDecisionCode.NOT_PERMITTED,
                reason_code="SHARING_AUTONOMOUS_CLINICAL_PROHIBITED",
                reason_detail="Clinical data sharing cannot be used to execute autonomous diagnoses, prescriptions, or triage.",
            )

        # 4. Destination validation if external
        if request.recipient_type in (
            DestinationType.REGISTERED_EXTERNAL_ORGANIZATION,
            DestinationType.REGISTERED_INTEROPERABILITY_ENDPOINT,
            DestinationType.AUTHORIZED_EXTERNAL_SYSTEM,
        ) and request.destination_url:
            try:
                validate_destination_url(request.destination_url, allow_empty=True)
            except SharingDestinationInvalidException as exc:
                return SharingEvaluationResponse(
                    allowed=False,
                    decision=SharingPolicyDecisionCode.NOT_PERMITTED,
                    reason_code="DESTINATION_INVALID",
                    reason_detail=str(exc.message),
                )

        # 5. Patient self-sharing: Patient sharing their own data to clinician/care team/export
        if actor_id == patient_id:
            # Patient has inherent authority to share their own records
            return SharingEvaluationResponse(
                allowed=True,
                decision=SharingPolicyDecisionCode.ALLOW,
                reason_code="PATIENT_SELF_SHARE",
                reason_detail="Patient initiated share of own clinical data",
                filtered_resource_scopes=resource_scopes,
            )

        # 6. Third-party actor sharing patient data: Consult Phase 43 Consent Engine for each scope
        authorized_scopes: List[str] = []
        last_denial_code = "CONSENT_REQUIRED"
        last_denial_reason = "No active consent found for requested scopes."
        matched_consent_id: Optional[str] = None

        for scope in resource_scopes:
            access_req = AccessEvaluationRequest(
                actor_id=actor_id,
                actor_role=actor_role,
                patient_id=patient_id,
                resource_type=scope,
                action=action,
                purpose=purpose,
            )
            eval_res: AccessEvaluationResponse = await self.consent_access_service.evaluate_access(access_req)

            if eval_res.allowed:
                authorized_scopes.append(scope)
                if eval_res.consent_id:
                    matched_consent_id = eval_res.consent_id
            else:
                last_denial_code = eval_res.reason_code or (eval_res.decision.value if hasattr(eval_res.decision, "value") else str(eval_res.decision))
                last_denial_reason = getattr(eval_res, "reason_detail", None) or f"Consent evaluation denied access ({last_denial_code})."

        if not authorized_scopes:
            # Distinguish expired, withdrawn, or missing consent
            decision_code = SharingPolicyDecisionCode.REQUIRES_AUTHORIZATION
            if "WITHDRAWN" in last_denial_code:
                decision_code = SharingPolicyDecisionCode.REVOKED
            elif "EXPIRED" in last_denial_code:
                decision_code = SharingPolicyDecisionCode.EXPIRED

            return SharingEvaluationResponse(
                allowed=False,
                decision=decision_code,
                reason_code=last_denial_code,
                reason_detail=last_denial_reason,
                filtered_resource_scopes=[],
            )

        # Partial or full authorization
        return SharingEvaluationResponse(
            allowed=True,
            decision=SharingPolicyDecisionCode.ALLOW,
            reason_code="AUTHORIZED_BY_CONSENT",
            reason_detail="Sharing operation authorized under valid active patient consent.",
            filtered_resource_scopes=authorized_scopes,
            consent_id=matched_consent_id,
        )

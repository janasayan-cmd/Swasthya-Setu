"""Payer Webhook Service (Phase 33).

Handles:
- Cryptographic HMAC-SHA256 signature verification
- Event deduplication and replay attack prevention
- Automatic claim and prior-authorization lifecycle state advancement
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, Optional

from app.core.exceptions import (
    PayerWebhookDuplicateException,
    PayerWebhookInvalidException,
    PayerWebhookSignatureInvalidException,
)
from app.integrations.payers.base import PayerProvider
from app.integrations.payers.providers.mock import MockPayerProvider
from app.repositories.authorization_repository import AuthorizationRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.payer_webhook_repository import PayerWebhookRepository
from app.schemas.authorization import PreAuthorizationStatus
from app.schemas.claim import ClaimStatus
from app.schemas.payer_webhook import (
    PayerWebhookEventRecord,
    PayerWebhookEventStatus,
    PayerWebhookResult,
)
from app.services.insurance_validation_service import InsuranceValidationService

logger = logging.getLogger(__name__)


class PayerWebhookService:
    """Service receiving and dispatching asynchronous payer clearinghouse events."""

    def __init__(
        self,
        claim_repo: Optional[ClaimRepository] = None,
        auth_repo: Optional[AuthorizationRepository] = None,
        webhook_repo: Optional[PayerWebhookRepository] = None,
        provider: Optional[PayerProvider] = None,
    ) -> None:
        self.claim_repo = claim_repo or ClaimRepository()
        self.auth_repo = auth_repo or AuthorizationRepository()
        self.webhook_repo = webhook_repo or PayerWebhookRepository()
        self.provider = provider or MockPayerProvider()

    async def handle_webhook(
        self,
        provider_name: str,
        raw_body: bytes,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> PayerWebhookResult:
        """Process inbound payer webhook event."""
        # 1. Cryptographic HMAC signature check
        if not self.provider.verify_webhook_signature(raw_body, headers):
            logger.warning(f"Rejected payer webhook: Invalid signature from provider {provider_name}")
            raise PayerWebhookSignatureInvalidException("Payer webhook HMAC signature verification failed.")

        # 2. Parse event payload
        parsed = self.provider.parse_webhook(payload, headers)
        if not parsed.event_id:
            raise PayerWebhookInvalidException("Missing event_id in webhook payload.")

        # 3. Deduplication check
        existing = self.webhook_repo.get_by_provider_event(provider_name, parsed.event_id)
        if existing:
            logger.info(f"Duplicate payer webhook ignored: provider={provider_name}, event={parsed.event_id}")
            return PayerWebhookResult(
                event_id=parsed.event_id,
                status=PayerWebhookEventStatus.DUPLICATE,
                message="Event has already been processed.",
                claim_id=existing.claim_id,
                authorization_id=existing.authorization_id,
            )

        payload_hash = hashlib.sha256(raw_body).hexdigest()
        matched_claim_id: Optional[str] = None
        matched_auth_id: Optional[str] = None

        # 4. Handle Claim updates
        claim = None
        if parsed.provider_claim_reference:
            claim = self.claim_repo.get_by_provider_reference(parsed.provider_claim_reference)
        if not claim and parsed.raw_data.get("claim_id"):
            claim = self.claim_repo.get(parsed.raw_data["claim_id"])

        if claim:
            matched_claim_id = claim.id
            status_str = (parsed.status or "").upper()
            if "APPROV" in status_str or "PAID" in status_str:
                target_status = ClaimStatus.APPROVED
                claim.approved_amount_in_minor_units = parsed.amount_in_minor_units or claim.total_amount_in_minor_units
                claim.payer_paid_amount_in_minor_units = claim.approved_amount_in_minor_units
                claim.patient_responsibility_in_minor_units = parsed.raw_data.get("patient_responsibility", 0)
            elif "DENI" in status_str or "REJECT" in status_str:
                target_status = ClaimStatus.DENIED
                claim.denial_reason = parsed.raw_data.get("denial_reason") or parsed.raw_data.get("reason", "Denied by payer")
                claim.denial_code = parsed.raw_data.get("denial_code")
            else:
                target_status = ClaimStatus.RECEIVED

            InsuranceValidationService.validate_claim_transition(claim.status, target_status)
            claim.status = target_status
            self.claim_repo.update(claim)
            logger.info(f"Updated claim {claim.claim_number} to {target_status.value} from webhook")

        # 5. Handle Pre-Authorization updates
        auth_rec = None
        if parsed.authorization_reference:
            auth_rec = self.auth_repo.get_by_payer_reference(parsed.authorization_reference)
        if not auth_rec and parsed.raw_data.get("authorization_id"):
            auth_rec = self.auth_repo.get(parsed.raw_data["authorization_id"])

        if auth_rec:
            matched_auth_id = auth_rec.id
            status_str = (parsed.status or "").upper()
            if "APPROV" in status_str:
                target_auth_status = PreAuthorizationStatus.APPROVED
                auth_rec.approved_amount_in_minor_units = parsed.amount_in_minor_units or auth_rec.estimated_amount_in_minor_units
            elif "DENI" in status_str:
                target_auth_status = PreAuthorizationStatus.DENIED
                auth_rec.denial_reason = parsed.raw_data.get("denial_reason") or parsed.raw_data.get("reason", "Denied by payer")
                auth_rec.denial_code = parsed.raw_data.get("denial_code")
            else:
                target_auth_status = PreAuthorizationStatus.PENDING

            InsuranceValidationService.validate_auth_transition(auth_rec.status, target_auth_status)
            auth_rec.status = target_auth_status
            self.auth_repo.update(auth_rec)
            logger.info(f"Updated pre-auth {auth_rec.authorization_number} to {target_auth_status.value} from webhook")

        # 6. Record processed webhook event
        log_record = PayerWebhookEventRecord(
            id=f"pwhk_{uuid.uuid4().hex[:12]}",
            event_id=parsed.event_id,
            provider_name=provider_name.upper(),
            event_type=parsed.event_type,
            status=PayerWebhookEventStatus.ACCEPTED,
            payload_hash=payload_hash,
            claim_id=matched_claim_id,
            authorization_id=matched_auth_id,
        )
        self.webhook_repo.record_event(log_record)

        return PayerWebhookResult(
            event_id=parsed.event_id,
            status=PayerWebhookEventStatus.ACCEPTED,
            message="Payer webhook event processed successfully.",
            claim_id=matched_claim_id,
            authorization_id=matched_auth_id,
        )

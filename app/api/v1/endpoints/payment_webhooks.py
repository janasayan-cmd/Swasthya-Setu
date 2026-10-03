"""Payment Webhook Ingestion Endpoint (Phase 32).

Receives, verifies, and dispatches external payment provider events.

CRITICAL INVARIANTS:
- WEBHOOK ≠ TRUSTED UNTIL CRYPTOGRAPHICALLY VERIFIED
- Enforces HMAC-SHA256 signature verification.
- Replay and duplication protection.
- No cardholder data / secrets are logged.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import get_payment_webhook_service
from app.core.exceptions import WebhookEventInvalidException
from app.schemas.payment_webhook import WebhookProcessResult
from app.services.payment_webhook_service import PaymentWebhookService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Payment Webhooks"])


@router.post(
    "/webhooks/payments/{provider}",
    response_model=WebhookProcessResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest Payment Gateway Webhook",
    description="Validates cryptographic signature, enforces idempotency, and reconciles transaction state.",
)
async def receive_payment_webhook(
    provider: str,
    request: Request,
    webhook_service: Annotated[PaymentWebhookService, Depends(get_payment_webhook_service)],
) -> WebhookProcessResult:
    # 1. Read raw body bytes for signature verification
    raw_body = await request.body()
    headers = dict(request.headers)

    # 2. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        logger.warning(f"Malformed webhook JSON received from provider {provider}: {e}")
        raise WebhookEventInvalidException("Invalid JSON body in webhook request")

    # 3. Process verified webhook
    return await webhook_service.handle_webhook(
        provider_name=provider,
        raw_body=raw_body,
        headers=headers,
        payload=payload,
    )

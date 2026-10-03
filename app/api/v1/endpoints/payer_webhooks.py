"""Payer Gateway Webhook Ingestion Endpoint (Phase 33).

Provides cryptographic HMAC-verified ingestion of asynchronous clearinghouse events:
- Claim adjudication (approved, denied, remittance advice)
- Prior authorization status changes
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import get_payer_webhook_service
from app.core.exceptions import PayerWebhookInvalidException
from app.schemas.payer_webhook import PayerWebhookResult
from app.services.payer_webhook_service import PayerWebhookService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Payer Webhooks"])


@router.post(
    "/webhooks/payers/{provider}",
    response_model=PayerWebhookResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest Payer Clearinghouse Webhook",
    description="Receives and validates asynchronous adjudication and authorization events.",
)
async def ingest_payer_webhook(
    provider: str,
    request: Request,
    webhook_service: Annotated[PayerWebhookService, Depends(get_payer_webhook_service)],
) -> PayerWebhookResult:
    raw_body = await request.body()
    headers = dict(request.headers)

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as exc:
        raise PayerWebhookInvalidException(f"Invalid JSON payload: {exc}")

    return await webhook_service.handle_webhook(
        provider_name=provider,
        raw_body=raw_body,
        headers=headers,
        payload=payload,
    )

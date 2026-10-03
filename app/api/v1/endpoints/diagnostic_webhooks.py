"""Diagnostic Webhook Endpoints (Phase 34).

Supports receiving signed webhooks from external laboratories and diagnostic gateways.
Enforces HMAC signature verification, event replay protection, and payload validation.
"""

from __future__ import annotations

import json
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import get_diagnostic_webhook_service
from app.core.exceptions import (
    DiagnosticWebhookDuplicateException,
    DiagnosticWebhookInvalidException,
    DiagnosticWebhookSignatureInvalidException,
)
from app.schemas.diagnostic_webhook import (
    DiagnosticWebhookPayload,
    WebhookIngestResponse,
)
from app.services.diagnostic_webhook_service import DiagnosticWebhookService

router = APIRouter(prefix="/webhooks/diagnostics", tags=["Diagnostic Webhooks"])


@router.post(
    "/{provider}",
    response_model=WebhookIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive provider diagnostic webhook",
)
async def receive_diagnostic_webhook(
    provider: str,
    request: Request,
    x_diagnostic_signature: Optional[str] = Header(None, alias="X-Diagnostic-Signature"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    webhook_service: DiagnosticWebhookService = Depends(get_diagnostic_webhook_service),
) -> WebhookIngestResponse:
    """Ingest external diagnostic provider webhook with HMAC signature verification."""
    signature = x_diagnostic_signature or x_hub_signature_256
    raw_body = await request.body()

    try:
        data = json.loads(raw_body.decode("utf-8"))
        payload = DiagnosticWebhookPayload.model_validate(data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed webhook payload: {e}",
        )

    try:
        return await webhook_service.process_webhook(
            raw_body=raw_body,
            signature_header=signature,
            payload=payload,
        )
    except DiagnosticWebhookSignatureInvalidException as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except DiagnosticWebhookDuplicateException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

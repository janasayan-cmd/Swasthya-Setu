"""Inbound Provider Webhook API Endpoints (Phase 45).

SAFETY INVARIANTS:
- WEBHOOK RECEIVED != DATA INTEGRATED
- SIGNATURE VERIFICATION REQUIRED
- REPLAY PROTECTION VIA NONCE & TIMESTAMP WINDOW
- INVALID SIGNATURE / REPLAY MUST FAIL CLOSED
"""

from __future__ import annotations

from typing import Annotated, Any, Dict
from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import get_ingestion_service
from app.core.exceptions import IngestionWebhookSignatureInvalidException
from app.core.logging import request_id_ctx_var
from app.schemas.ingestion import IngestionResponse, WebhookIngestionPayload
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(tags=["Provider Webhooks"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.post(
    "/integrations/{provider}/webhook",
    status_code=status.HTTP_200_OK,
    response_model=StandardSuccessResponse[IngestionResponse],
    summary="Receive inbound provider webhook",
    description="Processes asynchronous clinical event webhooks from registered external providers.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Invalid cryptographic signature"},
        409: {"model": StandardErrorResponse, "description": "Event replay detected"},
        422: {"model": StandardErrorResponse, "description": "Malformed payload"},
    },
)
async def receive_provider_webhook(
    request: Request,
    provider: str,
    payload: Dict[str, Any],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
    x_signature: str | None = Header(None, alias="X-Signature"),
    x_event_id: str | None = Header(None, alias="X-Event-ID"),
    x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    x_nonce: str | None = Header(None, alias="X-Nonce"),
) -> StandardSuccessResponse[IngestionResponse]:
    """Ingest external clinical event webhook securely."""
    # Allow headers or payload-embedded signature metadata
    signature = x_signature or payload.get("signature") or ""
    event_id = x_event_id or payload.get("event_id") or payload.get("id") or "evt-unknown"
    timestamp = x_timestamp or payload.get("timestamp") or ""
    nonce = x_nonce or payload.get("nonce") or event_id

    if not signature:
        raise IngestionWebhookSignatureInvalidException("Missing required webhook HMAC signature header or field.")

    data_payload = payload.get("data") if "data" in payload and isinstance(payload["data"], dict) else payload

    webhook_obj = WebhookIngestionPayload(
        provider=provider,
        event_id=str(event_id),
        event_type=str(payload.get("event_type", "clinical_event")),
        timestamp=str(timestamp),
        signature=str(signature),
        nonce=str(nonce),
        data=data_payload,
    )

    result = await ingestion_service.process_webhook(webhook_obj)

    return StandardSuccessResponse(
        data=ingestion_service._to_response(result),
        request_id=_req_id(request),
        message="Provider webhook received, validated, and processed.",
    )

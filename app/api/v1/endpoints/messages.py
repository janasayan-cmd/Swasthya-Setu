"""Clinical Message Management, Delivery, and Safety Gate Endpoints (Phase 41).

CRITICAL ARCHITECTURAL CONTRACT & NON-NEGOTIABLE SAFETY PRINCIPLES:
- MESSAGING IS A COMMUNICATION MECHANISM, NOT CLINICAL AUTHORITY
- MESSAGE != CLINICAL ORDER
- MESSAGE != DIAGNOSIS
- MESSAGE != TRIAGE
- MESSAGE != PRESCRIPTION
- MESSAGE != MEDICATION CHANGE
- MESSAGE != EMERGENCY DISPATCH
- SENT != DELIVERED
- DELIVERED != READ
- READ != ACKNOWLEDGED
- ACKNOWLEDGED != CLINICAL ACTION COMPLETED
- AI DRAFT != APPROVED CLINICAL COMMUNICATION
- AI CANNOT AUTONOMOUSLY SEND CLINICAL MESSAGES TO PATIENTS
- TRANSLATION != CLINICAL INTERPRETATION
- PROVIDER FAILURE != SUCCESS
- UNKNOWN STATUS != SUCCESS
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.api.deps import (
    get_communication_policy_service,
    get_communication_provider,
    get_current_user,
    get_message_delivery_service,
    get_message_search_service,
    get_message_service,
)
from app.integrations.communication.providers.mock import MockCommunicationProvider
from app.schemas.communication import CommunicationMetricsResponse, ProviderState, WebhookPayload
from app.schemas.message import (
    AIDraftRequest,
    AIDraftResponse,
    ConversationSummaryResponse,
    MessageAcknowledgeRequest,
    MessageDeliveryHistoryRecord,
    MessageListResponse,
    MessageRecord,
    MessageSendRequest,
    MessageStatus,
    MessageTranslationRequest,
    MessageTranslationResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.communication_policy_service import CommunicationPolicyService
from app.services.message_delivery_service import MessageDeliveryService
from app.services.message_search_service import MessageSearchService
from app.services.message_service import MessageService

router = APIRouter(tags=["Clinical Messages & Delivery"])


# ---------------------------------------------------------------------------
# Message Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit and dispatch a message",
)
async def send_message(
    conversation_id: str,
    payload: MessageSendRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageRecord:
    """Submit a message into a conversation with strict delivery and clinical safety rules."""
    if idempotency_key and not payload.idempotency_key:
        payload.idempotency_key = idempotency_key

    return await service.send_message(conversation_id, payload, current_user)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="List messages in a conversation",
)
async def list_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageListResponse:
    """Retrieve chronologically bounded message history with cursor support."""
    return service.list_messages(conversation_id, current_user, limit, cursor)


@router.get(
    "/messages/{message_id}",
    response_model=MessageRecord,
    summary="Get single message",
)
async def get_message(
    message_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageRecord:
    """Retrieve single message with enumeration protection."""
    return service.get_message(message_id, current_user)


@router.post(
    "/messages/{message_id}/read",
    response_model=MessageRecord,
    summary="Mark message as read",
)
async def mark_message_read(
    message_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageRecord:
    """Record that the current user has opened and read the message."""
    return service.mark_as_read(message_id, current_user)


@router.post(
    "/messages/{message_id}/acknowledge",
    response_model=MessageRecord,
    summary="Acknowledge message (clinicians only)",
)
async def acknowledge_message(
    message_id: str,
    payload: MessageAcknowledgeRequest = MessageAcknowledgeRequest(),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageRecord:
    """Record clinician formal acknowledgment (Note: Acknowledgment != clinical action)."""
    return service.acknowledge_message(message_id, payload, current_user)


@router.post(
    "/messages/{message_id}/retry",
    response_model=MessageRecord,
    summary="Retry failed message delivery",
)
async def retry_message(
    message_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageRecord:
    """Retry outbound transmission for a failed or pending message."""
    return await service.retry_message(message_id, current_user)


@router.get(
    "/messages/{message_id}/history",
    response_model=List[MessageDeliveryHistoryRecord],
    summary="Get message delivery state history",
)
async def get_message_delivery_history(
    message_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> List[MessageDeliveryHistoryRecord]:
    """Retrieve delivery state transition audit log for message."""
    return service.get_message_delivery_history(message_id, current_user)


@router.get(
    "/clinicians/me/messages",
    response_model=List[MessageRecord],
    summary="Clinician unread messages",
)
async def get_my_clinician_messages(
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> List[MessageRecord]:
    """Retrieve messages needing attention across clinician conversations."""
    return service._msg_repo.get_unread_messages(current_user.user_id, limit=limit)


# ---------------------------------------------------------------------------
# AI Assistance & Translation Boundaries
# ---------------------------------------------------------------------------

@router.post(
    "/conversations/{conversation_id}/messages/draft",
    response_model=AIDraftResponse,
    summary="Generate AI draft response for clinician review",
)
async def generate_ai_draft(
    conversation_id: str,
    payload: AIDraftRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> AIDraftResponse:
    """Generate an AI response suggestion with mandatory human clinician approval boundaries."""
    return service.generate_ai_draft(conversation_id, payload, current_user)


@router.post(
    "/messages/{message_id}/translate",
    response_model=MessageTranslationResponse,
    summary="Translate message content",
)
async def translate_message(
    message_id: str,
    payload: MessageTranslationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageTranslationResponse:
    """Obtain derived translated representation of an authoritative message."""
    return service.translate_message(message_id, payload, current_user)


@router.post(
    "/conversations/{conversation_id}/summarize",
    response_model=ConversationSummaryResponse,
    summary="Summarize conversation for operational overview",
)
async def summarize_conversation(
    conversation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> ConversationSummaryResponse:
    """Generate non-authoritative communication summary for operational review."""
    return service.summarize_conversation(conversation_id, current_user)


# ---------------------------------------------------------------------------
# Search Integration (Phase 30)
# ---------------------------------------------------------------------------

@router.get(
    "/conversations/search",
    response_model=List[MessageRecord],
    summary="Authorized message search",
)
async def search_messages(
    q: str = Query(..., min_length=1, max_length=200, description="Search term"),
    conversation_id: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: MessageSearchService = Depends(get_message_search_service),
) -> List[MessageRecord]:
    """Search messages within authorized conversation scopes (Search relevance != clinical importance)."""
    return search_service.search_messages(
        query=q,
        current_user=current_user,
        conversation_id=conversation_id,
        patient_id=patient_id,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Webhook Ingestion
# ---------------------------------------------------------------------------

@router.post(
    "/communication/webhooks/{provider_name}",
    response_model=WebhookPayload,
    summary="Ingest external communication provider webhook",
)
async def handle_provider_webhook(
    provider_name: str,
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_provider_signature: Optional[str] = Header(None, alias="X-Provider-Signature"),
    delivery_service: MessageDeliveryService = Depends(get_message_delivery_service),
) -> WebhookPayload:
    """Receive untrusted provider delivery callback with mandatory signature verification and replay protection."""
    signature = x_signature or x_provider_signature or ""
    payload_bytes = await request.body()
    payload_json = await request.json() if payload_bytes else {}

    return await delivery_service.process_webhook(
        payload_bytes=payload_bytes,
        signature=signature,
        payload_dict=payload_json,
    )


# ---------------------------------------------------------------------------
# Operational Admin Telemetry (Phase 18 Integration)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/communication/metrics",
    response_model=CommunicationMetricsResponse,
    summary="Operational communication metrics",
)
async def get_communication_metrics(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
    provider: MockCommunicationProvider = Depends(get_communication_provider),
) -> CommunicationMetricsResponse:
    """PHI-safe operational metrics summary."""
    provider_health = await provider.health_check()
    return CommunicationMetricsResponse(
        total_conversations=service._conv_repo.count_total(),
        active_conversations=service._conv_repo.count_active(),
        closed_conversations=service._conv_repo.count_closed(),
        total_messages=service._msg_repo.count_total(),
        sent_messages=service._msg_repo.count_by_status(status=MessageStatus.SENT),
        delivered_messages=service._msg_repo.count_by_status(status=MessageStatus.DELIVERED),
        read_messages=service._msg_repo.count_by_status(status=MessageStatus.READ),
        acknowledged_messages=service._msg_repo.count_by_status(status=MessageStatus.ACKNOWLEDGED),
        failed_messages=service._msg_repo.count_by_status(status=MessageStatus.FAILED),
        provider_state=provider_health,
        active_provider=provider.provider_name,
    )


@router.post(
    "/admin/communication/providers/{provider_name}/health",
    summary="Probe communication provider health",
)
async def probe_provider_health(
    provider_name: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    provider: MockCommunicationProvider = Depends(get_communication_provider),
) -> dict:
    """Probe and return provider connectivity status."""
    state = await provider.health_check()
    return {"provider": provider_name, "state": state.value}

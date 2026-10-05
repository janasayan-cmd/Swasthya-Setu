"""Clinical Communication and Conversation Management Endpoints (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY PRINCIPLES:
- CONVERSATION != CLINICAL ENCOUNTER
- CONVERSATION != MEDICAL RECORD BY DEFAULT
- CONVERSATION CLOSURE DOES NOT MEAN CLINICAL RESOLUTION
- PATIENT MESSAGES REMAIN COMMUNICATION, NOT UNVERIFIED CLINICAL TRUTH
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_conversation_service,
    get_current_user,
)
from app.schemas.auth import UserRole
from app.schemas.conversation import (
    ConversationCategory,
    ConversationCloseRequest,
    ConversationCreateRequest,
    ConversationHistoryRecord,
    ConversationListResponse,
    ConversationRecord,
    ConversationReopenRequest,
    ConversationStatus,
    ParticipantAddRequest,
    ParticipantRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["Clinical Communication & Conversations"])


# ---------------------------------------------------------------------------
# Conversation Lifecycle Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/conversations",
    response_model=ConversationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new clinical conversation",
)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationRecord:
    """Initiate a controlled clinical or operational conversation."""
    return service.create_conversation(payload, current_user)


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List conversations scoped to current user",
)
async def list_conversations(
    status: Optional[ConversationStatus] = Query(None, description="Filter by status"),
    category: Optional[ConversationCategory] = Query(None, description="Filter by category"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    organization_id: Optional[str] = Query(None, description="Filter by organization ID"),
    facility_id: Optional[str] = Query(None, description="Filter by facility ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """List conversations authorized for current actor."""
    conversations, total = service.list_conversations(
        current_user=current_user,
        status=status,
        category=category,
        patient_id=patient_id,
        organization_id=organization_id,
        facility_id=facility_id,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        conversations=conversations,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationRecord,
    summary="Get conversation details",
)
async def get_conversation(
    conversation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationRecord:
    """Retrieve full conversation details with participant list."""
    return service.get_conversation(conversation_id, current_user)


@router.post(
    "/conversations/{conversation_id}/close",
    response_model=ConversationRecord,
    summary="Close an active conversation",
)
async def close_conversation(
    conversation_id: str,
    payload: ConversationCloseRequest = ConversationCloseRequest(),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationRecord:
    """Close an active conversation to normal message posting."""
    return service.close_conversation(conversation_id, payload, current_user)


@router.post(
    "/conversations/{conversation_id}/reopen",
    response_model=ConversationRecord,
    summary="Reopen a closed conversation",
)
async def reopen_conversation(
    conversation_id: str,
    payload: ConversationReopenRequest = ConversationReopenRequest(),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationRecord:
    """Reopen a previously closed conversation."""
    return service.reopen_conversation(conversation_id, payload, current_user)


# ---------------------------------------------------------------------------
# Participant Management Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/conversations/{conversation_id}/participants",
    response_model=List[ParticipantRecord],
    summary="List participants in a conversation",
)
async def list_participants(
    conversation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> List[ParticipantRecord]:
    """Retrieve active and historical participants of a conversation."""
    conv = service.get_conversation(conversation_id, current_user)
    return conv.participants


@router.post(
    "/conversations/{conversation_id}/participants",
    response_model=ParticipantRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Add participant to conversation",
)
async def add_participant(
    conversation_id: str,
    payload: ParticipantAddRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ParticipantRecord:
    """Add an authorized user as a participant in an active conversation."""
    return service.add_participant(conversation_id, payload, current_user)


@router.delete(
    "/conversations/{conversation_id}/participants/{participant_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove/deactivate participant from conversation",
)
async def remove_participant(
    conversation_id: str,
    participant_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> dict:
    """Deactivate participant membership in conversation."""
    success = service.remove_participant(conversation_id, participant_id, current_user)
    return {"success": success, "participant_id": participant_id}


@router.get(
    "/conversations/{conversation_id}/history",
    response_model=List[ConversationHistoryRecord],
    summary="Get conversation lifecycle history",
)
async def get_conversation_history(
    conversation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> List[ConversationHistoryRecord]:
    """Audit transition history of conversation states."""
    return service.get_conversation_history(conversation_id, current_user)


# ---------------------------------------------------------------------------
# Scoped Conversation Queries
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/conversations",
    response_model=ConversationListResponse,
    summary="Patient-scoped conversations",
)
async def get_patient_conversations(
    patient_id: str,
    status: Optional[ConversationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """List conversations for a specific patient subject."""
    convs, total = service.list_conversations(
        current_user=current_user,
        patient_id=patient_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        conversations=convs,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/clinicians/me/conversations",
    response_model=ConversationListResponse,
    summary="Clinician-scoped conversations",
)
async def get_my_clinician_conversations(
    status: Optional[ConversationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """List conversations where the authenticated clinician participates."""
    convs, total = service.list_conversations(
        current_user=current_user,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        conversations=convs,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/organizations/{organization_id}/conversations",
    response_model=ConversationListResponse,
    summary="Organization-scoped conversations",
)
async def get_organization_conversations(
    organization_id: str,
    status: Optional[ConversationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """List conversations within an organization boundary."""
    convs, total = service.list_conversations(
        current_user=current_user,
        organization_id=organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        conversations=convs,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/facilities/{facility_id}/conversations",
    response_model=ConversationListResponse,
    summary="Facility-scoped conversations",
)
async def get_facility_conversations(
    facility_id: str,
    status: Optional[ConversationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """List conversations within a facility boundary."""
    convs, total = service.list_conversations(
        current_user=current_user,
        facility_id=facility_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        conversations=convs,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/admin/conversations",
    response_model=ConversationListResponse,
    summary="Admin operational conversations list",
)
async def get_admin_conversations(
    status: Optional[ConversationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """Admin operational inspection with restricted metadata (no unrestricted PHI)."""
    convs, total = service.list_conversations(
        current_user=current_user,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        conversations=convs,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get(
    "/admin/conversations/{conversation_id}",
    response_model=ConversationRecord,
    summary="Admin operational conversation inspection",
)
async def get_admin_conversation(
    conversation_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationRecord:
    """Admin-scoped conversation inspection with mandatory auditing."""
    return service.get_conversation(conversation_id, current_user)

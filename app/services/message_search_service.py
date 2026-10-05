"""Authorized Clinical Message Search and Retrieval Service (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- SEARCH RELEVANCE != CLINICAL IMPORTANCE
- Never rank messages according to medical severity using heuristics or LLMs.
- Strict authorization: No unauthorized snippet preview, counts, or autocomplete leaks.
- Minimum necessary PHI retrieval principles.
"""

from __future__ import annotations

from typing import List, Optional

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.auth import UserRole
from app.schemas.message import MessageRecord
from app.schemas.user import AuthenticatedUserContext
from app.services.conversation_authorization_service import ConversationAuthorizationService


class MessageSearchService:
    """Scoped, permission-aware message search."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        authorization_service: ConversationAuthorizationService,
        enabled: bool = True,
    ) -> None:
        self._conv_repo = conversation_repository
        self._msg_repo = message_repository
        self._authz = authorization_service
        self._enabled = enabled

    def search_messages(
        self,
        query: str,
        current_user: AuthenticatedUserContext,
        conversation_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[MessageRecord]:
        """Search authorized messages matching search query."""
        if not query or not query.strip():
            return []

        clean_query = query.strip().lower()

        # Resolve candidate conversations authorized for actor
        if conversation_id:
            conv = self._conv_repo.get_by_id(conversation_id)
            if not conv or not self._authz.can_access_conversation(current_user, conv):
                return []
            candidate_conv_ids = [conv.id]
        else:
            # List user conversations
            convs, _ = self._conv_repo.list_conversations(
                patient_id=current_user.user_id if current_user.role in (UserRole.PATIENT, "PATIENT") else patient_id,
                user_id=current_user.user_id if current_user.role not in (UserRole.PATIENT, UserRole.ADMIN, "ADMIN") else None,
                limit=100,
            )
            candidate_conv_ids = [c.id for c in convs if self._authz.can_access_conversation(current_user, c)]

        results: List[MessageRecord] = []
        for cid in candidate_conv_ids:
            messages, _, _, _ = self._msg_repo.list_messages(cid, limit=200)
            for m in messages:
                if clean_query in m.content.lower():
                    results.append(m)
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

        # Chronological ordering (NOT medical ranking)
        results.sort(key=lambda m: m.created_at, reverse=True)
        return results

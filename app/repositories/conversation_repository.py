"""Clinical Conversation and Participant Repository (Phase 41).

Thread-safe repository for conversation entities, participant memberships,
and lifecycle transition histories.

ARCHITECTURAL INVARIANTS:
- Consumes existing database contract without duplicating tables.
- Concurrency safety is guaranteed via threading.Lock.
- Participant queries are optimized to avoid N+1 scans.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.conversation import (
    ConversationCategory,
    ConversationHistoryRecord,
    ConversationRecord,
    ConversationStatus,
    ParticipantRecord,
)


class ConversationRepository:
    """Thread-safe in-memory repository for conversations and participants."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conversations: Dict[str, ConversationRecord] = {}
        self._history: Dict[str, List[ConversationHistoryRecord]] = {}  # conversation_id -> list
        self._user_conversations: Dict[str, set[str]] = {}  # user_id -> set of conversation_ids

    def save(self, conversation: ConversationRecord) -> ConversationRecord:
        """Persist or update a conversation record."""
        with self._lock:
            conversation.updated_at = datetime.now(timezone.utc)
            self._conversations[conversation.id] = conversation

            # Index participants for quick lookup
            for p in conversation.participants:
                if p.is_active:
                    self._user_conversations.setdefault(p.user_id, set()).add(conversation.id)
                elif p.user_id in self._user_conversations:
                    self._user_conversations[p.user_id].discard(conversation.id)

            return conversation

    def get_by_id(self, conversation_id: str) -> Optional[ConversationRecord]:
        """Retrieve conversation by ID."""
        with self._lock:
            conv = self._conversations.get(conversation_id)
            return conv.model_copy(deep=True) if conv else None

    def list_conversations(
        self,
        status: Optional[ConversationStatus] = None,
        category: Optional[ConversationCategory] = None,
        patient_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ConversationRecord], int]:
        """Query conversations with filters and pagination."""
        with self._lock:
            # If user_id specified, start from indexed conversation IDs
            if user_id is not None:
                candidate_ids = self._user_conversations.get(user_id, set())
                records = [self._conversations[cid] for cid in candidate_ids if cid in self._conversations]
            else:
                records = list(self._conversations.values())

        # Filter
        filtered: List[ConversationRecord] = []
        for r in records:
            if status is not None and r.status != status:
                continue
            if category is not None and r.category != category:
                continue
            if patient_id is not None and r.patient_id != patient_id:
                continue
            if organization_id is not None and r.organization_id != organization_id:
                continue
            if facility_id is not None and r.facility_id != facility_id:
                continue
            filtered.append(r)

        # Sort descending by updated_at / last_message_at
        filtered.sort(
            key=lambda c: c.last_message_at or c.updated_at or c.created_at,
            reverse=True,
        )

        total = len(filtered)
        paginated = filtered[offset : offset + limit]
        return [c.model_copy(deep=True) for c in paginated], total

    def add_participant(self, conversation_id: str, participant: ParticipantRecord) -> Optional[ParticipantRecord]:
        """Add participant to conversation."""
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return None

            # Remove existing inactive participant record for same user if present
            conv.participants = [p for p in conv.participants if p.user_id != participant.user_id]
            conv.participants.append(participant)
            conv.updated_at = datetime.now(timezone.utc)
            self._user_conversations.setdefault(participant.user_id, set()).add(conversation_id)
            return participant.model_copy(deep=True)

    def remove_participant(self, conversation_id: str, participant_id: str) -> bool:
        """Mark participant as left/inactive."""
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return False

            found = False
            for p in conv.participants:
                if p.participant_id == participant_id:
                    p.is_active = False
                    p.left_at = datetime.now(timezone.utc)
                    self._user_conversations.get(p.user_id, set()).discard(conversation_id)
                    found = True
                    break

            if found:
                conv.updated_at = datetime.now(timezone.utc)
            return found

    def get_participant(self, conversation_id: str, user_id: str) -> Optional[ParticipantRecord]:
        """Get participant record for a user in a conversation."""
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return None
            for p in conv.participants:
                if p.user_id == user_id and p.is_active:
                    return p.model_copy(deep=True)
            return None

    def record_history(self, entry: ConversationHistoryRecord) -> None:
        """Append an audit transition to history."""
        with self._lock:
            self._history.setdefault(entry.conversation_id, []).append(entry)

    def get_history(self, conversation_id: str) -> List[ConversationHistoryRecord]:
        """Retrieve conversation lifecycle history."""
        with self._lock:
            entries = self._history.get(conversation_id, [])
            return [e.model_copy(deep=True) for e in entries]

    def count_total(self) -> int:
        """Count total conversations."""
        with self._lock:
            return len(self._conversations)

    def count_active(self) -> int:
        """Count active conversations."""
        with self._lock:
            return sum(1 for c in self._conversations.values() if c.status == ConversationStatus.ACTIVE)

    def count_closed(self) -> int:
        """Count closed conversations."""
        with self._lock:
            return sum(1 for c in self._conversations.values() if c.status == ConversationStatus.CLOSED)

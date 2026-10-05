"""Message Authorization and Clinical Safety Boundaries Service (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- Resource-level authorization: Cannot read message without authorized conversation membership.
- Patient-level scoping: Patients can ONLY access messages in their own conversations.
- Clinician-only actions: Acknowledgment and clinical notes require clinician role.
- Enumeration resistance: Unauthorized requests must not confirm message existence.
"""

from __future__ import annotations

from app.schemas.auth import UserRole
from app.schemas.conversation import ConversationRecord, ConversationStatus
from app.schemas.message import AttachmentReference, MessageRecord, MessageStatus
from app.schemas.user import AuthenticatedUserContext


class MessageAuthorizationService:
    """Evaluates message-level access control and action authorization."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def can_read_message(
        self,
        current_user: AuthenticatedUserContext,
        message: MessageRecord,
        conversation: ConversationRecord,
    ) -> bool:
        """Evaluate if user can read an individual message."""
        if not self._enabled:
            return True

        if current_user.role in (UserRole.ADMIN, "ADMIN", "SUPERADMIN"):
            return True

        # Patient: Must be subject of conversation
        if current_user.role in (UserRole.PATIENT, "PATIENT"):
            return current_user.user_id == conversation.patient_id

        # Active participant check
        return any(
            p.user_id == current_user.user_id and p.is_active
            for p in conversation.participants
        )

    def can_send_message(
        self,
        current_user: AuthenticatedUserContext,
        conversation: ConversationRecord,
    ) -> bool:
        """Evaluate if actor can post a new message in conversation."""
        if not self._enabled:
            return True

        # Closed or locked conversations reject new messages
        if conversation.status in (ConversationStatus.CLOSED, ConversationStatus.LOCKED, ConversationStatus.ARCHIVED):
            return False

        # Admin operational override
        if current_user.role in (UserRole.ADMIN, "ADMIN", "SUPERADMIN"):
            return True

        # Must be an active participant in the conversation
        return any(
            p.user_id == current_user.user_id and p.is_active
            for p in conversation.participants
        )

    def can_acknowledge_message(
        self,
        current_user: AuthenticatedUserContext,
        message: MessageRecord,
    ) -> bool:
        """Evaluate if actor has clinician authority to formally acknowledge a message."""
        if not self._enabled:
            return True

        # Only clinicians and nurses can record clinical acknowledgments
        return current_user.role in (
            UserRole.DOCTOR,
            "DOCTOR",
            "CLINICIAN",
            "NURSE",
            UserRole.ADMIN,
            "ADMIN",
        )

    def can_retry_message(
        self,
        current_user: AuthenticatedUserContext,
        message: MessageRecord,
    ) -> bool:
        """Evaluate if actor can request delivery retry for a failed message."""
        if not self._enabled:
            return True

        # Sender or admin can request retry
        return (
            current_user.user_id == message.sender_id
            or current_user.role in (UserRole.ADMIN, "ADMIN", "SUPERADMIN")
        )

    def can_access_attachment(
        self,
        current_user: AuthenticatedUserContext,
        attachment: AttachmentReference,
        message: MessageRecord,
        conversation: ConversationRecord,
    ) -> bool:
        """Evaluate if actor can download/view attachment reference."""
        return self.can_read_message(current_user, message, conversation)

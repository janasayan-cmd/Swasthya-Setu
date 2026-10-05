"""Conversation Authorization and Tenancy Boundary Service (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- Resource-level authorization: NEVER authorize solely based on knowing conversation ID or patient ID.
- Organization / facility isolation must be strictly enforced.
- Patient-level access: Patients can ONLY access their own conversations.
- Minimum necessary access principles apply.
"""

from __future__ import annotations

from typing import Optional

from app.schemas.auth import UserRole
from app.schemas.conversation import ConversationRecord, ConversationStatus
from app.schemas.user import AuthenticatedUserContext


class ConversationAuthorizationService:
    """Evaluates resource-level authorization and tenancy rules for conversations."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def can_access_conversation(
        self,
        current_user: AuthenticatedUserContext,
        conversation: ConversationRecord,
    ) -> bool:
        """Evaluate if actor can view conversation metadata and participant list."""
        if not self._enabled:
            return True

        # System admin operational view (audited, scoped)
        if current_user.role in (UserRole.ADMIN, "ADMIN", "SUPERADMIN"):
            return True

        # Patient scope: Patient can ONLY access if they are the subject of the conversation
        if current_user.role in (UserRole.PATIENT, "PATIENT"):
            return current_user.user_id == conversation.patient_id

        # Check explicit active participant membership
        is_participant = any(
            p.user_id == current_user.user_id and p.is_active
            for p in conversation.participants
        )
        if is_participant:
            return True

        # Clinician scope: Clinician in same organization/facility caring for patient
        if current_user.role in (UserRole.DOCTOR, "DOCTOR", "CLINICIAN", "NURSE"):
            # Must match organization boundary if specified
            if conversation.organization_id and current_user.organization_id:
                if conversation.organization_id != current_user.organization_id:
                    return False
            # If clinician created it or is active participant
            return current_user.user_id == conversation.created_by

        # Hospital / Facility Admin scope
        if current_user.role in (UserRole.HOSPITAL_ADMIN, "HOSPITAL_ADMIN", "FACILITY_ADMIN"):
            if conversation.organization_id and current_user.organization_id:
                return conversation.organization_id == current_user.organization_id
            if conversation.facility_id and current_user.facility_id:
                return conversation.facility_id == current_user.facility_id

        return False

    def can_modify_conversation(
        self,
        current_user: AuthenticatedUserContext,
        conversation: ConversationRecord,
    ) -> bool:
        """Evaluate if actor can add/remove participants or close conversation."""
        if not self._enabled:
            return True

        if conversation.status in (ConversationStatus.LOCKED, ConversationStatus.ARCHIVED):
            return False

        if current_user.role in (UserRole.ADMIN, "ADMIN", "SUPERADMIN"):
            return True

        # Creator or active clinician participant can manage
        if current_user.user_id == conversation.created_by:
            return True

        for p in conversation.participants:
            if p.user_id == current_user.user_id and p.is_active:
                if p.role in ("CLINICIAN", "ORGANIZATION_ADMIN"):
                    return True

        return False

    def can_close_conversation(
        self,
        current_user: AuthenticatedUserContext,
        conversation: ConversationRecord,
    ) -> bool:
        """Evaluate if actor can close an active conversation."""
        if not self._enabled:
            return True

        if conversation.status != ConversationStatus.ACTIVE:
            return False

        return self.can_modify_conversation(current_user, conversation)

    def can_reopen_conversation(
        self,
        current_user: AuthenticatedUserContext,
        conversation: ConversationRecord,
    ) -> bool:
        """Evaluate if actor can reopen a closed conversation."""
        if not self._enabled:
            return True

        if conversation.status != ConversationStatus.CLOSED:
            return False

        # Clinician, creator, or admin can reopen
        if current_user.role in (UserRole.ADMIN, "ADMIN", UserRole.DOCTOR, "DOCTOR"):
            return True

        return current_user.user_id == conversation.created_by

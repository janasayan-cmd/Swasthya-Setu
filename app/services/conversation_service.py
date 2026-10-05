"""Clinical Conversation Management Service (Phase 41).

Orchestrates conversation lifecycle, participant memberships,
closed/reopened state transitions, and audit integration.

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- CONVERSATION != CLINICAL ENCOUNTER
- CONVERSATION != MEDICAL RECORD BY DEFAULT
- CLOSED CONVERSATIONS DO NOT PERMIT UNCONTROLLED MESSAGE INGESTION
- CONVERSATION CLOSURE DOES NOT MEAN CLINICAL RESOLUTION
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.exceptions import (
    ConversationAccessDeniedException,
    ConversationClosedException,
    ConversationLockedException,
    ConversationNotFoundException,
    ParticipantAlreadyExistsException,
    ParticipantLimitExceededException,
    ParticipantNotFoundException,
)
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.auth import UserRole
from app.schemas.conversation import (
    ConversationCategory,
    ConversationCloseRequest,
    ConversationCreateRequest,
    ConversationHistoryRecord,
    ConversationRecord,
    ConversationReopenRequest,
    ConversationStatus,
    ParticipantAddRequest,
    ParticipantRecord,
    ParticipantRole,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.communication_policy_service import CommunicationPolicyService
from app.services.conversation_authorization_service import ConversationAuthorizationService


class ConversationService:
    """Manages conversations, participant memberships, and lifecycle transitions."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        authorization_service: ConversationAuthorizationService,
        policy_service: CommunicationPolicyService,
        audit_service: AuditService,
        max_participants: int = 50,
        enabled: bool = True,
    ) -> None:
        self._repo = conversation_repository
        self._authz = authorization_service
        self._policy = policy_service
        self._audit = audit_service
        self._max_participants = max_participants
        self._enabled = enabled

    def _record_audit(self, event: AuditEventRecord) -> None:
        """Safely record audit event across sync and async execution contexts."""
        if not self._audit:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._audit.log_event(event))
        except RuntimeError:
            try:
                asyncio.run(self._audit.log_event(event))
            except Exception:
                pass
        except Exception:
            pass

    def create_conversation(
        self,
        payload: ConversationCreateRequest,
        current_user: AuthenticatedUserContext,
    ) -> ConversationRecord:
        """Create and activate a new conversation."""
        self._policy.check_rate_limit(current_user.user_id, action="create_conversation")

        # Patients can only create conversations for themselves
        if current_user.role in (UserRole.PATIENT, "PATIENT") and payload.patient_id != current_user.user_id:
            raise ConversationAccessDeniedException("Patients can only initiate conversations for themselves.")

        conv_id = f"conv-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Build initial participants
        participants: List[ParticipantRecord] = []

        # Add creator as initial participant
        creator_role = ParticipantRole.PATIENT if current_user.role in (UserRole.PATIENT, "PATIENT") else ParticipantRole.CLINICIAN
        participants.append(
            ParticipantRecord(
                participant_id=f"part-{uuid.uuid4().hex[:8]}",
                conversation_id=conv_id,
                user_id=current_user.user_id,
                role=creator_role,
                organization_id=current_user.organization_id or payload.organization_id,
                facility_id=current_user.facility_id or payload.facility_id,
                joined_at=now,
                is_active=True,
            )
        )

        # Add patient if creator is not patient
        if payload.patient_id != current_user.user_id:
            participants.append(
                ParticipantRecord(
                    participant_id=f"part-{uuid.uuid4().hex[:8]}",
                    conversation_id=conv_id,
                    user_id=payload.patient_id,
                    role=ParticipantRole.PATIENT,
                    joined_at=now,
                    is_active=True,
                )
            )

        # Add any initial extra participant IDs
        if payload.initial_participant_ids:
            for extra_id in payload.initial_participant_ids:
                if not any(p.user_id == extra_id for p in participants):
                    participants.append(
                        ParticipantRecord(
                            participant_id=f"part-{uuid.uuid4().hex[:8]}",
                            conversation_id=conv_id,
                            user_id=extra_id,
                            role=ParticipantRole.CARE_TEAM_MEMBER,
                            joined_at=now,
                            is_active=True,
                        )
                    )

        conversation = ConversationRecord(
            id=conv_id,
            patient_id=payload.patient_id,
            category=payload.category,
            subject=payload.subject,
            status=ConversationStatus.ACTIVE,
            organization_id=payload.organization_id or current_user.organization_id,
            facility_id=payload.facility_id or current_user.facility_id,
            encounter_id=payload.encounter_id,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
            participants=participants,
            metadata=payload.metadata,
        )

        saved = self._repo.save(conversation)

        # Record history & audit
        self._repo.record_history(
            ConversationHistoryRecord(
                id=f"hist-{uuid.uuid4().hex[:8]}",
                conversation_id=conv_id,
                actor_id=current_user.user_id,
                action="CONVERSATION_CREATED",
                new_status=ConversationStatus.ACTIVE,
                reason="Initial creation",
            )
        )

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.CONVERSATION_CREATED,
                actor_id=current_user.user_id,
                target_id=conv_id,
                patient_id=payload.patient_id,
                organization_id=conversation.organization_id,
                metadata={"category": payload.category.value, "subject": payload.subject},
            )
        )

        return saved

    def get_conversation(
        self,
        conversation_id: str,
        current_user: AuthenticatedUserContext,
    ) -> ConversationRecord:
        """Retrieve conversation with strict resource authorization."""
        conv = self._repo.get_by_id(conversation_id)
        if not conv:
            raise ConversationNotFoundException(f"Conversation '{conversation_id}' was not found.")

        if not self._authz.can_access_conversation(current_user, conv):
            self._record_audit(
                AuditEventRecord(
                    event_type=AuditEventType.COMMUNICATION_ACCESS_DENIED,
                    actor_id=current_user.user_id,
                    target_id=conversation_id,
                    patient_id=conv.patient_id,
                    metadata={"reason": "Unauthorized conversation retrieval attempt"},
                )
            )
            # Use authorization-safe not-found to prevent enumeration for unrelated patients
            if current_user.role in (UserRole.PATIENT, "PATIENT"):
                raise ConversationNotFoundException(f"Conversation '{conversation_id}' was not found.")
            raise ConversationAccessDeniedException("You are not authorized to view this conversation.")

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.CONVERSATION_ACCESSED,
                actor_id=current_user.user_id,
                target_id=conversation_id,
                patient_id=conv.patient_id,
            )
        )
        return conv

    def list_conversations(
        self,
        current_user: AuthenticatedUserContext,
        status: Optional[ConversationStatus] = None,
        category: Optional[ConversationCategory] = None,
        patient_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ConversationRecord], int]:
        """List conversations scoped to current user's authorization."""
        # Patient filter scoping
        if current_user.role in (UserRole.PATIENT, "PATIENT"):
            patient_id = current_user.user_id
            user_id = None
        elif current_user.role in (UserRole.ADMIN, "ADMIN", "SUPERADMIN"):
            user_id = None
        else:
            # Clinician/Staff defaults to conversations where they participate or within their org
            user_id = current_user.user_id
            if current_user.organization_id and not organization_id:
                organization_id = current_user.organization_id

        return self._repo.list_conversations(
            status=status,
            category=category,
            patient_id=patient_id,
            organization_id=organization_id,
            facility_id=facility_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    def add_participant(
        self,
        conversation_id: str,
        payload: ParticipantAddRequest,
        current_user: AuthenticatedUserContext,
    ) -> ParticipantRecord:
        """Add participant to conversation."""
        conv = self.get_conversation(conversation_id, current_user)

        if conv.status == ConversationStatus.CLOSED:
            raise ConversationClosedException("Cannot add participants to a closed conversation.")
        if conv.status == ConversationStatus.LOCKED:
            raise ConversationLockedException("Cannot add participants to a locked conversation.")

        if not self._authz.can_modify_conversation(current_user, conv):
            raise ConversationAccessDeniedException("You do not have permission to add participants.")

        # Check participant limits
        active_count = sum(1 for p in conv.participants if p.is_active)
        if active_count >= self._max_participants:
            raise ParticipantLimitExceededException(
                f"Conversation cannot exceed {self._max_participants} participants."
            )

        # Check if already active
        existing = next((p for p in conv.participants if p.user_id == payload.user_id and p.is_active), None)
        if existing:
            raise ParticipantAlreadyExistsException(f"User '{payload.user_id}' is already an active participant.")

        participant = ParticipantRecord(
            participant_id=f"part-{uuid.uuid4().hex[:8]}",
            conversation_id=conversation_id,
            user_id=payload.user_id,
            role=payload.role,
            display_name=payload.display_name,
            organization_id=payload.organization_id or conv.organization_id,
            facility_id=payload.facility_id or conv.facility_id,
            joined_at=datetime.now(timezone.utc),
            is_active=True,
        )

        added = self._repo.add_participant(conversation_id, participant)
        if not added:
            raise ConversationNotFoundException(f"Conversation '{conversation_id}' was not found.")

        self._repo.record_history(
            ConversationHistoryRecord(
                id=f"hist-{uuid.uuid4().hex[:8]}",
                conversation_id=conversation_id,
                actor_id=current_user.user_id,
                action="PARTICIPANT_ADDED",
                reason=f"Added user {payload.user_id} as {payload.role}",
            )
        )

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.PARTICIPANT_ADDED,
                actor_id=current_user.user_id,
                target_id=conversation_id,
                patient_id=conv.patient_id,
                metadata={"participant_user_id": payload.user_id, "role": payload.role.value},
            )
        )

        return added

    def remove_participant(
        self,
        conversation_id: str,
        participant_id: str,
        current_user: AuthenticatedUserContext,
    ) -> bool:
        """Remove/deactivate a participant."""
        conv = self.get_conversation(conversation_id, current_user)

        if not self._authz.can_modify_conversation(current_user, conv):
            raise ConversationAccessDeniedException("You do not have permission to remove participants.")

        target_participant = next((p for p in conv.participants if p.participant_id == participant_id), None)
        if not target_participant:
            raise ParticipantNotFoundException(f"Participant '{participant_id}' was not found.")

        success = self._repo.remove_participant(conversation_id, participant_id)
        if success:
            self._repo.record_history(
                ConversationHistoryRecord(
                    id=f"hist-{uuid.uuid4().hex[:8]}",
                    conversation_id=conversation_id,
                    actor_id=current_user.user_id,
                    action="PARTICIPANT_REMOVED",
                    reason=f"Removed participant {participant_id} ({target_participant.user_id})",
                )
            )

            self._record_audit(
                AuditEventRecord(
                    event_type=AuditEventType.PARTICIPANT_REMOVED,
                    actor_id=current_user.user_id,
                    target_id=conversation_id,
                    patient_id=conv.patient_id,
                    metadata={"participant_id": participant_id, "user_id": target_participant.user_id},
                )
            )

        return success

    def close_conversation(
        self,
        conversation_id: str,
        payload: ConversationCloseRequest,
        current_user: AuthenticatedUserContext,
    ) -> ConversationRecord:
        """Close an active conversation."""
        conv = self.get_conversation(conversation_id, current_user)

        if not self._authz.can_close_conversation(current_user, conv):
            raise ConversationAccessDeniedException("You do not have permission to close this conversation.")

        if conv.status == ConversationStatus.CLOSED:
            return conv

        conv.status = ConversationStatus.CLOSED
        conv.closed_at = datetime.now(timezone.utc)
        conv.closed_by = current_user.user_id
        conv.close_reason = payload.reason

        saved = self._repo.save(conv)

        self._repo.record_history(
            ConversationHistoryRecord(
                id=f"hist-{uuid.uuid4().hex[:8]}",
                conversation_id=conversation_id,
                actor_id=current_user.user_id,
                action="CONVERSATION_CLOSED",
                previous_status=ConversationStatus.ACTIVE,
                new_status=ConversationStatus.CLOSED,
                reason=payload.reason,
            )
        )

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.CONVERSATION_CLOSED,
                actor_id=current_user.user_id,
                target_id=conversation_id,
                patient_id=conv.patient_id,
                metadata={"reason": payload.reason},
            )
        )

        return saved

    def reopen_conversation(
        self,
        conversation_id: str,
        payload: ConversationReopenRequest,
        current_user: AuthenticatedUserContext,
    ) -> ConversationRecord:
        """Reopen a closed conversation."""
        conv = self.get_conversation(conversation_id, current_user)

        if not self._authz.can_reopen_conversation(current_user, conv):
            raise ConversationAccessDeniedException("You do not have permission to reopen this conversation.")

        if conv.status == ConversationStatus.ACTIVE:
            return conv

        prev_status = conv.status
        conv.status = ConversationStatus.ACTIVE
        conv.closed_at = None
        conv.closed_by = None
        conv.close_reason = None

        saved = self._repo.save(conv)

        self._repo.record_history(
            ConversationHistoryRecord(
                id=f"hist-{uuid.uuid4().hex[:8]}",
                conversation_id=conversation_id,
                actor_id=current_user.user_id,
                action="CONVERSATION_REOPENED",
                previous_status=prev_status,
                new_status=ConversationStatus.ACTIVE,
                reason=payload.reason,
            )
        )

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.CONVERSATION_REOPENED,
                actor_id=current_user.user_id,
                target_id=conversation_id,
                patient_id=conv.patient_id,
                metadata={"reason": payload.reason},
            )
        )

        return saved

    def get_conversation_history(
        self,
        conversation_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[ConversationHistoryRecord]:
        """Retrieve audit history of conversation transitions."""
        # Validates authorization first
        self.get_conversation(conversation_id, current_user)
        return self._repo.get_history(conversation_id)

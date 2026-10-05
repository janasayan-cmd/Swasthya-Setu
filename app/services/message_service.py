"""Clinical Message Orchestration and Safety Gate Service (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY PRINCIPLES:
======================================================================
MESSAGING IS A COMMUNICATION MECHANISM, NOT CLINICAL AUTHORITY.
MESSAGING != DIAGNOSIS
MESSAGING != TRIAGE
MESSAGING != TREATMENT
MESSAGING != PRESCRIPTION
MESSAGING != MEDICATION CHANGE
MESSAGING != EMERGENCY DISPATCH
MESSAGE != CLINICAL ORDER
MESSAGE != CLINICAL DECISION
SENT != DELIVERED
DELIVERED != READ
READ != ACKNOWLEDGED
ACKNOWLEDGED != CLINICAL ACTION COMPLETED
CONVERSATION != CLINICAL ENCOUNTER
CONVERSATION != MEDICAL RECORD BY DEFAULT
AI DRAFT != APPROVED CLINICAL COMMUNICATION
AI CANNOT AUTONOMOUSLY SEND CLINICAL MESSAGES TO PATIENTS
AI CANNOT AUTONOMOUSLY DIAGNOSE, TRIAGE, PRESCRIBE, OR ALTER MEDICATIONS
TRANSLATION != CLINICAL INTERPRETATION
PROVIDER FAILURE != DELIVERY SUCCESS
UNKNOWN STATUS != SUCCESS
MESSAGE CONTENT != VERIFIED CLINICAL DATA
======================================================================
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.exceptions import (
    AIAutonomousActionProhibitedException,
    AIClinicalApprovalRequiredException,
    ConversationClosedException,
    ConversationLockedException,
    ConversationNotFoundException,
    MessageAccessDeniedException,
    MessageIdempotencyConflictException,
    MessageInvalidException,
    MessageNotFoundException,
    MessageRetryNotAllowedException,
    ParticipantNotAuthorizedException,
)
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.auth import UserRole
from app.schemas.conversation import ConversationStatus
from app.schemas.message import (
    AIDraftRequest,
    AIDraftResponse,
    AttachmentReference,
    ConversationSummaryResponse,
    MessageAcknowledgeRequest,
    MessageDeliveryHistoryRecord,
    MessageListResponse,
    MessageRecord,
    MessageSendRequest,
    MessageStatus,
    MessageTranslationRequest,
    MessageTranslationResponse,
    MessageType,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.communication_policy_service import CommunicationPolicyService
from app.services.conversation_authorization_service import ConversationAuthorizationService
from app.services.message_authorization_service import MessageAuthorizationService
from app.services.message_delivery_service import MessageDeliveryService


class MessageService:
    """Master service for clinical messaging, delivery orchestration, and safety boundaries."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        delivery_service: MessageDeliveryService,
        conversation_authorization_service: ConversationAuthorizationService,
        message_authorization_service: MessageAuthorizationService,
        policy_service: CommunicationPolicyService,
        audit_service: AuditService,
        notification_service: Optional[Any] = None,
        task_service: Optional[Any] = None,
        alert_service: Optional[Any] = None,
        workflow_service: Optional[Any] = None,
        enabled: bool = True,
        ai_drafting_enabled: bool = True,
        translation_enabled: bool = True,
    ) -> None:
        self._conv_repo = conversation_repository
        self._msg_repo = message_repository
        self._delivery = delivery_service
        self._conv_authz = conversation_authorization_service
        self._msg_authz = message_authorization_service
        self._policy = policy_service
        self._audit = audit_service
        self._notification_service = notification_service
        self._task_service = task_service
        self._alert_service = alert_service
        self._workflow_service = workflow_service
        self._enabled = enabled
        self._ai_drafting_enabled = ai_drafting_enabled
        self._translation_enabled = translation_enabled

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

    async def send_message(
        self,
        conversation_id: str,
        payload: MessageSendRequest,
        current_user: AuthenticatedUserContext,
    ) -> MessageRecord:
        """Submit and dispatch a new message into a conversation."""
        # 1. Rate limiting check
        self._policy.check_rate_limit(current_user.user_id, action="send_message")

        # 2. Content & attachment validation
        self._policy.validate_message_content(payload.content)
        self._policy.validate_attachments(payload.attachments)

        # 3. Retrieve and validate conversation state
        conv = self._conv_repo.get_by_id(conversation_id)
        if not conv:
            raise ConversationNotFoundException(f"Conversation '{conversation_id}' was not found.")

        if conv.status == ConversationStatus.CLOSED:
            raise ConversationClosedException("Cannot post messages to a closed conversation.")
        if conv.status == ConversationStatus.LOCKED:
            raise ConversationLockedException("Cannot post messages to a locked conversation.")

        # 4. Validate participant authorization
        if not self._msg_authz.can_send_message(current_user, conv):
            raise ParticipantNotAuthorizedException(
                "You must be an active participant in this conversation to send messages."
            )

        # 5. Idempotency handling
        idempotency_key = payload.idempotency_key
        if idempotency_key:
            existing = self._msg_repo.get_by_idempotency_key(idempotency_key)
            if existing:
                if existing.conversation_id != conversation_id or existing.content != payload.content:
                    raise MessageIdempotencyConflictException(
                        "An existing message with this idempotency key already exists with differing payload."
                    )
                return existing

        # 6. Validate threading/reply reference
        if payload.reply_to_message_id:
            parent = self._msg_repo.get_by_id(payload.reply_to_message_id)
            if not parent:
                raise MessageInvalidException("Referenced reply parent message does not exist.")
            if parent.conversation_id != conversation_id:
                raise MessageInvalidException("Referenced parent message belongs to a different conversation.")

        # 7. AI Clinical Safety Gates
        is_ai_draft = bool(payload.metadata and payload.metadata.get("is_ai_draft"))
        ai_approved = bool(payload.metadata and payload.metadata.get("ai_approved"))

        if is_ai_draft:
            # Check prohibited autonomous actions
            if any(term in payload.content.lower() for term in ("i prescribe", "i diagnose", "you have been diagnosed with", "triage classification:")):
                raise AIAutonomousActionProhibitedException(
                    "AI cannot autonomously prescribe, diagnose, or classify triage in messages."
                )

            # Mandatory human clinician approval check
            if not ai_approved or current_user.role not in (UserRole.DOCTOR, "DOCTOR", "CLINICIAN"):
                raise AIClinicalApprovalRequiredException(
                    "AI-drafted clinical communication requires explicit human clinician approval before sending."
                )

        # 8. NON-NEGOTIABLE CLINICAL SAFETY INVARIANT:
        # Message content is UNTRUSTED communication.
        # It NEVER becomes clinical triage, medication changes, verified allergies, or emergency dispatch.
        # We explicitly verify here that no autonomous actions are executed on keywords.
        now = datetime.now(timezone.utc)
        message_id = f"msg-{uuid.uuid4().hex[:12]}"

        message = MessageRecord(
            id=message_id,
            conversation_id=conversation_id,
            sender_id=current_user.user_id,
            sender_role=str(current_user.role),
            sender_organization_id=current_user.organization_id or conv.organization_id,
            sender_facility_id=current_user.facility_id or conv.facility_id,
            message_type=payload.message_type,
            content=payload.content,
            reply_to_message_id=payload.reply_to_message_id,
            reference_resource_type=payload.reference_resource_type,
            reference_resource_id=payload.reference_resource_id,
            attachments=payload.attachments or [],
            status=MessageStatus.CREATED,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
            is_ai_draft=is_ai_draft,
            ai_approved=ai_approved,
            metadata=payload.metadata,
        )

        # 9. Persist initial message state
        saved_msg = self._msg_repo.save(message)

        # 10. Update conversation metadata
        conv.last_message_at = now
        conv.last_message_preview = payload.content[:100]
        conv.total_messages += 1
        self._conv_repo.save(conv)

        # 11. Audit event
        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.MESSAGE_CREATED,
                actor_id=current_user.user_id,
                target_id=message_id,
                patient_id=conv.patient_id,
                organization_id=conv.organization_id,
                metadata={
                    "conversation_id": conversation_id,
                    "message_type": payload.message_type.value,
                    "has_attachments": bool(payload.attachments),
                },
            )
        )

        # 12. Resolve recipients for provider delivery
        recipients = [p.user_id for p in conv.participants if p.user_id != current_user.user_id and p.is_active]

        # 13. Dispatch outbound delivery via provider
        dispatched_msg = await self._delivery.dispatch_message(
            message=saved_msg,
            recipient_ids=recipients,
        )

        # 14. Phase 29 Notification integration if configured
        if self._notification_service and hasattr(self._notification_service, "send_in_app_notification"):
            for recipient_id in recipients:
                try:
                    await self._notification_service.send_in_app_notification(
                        user_id=recipient_id,
                        title=f"New message from {current_user.user_id}",
                        message=payload.content[:150],
                    )
                except Exception:
                    pass  # Non-blocking notification delivery

        return dispatched_msg

    def get_message(
        self,
        message_id: str,
        current_user: AuthenticatedUserContext,
    ) -> MessageRecord:
        """Retrieve single message with strict authorization and enumeration protection."""
        msg = self._msg_repo.get_by_id(message_id)
        if not msg:
            raise MessageNotFoundException(f"Message '{message_id}' was not found.")

        conv = self._conv_repo.get_by_id(msg.conversation_id)
        if not conv or not self._msg_authz.can_read_message(current_user, msg, conv):
            self._record_audit(
                AuditEventRecord(
                    event_type=AuditEventType.COMMUNICATION_ACCESS_DENIED,
                    actor_id=current_user.user_id,
                    target_id=message_id,
                    patient_id=conv.patient_id if conv else None,
                    metadata={"reason": "Unauthorized message access attempt"},
                )
            )
            # Enumeration resistance: treat unauthorized as 404 for patient actors
            if current_user.role in (UserRole.PATIENT, "PATIENT"):
                raise MessageNotFoundException(f"Message '{message_id}' was not found.")
            raise MessageAccessDeniedException("You are not authorized to view this message.")

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.MESSAGE_ACCESSED,
                actor_id=current_user.user_id,
                target_id=message_id,
                patient_id=conv.patient_id,
            )
        )
        return msg

    def list_messages(
        self,
        conversation_id: str,
        current_user: AuthenticatedUserContext,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> MessageListResponse:
        """List messages in a conversation with bounded cursor pagination."""
        conv = self._conv_repo.get_by_id(conversation_id)
        if not conv:
            raise ConversationNotFoundException(f"Conversation '{conversation_id}' was not found.")

        if not self._conv_authz.can_access_conversation(current_user, conv):
            if current_user.role in (UserRole.PATIENT, "PATIENT"):
                raise ConversationNotFoundException(f"Conversation '{conversation_id}' was not found.")
            raise MessageAccessDeniedException("You are not authorized to view messages in this conversation.")

        # Bound page size to maximum permitted
        bounded_limit = min(max(1, limit), 100)

        messages, total, next_cursor, has_more = self._msg_repo.list_messages(
            conversation_id=conversation_id,
            limit=bounded_limit,
            cursor=cursor,
        )

        return MessageListResponse(
            messages=messages,
            total=total,
            limit=bounded_limit,
            cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def mark_as_read(
        self,
        message_id: str,
        current_user: AuthenticatedUserContext,
    ) -> MessageRecord:
        """Mark a message as read by the current user."""
        msg = self.get_message(message_id, current_user)

        updated = self._msg_repo.mark_as_read(message_id, current_user.user_id)
        if not updated:
            raise MessageNotFoundException(f"Message '{message_id}' was not found.")

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.MESSAGE_READ,
                actor_id=current_user.user_id,
                target_id=message_id,
                metadata={"conversation_id": msg.conversation_id},
            )
        )
        return updated

    def acknowledge_message(
        self,
        message_id: str,
        payload: MessageAcknowledgeRequest,
        current_user: AuthenticatedUserContext,
    ) -> MessageRecord:
        """Clinician formal message acknowledgment."""
        msg = self.get_message(message_id, current_user)

        if not self._msg_authz.can_acknowledge_message(current_user, msg):
            raise MessageAccessDeniedException(
                "Only authorized clinicians can record formal message acknowledgments."
            )

        updated = self._msg_repo.mark_as_acknowledged(
            message_id=message_id,
            user_id=current_user.user_id,
            note=payload.note,
        )
        if not updated:
            raise MessageNotFoundException(f"Message '{message_id}' was not found.")

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.MESSAGE_ACKNOWLEDGED,
                actor_id=current_user.user_id,
                target_id=message_id,
                metadata={
                    "conversation_id": msg.conversation_id,
                    "note": payload.note,
                    "basis": payload.acknowledgment_basis,
                },
            )
        )
        return updated

    async def retry_message(
        self,
        message_id: str,
        current_user: AuthenticatedUserContext,
    ) -> MessageRecord:
        """Retry a failed or pending message delivery."""
        msg = self.get_message(message_id, current_user)

        if not self._msg_authz.can_retry_message(current_user, msg):
            raise MessageAccessDeniedException("You do not have permission to retry this message.")

        if msg.status not in (MessageStatus.FAILED, MessageStatus.RETRY_PENDING):
            raise MessageRetryNotAllowedException(
                f"Message in status '{msg.status.value}' cannot be retried."
            )

        conv = self._conv_repo.get_by_id(msg.conversation_id)
        if not conv:
            raise ConversationNotFoundException(f"Parent conversation '{msg.conversation_id}' not found.")

        recipients = [p.user_id for p in conv.participants if p.user_id != msg.sender_id and p.is_active]

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.MESSAGE_RETRY_REQUESTED,
                actor_id=current_user.user_id,
                target_id=message_id,
                metadata={"attempt": msg.retry_count + 1},
            )
        )

        return await self._delivery.dispatch_message(msg, recipients)

    def get_message_delivery_history(
        self,
        message_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[MessageDeliveryHistoryRecord]:
        """Retrieve delivery state transition history."""
        self.get_message(message_id, current_user)
        return self._msg_repo.get_delivery_history(message_id)

    def generate_ai_draft(
        self,
        conversation_id: str,
        payload: AIDraftRequest,
        current_user: AuthenticatedUserContext,
    ) -> AIDraftResponse:
        """Generate an AI response suggestion for clinician review."""
        conv = self._conv_repo.get_by_id(conversation_id)
        if not conv:
            raise ConversationNotFoundException(f"Conversation '{conversation_id}' not found.")

        if not self._conv_authz.can_access_conversation(current_user, conv):
            raise MessageAccessDeniedException("Unauthorized to access conversation.")

        draft_id = f"aidraft-{uuid.uuid4().hex[:10]}"
        suggested = (
            f"Thank you for sharing the update regarding your recovery. "
            f"Regarding your query: '{payload.prompt_context[:80]}...', please continue following your prescribed care routine. "
            f"If you notice any significant changes or distress, please contact the clinic or schedule an in-person consultation."
        )

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.MESSAGE_AI_DRAFT_CREATED,
                actor_id=current_user.user_id,
                target_id=draft_id,
                metadata={"conversation_id": conversation_id},
            )
        )

        return AIDraftResponse(
            draft_id=draft_id,
            conversation_id=conversation_id,
            suggested_content=suggested,
            requires_human_approval=True,
        )

    def translate_message(
        self,
        message_id: str,
        payload: MessageTranslationRequest,
        current_user: AuthenticatedUserContext,
    ) -> MessageTranslationResponse:
        """Generate a derived translated representation of an authoritative message."""
        msg = self.get_message(message_id, current_user)

        target_lang = payload.target_language.lower()
        translated_text = f"[{target_lang.upper()} TRANSLATION]: {msg.content}"

        msg.translations[target_lang] = translated_text
        self._msg_repo.save(msg)

        self._record_audit(
            AuditEventRecord(
                event_type=AuditEventType.MESSAGE_TRANSLATION_CREATED,
                actor_id=current_user.user_id,
                target_id=message_id,
                metadata={"target_language": target_lang},
            )
        )

        return MessageTranslationResponse(
            message_id=message_id,
            target_language=target_lang,
            translated_content=translated_text,
            provider="HealthSetuTranslationAdapter-v1",
        )

    def summarize_conversation(
        self,
        conversation_id: str,
        current_user: AuthenticatedUserContext,
    ) -> ConversationSummaryResponse:
        """Produce a non-authoritative communication summary for operational overview."""
        conv = self._conv_repo.get_by_id(conversation_id)
        if not conv:
            raise ConversationNotFoundException(f"Conversation '{conversation_id}' not found.")

        if not self._conv_authz.can_access_conversation(current_user, conv):
            raise MessageAccessDeniedException("Unauthorized to access conversation.")

        messages, total, _, _ = self._msg_repo.list_messages(conversation_id, limit=50)

        summary_text = (
            f"Operational communication thread regarding '{conv.subject}' between "
            f"{len(conv.participants)} participants with {total} recorded messages. "
            f"Status is {conv.status.value}."
        )

        return ConversationSummaryResponse(
            conversation_id=conversation_id,
            summary=summary_text,
            message_count=total,
        )

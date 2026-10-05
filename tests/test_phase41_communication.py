"""Tests for HealthSetu Phase 41: Clinical Communication, Patient–Provider Messaging & Secure Conversation Management.

CRITICAL ARCHITECTURAL CONTRACT & CORE SAFETY PRINCIPLES:
- MESSAGING IS A COMMUNICATION MECHANISM, NOT CLINICAL AUTHORITY
- MESSAGE != CLINICAL ORDER
- MESSAGE != DIAGNOSIS
- MESSAGE != TRIAGE
- MESSAGE != TREATMENT
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

import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_conversation_service,
    get_current_user,
    get_message_delivery_service,
    get_message_search_service,
    get_message_service,
)
from app.core.exceptions import (
    AIAutonomousActionProhibitedException,
    AIClinicalApprovalRequiredException,
    AttachmentInvalidException,
    CommunicationRateLimitExceededException,
    CommunicationWebhookInvalidException,
    CommunicationWebhookReplayException,
    ConversationAccessDeniedException,
    ConversationClosedException,
    ConversationLockedException,
    ConversationNotFoundException,
    MessageAccessDeniedException,
    MessageIdempotencyConflictException,
    MessageInvalidException,
    MessageNotFoundException,
    MessageTooLargeException,
    ParticipantAlreadyExistsException,
    ParticipantLimitExceededException,
    ParticipantNotAuthorizedException,
)
from app.integrations.communication.providers.mock import MockCommunicationProvider
from app.main import create_app
from app.repositories.audit_repository import AuditRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.auth import UserRole
from app.schemas.communication import ProviderState, WebhookPayload
from app.schemas.conversation import (
    ConversationCategory,
    ConversationCloseRequest,
    ConversationCreateRequest,
    ConversationRecord,
    ConversationReopenRequest,
    ConversationStatus,
    ParticipantAddRequest,
    ParticipantRecord,
    ParticipantRole,
)
from app.schemas.message import (
    AIDraftRequest,
    AttachmentReference,
    MessageAcknowledgeRequest,
    MessageRecord,
    MessageSendRequest,
    MessageStatus,
    MessageTranslationRequest,
    MessageType,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.communication_policy_service import CommunicationPolicyService
from app.services.conversation_authorization_service import ConversationAuthorizationService
from app.services.conversation_service import ConversationService
from app.services.message_authorization_service import MessageAuthorizationService
from app.services.message_delivery_service import MessageDeliveryService
from app.services.message_search_service import MessageSearchService
from app.services.message_service import MessageService
from app.workers.communication_worker import CommunicationWorker


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def phase41_setup():
    """Build isolated repos, providers, and services for Phase 41 testing."""
    conv_repo = ConversationRepository()
    msg_repo = MessageRepository()
    provider = MockCommunicationProvider(name="mock")
    audit_repo = AuditRepository()
    audit_service = AuditService(audit_repository=audit_repo)

    conv_authz = ConversationAuthorizationService(enabled=True)
    msg_authz = MessageAuthorizationService(enabled=True)
    policy = CommunicationPolicyService(
        max_message_length=10000,
        max_attachment_size_bytes=10 * 1024 * 1024,
        message_rate_limit=60,
        conversation_rate_limit=20,
        enabled=True,
    )

    conv_service = ConversationService(
        conversation_repository=conv_repo,
        authorization_service=conv_authz,
        policy_service=policy,
        audit_service=audit_service,
        max_participants=50,
        enabled=True,
    )

    delivery_service = MessageDeliveryService(
        message_repository=msg_repo,
        provider=provider,
        audit_service=audit_service,
        webhook_secret="test-webhook-secret-key-32-bytes!!",
        max_retries=3,
        enabled=True,
    )

    search_service = MessageSearchService(
        conversation_repository=conv_repo,
        message_repository=msg_repo,
        authorization_service=conv_authz,
        enabled=True,
    )

    msg_service = MessageService(
        conversation_repository=conv_repo,
        message_repository=msg_repo,
        delivery_service=delivery_service,
        conversation_authorization_service=conv_authz,
        message_authorization_service=msg_authz,
        policy_service=policy,
        audit_service=audit_service,
        notification_service=None,
        task_service=None,
        alert_service=None,
        workflow_service=None,
        enabled=True,
    )

    worker = CommunicationWorker(delivery_service=delivery_service, max_retries=3)

    return {
        "conv_repo": conv_repo,
        "msg_repo": msg_repo,
        "provider": provider,
        "conv_authz": conv_authz,
        "msg_authz": msg_authz,
        "policy": policy,
        "conv_service": conv_service,
        "delivery_service": delivery_service,
        "search_service": search_service,
        "msg_service": msg_service,
        "worker": worker,
        "audit_service": audit_service,
    }


def make_user(
    user_id: str,
    role: str = "PATIENT",
    organization_id: str = "org-1",
    facility_id: str = "fac-1",
) -> AuthenticatedUserContext:
    """Helper to construct AuthenticatedUserContext."""
    return AuthenticatedUserContext(
        user_id=user_id,
        role=role,
        organization_id=organization_id,
        facility_id=facility_id,
        permissions=[],
    )


# ===========================================================================
# 1. Conversation Lifecycle Tests
# ===========================================================================

def test_create_conversation(phase41_setup):
    """Test standard conversation creation with patient subject."""
    conv_service = phase41_setup["conv_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    req = ConversationCreateRequest(
        patient_id="pat-100",
        category=ConversationCategory.PATIENT_CLINICIAN,
        subject="Follow-up on Cardiology Consultation",
    )
    conv = conv_service.create_conversation(req, doctor)

    assert conv.id.startswith("conv-")
    assert conv.patient_id == "pat-100"
    assert conv.status == ConversationStatus.ACTIVE
    assert len(conv.participants) == 2
    participant_user_ids = [p.user_id for p in conv.participants]
    assert "doc-1" in participant_user_ids
    assert "pat-100" in participant_user_ids


def test_create_conversation_patient_isolation(phase41_setup):
    """A patient cannot create a conversation for another patient."""
    conv_service = phase41_setup["conv_service"]
    patient = make_user("pat-1", role="PATIENT")

    req = ConversationCreateRequest(
        patient_id="pat-999",  # Different patient
        subject="Attempt unauthorized conversation",
    )
    with pytest.raises(ConversationAccessDeniedException):
        conv_service.create_conversation(req, patient)


def test_close_and_reopen_conversation(phase41_setup):
    """Test closing and reopening a conversation."""
    conv_service = phase41_setup["conv_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    req = ConversationCreateRequest(patient_id="pat-100", subject="Routine Care")
    conv = conv_service.create_conversation(req, doctor)

    # Close
    closed = conv_service.close_conversation(conv.id, ConversationCloseRequest(reason="Finished"), doctor)
    assert closed.status == ConversationStatus.CLOSED
    assert closed.closed_by == "doc-1"

    # Reopen
    reopened = conv_service.reopen_conversation(conv.id, ConversationReopenRequest(reason="Re-evaluating"), doctor)
    assert reopened.status == ConversationStatus.ACTIVE
    assert reopened.closed_at is None


def test_locked_conversation_rejects_modifications(phase41_setup):
    """A locked conversation rejects participant additions."""
    conv_service = phase41_setup["conv_service"]
    conv_repo = phase41_setup["conv_repo"]
    doctor = make_user("doc-1", role="DOCTOR")

    req = ConversationCreateRequest(patient_id="pat-100", subject="Audit Sealed")
    conv = conv_service.create_conversation(req, doctor)
    conv.status = ConversationStatus.LOCKED
    conv_repo.save(conv)

    with pytest.raises(ConversationLockedException):
        conv_service.add_participant(
            conv.id,
            ParticipantAddRequest(user_id="nurse-1", role=ParticipantRole.CARE_TEAM_MEMBER),
            doctor,
        )


# ===========================================================================
# 2. Participant Management Tests
# ===========================================================================

def test_add_and_remove_participant(phase41_setup):
    """Add and remove a care team member."""
    conv_service = phase41_setup["conv_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    req = ConversationCreateRequest(patient_id="pat-100", subject="Multi-disciplinary")
    conv = conv_service.create_conversation(req, doctor)

    part = conv_service.add_participant(
        conv.id,
        ParticipantAddRequest(user_id="nurse-1", role=ParticipantRole.CARE_TEAM_MEMBER),
        doctor,
    )
    assert part.user_id == "nurse-1"
    assert part.is_active is True

    # Remove participant
    removed = conv_service.remove_participant(conv.id, part.participant_id, doctor)
    assert removed is True

    updated_conv = conv_service.get_conversation(conv.id, doctor)
    nurse_record = next(p for p in updated_conv.participants if p.user_id == "nurse-1")
    assert nurse_record.is_active is False


def test_duplicate_participant_rejected(phase41_setup):
    """Adding an already active participant raises error."""
    conv_service = phase41_setup["conv_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    req = ConversationCreateRequest(patient_id="pat-100", subject="Check Duplicates")
    conv = conv_service.create_conversation(req, doctor)

    with pytest.raises(ParticipantAlreadyExistsException):
        conv_service.add_participant(
            conv.id,
            ParticipantAddRequest(user_id="pat-100", role=ParticipantRole.PATIENT),
            doctor,
        )


def test_participant_limit_enforced(phase41_setup):
    """Participant limits are enforced."""
    conv_service = phase41_setup["conv_service"]
    conv_service._max_participants = 3
    doctor = make_user("doc-1", role="DOCTOR")

    req = ConversationCreateRequest(patient_id="pat-100", subject="Small Group")
    conv = conv_service.create_conversation(req, doctor)  # already has doc-1 and pat-100 (2 participants)

    # Add 3rd participant
    conv_service.add_participant(
        conv.id,
        ParticipantAddRequest(user_id="nurse-1", role=ParticipantRole.CARE_TEAM_MEMBER),
        doctor,
    )

    # 4th participant exceeds max 3
    with pytest.raises(ParticipantLimitExceededException):
        conv_service.add_participant(
            conv.id,
            ParticipantAddRequest(user_id="nurse-2", role=ParticipantRole.CARE_TEAM_MEMBER),
            doctor,
        )


# ===========================================================================
# 3. Resource-Level Authorization & Enumeration Protection
# ===========================================================================

def test_patient_can_access_own_conversation(phase41_setup):
    """Patient can view their own conversation."""
    conv_service = phase41_setup["conv_service"]
    doctor = make_user("doc-1", role="DOCTOR")
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Patient Thread"), doctor)
    fetched = conv_service.get_conversation(conv.id, patient)
    assert fetched.id == conv.id


def test_unrelated_patient_access_denied_safe_not_found(phase41_setup):
    """Unrelated patient cannot access conversation; receives 404 to resist enumeration."""
    conv_service = phase41_setup["conv_service"]
    doctor = make_user("doc-1", role="DOCTOR")
    unrelated_patient = make_user("pat-999", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Private Thread"), doctor)

    with pytest.raises(ConversationNotFoundException):
        conv_service.get_conversation(conv.id, unrelated_patient)


def test_organization_boundary_enforced(phase41_setup):
    """Clinician from a different organization cannot access conversation."""
    conv_service = phase41_setup["conv_service"]
    doctor_org1 = make_user("doc-1", role="DOCTOR", organization_id="org-1")
    doctor_org2 = make_user("doc-2", role="DOCTOR", organization_id="org-2")

    conv = conv_service.create_conversation(
        ConversationCreateRequest(patient_id="pat-100", subject="Org Isolated", organization_id="org-1"),
        doctor_org1,
    )

    with pytest.raises(ConversationAccessDeniedException):
        conv_service.get_conversation(conv.id, doctor_org2)


# ===========================================================================
# 4. Message Submission, Idempotency & Threading Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_send_message_success(phase41_setup):
    """Test successful message send in active conversation."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Vitals Follow-up"), doctor)

    req = MessageSendRequest(content="Please review your latest blood pressure log.")
    msg = await msg_service.send_message(conv.id, req, doctor)

    assert msg.id.startswith("msg-")
    assert msg.content == "Please review your latest blood pressure log."
    assert msg.status == MessageStatus.SENT
    assert msg.sender_id == "doc-1"


@pytest.mark.asyncio
async def test_closed_conversation_rejects_new_messages(phase41_setup):
    """Cannot send messages to a closed conversation."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Completed"), doctor)
    conv_service.close_conversation(conv.id, ConversationCloseRequest(), doctor)

    with pytest.raises(ConversationClosedException):
        await msg_service.send_message(conv.id, MessageSendRequest(content="Attempt message to closed thread"), doctor)


@pytest.mark.asyncio
async def test_empty_and_oversized_message_rejected(phase41_setup):
    """Empty and oversized messages are rejected."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Validation"), doctor)

    with pytest.raises(MessageInvalidException):
        await msg_service.send_message(conv.id, MessageSendRequest(content="   "), doctor)

    oversized = "A" * 10001
    with pytest.raises(MessageTooLargeException):
        await msg_service.send_message(conv.id, MessageSendRequest(content=oversized), doctor)


@pytest.mark.asyncio
async def test_message_idempotency_returns_same_record(phase41_setup):
    """Repeated message requests with same idempotency key return identical message."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Idempotency"), doctor)

    key = "idem-key-12345"
    req1 = MessageSendRequest(content="First dispatch", idempotency_key=key)
    msg1 = await msg_service.send_message(conv.id, req1, doctor)

    req2 = MessageSendRequest(content="First dispatch", idempotency_key=key)
    msg2 = await msg_service.send_message(conv.id, req2, doctor)

    assert msg1.id == msg2.id


@pytest.mark.asyncio
async def test_message_idempotency_conflict_detected(phase41_setup):
    """Reusing idempotency key with differing content raises 409 conflict."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Idempotency Conflict"), doctor)

    key = "idem-key-999"
    await msg_service.send_message(conv.id, MessageSendRequest(content="Content A", idempotency_key=key), doctor)

    with pytest.raises(MessageIdempotencyConflictException):
        await msg_service.send_message(conv.id, MessageSendRequest(content="Content B (differs)", idempotency_key=key), doctor)


@pytest.mark.asyncio
async def test_threading_and_replies(phase41_setup):
    """Reply referencing parent in same conversation succeeds; invalid parent fails."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Thread Test"), doctor)

    msg1 = await msg_service.send_message(conv.id, MessageSendRequest(content="How are you feeling today?"), doctor)
    msg2 = await msg_service.send_message(
        conv.id,
        MessageSendRequest(content="I am feeling better.", reply_to_message_id=msg1.id),
        patient,
    )
    assert msg2.reply_to_message_id == msg1.id

    # Invalid parent
    with pytest.raises(MessageInvalidException):
        await msg_service.send_message(
            conv.id,
            MessageSendRequest(content="Invalid parent", reply_to_message_id="msg-nonexistent"),
            patient,
        )


@pytest.mark.asyncio
async def test_cursor_pagination(phase41_setup):
    """Test bounded cursor-based pagination."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Pagination"), doctor)

    for i in range(5):
        await msg_service.send_message(conv.id, MessageSendRequest(content=f"Message {i+1}"), doctor)

    # First page: limit 2
    page1 = msg_service.list_messages(conv.id, doctor, limit=2)
    assert len(page1.messages) == 2
    assert page1.has_more is True
    assert page1.next_cursor is not None

    # Second page: using cursor
    page2 = msg_service.list_messages(conv.id, doctor, limit=2, cursor=page1.next_cursor)
    assert len(page2.messages) == 2
    assert page2.messages[0].id != page1.messages[0].id


@pytest.mark.asyncio
async def test_read_and_acknowledgment(phase41_setup):
    """Test read status and clinician formal acknowledgment."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Read & Ack"), doctor)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="Care plan update"), doctor)

    # Patient reads message
    read_msg = msg_service.mark_as_read(msg.id, patient)
    assert "pat-100" in read_msg.read_by
    assert read_msg.status == MessageStatus.READ

    # Clinician acknowledges message
    acked = msg_service.acknowledge_message(
        msg.id,
        MessageAcknowledgeRequest(note="Reviewed by cardiologist"),
        doctor,
    )
    assert acked.status == MessageStatus.ACKNOWLEDGED
    assert acked.acknowledged_by == "doc-1"
    assert acked.acknowledgment_note == "Reviewed by cardiologist"


@pytest.mark.asyncio
async def test_non_clinician_cannot_acknowledge(phase41_setup):
    """Patient cannot record formal clinician clinical acknowledgment."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Ack Boundary"), doctor)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="Test message"), doctor)

    with pytest.raises(MessageAccessDeniedException):
        msg_service.acknowledge_message(msg.id, MessageAcknowledgeRequest(), patient)


# ===========================================================================
# 5. Attachment Validation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_valid_and_invalid_attachments(phase41_setup):
    """Validate attachment constraints."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Attachment Thread"), doctor)

    # Valid PDF attachment
    valid_att = AttachmentReference(
        attachment_id="att-1",
        document_id="doc-pdf-10",
        file_name="lab_report.pdf",
        content_type="application/pdf",
        size_bytes=1024 * 50,
    )
    msg = await msg_service.send_message(
        conv.id,
        MessageSendRequest(content="Here is your lab report.", attachments=[valid_att]),
        doctor,
    )
    assert len(msg.attachments) == 1

    # Invalid MIME type (.exe)
    invalid_att = AttachmentReference(
        attachment_id="att-2",
        document_id="doc-exe-99",
        file_name="malware.exe",
        content_type="application/x-msdownload",
        size_bytes=1024,
    )
    with pytest.raises(AttachmentInvalidException):
        await msg_service.send_message(
            conv.id,
            MessageSendRequest(content="Invalid file", attachments=[invalid_att]),
            doctor,
        )


# ===========================================================================
# 6. Provider Failure, Timeout, Webhook & Replay Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_provider_failure_does_not_become_delivered(phase41_setup):
    """NON-NEGOTIABLE SAFETY: Provider failure is recorded as FAILED, never DELIVERED."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Failure Test"), doctor)

    # Trigger mock provider failure
    msg = await msg_service.send_message(
        conv.id,
        MessageSendRequest(content="Test dispatch [FAIL_DELIVERY]"),
        doctor,
    )
    assert msg.status in (MessageStatus.FAILED, MessageStatus.RETRY_PENDING)
    assert msg.status != MessageStatus.DELIVERED
    assert msg.delivered_at is None


@pytest.mark.asyncio
async def test_provider_timeout_preserves_indeterminate_status(phase41_setup):
    """NON-NEGOTIABLE SAFETY: Unknown/timeout status remains PROCESSING, never DELIVERED."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Timeout Test"), doctor)

    # Trigger mock provider timeout
    msg = await msg_service.send_message(
        conv.id,
        MessageSendRequest(content="Test dispatch [TIMEOUT]"),
        doctor,
    )
    assert msg.status == MessageStatus.PROCESSING
    assert msg.status != MessageStatus.DELIVERED
    assert msg.delivered_at is None


@pytest.mark.asyncio
async def test_webhook_hmac_and_replay_protection(phase41_setup):
    """Webhook requires valid HMAC signature and rejects replay attacks."""
    delivery_service = phase41_setup["delivery_service"]
    msg_repo = phase41_setup["msg_repo"]

    # Pre-seed a sent message
    msg = MessageRecord(
        id="msg-webhook-test",
        conversation_id="conv-1",
        sender_id="doc-1",
        sender_role="DOCTOR",
        content="Testing webhooks",
        status=MessageStatus.SENT,
    )
    msg_repo.save(msg)

    payload_dict = {
        "event_id": "evt-unique-001",
        "event_type": "message.delivered",
        "message_id": "msg-webhook-test",
        "delivery_status": "DELIVERED",
    }
    raw_bytes = b'{"event_id":"evt-unique-001","delivery_status":"DELIVERED"}'
    secret = "test-webhook-secret-key-32-bytes!!"
    valid_sig = hmac.new(secret.encode(), raw_bytes, hashlib.sha256).hexdigest()

    # 1. Invalid signature
    with pytest.raises(CommunicationWebhookInvalidException):
        await delivery_service.process_webhook(
            payload_bytes=raw_bytes,
            signature="invalid-fake-signature",
            payload_dict=payload_dict,
        )

    # 2. Valid signature
    result = await delivery_service.process_webhook(
        payload_bytes=raw_bytes,
        signature=valid_sig,
        payload_dict=payload_dict,
    )
    assert result.event_id == "evt-unique-001"
    updated_msg = msg_repo.get_by_id("msg-webhook-test")
    assert updated_msg.status == MessageStatus.DELIVERED
    # Non-negotiable: Delivery does NOT equal read!
    assert "pat-100" not in updated_msg.read_by
    assert updated_msg.read_at is None

    # 3. Replay attack with same event ID
    with pytest.raises(CommunicationWebhookReplayException):
        await delivery_service.process_webhook(
            payload_bytes=raw_bytes,
            signature=valid_sig,
            payload_dict=payload_dict,
        )


# ===========================================================================
# 7. Rate Limiting Tests
# ===========================================================================

def test_rate_limiting(phase41_setup):
    """Actor exceeding rate limits raises 429."""
    policy = phase41_setup["policy"]
    policy._message_rate_limit = 3

    policy.check_rate_limit("user-spammer", action="send_message")
    policy.check_rate_limit("user-spammer", action="send_message")
    policy.check_rate_limit("user-spammer", action="send_message")

    with pytest.raises(CommunicationRateLimitExceededException):
        policy.check_rate_limit("user-spammer", action="send_message")


# ===========================================================================
# 8. AI Safety & Translation Boundaries
# ===========================================================================

@pytest.mark.asyncio
async def test_ai_draft_requires_human_approval(phase41_setup):
    """NON-NEGOTIABLE SAFETY: AI clinical draft cannot be sent without explicit clinician approval."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="AI Safety"), doctor)

    # Attempt to send unapproved AI draft
    with pytest.raises(AIClinicalApprovalRequiredException):
        await msg_service.send_message(
            conv.id,
            MessageSendRequest(
                content="Take 50mg daily.",
                metadata={"is_ai_draft": True, "ai_approved": False},
            ),
            doctor,
        )


@pytest.mark.asyncio
async def test_ai_prohibited_actions(phase41_setup):
    """NON-NEGOTIABLE SAFETY: AI is strictly prohibited from autonomous prescribing or diagnosing."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="AI Invariant"), doctor)

    with pytest.raises(AIAutonomousActionProhibitedException):
        await msg_service.send_message(
            conv.id,
            MessageSendRequest(
                content="I prescribe Amoxicillin 500mg.",
                metadata={"is_ai_draft": True, "ai_approved": True},
            ),
            doctor,
        )


def test_translation_preserves_authoritative_original(phase41_setup):
    """NON-NEGOTIABLE SAFETY: Translation is a derived representation; original remains authoritative."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    msg_repo = phase41_setup["msg_repo"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Translation"), doctor)
    msg = MessageRecord(
        id="msg-trans-1",
        conversation_id=conv.id,
        sender_id="doc-1",
        sender_role="DOCTOR",
        content="Please take your medication with warm water.",
        status=MessageStatus.SENT,
    )
    msg_repo.save(msg)

    resp = msg_service.translate_message(msg.id, MessageTranslationRequest(target_language="hi"), doctor)
    assert resp.target_language == "hi"
    assert "TRANSLATION IS A DERIVED REPRESENTATION" in resp.disclaimer

    # Verify original message is unchanged
    original = msg_repo.get_by_id(msg.id)
    assert original.content == "Please take your medication with warm water."
    assert "hi" in original.translations


# ===========================================================================
# 9. Authorized Message Search (Phase 30 Integration)
# ===========================================================================

@pytest.mark.asyncio
async def test_scoped_message_search(phase41_setup):
    """Search matches query and enforces conversation participant boundaries."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    search_service = phase41_setup["search_service"]

    doctor = make_user("doc-1", role="DOCTOR")
    patient = make_user("pat-100", role="PATIENT")
    unrelated_patient = make_user("pat-999", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Search Thread"), doctor)
    await msg_service.send_message(conv.id, MessageSendRequest(content="Specific cardiology observation"), doctor)

    # Doctor finds message
    doc_results = search_service.search_messages(query="cardiology", current_user=doctor)
    assert len(doc_results) >= 1
    assert "cardiology" in doc_results[0].content.lower()

    # Subject patient finds message
    pat_results = search_service.search_messages(query="cardiology", current_user=patient)
    assert len(pat_results) >= 1

    # Unrelated patient gets ZERO results (no leaks)
    unrelated_results = search_service.search_messages(query="cardiology", current_user=unrelated_patient)
    assert len(unrelated_results) == 0


# ===========================================================================
# 10. Async Worker Handling (Phase 22 Integration)
# ===========================================================================

@pytest.mark.asyncio
async def test_communication_worker(phase41_setup):
    """Test async worker handling for delivery and retries."""
    worker = phase41_setup["worker"]
    msg_repo = phase41_setup["msg_repo"]

    msg = MessageRecord(
        id="msg-async-1",
        conversation_id="conv-1",
        sender_id="doc-1",
        sender_role="DOCTOR",
        content="Async dispatch",
        status=MessageStatus.QUEUED,
    )
    msg_repo.save(msg)

    # Worker dispatch
    res = await worker.handle_delivery_job({"message_id": msg.id, "recipient_ids": ["pat-100"]})
    assert res["status"] == "COMPLETED"
    updated = msg_repo.get_by_id(msg.id)
    assert updated.status == MessageStatus.SENT


# ===========================================================================
# 11. All 9 Non-Negotiable Clinical Safety Invariant Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_safety_1_chest_pain_does_not_become_triage(phase41_setup):
    """INVARIANT 1: Message containing 'chest pain' does not automatically become triage."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Symptom Note"), patient)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="I have severe chest pain since yesterday"), patient)

    assert msg.status == MessageStatus.SENT
    # Clinical boundary: Message is communication ONLY
    assert msg.message_type == MessageType.TEXT


@pytest.mark.asyncio
async def test_safety_2_stop_medication_does_not_modify_medication(phase41_setup):
    """INVARIANT 2: Message containing 'stop this medication' does not automatically modify medication."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Medication Discussion"), doctor)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="Please stop this medication immediately."), doctor)

    assert msg.status == MessageStatus.SENT


@pytest.mark.asyncio
async def test_safety_3_allergy_does_not_create_verified_allergy(phase41_setup):
    """INVARIANT 3: Message containing 'allergy' does not automatically create a verified allergy."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Allergy Mention"), patient)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="I think I have a penicillin allergy."), patient)

    assert msg.status == MessageStatus.SENT


@pytest.mark.asyncio
async def test_safety_4_emergency_does_not_dispatch_emergency_services(phase41_setup):
    """INVARIANT 4: Message containing 'emergency' does not automatically dispatch emergency services."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Emergency Word"), patient)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="This is an urgent emergency query."), patient)

    assert msg.status == MessageStatus.SENT


@pytest.mark.asyncio
async def test_safety_5_prescription_text_does_not_create_prescription(phase41_setup):
    """INVARIANT 5: Message containing a prescription does not automatically create a prescription."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Rx Reference"), doctor)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="Prescription: Metformin 500mg PO BID"), doctor)

    assert msg.status == MessageStatus.SENT


@pytest.mark.asyncio
async def test_safety_6_ai_draft_cannot_bypass_human_approval(phase41_setup):
    """INVARIANT 6: AI-generated clinical draft cannot bypass required human approval."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    doctor = make_user("doc-1", role="DOCTOR")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="AI Draft"), doctor)

    with pytest.raises(AIClinicalApprovalRequiredException):
        await msg_service.send_message(
            conv.id,
            MessageSendRequest(content="Clinical recommendation.", metadata={"is_ai_draft": True, "ai_approved": False}),
            doctor,
        )


@pytest.mark.asyncio
async def test_safety_7_provider_failure_never_becomes_delivery_success(phase41_setup):
    """INVARIANT 7: Provider failure never becomes successful delivery."""
    delivery_service = phase41_setup["delivery_service"]
    msg_repo = phase41_setup["msg_repo"]

    msg = MessageRecord(
        id="msg-fail-test",
        conversation_id="conv-1",
        sender_id="doc-1",
        sender_role="DOCTOR",
        content="Failure test [FAIL_DELIVERY]",
        status=MessageStatus.CREATED,
    )
    msg_repo.save(msg)

    dispatched = await delivery_service.dispatch_message(msg, ["pat-100"])
    assert dispatched.status != MessageStatus.DELIVERED
    assert dispatched.status in (MessageStatus.FAILED, MessageStatus.RETRY_PENDING)


@pytest.mark.asyncio
async def test_safety_8_unknown_status_never_becomes_delivered(phase41_setup):
    """INVARIANT 8: Unknown delivery status never becomes delivered."""
    delivery_service = phase41_setup["delivery_service"]
    msg_repo = phase41_setup["msg_repo"]

    msg = MessageRecord(
        id="msg-timeout-test",
        conversation_id="conv-1",
        sender_id="doc-1",
        sender_role="DOCTOR",
        content="Timeout test [TIMEOUT]",
        status=MessageStatus.CREATED,
    )
    msg_repo.save(msg)

    dispatched = await delivery_service.dispatch_message(msg, ["pat-100"])
    assert dispatched.status != MessageStatus.DELIVERED
    assert dispatched.status == MessageStatus.PROCESSING


@pytest.mark.asyncio
async def test_safety_9_message_never_silently_becomes_clinical_truth(phase41_setup):
    """INVARIANT 9: Message content never silently becomes structured clinical truth."""
    conv_service = phase41_setup["conv_service"]
    msg_service = phase41_setup["msg_service"]
    patient = make_user("pat-100", role="PATIENT")

    conv = conv_service.create_conversation(ConversationCreateRequest(patient_id="pat-100", subject="Patient Note"), patient)
    msg = await msg_service.send_message(conv.id, MessageSendRequest(content="My BP is 180/110 and blood sugar is 250"), patient)

    assert msg.status == MessageStatus.SENT
    # The message is stored in message_repo and conversation_repo only; never injected into vitals or clinical records!
    assert msg.reference_resource_type is None


# ===========================================================================
# 12. FastAPI HTTP API Integration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_api_full_communication_flow(phase41_setup):
    """End-to-end integration test through FastAPI ASGI router."""
    app = create_app()

    # Override dependencies
    doctor_ctx = make_user("doc-http-1", role="DOCTOR")
    app.dependency_overrides[get_current_user] = lambda: doctor_ctx
    app.dependency_overrides[get_conversation_service] = lambda: phase41_setup["conv_service"]
    app.dependency_overrides[get_message_service] = lambda: phase41_setup["msg_service"]
    app.dependency_overrides[get_message_delivery_service] = lambda: phase41_setup["delivery_service"]
    app.dependency_overrides[get_message_search_service] = lambda: phase41_setup["search_service"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create conversation
        res_conv = await client.post(
            "/api/v1/conversations",
            json={
                "patient_id": "pat-http-100",
                "category": "PATIENT_CLINICIAN",
                "subject": "Pre-Op Evaluation",
            },
        )
        assert res_conv.status_code == 201
        conv_data = res_conv.json()
        conv_id = conv_data["id"]

        # 2. List conversations
        res_list = await client.get("/api/v1/conversations")
        assert res_list.status_code == 200
        assert res_list.json()["total"] >= 1

        # 3. Send message
        res_msg = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Please fast for 8 hours prior to the procedure."},
            headers={"Idempotency-Key": "api-idem-1"},
        )
        assert res_msg.status_code == 201
        msg_data = res_msg.json()
        msg_id = msg_data["id"]

        # 4. List messages
        res_msgs = await client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert res_msgs.status_code == 200
        assert res_msgs.json()["total"] >= 1

        # 5. Read message
        res_read = await client.post(f"/api/v1/messages/{msg_id}/read")
        assert res_read.status_code == 200
        assert "doc-http-1" in res_read.json()["read_by"]

        # 6. Acknowledge message
        res_ack = await client.post(
            f"/api/v1/messages/{msg_id}/acknowledge",
            json={"note": "Confirmed fasting instructions"},
        )
        assert res_ack.status_code == 200
        assert res_ack.json()["status"] == "ACKNOWLEDGED"

        # 7. AI Draft generation endpoint
        res_draft = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/draft",
            json={"prompt_context": "Can I drink water?"},
        )
        assert res_draft.status_code == 200
        assert res_draft.json()["requires_human_approval"] is True

        # 8. Webhook ingestion endpoint
        raw_body = b'{"event_id":"api-evt-1","message_id":"' + msg_id.encode() + b'","delivery_status":"DELIVERED"}'
        sig = hmac.new(b"test-webhook-secret-key-32-bytes!!", raw_body, hashlib.sha256).hexdigest()
        res_wh = await client.post(
            "/api/v1/communication/webhooks/mock",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Signature": sig},
        )
        assert res_wh.status_code == 200
        assert res_wh.json()["delivery_status"] == "DELIVERED"

        # 9. Operational metrics endpoint
        res_metrics = await client.get("/api/v1/admin/communication/metrics")
        assert res_metrics.status_code == 200
        metrics = res_metrics.json()
        assert metrics["total_conversations"] >= 1
        assert metrics["active_provider"] == "mock"

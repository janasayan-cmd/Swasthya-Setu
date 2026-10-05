# HealthSetu — Phase 41: Clinical Communication, Patient–Provider Messaging & Secure Conversation Management

## 1. Architectural Overview & Clinical Safety Boundaries

Phase 41 implements the backend communication layer required for secure, authorized, and auditable communication between patients, clinicians, care teams, and authorized healthcare organizations.

```
Client / Mobile / Web
       ↓
API Router (/api/v1/conversations, /api/v1/messages)
       ↓
Authentication (Phase 2 JWT / Argon2id)
       ↓
Authorization & Consent (Phase 3 & Resource-Level RBAC)
       ↓
Conversation & Message Authorization Services
       ↓
Communication Policy Service (Rate Limits, Payload Hygiene, Max Size)
       ↓
Conversation & Message Domain Services
       ↓
Message Repository (Thread-Safe, Idempotency-Locked)
       ↓
Audit Service (Phase 15 - PHI-Safe Structured Logging)
       ↓
Async Delivery Worker (Phase 22) & Notification Adapter (Phase 29)
       ↓
Communication Provider Adapter (Phase 41 Mock / Twilio / SendGrid)
       ↓
Authorized Recipient Device
```

### Non-Negotiable Clinical Safety Principles

```
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
```

The backend strictly guarantees that no autonomous clinical action (triage classification, medication changes, verified allergy recording, or emergency dispatch) is ever triggered merely because clinical terms (e.g. "chest pain", "stop medication", "allergy", "emergency", "prescription") appear inside untrusted message text.

---

## 2. Conversation & Message Lifecycles

### Conversation State Machine
```
CREATED ──→ ACTIVE ──┬──→ PAUSED ──→ ACTIVE (Resume)
                     ├──→ CLOSED ──→ ACTIVE (Authorized Reopen)
                     ├──→ ARCHIVED (Read-Only)
                     ├──→ LOCKED
                     └──→ CANCELLED
```

- **CLOSED**: A closed conversation rejects normal new message posting unless explicitly reopened by an authorized clinician or creator.
- **LOCKED**: Modifications and participant changes are strictly rejected.

### Message Delivery State Machine
```
CREATED ──→ QUEUED ──→ PROCESSING ──┬──→ SENT ──→ DELIVERED ──→ READ ──→ ACKNOWLEDGED
                                   ├──→ RETRY_PENDING (Bounded Retries)
                                   ├──→ FAILED (Exhausted / Explicit Rejection)
                                   └──→ EXPIRED / CANCELLED
```

- **SENT**: External communication provider has accepted the dispatch request.
- **DELIVERED**: External provider has confirmed delivery to the destination device. (Does NOT mean read by patient).
- **READ**: The recipient has opened the message in an authenticated session.
- **ACKNOWLEDGED**: A clinician has formally reviewed and acknowledged the message. (Does NOT mean a clinical action was completed).

---

## 3. Endpoints & API Contract

All endpoints are mounted under `/api/v1`:

### Conversation Management
- `POST /api/v1/conversations`: Create a new clinical or operational conversation.
- `GET /api/v1/conversations`: List conversations authorized for the current actor.
- `GET /api/v1/conversations/{conversation_id}`: Retrieve detailed conversation metadata and active participants.
- `POST /api/v1/conversations/{conversation_id}/close`: Close an active conversation.
- `POST /api/v1/conversations/{conversation_id}/reopen`: Reopen a previously closed conversation.
- `GET /api/v1/conversations/{conversation_id}/participants`: List participants.
- `POST /api/v1/conversations/{conversation_id}/participants`: Add an authorized participant.
- `DELETE /api/v1/conversations/{conversation_id}/participants/{participant_id}`: Deactivate participant membership.
- `GET /api/v1/conversations/{conversation_id}/history`: Retrieve audit transition history.

### Message Operations
- `POST /api/v1/conversations/{conversation_id}/messages`: Submit and dispatch a message (supports `Idempotency-Key` header).
- `GET /api/v1/conversations/{conversation_id}/messages`: Retrieve bounded message history with cursor pagination.
- `GET /api/v1/messages/{message_id}`: Retrieve an individual message (enumeration-protected).
- `POST /api/v1/messages/{message_id}/read`: Mark message as read by the authenticated user.
- `POST /api/v1/messages/{message_id}/acknowledge`: Formally record clinician acknowledgment.
- `POST /api/v1/messages/{message_id}/retry`: Retry delivery for a failed message.
- `GET /api/v1/messages/{message_id}/history`: Retrieve delivery state audit history.
- `GET /api/v1/clinicians/me/messages`: Retrieve unread messages for clinician.

### Scoped Retrieval
- `GET /api/v1/patients/{patient_id}/conversations`: Patient-scoped conversations.
- `GET /api/v1/clinicians/me/conversations`: Clinician-scoped conversations.
- `GET /api/v1/organizations/{organization_id}/conversations`: Organization-scoped conversations.
- `GET /api/v1/facilities/{facility_id}/conversations`: Facility-scoped conversations.
- `GET /api/v1/admin/conversations`: Admin operational conversations list.

### AI Assistance & Translation Boundaries
- `POST /api/v1/conversations/{conversation_id}/messages/draft`: AI draft generation with `requires_human_approval=True`.
- `POST /api/v1/messages/{message_id}/translate`: Derived translation preserving original authoritative content.
- `POST /api/v1/conversations/{conversation_id}/summarize`: Non-authoritative communication summary.

### Search Integration (Phase 30)
- `GET /api/v1/conversations/search`: Authorized message search (Search relevance != clinical importance).

### Webhook Ingestion
- `POST /api/v1/communication/webhooks/{provider_name}`: Inbound provider delivery callbacks with HMAC signature verification and replay protection.

---

## 4. Security & Privacy Hardening

1. **Authentication & Authorization**: Bearer JWT tokens evaluated against resource tenancy (patient ID, participant list, organization, facility).
2. **Enumeration Protection**: Unauthorized requests from patient actors return 404 Not Found rather than 403 Forbidden to prevent resource existence probing.
3. **Replay Protection**: Webhook event IDs are tracked to discard duplicate external callbacks.
4. **Idempotency**: Repeated message submissions with the same `Idempotency-Key` return identical message responses without duplicating delivery.
5. **PHI Redaction in Telemetry**: Metric labels and operational audit records never contain full message bodies or raw clinical text.
6. **Attachment Security**: Reuses Phase 5 object-storage signed URLs; attachments are bounded to 10MB and authorized MIME types.
